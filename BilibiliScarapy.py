import os
import requests
import json
import re
from time import sleep
# from multiprocessing import Pool
from tqdm import tqdm
import dmToass


class Bilibili:
    def __init__(self, url):
        self.title = ""
        self.bvs = []
        self.avs = []
        self.cids = []
        self.names = []
        self.url = url
        self.count = 0
        self.width = []
        self.height = []
        self.length = []
        self.download_url = []
        self.size = []
        self.headers = {
            "User-Agent": "Mozilla/5.0(Windows NT 10.0;WOW64) AppleWebKit/537.36(KHTML,likeGecko)Chrome/63.0.3239.132Safari/537.36",
            "cookie": "buvid3=560A8DC3-6376-4CF0-9B32-1D753924A397143107infoc; rpdid=|(um~JY|||)|0J'ulm)|uJkl); LIVE_BUVID=AUTO4115999886687727; buvid_fp=560A8DC3-6376-4CF0-9B32-1D753924A397143107infoc; _uuid=6D6FE884-C81B-332E-5E85-D5E4A05DCDE562033infoc; SESSDATA=b7fbc2f7,1653551383,cf57d*b1; bili_jct=a95e28622a291692274c33218d81f603; DedeUserID=526132913; DedeUserID__ckMd5=38a60a1a2d4c4d3b; sid=4kc0khpi; video_page_version=v_old_home; i-wanna-go-back=-1; b_ut=5; CURRENT_BLACKGAP=0; fingerprint=c60857466f179496a5c1db8cc759e921; fingerprint3=c4d6a08d29c3e0aa7528d2ba04543928; fingerprint_s=1d5794b6b8c7563a3f4657a28d89304a; bp_t_offset_526132913=607359837961319496; bp_video_offset_526132913=607388197624329700; buvid_fp_plain=EA66168A-2B62-835D-8321-93B83599DAF261112infoc; blackside_state=0; CURRENT_QUALITY=120; b_lsid=3DE64B13_17DEC31DAE3; innersign=1; CURRENT_FNVAL=80; PVID=2",
            'referer': 'https://www.bilibili.com/'
        }
        self.chunk_size = 1024 * 4

    def __str__(self):
        s = ""
        if self.count == 0:
            return "获取信息失败"
        else:
            for i in range(self.count):
                s += self.bvs[i] + "\t" + self.names[i] + "\t" + str(
                    round(self.size[i] / 1024 / 1024, 2)) + f"MB\t{round(self.size[i] / self.chunk_size, 2)}it\n"
            return s

    def get_animation_data(self):  # 获取番剧信息
        res = requests.get(self.url, self.headers)
        res.encoding = "utf-8"
        data = re.findall("__INITIAL_STATE__=(.+});", res.text)[0]
        js = json.loads(data)
        self.height = re.findall("\"height\":(\d+)", res.text)
        self.width = re.findall("\"width\":(\d+)", res.text)
        media_info = js["mediaInfo"]["episodes"]
        # print(media_info)
        for each in media_info:
            if each["badge"] == "" or each["badge"] == "会员":
                self.bvs.append(each["bvid"])
                self.cids.append(each["cid"])
                self.avs.append(each["aid"])
                self.names.append(each["share_copy"])
        self.count = len(self.bvs)
        self.title = js["mediaInfo"]["season_title"]
        self.get_download_url()

    def get_media_data(self):  # 获取视频信息
        res = requests.get(self.url, self.headers)
        res.encoding = "utf-8"
        data = re.findall("__INITIAL_STATE__=(.+});", res.text)[0]
        js = json.loads(data)
        media_info = js["videoData"]
        # print(js)
        self.bvs.append(media_info["bvid"])
        self.cids.append(media_info["cid"])
        self.avs.append(media_info["aid"])
        self.names.append(media_info["title"])
        self.title = "Bilibili_videos"
        self.count = len(self.bvs)
        self.get_download_url()

    def get_download_url(self):
        dic = ["超清 4K", "高清1080 P60", "高清 1080P+", "高清 1080P", "高清 720P", "清晰 480P", "流畅 360P"]
        for i in range(6):
            print(str(i) + ':' + dic[i])
        x = int(input('请选择清晰度:'))
        dic2 = [120, 116, 112, 80, 64, 32, 16]
        url2 = "https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=" + str(
            dic2[x]) + "&type=&otype=json&fourk=1"
        for bv, cid in zip(self.bvs, self.cids):
            response = requests.get(url2.format(bvid=bv, cid=cid), headers=self.headers).json()
            # print(response)
            self.length.append(int(response["data"]["durl"][0]["length"]) / 1000)
            self.size.append(response["data"]["durl"][0]["size"])
            self.download_url.append(response["data"]["durl"][0]["url"])

    def download(self, i):
        file_name = f"{self.title}/{self.names[i]}.flv"
        self.names[i] = self.names[i].translate(str.maketrans('', '', '?|*\\/<>\"'))
        if os.path.isfile(file_name) and abs(os.path.getsize(file_name) - self.size[i]) < 5000:
            print(f"文件 {file_name} 已存在!")
        else:
            res = requests.get(self.download_url[i], headers=self.headers, stream=True)
            with open(self.title + "/{name}.flv".format(name=self.names[i]), "wb+") as f:
                for data in tqdm(res.iter_content(self.chunk_size), desc=self.names[i], leave=True):
                    f.write(data)

    def get_dm(self):
        try:
            os.mkdir(self.title)
        except FileExistsError:
            pass
        for i in range(self.count):
            dm_url = "https://comment.bilibili.com/{cid}.xml".format(cid=self.cids[i])
            dm_res = requests.get(dm_url)
            dm_res.encoding = "utf-8"
            dm_xml = dm_res.text
            dm_limit = [100, 300, 500, 1000, 1500, 3000, 6000, 8000]
            l = self.length[i]
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
            # print(dm_xml)
            ass = dmToass.convert(dm_xml, "%s:%s" % (self.width[i], self.height[i]), "黑体", int(self.height[i]) / 30, 6,
                                  10, 0, limit)
            # print(ass)
            self.title = self.title.translate(str.maketrans('', '', '?|*\\/<>\"'))
            with open(self.title + "/{name}.ass".format(name=self.names[i]), "w+", encoding="utf-8") as f:
                f.write(ass)

    # def start(self):
    #     if "video" in self.url:
    #         self.get_media_data()
    #         self.get_dm()
    #         print(self)
    #         self.download(0)
    #     else:
    #         self.get_animation_data()
    #         self.get_dm()
    #         print(self)
    #         n = int(input("请输入并行下载数目:"))
    #         pool = Pool(processes=n)
    #         for i in range(self.count):
    #             pool.apply_async(self.download,args=(i,))
    #             sleep(0.5)
    #         pool.close()
    #         pool.join()
    #     sleep(1)
    def start(self):
        if "video" in self.url:
            self.get_media_data()
        else:
            self.get_animation_data()
        self.get_dm()
        print(self)
        for i in range(self.count):
            self.download(i)
        sleep(1)


if __name__ == '__main__':
    bili_url = str(input("请输入地址:"))
    bili = Bilibili(bili_url)
    bili.start()
