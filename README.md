# NeteaseCloudMusic Playlist Importer

批量导入歌曲清单到网易云音乐歌单。

## 项目结构

```
songlistdemo/
├── NeteaseCloudMusicApi/    # 本地 API 代理服务（api-enhanced）
├── import_playlist.py       # 主脚本：搜索歌曲 → 创建歌单 → 批量添加
├── login.py                 # 扫码登录脚本（备用，依赖 TTY）
├── songs.txt                # 歌曲清单，每行 "歌名 - 歌手"
├── .cookie                  # 登录 cookie（已设置，勿泄露）
├── success.txt              # 成功匹配的歌曲列表
├── low_confidence.txt       # 低置信度匹配，需人工核对
├── unmatched.txt            # 完全未匹配到的歌曲
└── README.md
```

## 前置条件

- Node.js 18+
- Python 3

## 快速开始

### 1. 启动 API 服务

```bash
cd NeteaseCloudMusicApi
npm install
ENABLE_GENERAL_UNBLOCK=false node app.js
```

服务默认监听 `http://localhost:3000`。

> 注意：首次请求因连接网易云后端可能慢（约 30-60s），之后保持连接复用。

### 2. 准备 songs.txt

每行格式：

```
歌名 - 歌手
```

示例：

```
稻香 - 周杰伦
Love Faces - Trey Songz
```

### 3. 登录（首次使用）

网易云音乐的 `MUSIC_U` 为 HttpOnly 无法通过 JS 获取，推荐手动导出 cookie：

1. 浏览器打开 https://music.163.com 并登录
2. F12 → Application → Cookies → https://music.163.com
3. 选中所有 cookie，右键 → Copy → **Copy as cURL (bash)**
4. 提取 `-H 'Cookie: ...'` 部分写入 `.cookie` 文件

或通过扫码登录（需 TTY 环境）：

```bash
python3 login.py
```

### 4. 导入歌单

```bash
python3 import_playlist.py "歌单名称"
```

脚本会自动完成：搜索匹配 → 创建歌单 → 批量添加歌曲。

## 匹配规则

1. 搜索结果中 `ar[].name` **包含**输入歌手名 → 正常匹配
2. 包含 `&` 与 `,` 的歌手名视为等价（如 "A & B" 与 "A, B"）
3. 无歌手匹配时取第一条，且标记低置信度
4. 完全搜不到的写入 unmatched.txt

## 输出文件

| 文件 | 说明 |
|------|------|
| `success.txt` | 成功添加的歌曲，格式 `歌名 - 歌手 - songId` |
| `low_confidence.txt` | 歌手名不匹配的结果，需人工确认 |
| `unmatched.txt` | 无法搜索到的歌曲 |
| `.cookie` | 已登录的 cookie（建议加入 .gitignore） |

## 技术栈

- **API 代理**: [api-enhanced](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced) (Express, axios)
- **客户端**: Python 3 + requests
- **登录**: 基于网易云音乐 QR 扫码 / Cookie 携带
