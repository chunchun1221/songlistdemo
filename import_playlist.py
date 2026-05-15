#!/usr/bin/env python3
"""批量导入歌曲清单到网易云音乐歌单"""

import http.client
import json
import os
import re
import sys
import time

API_HOST = "localhost"
API_PORT = 3000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, ".cookie")
SONGS_FILE = os.path.join(BASE_DIR, "songs.txt")

# 结果文件
SUCCESS_FILE = os.path.join(BASE_DIR, "success.txt")
LOW_CONF_FILE = os.path.join(BASE_DIR, "low_confidence.txt")
UNMATCHED_FILE = os.path.join(BASE_DIR, "unmatched.txt")

COMMON_PARAMS = "realIP=183.2.175.120&domain=https://music.163.com"

COOKIE_CACHE = ""


def load_cookie():
    global COOKIE_CACHE
    if COOKIE_CACHE:
        return COOKIE_CACHE
    if not os.path.exists(COOKIE_FILE):
        return ""
    with open(COOKIE_FILE) as f:
        content = f.read().strip()
    if content.startswith("#") or content.startswith("请将"):
        return ""
    COOKIE_CACHE = content
    return content


def api_get(path, params="", retries=3, timeout=90):
    """使用 http.client 发 GET 请求"""
    url = path
    if params:
        url = path + "?" + params

    cookie = load_cookie()

    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
            headers = {}
            if cookie:
                headers["Cookie"] = cookie
            conn.request("GET", url, headers=headers)
            r = conn.getresponse()
            data = json.loads(r.read().decode("utf-8"))
            conn.close()

            code = data.get("code")
            if code == 200:
                return data
            msg = data.get("msg", "")
            if "需要登录" in msg:
                print(f"  [!] 需要登录，跳过")
                return None
            # 其他 code（如 502）=> 重试
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return None


def api_post(path, data, retries=3, timeout=90):
    """使用 http.client 发 POST 请求"""
    params = data + "&" + COMMON_PARAMS
    cookie = load_cookie()

    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if cookie:
                headers["Cookie"] = cookie
            conn.request("POST", path, body=params, headers=headers)
            r = conn.getresponse()
            resp = json.loads(r.read().decode("utf-8"))
            conn.close()

            if resp.get("code") == 200:
                return resp
            msg = resp.get("msg", "")
            if "需要登录" in msg:
                print(f"  [!] 需要登录，跳过")
                return None
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return None


def search_song(song_name, artist_name):
    """搜索单曲，返回匹配结果"""
    params = "keywords={} {}&{}&limit=10".format(song_name, artist_name, COMMON_PARAMS)
    resp = api_get("/cloudsearch", params)
    if not resp:
        return None

    songs = resp.get("result", {}).get("songs", [])
    if not songs:
        return None

    artist_lower = artist_name.lower()
    # 替换 & 为 , 再比较
    artist_normalized = artist_lower.replace("&", ",").replace(" and ", ",")

    for s in songs:
        ar_names = [ar.get("name", "") for ar in s.get("ar", [])]
        ar_lower = "".join(n.lower() for n in ar_names)
        # 检查歌手名是否匹配（支持 & 和 , 等价）
        if artist_normalized.replace(",", "") in ar_lower.replace(",", ""):
            return {"song": s, "confidence": "high"}
        for n in ar_lower:
            if artist_normalized in n or n in artist_normalized:
                return {"song": s, "confidence": "high"}

    first = songs[0]
    return {"song": first, "confidence": "low"}


def create_playlist(name):
    """创建歌单，返回 playlist_id"""
    resp = api_post("/playlist/create", "name={}&{}".format(name, COMMON_PARAMS))
    if not resp:
        return None
    return resp.get("playlist", {}).get("id")


def add_tracks(playlist_id, song_ids):
    """批量添加歌曲到歌单"""
    all_ids = list(song_ids)
    for i in range(0, len(all_ids), 100):
        batch = all_ids[i : i + 100]
        ids_str = ",".join(str(sid) for sid in batch)
        resp = api_post(
            "/playlist/tracks",
            "op=add&pid={}&tracks={}&{}".format(playlist_id, ids_str, COMMON_PARAMS),
        )
        if not resp:
            return False
    return True


def warmup():
    print("[*] 预热连接...")
    start = time.time()
    api_get("/cloudsearch", "keywords=warmup&{}".format(COMMON_PARAMS), timeout=60)
    elapsed = time.time() - start
    if elapsed > 2:
        print(f"   (耗时 {elapsed:.0f}s)")


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {os.path.basename(__file__)} \"歌单名称\"")
        sys.exit(1)

    playlist_name = sys.argv[1]

    if not os.path.exists(SONGS_FILE):
        print(f"[-] 未找到 {SONGS_FILE}")
        sys.exit(1)

    cookie = load_cookie()
    if not cookie:
        print("[!] .cookie 文件为空，请先登录")
        print("    python3 login.py   # 扫码登录")
        print("    或手动粘贴 cookie 到 .cookie 文件")
        sys.exit(1)
    print("[+] Cookie 已加载")

    # 读取歌曲
    songs = []
    with open(SONGS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(.+?)\s*-\s*(.+)$", line)
            if m:
                songs.append((m.group(1).strip(), m.group(2).strip()))
            else:
                print(f"  [!] 跳过无法解析的行: {line}")

    print(f"[*] 共读取 {len(songs)} 首歌曲")

    warmup()

    # 搜索匹配
    print("\n[*] 开始搜索匹配歌曲...")
    matched_ids = []
    low_confidence = []
    unmatched = []
    success = []

    for idx, (song_name, artist_name) in enumerate(songs, 1):
        print(f"  [{idx}/{len(songs)}] {song_name} - {artist_name}")
        result = search_song(song_name, artist_name)
        if result is None:
            unmatched.append(f"{song_name} - {artist_name}")
            print(f"    -> 未找到")
        else:
            s = result["song"]
            sid = s.get("id")
            sname = s.get("name", "?")
            sar = ", ".join(ar.get("name", "") for ar in s.get("ar", []))
            matched_ids.append(sid)
            success.append(f"{sname} - {sar} - {sid}")
            if result["confidence"] == "high":
                print(f"    -> ✓ {sname} - {sar}")
            else:
                low_confidence.append(
                    f"{song_name} - {artist_name} -> 匹配: {sname} - {sar} - {sid}"
                )
                print(f"    -> ? {sname} - {sar} (歌手不匹配)")
        time.sleep(0.5)

    # 创建歌单
    print(f"\n[*] 创建歌单「{playlist_name}」...")
    playlist_id = create_playlist(playlist_name)
    if not playlist_id:
        print("[-] 创建歌单失败（可能需要重新登录）")
        sys.exit(1)
    print(f"[+] 歌单创建成功: {playlist_id}")

    # 添加歌曲
    print(f"[*] 添加 {len(matched_ids)} 首歌曲到歌单...")
    ok = add_tracks(playlist_id, matched_ids)
    if ok:
        print("[+] 添加成功！")
    else:
        print("[!] 部分歌曲添加可能失败")

    # 写报告
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
