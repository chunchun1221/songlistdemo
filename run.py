#!/usr/bin/env python3
"""一键启动：启动 API → 登录（Cookie 粘贴）→ 导入歌单"""

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
        if account.get("id"):
            print("    登录用户:", account.get("userName", "?"))
            return True
        return False
    except Exception:
        return False


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
        # 完整 cURL 命令格式
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

    # 验证
    print("\n[*] 验证 Cookie...")
    valid = check_cookie_valid(cookie_val)
    if not valid:
        print("[-] Cookie 无效，请确认已登录 music.163.com 后重试")
        # 问是否还要保存
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
            else:
                print("[!] Cookie 已过期")

    # 引导用户粘贴 cookie
    return input_cookie()


def run_import():
    print()
    import_script = os.path.join(BASE_DIR, "import_playlist.py")
    if not os.path.exists(import_script):
        print("[-] 未找到 import_playlist.py")
        return False

    if len(sys.argv) >= 2:
        playlist_name = sys.argv[1]
    else:
        playlist_name = input("请输入歌单名称: ").strip() or "我的歌单"

    result = subprocess.run([sys.executable, import_script, playlist_name], cwd=BASE_DIR)
    return result.returncode == 0


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


def main():
    if not start_api():
        sys.exit(1)

    warmup()

    if not ensure_login():
        print("\n[!] 登录失败")
        sys.exit(1)

    if not run_import():
        print("\n[!] 导入失败")
        sys.exit(1)

    print("\n[✓] 全部完成！")


if __name__ == "__main__":
    main()
