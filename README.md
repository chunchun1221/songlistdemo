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

### 一键运行

```bash
python3 run.py
```

脚本会自动：

1. 启动 API 服务
2. 检测登录状态 → 引导登录（扫码或粘贴 Cookie）
3. 询问歌曲来源：
   - 已有 `songs.txt`？直接使用
   - 没有？粘贴歌名列表，或拖拽文件到终端
4. 搜索匹配歌曲（可按 **Ctrl+C** 中断并用已匹配结果创建歌单）
5. **搜索完成后**询问歌单名称 → 创建歌单 → 批量添加
6. 完成后可选择退出网易云账号

## 歌曲清单格式

支持多种输入格式，自动识别：

| 格式 | 示例 |
|------|------|
| `歌名 - 歌手` | `晴天 - 周杰伦` |
| `歌手《歌名》` | `周杰伦《晴天》` |
| `歌手《歌名1》《歌名2》` | `周杰伦《晴天》《七里香》`（一行多首）|
| 纯歌名（无歌手） | `晴天`（自动匹配，标记低置信度）|
| 带项目符号 | `• 晴天 - 周杰伦` |

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

### Cookie 验证失败时

如果 Cookie 验证失败（过期或网络波动），脚本会询问：

- **1) 直接继续**（跳过验证，适合网络不稳时）
- **2) 重新扫码登录**
- **3) 粘贴新 Cookie**

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
