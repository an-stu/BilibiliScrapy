import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from time import sleep

import requests
from tqdm import tqdm

import dmToass


DEFAULT_COOKIE = ""


class Bilibili:
    def __init__(self, url, cookie=""):
        self.title = ""
        self.bvs = []
        self.avs = []
        self.cids = []
        self.names = []
        self.url = url.strip()
        self.count = 0
        self.width = []
        self.height = []
        self.length = []
        self.download_url = []
        self.download_segments = []
        self.download_modes = []
        self.dash_video_urls = []
        self.dash_audio_urls = []
        self.file_exts = []
        self.size = []
        self.season_rights = {}
        self.account_nav = {}
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/132.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
        }
        if cookie:
            self.headers["Cookie"] = cookie.strip()
        self.chunk_size = 1024 * 256

    def __str__(self):
        if self.count == 0:
            return "获取信息失败"
        rows = []
        for i in range(self.count):
            mb = round(self.size[i] / 1024 / 1024, 2) if i < len(self.size) else 0
            rows.append(f"{self.bvs[i]}\t{self.names[i]}\t{mb}MB")
        return "\n".join(rows)

    @staticmethod
    def _safe_name(text):
        return text.translate(str.maketrans("", "", '?|*\\/<>:"')).strip()

    def _get_json(self, url, params=None):
        resp = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def _get_text(self, url):
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def get_animation_data(self, download_all=False, auto_best=False):
        ep_match = re.search(r"/ep(\d+)", self.url)
        if not ep_match:
            raise ValueError("番剧地址格式错误，示例: https://www.bilibili.com/bangumi/play/ep341245")

        ep_id = ep_match.group(1)
        js = self._get_json(
            "https://api.bilibili.com/pgc/view/web/season",
            params={"ep_id": ep_id},
        )
        if js.get("code") != 0:
            raise RuntimeError(f"获取番剧信息失败: {js.get('message')}")

        result = js["result"]
        self.season_rights = result.get("rights") or {}
        all_episodes = result.get("episodes", [])
        if not all_episodes:
            raise RuntimeError("未找到对应剧集信息")
        ep_map = {str(ep["id"]): ep for ep in all_episodes}
        current = ep_map.get(ep_id)
        if not current:
            raise RuntimeError("未找到当前剧集信息")

        self.title = self._safe_name(result.get("season_title", "Bilibili_Bangumi"))
        target_episodes = [current]
        if download_all:
            target_episodes = sorted(all_episodes, key=lambda x: int(x.get("id", 0)))
            print(f"已识别整季，共 {len(target_episodes)} 集，将按同一清晰度依次下载。")
        else:
            print("默认仅下载当前这一集。")

        for ep in target_episodes:
            aid = ep.get("aid")
            cid = ep.get("cid")
            if not aid or not cid:
                continue
            self.bvs.append(ep.get("bvid", ""))
            self.cids.append(cid)
            self.avs.append(aid)
            show_title = ep.get("show_title") or ep.get("title", "")
            long_title = ep.get("long_title") or ""
            if show_title and long_title and long_title in show_title:
                ep_title = show_title
            else:
                ep_title = f"{show_title} {long_title}".strip()
            ep_title = ep_title or ep.get("share_copy") or str(ep.get("id"))
            self.names.append(self._safe_name(str(ep_title)))
        self.count = len(self.bvs)
        if self.count == 0:
            raise RuntimeError("番剧剧集列表为空，无法下载")
        self.get_download_url(is_bangumi=True, auto_best=auto_best)

    def diagnose_account(self):
        try:
            nav = self._get_json("https://api.bilibili.com/x/web-interface/nav")
        except Exception as e:
            print(f"账号状态检查失败: {e}")
            return

        data = nav.get("data") or {}
        self.account_nav = data
        is_login = bool(data.get("isLogin"))
        vip_status = data.get("vipStatus")
        vip_type = data.get("vipType")
        uname = data.get("uname") or "未登录"
        print(
            f"账号检测: login={is_login}, uname={uname}, "
            f"vipStatus={vip_status}, vipType={vip_type}"
        )

    def get_media_data(self, auto_best=False):
        html = self._get_text(self.url)
        state_match = re.search(r"__INITIAL_STATE__=(\{.*?\});", html)
        if not state_match:
            raise RuntimeError("无法从页面中解析视频信息，请检查链接是否正确")
        js = json.loads(state_match.group(1))
        media_info = js["videoData"]

        self.bvs.append(media_info["bvid"])
        self.cids.append(media_info["cid"])
        self.avs.append(media_info["aid"])
        self.names.append(self._safe_name(media_info["title"]))
        self.title = "Bilibili_videos"
        self.count = 1
        self.get_download_url(is_bangumi=False, auto_best=auto_best)

    def get_download_url(self, is_bangumi, auto_best=False):
        def fetch_play_payload(index, qn, fnval):
            if is_bangumi:
                api = "https://api.bilibili.com/pgc/player/web/playurl"
                params = {
                    "avid": self.avs[index],
                    "cid": self.cids[index],
                    "qn": qn,
                    "fnval": fnval,
                    "fourk": 1,
                }
            else:
                api = "https://api.bilibili.com/x/player/playurl"
                params = {
                    "bvid": self.bvs[index],
                    "cid": self.cids[index],
                    "qn": qn,
                    "otype": "json",
                    "fnval": fnval,
                    "fourk": 1,
                }

            response = self._get_json(api, params=params)
            if response.get("code") != 0:
                raise RuntimeError(f"获取下载地址失败: {response.get('message')}")
            payload = response.get("result") or response.get("data") or {}
            return payload

        # Probe with DASH to get full quality capabilities (including VIP 4K/HDR tiers).
        probe_payload = fetch_play_payload(0, 125, 4048)
        support_formats = probe_payload.get("support_formats") or []
        available = []
        for item in support_formats:
            quality = item.get("quality")
            if quality is None:
                continue
            desc = item.get("new_description") or item.get("display_desc") or str(quality)
            available.append((int(quality), str(desc)))
        available = sorted(list({q: d for q, d in available}.items()), key=lambda x: x[0], reverse=True)
        if not available:
            raise RuntimeError("未获取到可用清晰度列表")

        print("可用清晰度:")
        for idx, (code, desc) in enumerate(available):
            print(f"{idx}: {desc} (qn={code})")
        default_qn, default_desc = available[0]
        if auto_best:
            qn = default_qn
            print(f"已启用自动最高画质: {default_desc} (qn={default_qn})")
        else:
            selected = input(f"请选择清晰度序号(回车默认最高 {default_desc}): ").strip()
            if selected == "":
                qn = default_qn
            else:
                x = int(selected)
                if x < 0 or x >= len(available):
                    raise ValueError("清晰度序号超出范围")
                qn = available[x][0]
        fallback_qns = [code for code, _ in available if code <= qn]

        for i in range(self.count):
            payload = None
            selected_qn = None
            mode = None

            for try_qn in fallback_qns:
                # Prefer direct progressive stream first for compatibility.
                p0 = fetch_play_payload(i, try_qn, 0)
                durl0 = p0.get("durl") or p0.get("durls") or []
                q0 = int(p0.get("quality") or 0)
                if durl0 and q0 >= try_qn:
                    payload = p0
                    selected_qn = try_qn
                    mode = "durl"
                    break

                # Fall back to DASH for high tiers such as 4K/HDR/1080P+.
                p1 = fetch_play_payload(i, try_qn, 4048)
                dash = p1.get("dash") or {}
                videos = dash.get("video") or []
                if videos:
                    payload = p1
                    selected_qn = try_qn
                    mode = "dash"
                    break

                if durl0:
                    payload = p0
                    selected_qn = try_qn
                    mode = "durl"
                    break

            if payload is None or selected_qn is None or mode is None:
                raise RuntimeError("获取播放信息失败")
            if selected_qn != qn:
                print(f"第{i + 1}集所选清晰度不可用，自动降级到 qn={selected_qn}")

            stream_format = str(payload.get("format") or "mp4").lower()
            ext = "mp4" if "mp4" in stream_format else "flv"
            is_preview = payload.get("is_preview", 0)
            full_ms = int(payload.get("timelength", 0) or 0)
            durl = payload.get("durl") or payload.get("durls") or []
            dash = payload.get("dash") or {}
            if mode == "durl" and not durl:
                raise RuntimeError("当前清晰度不可用，或账号权限不足（请检查 cookie）")
            if mode == "dash" and not (dash.get("video") or []):
                raise RuntimeError("当前清晰度的 DASH 视频流缺失")

            if is_preview:
                playable_s = round(sum(int(x.get("length", 0) or 0) for x in durl) / 1000, 2)
                full_s = round(full_ms / 1000, 2) if full_ms > 0 else 0
                print(
                    f"警告: 当前返回为试看片段(is_preview=1)，可下载约 {playable_s}s，"
                    f"完整时长约 {full_s}s。请确认 Cookie 是否为可播放完整正片的账号。"
                )
                if self.season_rights:
                    area_limit = self.season_rights.get("area_limit")
                    ban_area_show = self.season_rights.get("ban_area_show")
                    print(
                        f"番剧权限信息: area_limit={area_limit}, ban_area_show={ban_area_show}, "
                        f"only_vip_download={self.season_rights.get('only_vip_download')}"
                    )

            if mode == "durl":
                part_urls = [x["url"] for x in durl if x.get("url")]
                total_len_ms = sum(int(x.get("length", 0) or 0) for x in durl)
                total_size = sum(int(x.get("size", 0) or 0) for x in durl)

                self.length.append(total_len_ms / 1000)
                self.size.append(total_size)
                self.download_url.append(part_urls[0])
                self.download_segments.append(part_urls)
                self.file_exts.append(ext)
                self.download_modes.append("durl")
                self.dash_video_urls.append("")
                self.dash_audio_urls.append("")
            else:
                # Pick the closest available video representation at/under selected quality.
                videos = dash.get("video") or []
                audios = dash.get("audio") or []
                video_sorted = sorted(videos, key=lambda x: int(x.get("id") or 0), reverse=True)
                target_video = None
                for v in video_sorted:
                    if int(v.get("id") or 0) <= selected_qn:
                        target_video = v
                        break
                if not target_video and video_sorted:
                    target_video = video_sorted[0]
                if not target_video:
                    raise RuntimeError("DASH 视频流为空")

                audio_sorted = sorted(audios, key=lambda x: int(x.get("bandwidth") or 0), reverse=True)
                target_audio = audio_sorted[0] if audio_sorted else None

                video_url = target_video.get("baseUrl") or target_video.get("base_url") or ""
                audio_url = ""
                if target_audio:
                    audio_url = target_audio.get("baseUrl") or target_audio.get("base_url") or ""
                if not video_url:
                    raise RuntimeError("DASH 视频地址解析失败")

                raw_duration = dash.get("duration")
                if raw_duration is None:
                    duration_s = full_ms / 1000.0
                else:
                    raw_duration = float(raw_duration)
                    # Some endpoints return seconds, others milliseconds.
                    duration_s = raw_duration / 1000.0 if raw_duration > 10000 else raw_duration
                v_bw = int(target_video.get("bandwidth") or 0)
                a_bw = int(target_audio.get("bandwidth") or 0) if target_audio else 0
                estimate_size = int((v_bw + a_bw) * duration_s / 8) if duration_s > 0 else 0

                self.length.append(duration_s if duration_s > 0 else full_ms / 1000.0)
                self.size.append(estimate_size)
                self.download_url.append(video_url)
                self.download_segments.append([video_url])
                self.file_exts.append("mp4")
                self.download_modes.append("dash")
                self.dash_video_urls.append(video_url)
                self.dash_audio_urls.append(audio_url)

            dim = payload.get("dimension") or {}
            self.width.append(str(dim.get("width", 1920)))
            self.height.append(str(dim.get("height", 1080)))

    def download(self, i):
        os.makedirs(self.title, exist_ok=True)
        ext = self.file_exts[i] if i < len(self.file_exts) else "flv"
        file_name = os.path.join(self.title, f"{self.names[i]}.{ext}")
        if os.path.isfile(file_name) and abs(os.path.getsize(file_name) - self.size[i]) < 5000:
            print(f"文件 {file_name} 已存在")
            return

        mode = self.download_modes[i] if i < len(self.download_modes) else "durl"
        if mode == "dash":
            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                raise RuntimeError(
                    "选择了 DASH 高清流（如 4K/HDR），但系统未安装 ffmpeg，无法合并音视频。"
                    "请先安装 ffmpeg，或改选 1080P 及以下直链清晰度。"
                )

            video_url = self.dash_video_urls[i]
            audio_url = self.dash_audio_urls[i]
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = os.path.join(tmpdir, "video.m4s")
                audio_path = os.path.join(tmpdir, "audio.m4s")
                with requests.get(video_url, headers=self.headers, stream=True, timeout=30) as res:
                    res.raise_for_status()
                    total_video = int(res.headers.get("Content-Length", 0))
                    with open(video_path, "wb") as f:
                        with tqdm(
                            total=total_video if total_video else None,
                            desc=f"{self.names[i]} 视频流",
                            unit="B",
                            unit_scale=True,
                            unit_divisor=1024,
                            leave=True,
                        ) as pbar:
                            for data in res.iter_content(self.chunk_size):
                                if data:
                                    f.write(data)
                                    pbar.update(len(data))

                cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostats", "-y", "-i", video_path]
                if audio_url:
                    with requests.get(audio_url, headers=self.headers, stream=True, timeout=30) as res:
                        res.raise_for_status()
                        total_audio = int(res.headers.get("Content-Length", 0))
                        with open(audio_path, "wb") as f:
                            with tqdm(
                                total=total_audio if total_audio else None,
                                desc=f"{self.names[i]} 音频流",
                                unit="B",
                                unit_scale=True,
                                unit_divisor=1024,
                                leave=True,
                            ) as pbar:
                                for data in res.iter_content(self.chunk_size):
                                    if data:
                                        f.write(data)
                                        pbar.update(len(data))
                    cmd += ["-i", audio_path, "-c", "copy", file_name]
                else:
                    cmd += ["-c", "copy", file_name]
                subprocess.run(cmd, check=True)
            return

        urls = self.download_segments[i] if i < len(self.download_segments) else [self.download_url[i]]
        with open(file_name, "wb") as f:
            for part_index, part_url in enumerate(urls, start=1):
                part_desc = f"{self.names[i]} P{part_index}/{len(urls)}"
                with requests.get(
                    part_url,
                    headers=self.headers,
                    stream=True,
                    timeout=30,
                ) as res:
                    res.raise_for_status()
                    total_part = int(res.headers.get("Content-Length", 0))
                    with tqdm(
                        total=total_part if total_part else None,
                        desc=part_desc,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        leave=True,
                    ) as pbar:
                        for data in res.iter_content(self.chunk_size):
                            if data:
                                f.write(data)
                                pbar.update(len(data))

    def get_dm(self):
        os.makedirs(self.title, exist_ok=True)
        for i in range(self.count):
            dm_url = f"https://comment.bilibili.com/{self.cids[i]}.xml"
            try:
                dm_res = requests.get(dm_url, headers=self.headers, timeout=20)
                dm_res.raise_for_status()
                dm_res.encoding = "utf-8"
                dm_xml = dm_res.text
            except requests.RequestException as e:
                print(f"弹幕下载失败，已跳过: {e}")
                continue

            dm_limit = [100, 300, 500, 1000, 1500, 3000, 6000, 8000]
            l = self.length[i] if i < len(self.length) else 0
            if 0 < l <= 30:
                limit = dm_limit[0]
            elif 30 < l <= 60:
                limit = dm_limit[1]
            elif 60 < l <= 180:
                limit = dm_limit[2]
            elif 180 < l <= 600:
                limit = dm_limit[3]
            elif 600 < l <= 900:
                limit = dm_limit[4]
            elif 900 < l <= 2400:
                limit = dm_limit[5]
            elif 2400 < l <= 3600:
                limit = dm_limit[6]
            else:
                limit = dm_limit[7]

            ass = dmToass.convert(
                dm_xml,
                f"{self.width[i]}:{self.height[i]}",
                "黑体",
                int(self.height[i]) / 30,
                6,
                10,
                0,
                limit,
            )

            ass_path = os.path.join(self.title, f"{self.names[i]}.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass)

    def start(self, download_all=False, auto_best=False):
        self.diagnose_account()
        if "/bangumi/play/ep" in self.url:
            self.get_animation_data(download_all=download_all, auto_best=auto_best)
        elif "/video/" in self.url:
            self.get_media_data(auto_best=auto_best)
        else:
            raise ValueError("仅支持 /video/ 或 /bangumi/play/ep 链接")

        self.get_dm()
        print(self)
        for i in tqdm(range(self.count), desc="总进度", unit="集"):
            self.download(i)
        sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bilibili 视频/番剧下载器")
    parser.add_argument(
        "--all-best",
        action="store_true",
        help="下载整部番剧并自动选择最高可用清晰度（仅对番剧 ep 链接生效）",
    )
    args = parser.parse_args()

    bili_url = input("请输入地址: ").strip()
    user_cookie = input("请输入 Cookie（直接回车使用 DEFAULT_COOKIE/cookie.txt）: ").strip()
    cookie = user_cookie or DEFAULT_COOKIE
    if not cookie:
        cookie_file = os.path.join(os.path.dirname(__file__), "cookie.txt")
        if os.path.isfile(cookie_file):
            with open(cookie_file, "r", encoding="utf-8") as f:
                cookie = f.read().strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    bili = Bilibili(bili_url, cookie=cookie)
    bili.start(download_all=args.all_best, auto_best=args.all_best)
