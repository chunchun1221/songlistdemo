# NeteaseCloudMusic Playlist Importer

批量导入歌曲清单到网易云音乐歌单。

## 项目结构

```
songlistdemo/
├── NeteaseCloudMusicApi/    # 本地 API 代理服务（api-enhanced）
├── run.py                   # 一键启动脚本（推荐入口）
├── import_playlist.py       # 主脚本：搜索歌曲 → 创建歌单 → 批量添加
├── login.py                 # 扫码登录脚本
├── songs.txt                # 歌曲清单，每行 "歌名 - 歌手"
├── .cookie                  # 登录凭证
└── README.md
```

## 前置条件

- Node.js 18+
- Python 3

```bash
pip3 install qrcode
```

## 快速开始

### 1. 一键运行

```bash
python3 run.py "歌单名"
```

脚本会自动：

1. 启动 API 服务
2. 检测登录状态 → 引导登录（扫码或粘贴 Cookie）
3. 询问歌曲来源：
   - 已有 `songs.txt`？直接使用
   - 没有？粘贴歌名列表（每行 `歌名 - 歌手`），或拖拽文件到终端
4. 搜索匹配歌曲 → 创建歌单 → 批量添加

首次运行需登录，后续只需执行 `python3 run.py "歌单名"` 即可。

## 登录方式

首次运行会提示选择登录方式：

#### 方式 ① 扫码登录

选择 `1`，终端显示二维码，用网易云音乐 App 扫码并确认即可。

#### 方式 ② 粘贴 Cookie

选择 `2`，按提示操作：

1. 浏览器打开 https://music.163.com 并**保持登录状态**
2. 按 `F12` → **Application** 标签 → **Cookies** → `https://music.163.com`
3. 点任意一条 cookie，按 `Cmd+A` / `Ctrl+A` 全选
4. **右键** → **Copy** → **Copy as cURL (bash)**
5. 在终端粘贴，脚本会自动提取 Cookie 并验证

> `MUSIC_U` 是 HttpOnly 的，不能用 `document.cookie` 获取，务必用 cURL 方式复制。

两种方式都会把 Cookie 保存到 `.cookie` 文件，后续运行 `run.py` 会自动检测。


## 匹配规则

1. 搜索结果中 `ar[].name` **包含**输入歌手名 → 正常匹配
2. `&` 与 `,` 视为等价（如 `A & B` 与 `A, B` 匹配相同结果）
3. 无歌手匹配时取第一条结果，标记为低置信度
4. 完全搜不到的写入 `unmatched.txt`

## 输出文件

| 文件 | 说明 |
|------|------|
| `success.txt` | 成功添加的歌曲（格式: `歌名 - 歌手 - songId`） |
| `low_confidence.txt` | 低置信度匹配，需人工确认 |
| `unmatched.txt` | 完全搜不到的歌曲 |

## 技术栈

- **API 代理**: [api-enhanced](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced)
- **客户端**: Python 3 + requests
- **登录**: 浏览器 Cookie 导出 / QR 扫码
