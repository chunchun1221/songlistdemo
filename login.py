#!/usr/bin/env python3
"""网易云音乐扫码登录 - 持久化 cookie 到 .cookie 文件"""

import http.client
import json
import os
import sys
import time

API_BASE = "localhost"
API_PORT = 3000
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cookie")
REAL_IP = "183.2.175.120"


def api_get(path, params_str="", retries=10):
    """使用 http.client 发 GET 请求，更稳定"""
    url = path
    if params_str:
        url = path + "?" + params_str

    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_BASE, API_PORT, timeout=60)
            conn.request("GET", url)
            r = conn.getresponse()
            data = json.loads(r.read().decode("utf-8"))
            conn.close()
            code = data.get("code")
            # 801 = 等待扫码（正常状态，不是错误）
            if code in (200, 800, 801, 802, 803):
                return data
            # 502 或其他错误 => 重试
        except Exception:
            pass
        if attempt < retries - 1:
            sys.stdout.write(f"\r  [重试 {attempt+1}/{retries}]")
            sys.stdout.flush()
            time.sleep(3)
    raise RuntimeError(f"请求 {path} 失败 ({retries} 次后放弃)")


def main():
    print("=" * 50)
    print("网易云音乐 - 扫码登录")
    print("=" * 50)

    # 预热 search
    print("\n[*] 预热连接...")
    try:
        conn = http.client.HTTPConnection(API_BASE, API_PORT, timeout=60)
        conn.request(
            "GET",
            "/search?keywords=warmup&realIP={}&domain=https://music.163.com".format(
                REAL_IP
            ),
        )
        conn.getresponse().read()
        conn.close()
    except Exception:
        pass

    # 1. 获取 key
    print("[*] 获取二维码 key...")
    resp = api_get(
        "/login/qr/key",
        "realIP={}&domain=https://music.163.com".format(REAL_IP),
    )
    key = resp.get("data", {}).get("unikey")
    print(f"[*] key: {key}")

    # 2. 创建二维码
    print("[*] 生成二维码...")
    resp = api_get(
        "/login/qr/create",
        "key={}&realIP={}&domain=https://music.163.com".format(key, REAL_IP),
    )
    qr_url = resp.get("data", {}).get("url")
    if not qr_url:
        qr_url = "https://music.163.com/login?codekey={}".format(key)

    # 3. 打印二维码
    import qrcode

    qr = qrcode.QRCode()
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr.print_ascii()

    print("\n[*] 请用网易云音乐 App 扫码登录")
    print("[*] 二维码有效期约 3 分钟\n")

    # 4. 轮询
    scanned = False
    for i in range(60):
        resp = api_get(
            "/login/qr/check",
            "key={}&realIP={}".format(key, REAL_IP),
            retries=3,
        )
        if resp is None:
            continue
        code = resp.get("code", -1)
        if code == 800:
            print("\n[!] 二维码已过期，请重新运行")
            sys.exit(1)
        if code == 801:
            # 等待扫码
            msg = "等待扫码"
        elif code == 802:
            # 已扫码，等待确认
            if not scanned:
                print("\n[✓] 已扫码，请在手机上确认登录")
                scanned = True
            msg = "等待确认"
        elif code == 803:
            cookie_str = resp.get("cookie", "")
            if not cookie_str:
                print(f"\n[-] 登录成功但 cookie 为空", file=sys.stderr)
                sys.exit(1)
            with open(COOKIE_FILE, "w") as f:
                f.write(cookie_str)
            os.chmod(COOKIE_FILE, 0o600)
            print(f"\n[+] 登录成功！Cookie 已保存到 .cookie")
            return
        else:
            msg = "等待中"
        sys.stdout.write(f"\r[*] {msg}{'.' * ((i + 1) % 4):<4}")
        sys.stdout.flush()
        time.sleep(3)

    print("\n[!] 等待超时，请重新运行")


if __name__ == "__main__":
    main()
