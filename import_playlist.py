#!/usr/bin/env python3
"""批量导入歌曲清单到网易云音乐歌单"""

import os
import re
import sys
import time
import requests

API_BASE = "http://localhost:3000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, ".cookie")
SONGS_FILE = os.path.join(BASE_DIR, "songs.txt")
COMMON_PARAMS = {
    "realIP": "183.2.175.120",
    "domain": "https://music.163.com",
}

# 结果文件
SUCCESS_FILE = os.path.join(BASE_DIR, "success.txt")
LOW_CONF_FILE = os.path.join(BASE_DIR, "low_confidence.txt")
UNMATCHED_FILE = os.path.join(BASE_DIR, "unmatched.txt")


def load_cookie():
    if not os.path.exists(COOKIE_FILE):
        return ""
    with open(COOKIE_FILE) as f:
        content = f.read().strip()
    # 跳过注释行和占位符
    if content.startswith("#") or content.startswith("请将"):
        return ""
    return content


def api_get(path, params=None, cookie="", timeout=120):
    if params is None:
        params = {}
    params.update(COMMON_PARAMS)
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    for attempt in range(3):
        try:
            r = requests.get(
                f"{API_BASE}{path}",
                params=params,
                headers=headers,
                timeout=timeout,
            )
            data = r.json()
            if data.get("code") == 200:
                return data
            msg = data.get("msg", "")
            if "需要登录" in msg:
                print(f"  [!] 需要登录，跳过")
                return None
        except Exception as e:
            pass
        if attempt < 2:
            wait = 2 ** attempt
            time.sleep(wait)
    return None


def api_post(path, data=None, cookie="", timeout=120):
    if data is None:
        data = {}
    data.update(COMMON_PARAMS)
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    for attempt in range(3):
        try:
            r = requests.post(
                f"{API_BASE}{path}",
                data=data,
                headers=headers,
                timeout=timeout,
            )
            resp = r.json()
            if resp.get("code") == 200:
                return resp
            msg = resp.get("msg", "")
            if "需要登录" in msg:
                print(f"  [!] 需要登录，跳过")
                return None
        except Exception:
            pass
        if attempt < 2:
            wait = 2 ** attempt
            time.sleep(wait)
    return None


def search_song(song_name, artist_name, cookie):
    """搜索单曲，返回匹配结果"""
    resp = api_get(
        "/cloudsearch",
        {"keywords": f"{song_name} {artist_name}"},
        cookie=cookie,
    )
    if not resp:
        return None

    songs = resp.get("result", {}).get("songs", [])
    if not songs:
        return None

    # 优先匹配歌手名
    artist_lower = artist_name.lower()
    for s in songs:
        ar_names = [ar.get("name", "") for ar in s.get("ar", [])]
        ar_lower = [n.lower() for n in ar_names]
        if any(artist_lower in n for n in ar_lower):
            return {"song": s, "confidence": "high"}

    # 取第一条，标记低置信度
    first = songs[0]
    first_ar = [ar.get("name", "") for ar in first.get("ar", [])]
    # 检查是否完全没有匹配
    first_ar_lower = [n.lower() for n in first_ar]
    if any(artist_lower in n for n in first_ar_lower):
        return {"song": first, "confidence": "high"}
    else:
        return {"song": first, "confidence": "low"}


def create_playlist(name, cookie):
    """创建歌单，返回 playlist_id"""
    resp = api_post("/playlist/create", {"name": name}, cookie=cookie)
    if not resp:
        return None
    return resp.get("playlist", {}).get("id")


def add_tracks(playlist_id, song_ids, cookie):
    """批量添加歌曲到歌单，返回 True/False"""
    # 每次最多 100 首
    all_ids = list(song_ids)
    for i in range(0, len(all_ids), 100):
        batch = all_ids[i : i + 100]
        ids_str = ",".join(str(sid) for sid in batch)
        resp = api_post(
            "/playlist/tracks",
            {"op": "add", "pid": playlist_id, "tracks": ids_str},
            cookie=cookie,
        )
        if not resp:
            return False
    return True


def warmup(cookie):
    """预热连接"""
    print("[*] 预热连接...")
    start = time.time()
    api_get("/cloudsearch", {"keywords": "warmup"}, cookie=cookie, timeout=60)
    elapsed = time.time() - start
    print(f"   耗时 {elapsed:.0f}s" if elapsed > 2 else "")


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {os.path.basename(__file__)} \"歌单名称\"")
        sys.exit(1)

    playlist_name = sys.argv[1]

    # 检查 songs.txt
    if not os.path.exists(SONGS_FILE):
        print(f"[-] 未找到 {SONGS_FILE}")
        sys.exit(1)

    # 加载 cookie
    cookie = load_cookie()
    if not cookie:
        print("[!] .cookie 文件未设置或为空")
        print("   请将网易云音乐 cookie 粘贴到 .cookie 文件")
        print("   获取方式：浏览器登录 music.163.com → F12 → Application → Cookies")
        sys.exit(1)
    print("[+] Cookie 已加载")

    # 读取歌曲清单
    songs = []
    with open(SONGS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^(.+?)\s*-\s*(.+)$", line)
            if match:
                songs.append((match.group(1).strip(), match.group(2).strip()))
            else:
                print(f"  [!] 跳过无法解析的行: {line}")

    print(f"[*] 共读取 {len(songs)} 首歌曲")

    # 预热
    warmup(cookie)

    # 搜索匹配
    print("\n[*] 开始搜索匹配歌曲...")
    matched_ids = []
    low_confidence = []
    unmatched = []
    success = []

    for idx, (song_name, artist_name) in enumerate(songs, 1):
        print(f"  [{idx}/{len(songs)}] {song_name} - {artist_name}")
        result = search_song(song_name, artist_name, cookie)
        if result is None:
            unmatched.append(f"{song_name} - {artist_name}")
            print(f"    -> 未找到")
        else:
            s = result["song"]
            sid = s.get("id")
            sname = s.get("name", "?")
            sar = ", ".join(ar.get("name", "") for ar in s.get("ar", []))
            if result["confidence"] == "high":
                matched_ids.append(sid)
                success.append(f"{sname} - {sar} - {sid}")
                print(f"    -> ✓ {sname} - {sar}")
            else:
                # 低置信度：歌手完全不匹配
                matched_ids.append(sid)
                low_confidence.append(f"{song_name} - {artist_name} -> 匹配: {sname} - {sar} - {sid}")
                success.append(f"{sname} - {sar} - {sid}")
                print(f"    -> ? {sname} - {sar} (歌手不匹配)")
        time.sleep(0.5)

    # 创建歌单
    print(f"\n[*] 创建歌单「{playlist_name}」...")
    playlist_id = create_playlist(playlist_name, cookie)
    if not playlist_id:
        print("[-] 创建歌单失败（可能需要登录）")
        sys.exit(1)
    print(f"[+] 歌单创建成功: {playlist_id}")

    # 添加歌曲
    print(f"[*] 添加 {len(matched_ids)} 首歌曲到歌单...")
    ok = add_tracks(playlist_id, matched_ids, cookie)
    if ok:
        print("[+] 添加成功！")
    else:
        print("[!] 部分歌曲添加可能失败")

    # 写入报告
    with open(SUCCESS_FILE, "w") as f:
        f.write("\n".join(success) + "\n")
    with open(LOW_CONF_FILE, "w") as f:
        f.write("\n".join(low_confidence) + "\n")
    with open(UNMATCHED_FILE, "w") as f:
        f.write("\n".join(unmatched) + "\n")

    print(f"\n{'='*50}")
    print(f"完成！报告：")
    print(f"  成功添加：{len(success)} 首 -> {SUCCESS_FILE}")
    print(f"  低置信度：{len(low_confidence)} 首 -> {LOW_CONF_FILE}")
    print(f"  未匹配：  {len(unmatched)} 首 -> {UNMATCHED_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
