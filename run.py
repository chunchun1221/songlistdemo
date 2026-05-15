#!/usr/bin/env python3
"""一键启动：启动 API → 登录（如需）→ 导入歌单"""

import http.client
import json
import os
import subprocess
import sys
import time

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
        print("    git clone https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced.git")
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
    """验证 cookie 是否有效"""
    try:
        conn = http.client.HTTPConnection("localhost", API_PORT, timeout=15)
        conn.request(
            "GET",
            "/login/status?realIP=183.2.175.120&domain=https://music.163.com",
            headers={"Cookie": content},
        )
        r = conn.getresponse()
        data = json.loads(r.read().decode("utf-8"))
        conn.close()
        account = data.get("data", {}).get("account", {})
        return account.get("id") is not None
    except Exception:
        return False


def ensure_login():
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            content = f.read().strip()
        if content and not content.startswith("#") and not content.startswith("请将"):
            if check_cookie_valid(content):
                print("[✓] Cookie 有效，已登录")
                return True
            else:
                print("[!] Cookie 已过期或无效，请重新登录")
        else:
            print("[!] Cookie 为空")

    print()
    print("请选择登录方式：")
    print("  1) 扫码登录（需要真实终端）")
    print("  2) 手动粘贴 Cookie（推荐）")
    print()

    choice = input("请选择 (1/2): ").strip()

    if choice == "1":
        print("\n[*] 启动扫码登录...")
        result = subprocess.run([sys.executable, "login.py"], cwd=BASE_DIR)
        if result.returncode != 0:
            print("[-] 扫码登录失败")
            return False
        return True

    elif choice == "2":
        print("\n[*] 请从浏览器复制 Cookie：")
        print("   1. 打开 https://music.163.com 并登录")
        print("   2. F12 → Application → Cookies → 全选右键 Copy as cURL")
        print("   3. 找到 -H 'Cookie: ...' 部分")
        print()
        cookie_val = input("请粘贴 Cookie 内容: ").strip()
        if cookie_val.startswith("Cookie:"):
            cookie_val = cookie_val[len("Cookie:"):].strip()
        cookie_val = cookie_val.strip("'\"")
        if not cookie_val:
            print("[-] Cookie 为空")
            return False
        with open(COOKIE_FILE, "w") as f:
            f.write(cookie_val)
        os.chmod(COOKIE_FILE, 0o600)
        print("[✓] Cookie 已保存")
        return True

    else:
        print("[-] 无效选择")
        return False


def run_import():
    print()
    import_script = os.path.join(BASE_DIR, "import_playlist.py")
    if not os.path.exists(import_script):
        print("[-] 未找到 import_playlist.py")
        return False

    if len(sys.argv) >= 2:
        playlist_name = sys.argv[1]
    else:
        playlist_name = input("请输入歌单名称: ").strip()
        if not playlist_name:
            playlist_name = "我的歌单"

    result = subprocess.run([sys.executable, import_script, playlist_name], cwd=BASE_DIR)
    return result.returncode == 0


def warmup():
    print("[*] 预热连接...")
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


def main():
    if not start_api():
        sys.exit(1)

    warmup()

    if not ensure_login():
        print("\n[!] 登录失败，请稍后重试")
        sys.exit(1)

    if not run_import():
        print("\n[!] 导入失败")
        sys.exit(1)

    print("\n[✓] 全部完成！")


if __name__ == "__main__":
    main()
