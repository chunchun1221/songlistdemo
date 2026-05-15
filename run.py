#!/usr/bin/env python3
"""一键启动：启动 API → 登录（Cookie 粘贴）→ 导入歌单"""

import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(BASE_DIR, "NeteaseCloudMusicApi")
COOKIE_FILE = os.path.join(BASE_DIR, ".cookie")
API_PORT = 3000


def is_api_running():
    import socket
    for host in ("::1", "127.0.0.1"):
        try:
            s = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((host, API_PORT))
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            pass
    return False


def start_api():
    print("=" * 50)
    print("网易云音乐歌单导入工具")
    print("=" * 50)

    if is_api_running():
        print("[✓] API 服务已在运行 (localhost:{})".format(API_PORT))
        return True

    print("[*] 启动 API 服务 (localhost:{})...".format(API_PORT))

    if not os.path.exists(os.path.join(API_DIR, "app.js")):
        print("[-] 未找到 API 目录，请先 clone api-enhanced")
        return False

    if not os.path.exists(os.path.join(API_DIR, "node_modules")):
        print("[*] 安装依赖...")
        subprocess.run(["npm", "install"], cwd=API_DIR, capture_output=True)

    log_file = open(os.path.join(BASE_DIR, "api.log"), "w")
    env = os.environ.copy()
    env["ENABLE_GENERAL_UNBLOCK"] = "false"
    subprocess.Popen(
        ["node", "app.js"],
        cwd=API_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    for _ in range(30):
        if is_api_running():
            print("[✓] API 服务启动成功")
            return True
        time.sleep(1)

    print("[-] API 服务启动超时，请查看 api.log")
    return False


def check_cookie_valid(content):
    params = urllib.parse.urlencode({"realIP": "183.2.175.120", "domain": "https://music.163.com"})
    last_err = ""
    for attempt in range(3):
        try:
            conn = http.client.HTTPConnection("localhost", API_PORT, timeout=30)
            conn.request(
                "GET",
                "/login/status?" + params,
                headers={"Cookie": content},
            )
            r = conn.getresponse()
            data = json.loads(r.read().decode("utf-8"))
            conn.close()
            account = (data.get("data") or {}).get("account") or {}
            if account.get("id"):
                print("    登录用户:", account.get("userName", "?"))
                return True
            last_err = str(data)[:300]
            return False
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                time.sleep(3)
    print(f"    [!] 验证失败原因: {last_err}")
    return False


def login_qr():
    """扫码登录"""
    print("\n[*] 启动扫码登录...")
    result = subprocess.run([sys.executable, "login.py"], cwd=BASE_DIR)
    if result.returncode != 0:
        print("[-] 扫码登录失败")
        return False
    return True


def input_cookie():
    print("\n" + "=" * 50)
    print("登录 - 手动粘贴 Cookie")
    print("=" * 50)
    print()
    print("操作步骤：")
    print("  1. 浏览器打开 https://music.163.com 并登录")
    print("  2. F12 → Application → Cookies → https://music.163.com")
    print("  3. 点任意一条 cookie，按 Cmd+A / Ctrl+A 全选")
    print("  4. 右键 → Copy → Copy as cURL (bash)")
    print("  5. 找到 Cookie: 开头的那段粘贴进来")
    print()

    cookie_val = input("请粘贴 Cookie 内容: ").strip()

    # 从 cURL 格式中提取 cookie 值
    if cookie_val.startswith("Cookie:"):
        cookie_val = cookie_val[len("Cookie:"):].strip()
    elif "Cookie:" in cookie_val:
        import re
        m = re.search(r"-H\s+'Cookie:\s*([^']+)'", cookie_val)
        if m:
            cookie_val = m.group(1)
        else:
            m = re.search(r"Cookie:\s*([^\s]+)", cookie_val)
            if m:
                cookie_val = m.group(1)

    cookie_val = cookie_val.strip("'\"")

    if not cookie_val:
        print("[-] Cookie 为空")
        return False

    print("\n[*] 验证 Cookie...")
    valid = check_cookie_valid(cookie_val)
    if not valid:
        print("[-] Cookie 无效，请确认已登录 music.163.com 后重试")
        save = input("是否仍保存到文件？(y/N): ").strip().lower()
        if save != "y":
            return False

    with open(COOKIE_FILE, "w") as f:
        f.write(cookie_val)
    os.chmod(COOKIE_FILE, 0o600)
    print("[✓] Cookie 已保存")
    return True


def ensure_login():
    # 如果已有有效 cookie，直接继续
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            content = f.read().strip()
        if content and not content.startswith("#"):
            print("[*] 检测登录状态...")
            if check_cookie_valid(content):
                print("[✓] Cookie 有效，已登录")
                return True
            print("[!] Cookie 验证失败（可能已过期，也可能是网络波动）")
            print()
            print("请选择：")
            print("  1) 直接使用已有 Cookie 继续（跳过验证）")
            print("  2) 重新扫码登录")
            print("  3) 粘贴新 Cookie")
            print()
            choice = input("请选择 (1/2/3，默认1): ").strip() or "1"
            if choice == "1":
                return True
            elif choice == "2":
                return login_qr()
            else:
                return input_cookie()

    # 没有 cookie 文件，让用户选择登录方式
    print()
    print("请选择登录方式：")
    print("  1) 扫码登录（用网易云 App 扫码）")
    print("  2) 粘贴 Cookie（从浏览器导出）")
    print()

    choice = input("请选择 (1/2): ").strip()

    if choice == "1":
        return login_qr()
    else:
        return input_cookie()


def run_import():
    print()
    import_script = os.path.join(BASE_DIR, "import_playlist.py")
    if not os.path.exists(import_script):
        print("[-] 未找到 import_playlist.py")
        return False

    result = subprocess.run([sys.executable, import_script], cwd=BASE_DIR)

    if result.returncode == 2:
        print("\n[!] 登录已过期，请重新登录")
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        if not ensure_login():
            return False
        print("\n[*] 重新登录成功，继续导入...")
        result = subprocess.run([sys.executable, import_script], cwd=BASE_DIR)

    return result.returncode == 0


def get_songs():
    """准备歌曲清单，写入 songs.txt，返回 True/False"""
    songs_file = os.path.join(BASE_DIR, "songs.txt")
    has_file = os.path.exists(songs_file)

    print()
    print("=" * 50)
    print("歌曲清单")
    print("=" * 50)
    print()

    if has_file:
        with open(songs_file) as f:
            count = sum(1 for line in f if line.strip())
        print("  检测到 songs.txt（{} 首）".format(count))
        use_file = input("\n直接使用此文件？(Y/n): ").strip().lower()
        if use_file != "n":
            return True

    print("请粘贴歌曲清单（每行格式：歌名 - 歌手）")
    print("粘贴完成后，按 Ctrl+D（Mac）/ Ctrl+Z（Windows）结束")
    print("或者将 songs.txt 文件拖拽到终端")
    print()

    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass

    content = _fix_surrogates("\n".join(lines).strip())
    if not content:
        print("[-] 未输入任何歌曲")
        return False

    # 如果用户拖拽了文件路径，读取文件内容
    if len(lines) == 1 and os.path.exists(lines[0].strip().replace("\\ ", " ")):
        filepath = lines[0].strip().replace("\\ ", " ")
        with open(filepath) as f:
            content = f.read().strip()

    # 保存并标准化格式
    normalized = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        for song, artist in _parse_songs(line):
            normalized.append("{} - {}".format(song, artist))

    with open(songs_file, "w") as f:
        f.write("\n".join(normalized) + "\n")

    print("[+] 已保存 {} 首歌曲到 songs.txt".format(len(normalized)))
    return True


def _fix_surrogates(s):
    try:
        s.encode("utf-8")   # 没有 surrogate，直接返回
        return s
    except UnicodeEncodeError:
        try:
            # 有 surrogate，还原字节后解码，去掉无法还原的替换符
            return s.encode("utf-8", "surrogatepass").decode("utf-8", "replace").replace("�", "")
        except Exception:
            return s


def _parse_songs(line):
    """解析单行歌曲，返回 [(歌名, 歌手), ...] 列表"""
    line = line.strip()
    if not line:
        return []
    line = line.lstrip("·•●○◆◇※☆★♪♫♬▷▶ ")

    # 歌手：《歌名1》《歌名2》... 或 歌手《歌名1》《歌名2》...
    titles = re.findall(r"《([^》]+)》", line)
    if titles:
        artist = line[: line.index("《")].strip().rstrip("：: ·•●○◆◇※☆★♪♫♬▷▶ ")
        return [(t, artist) for t in titles]

    # 歌名 - 歌手
    m = re.match(r"^(.+?)\s*[-—–]\s*(.+)$", line)
    if m:
        return [(m.group(1).strip(), m.group(2).strip())]

    # 歌名  歌手（多空格）
    m = re.match(r"^(.+?)\s{3,}(.+)$", line)
    if m:
        return [(m.group(1).strip(), m.group(2).strip())]

    return [(line, "")]


def warmup():
    print("[*] 预热连接（首次约 30-60s）...")
    try:
        conn = http.client.HTTPConnection("localhost", API_PORT, timeout=90)
        conn.request(
            "GET",
            "/search?keywords=warmup&realIP=183.2.175.120&domain=https://music.163.com",
        )
        conn.getresponse().read()
        conn.close()
    except Exception:
        pass


def logout():
    try:
        conn = http.client.HTTPConnection("localhost", API_PORT, timeout=10)
        with open(COOKIE_FILE) as f:
            cookie = f.read().strip()
        conn.request("GET", "/logout", headers={"Cookie": cookie})
        conn.getresponse().read()
        conn.close()
    except Exception:
        pass
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    print("[✓] 已退出登录，Cookie 已清除")


def main():
    if not start_api():
        sys.exit(1)

    warmup()

    if not ensure_login():
        print("\n[!] 登录失败")
        sys.exit(1)

    if not get_songs():
        print("\n[!] 歌曲清单为空")
        sys.exit(1)

    if not run_import():
        print("\n[!] 导入失败")
        sys.exit(1)

    print("\n[✓] 全部完成！")

    print()
    choice = input("是否退出网易云账号？(y/N): ").strip().lower()
    if choice == "y":
        logout()
    else:
        print("[i] 登录状态已保留，下次运行无需重新登录")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] 已退出")
