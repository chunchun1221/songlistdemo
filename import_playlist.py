#!/usr/bin/env python3
"""批量导入歌曲清单到网易云音乐歌单"""

import http.client
import json
import os
import re
import sys
import time
import urllib.parse

API_HOST = "localhost"
API_PORT = 3000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, ".cookie")
SONGS_FILE = os.path.join(BASE_DIR, "songs.txt")

# 结果文件
SUCCESS_FILE = os.path.join(BASE_DIR, "success.txt")
LOW_CONF_FILE = os.path.join(BASE_DIR, "low_confidence.txt")
UNMATCHED_FILE = os.path.join(BASE_DIR, "unmatched.txt")

COMMON_PARAMS = {
    "realIP": "183.2.175.120",
    "domain": "https://music.163.com",
}

COOKIE_CACHE = ""


def parse_song_line(line):
    """解析歌曲行，支持多种格式，返回 (歌名, 歌手) 或 None"""
    line = line.strip()
    if not line:
        return None

    # 去掉开头的装饰符号
    line = line.lstrip("·•●○◆◇※☆★♪♫♬▷▶ ")

    # 格式1: 歌手《歌名》 —— 最优先，因为《》很明确
    m = re.search(r"《([^》]+)》\s*(?:[-—–]+)?\s*$", line)
    if m:
        song = m.group(1).strip()
        artist = line[: m.start()].strip().rstrip("·•●○◆◇※☆★♪♫♬▷▶ ")
        if artist:
            return (song, artist)

    # 格式2: 歌名 - 歌手（或 歌名-歌手、歌名 — 歌手 等）
    m = re.match(r"^(.+?)\s*[-—–]\s*(.+)$", line)
    if m:
        return (m.group(1).strip(), m.group(2).strip())

    # 格式3: 歌名 歌手（用多个空格分隔）
    m = re.match(r"^(.+?)\s{3,}(.+)$", line)
    if m:
        return (m.group(1).strip(), m.group(2).strip())

    # 格式4: 只有歌名，没有歌手
    if line and not line.startswith("#"):
        return (line, "")

    return None


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


def api_get(path, params_dict=None, retries=3, timeout=90):
    url = path
    if params_dict:
        url = path + "?" + urllib.parse.urlencode(params_dict)

    cookie = load_cookie()

    last_info = ""
    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
            headers = {}
            if cookie:
                headers["Cookie"] = cookie
            conn.request("GET", url, headers=headers)
            r = conn.getresponse()
            raw = r.read()
            data = json.loads(raw.decode("utf-8"))
            conn.close()

            code = data.get("code")
            if code == 200:
                return data
            msg = data.get("msg", "") or data.get("message", "")
            last_info = f"code={code} msg={msg}"
            if "需要登录" in msg:
                print(f"  [!] 需要登录，请重新登录")
                return None
        except Exception as e:
            last_info = str(e)
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    print(f"    [!] 请求失败: {last_info}")
    return None


def api_post(path, params_dict, retries=3, timeout=90):
    """POST 请求，params_dict 自动 URL 编码"""
    params_dict = {**params_dict, **COMMON_PARAMS}
    body = urllib.parse.urlencode(params_dict)
    cookie = load_cookie()

    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if cookie:
                headers["Cookie"] = cookie
            conn.request("POST", path, body=body, headers=headers)
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


AUTO_MATCH_NO_ARTIST = True  # 无歌手歌曲是否自动取搜索结果第一条


def search_song(song_name, artist_name):
    if artist_name:
        keywords = "{} {}".format(song_name, artist_name)
    else:
        keywords = song_name

    params = {
        "keywords": keywords,
        "limit": "10",
        **COMMON_PARAMS,
    }
    resp = api_get("/cloudsearch", params)
    if not resp:
        return None

    songs = resp.get("result", {}).get("songs", [])
    if not songs:
        return None

    # 无歌手：取第一条
    if not artist_name:
        if AUTO_MATCH_NO_ARTIST:
            return {"song": songs[0], "confidence": "no_artist"}
        else:
            return None

    # 有歌手：匹配歌手名
    artist_lower = artist_name.lower()
    artist_normalized = artist_lower.replace("&", ",").replace(" and ", ",")

    for s in songs:
        ar_names = [ar.get("name", "") for ar in s.get("ar", [])]
        ar_lower = "".join(n.lower() for n in ar_names)
        if artist_normalized.replace(",", "") in ar_lower.replace(",", ""):
            return {"song": s, "confidence": "high"}
        for n in ar_lower:
            if artist_normalized in n or n in artist_normalized:
                return {"song": s, "confidence": "high"}

    return {"song": songs[0], "confidence": "low"}


def create_playlist(name):
    resp = api_post("/playlist/create", {"name": name})
    if not resp:
        return None
    return resp.get("playlist", {}).get("id")


def add_tracks(playlist_id, song_ids):
    all_ids = list(song_ids)
    for i in range(0, len(all_ids), 100):
        batch = all_ids[i : i + 100]
        ids_str = ",".join(str(sid) for sid in batch)
        resp = api_post(
            "/playlist/tracks",
            {"op": "add", "pid": str(playlist_id), "tracks": ids_str},
        )
        if not resp:
            return False
    return True


def warmup():
    print("[*] 预热连接...")
    start = time.time()
    api_get("/cloudsearch", {"keywords": "warmup", **COMMON_PARAMS}, timeout=60)
    elapsed = time.time() - start
    if elapsed > 2:
        print(f"   (耗时 {elapsed:.0f}s)")


def _fix_surrogates(s):
    try:
        s.encode("utf-8")
        return s
    except UnicodeEncodeError:
        try:
            return s.encode("utf-8", "surrogatepass").decode("utf-8", "replace").replace("�", "")
        except Exception:
            return s


def ask_playlist_name():
    """搜索完成后询问歌单名称"""
    print()
    name = input("请输入歌单名称（默认: 我的歌单）: ").strip()
    return _fix_surrogates(name) or "我的歌单"


def main():
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

    songs = []
    no_artist_count = 0
    with open(SONGS_FILE) as f:
        for line in f:
            result = parse_song_line(line)
            if result:
                songs.append(result)
                if not result[1]:
                    no_artist_count += 1
            elif line.strip():
                print(f"  [!] 无法解析: {line.strip()}")

    print(f"[*] 共读取 {len(songs)} 首歌曲")

    global AUTO_MATCH_NO_ARTIST
    if no_artist_count > 0:
        print(f"\n[!] 有 {no_artist_count} 首歌曲未指定歌手")
        choice = input("自动取搜索结果第一条？(Y/n): ").strip().lower()
        if choice == "n":
            AUTO_MATCH_NO_ARTIST = False
            print("  已跳过，这些歌不会被导入")
        else:
            print("  将自动取搜索第一条结果")

    warmup()

    print("\n[*] 开始搜索匹配歌曲...（按 Ctrl+C 可随时停止）")
    matched_ids = []
    low_confidence = []
    unmatched = []
    success = []
    idx = 0

    try:
        for idx, (song_name, artist_name) in enumerate(songs, 1):
            print(f"  [{idx}/{len(songs)}] {song_name} - {artist_name}")
            result = search_song(song_name, artist_name)
            if result is None:
                label = artist_name or song_name
                unmatched.append(f"{label}")
                print(f"    -> 未找到")
            else:
                s = result["song"]
                sid = s.get("id")
                sname = s.get("name", "?")
                sar = ", ".join(ar.get("name", "") for ar in s.get("ar", []))
                matched_ids.append(sid)
                success.append(f"{sname} - {sar} - {sid}")
                conf = result["confidence"]
                if conf == "high":
                    print(f"    -> ✓ {sname} - {sar}")
                elif conf == "no_artist":
                    low_confidence.append(
                        f"{song_name} (未指定歌手) -> 自动匹配: {sname} - {sar} - {sid}"
                    )
                    print(f"    -> ? {sname} - {sar} (自动匹配)")
                else:
                    low_confidence.append(
                        f"{song_name} - {artist_name} -> 匹配: {sname} - {sar} - {sid}"
                    )
                    print(f"    -> ? {sname} - {sar} (歌手不匹配)")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n\n[!] 已中断，已搜索 {idx}/{len(songs)} 首，匹配到 {len(matched_ids)} 首")
        if not matched_ids:
            print("[-] 没有已匹配的歌曲，退出")
            sys.exit(0)
        ans = input("是否用已匹配的歌曲创建歌单？(Y/n): ").strip().lower()
        if ans == "n":
            print("[-] 已取消")
            sys.exit(0)

    playlist_name = ask_playlist_name()

    print(f"\n[*] 创建歌单「{playlist_name}」...")
    playlist_id = create_playlist(playlist_name)
    if not playlist_id:
        print("[-] 创建歌单失败，登录已过期")
        sys.exit(2)  # 退出码 2 = 需要重新登录
    print(f"[+] 歌单创建成功: {playlist_id}")

    print(f"[*] 添加 {len(matched_ids)} 首歌曲到歌单...")
    ok = add_tracks(playlist_id, matched_ids)
    if ok:
        print("[+] 添加成功！")
    else:
        print("[!] 部分歌曲添加可能失败")

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
