# BilibiliScrapy

一个用于下载 B 站视频/番剧的 Python 脚本，支持：

- 普通视频链接（`/video/`）
- 番剧单集链接（`/bangumi/play/ep...`）
- 大会员高画质（如 4K/HDR，走 DASH + ffmpeg 合并）
- 弹幕下载并转换为 `.ass`

## 功能说明

### 1) 默认模式（交互式）
不带参数运行时：

- 番剧 `ep` 链接：默认只下载当前这一集
- 视频链接：下载该视频
- 会先探测“当前账号可用”的清晰度，然后让你选择
- 清晰度输入回车默认最高

### 2) 全集+最高画质模式
使用参数 `--all-best`：

- 对番剧 `ep` 链接生效
- 自动下载整季（主季）全部剧集
- 自动选择最高可用清晰度

## 环境要求

- Python 3.9+
- 依赖：`requests`, `tqdm`
- 可选但推荐：`ffmpeg`（下载 4K/HDR 等 DASH 音视频分离流时必须）

安装依赖：

```bash
pip install requests tqdm
```

安装 ffmpeg（macOS + Homebrew）：

```bash
brew install ffmpeg
```

## 使用方式

在仓库目录运行：

```bash
python3 BilibiliScarapy.py
```

或：

```bash
python3 BilibiliScarapy.py --all-best
```

运行后会依次输入：

1. 视频/番剧地址
2. Cookie（可直接回车使用 `cookie.txt`）
3. 清晰度序号（默认模式下）

## cookie.txt 说明（重点）

脚本支持两种 Cookie 输入方式：

1. 运行时粘贴 Cookie 字符串
2. 在脚本同目录放置 `cookie.txt`，运行时直接回车

### `cookie.txt` 文件格式

文件内容就是**一整行**浏览器请求头中的 Cookie 值，例如：

```txt
SESSDATA=xxxx; bili_jct=xxxx; DedeUserID=xxxx; ...
```

也兼容这种写法（脚本会自动去掉前缀）：

```txt
cookie: SESSDATA=xxxx; bili_jct=xxxx; DedeUserID=xxxx; ...
```

### 如何查找自己的 Cookie（Chrome/Edge）

1. 先在浏览器登录 [https://www.bilibili.com](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具
3. 切到 `Network` 面板，刷新页面
4. 点任意一个 `api.bilibili.com` 请求
5. 在 `Request Headers` 里找到 `cookie` 字段
6. 复制 `cookie:` 后面的完整值，保存到 `cookie.txt`

### Cookie 安全注意

- `cookie.txt` 等同于账号凭证，不要泄露给他人
- 本仓库已通过 `.gitignore` 忽略 `cookie.txt`，默认不会提交到 GitHub
- 建议定期更新 Cookie（过期后会出现未登录或仅试看片段）

## 常见问题

### 1) 明明是会员，为什么不是最高画质？

可能原因：

- Cookie 未生效或已过期
- 当前网络/地区限制
- 该片源当前账号无对应清晰度权限

脚本会打印账号检测信息（`isLogin/vipStatus`）和可用清晰度列表。

### 2) 为什么有时是 mp4，有时是 flv？

脚本会根据接口返回流格式自动保存后缀。DASH 模式会合并为 `mp4`。

### 3) ffmpeg 输出太多怎么办？

已默认静默，仅在错误时输出。

## 输出文件

下载目录默认以番剧名或 `Bilibili_videos` 命名，通常包含：

- 视频文件（`.mp4` / `.flv`）
- 弹幕字幕文件（`.ass`）

## 免责声明

请仅在遵守当地法律法规、平台服务条款及版权要求的前提下使用本项目。
