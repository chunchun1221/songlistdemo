# NeteaseCloudMusic Playlist Importer

批量导入歌曲清单到网易云音乐歌单。

## 项目结构

```
songlistdemo/
├── NeteaseCloudMusicApi/    # 本地 API 代理服务（api-enhanced）
├── import_playlist.py       # 主脚本：搜索歌曲 → 创建歌单 → 批量添加
├── login.py                 # 扫码登录脚本
├── songs.txt                # 歌曲清单，每行 "歌名 - 歌手"
├── .cookie                  # 登录凭证
├── .gitignore
└── README.md
```

## 前置条件

- Node.js 18+
- Python 3 + requests 库

```bash
pip3 install requests qrcode
```

## 快速开始

### 1. 启动 API 服务

```bash
cd NeteaseCloudMusicApi
npm install
ENABLE_GENERAL_UNBLOCK=false node app.js
```

服务默认监听 `http://localhost:3000`。

> 首次请求因连接网易云后端可能较慢（约 30-60 秒），之后保持长连接会快很多。

### 2. 准备 songs.txt

每行格式：`歌名 - 歌手`

```txt
稻香 - 周杰伦
Love Faces - Trey Songz
```

### 3. 登录（二选一）

#### 方式 A：浏览器导出 Cookie（推荐）

1. 浏览器打开 https://music.163.com 并**保持登录状态**
2. 按 `F12` → **Application** 标签 → **Cookies** → `https://music.163.com`
3. 点任意一条 cookie，按 `Cmd+A` / `Ctrl+A` 全选
4. **右键** → **Copy** → **Copy as cURL (bash)**
5. 在复制的内容中找到 `-H 'Cookie: ...'` 那一长串
6. 提取 `Cookie:` 后面的内容（一直延伸到下一个 `-H` 之前），写入 `.cookie` 文件

> 注意：`MUSIC_U` 是 HttpOnly 的，所以不能用 `document.cookie` 获取，务必用上面的方法。

#### 方式 B：扫码登录

在**真实的终端**中运行（不要通过 IDE 或非 TTY 环境）：

```bash
python3 login.py
```

终端会显示二维码，用网易云音乐 App 扫码即可。

### 4. 导入歌单

```bash
python3 import_playlist.py "歌单名称"
```

脚本会自动完成：搜索歌曲 → 匹配歌手 → 创建歌单 → 批量添加。

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
