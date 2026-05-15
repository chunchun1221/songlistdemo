#!/usr/bin/env python3
"""网易云音乐扫码登录 - 持久化 cookie 到 .cookie 文件"""

import os
import sys
import time

import requests

API_BASE = "http://localhost:3000"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cookie")
COMMON_PARAMS = {
    "realIP": "183.2.175.120",
    "domain": "https://music.163.com",
}


def api_get(path, params=None, retries=5):
    if params is None:
        params = {}
    params.update(COMMON_PARAMS)
    for attempt in range(retries):
        try:
            r = requests.get(
                f"{API_BASE}{path}", params=params, timeout=30
            )
            data = r.json()
            if data.get("code") == 200:
                return data
        except Exception:
            pass
        if attempt < retries - 1:
            sys.stdout.write(f"\r  [重试 {attempt+1}/{retries}]")
            sys.stdout.flush()
            time.sleep(2)
    raise RuntimeError(f"API {path} 请求失败 ({retries} 次)")


def main():
    print("=" * 50)
    print("网易云音乐 - 扫码登录")
    print("=" * 50)

    # 1. 获取二维码 key
    print("\n[*] 获取二维码 key...")
    resp = api_get("/login/qr/key")
    key = resp.get("data", {}).get("unikey")
    print(f"\n[*] key: {key}")

    # 2. 创建二维码
    print("[*] 生成二维码...")
    resp = api_get("/login/qr/create", {"key": key})
    qr_url = resp.get("data", {}).get("url")

    # 3. 打印 ASCII 二维码
    import qrcode

    qr = qrcode.QRCode()
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr.print_ascii()

    print("\n[*] 请用网易云音乐 App 扫码登录")
    print("[*] 二维码有效期约 3 分钟")

    # 4. 轮询扫码状态
    for i in range(60):
        resp = api_get("/login/qr/check", {"key": key}, retries=3)
        code = resp.get("code", -1)
        if code == 800:
            print("\n[!] 二维码已过期，请重新运行本脚本")
            sys.exit(1)
        if code == 803:
            cookie_str = resp.get("cookie", "")
            if not cookie_str:
                print(f"\n[-] 扫码成功但 cookie 为空: {resp}", file=sys.stderr)
                sys.exit(1)
            with open(COOKIE_FILE, "w") as f:
                f.write(cookie_str)
            os.chmod(COOKIE_FILE, 0o600)
            print(f"\n[+] 登录成功！Cookie 已保存到 {COOKIE_FILE}")
            return
        sys.stdout.write(f"\r[*] 等待扫码{'.' * ((i + 1) % 4):<4}")
        sys.stdout.flush()
        time.sleep(3)

    print("\n[!] 等待超时，请重新运行")


if __name__ == "__main__":
    main()
