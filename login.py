#!/usr/bin/env python3
"""网易云音乐扫码登录 - 持久化 cookie 到 .cookie 文件"""

import http.client
import json
import os
import sys
import time

API_HOST = "localhost"
API_PORT = 3000
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cookie")
REAL_IP = "183.2.175.120"
# 统一通过 /api 前缀走默认路由，不加 domain 覆盖（避免兼容问题）
BASE_PARAMS = "realIP={}".format(REAL_IP)


def api_get(path, params_str="", retries=5, timeout=90):
    url = path
    if params_str:
        url = path + "?" + params_str

    for attempt in range(retries):
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
            conn.request("GET", url)
            r = conn.getresponse()
            data = json.loads(r.read().decode("utf-8"))
            conn.close()
            code = data.get("code")
            if code in (200, 800, 801, 802, 803):
                return data
        except Exception:
            pass
        if attempt < retries - 1:
            wait = min(5 * (attempt + 1), 30)  # 5, 10, 15...
            sys.stdout.write(f"\r  [重试 {attempt+1}/{retries} {wait}s]")
            sys.stdout.flush()
            time.sleep(wait)
    return None


def wait_for_api():
    """等待 API 准备好（预热连接）"""
    print("[*] 预热连接（约 30-60s）...")
    api_get("/cloudsearch", "keywords=warmup&" + BASE_PARAMS, retries=2, timeout=90)


def main():
    print("=" * 50)
    print("网易云音乐 - 扫码登录")
    print("=" * 50)

    wait_for_api()

    # 1. 获取 key
    print("[*] 获取二维码 key...")
    resp = api_get("/login/qr/key", BASE_PARAMS)
    if not resp:
        print("[-] 获取 key 失败")
        sys.exit(1)
    key = resp.get("data", {}).get("unikey")
    if not key:
        print("[-] 获取 key 失败:", resp)
        sys.exit(1)
    print(f"[*] key: {key}")

    # 2. 创建二维码
    print("[*] 生成二维码...")
    resp = api_get("/login/qr/create", "key={}&{}".format(key, BASE_PARAMS))
    if not resp:
        print("[-] 创建二维码失败")
        sys.exit(1)
    qr_url = resp.get("data", {}).get("url") or "https://music.163.com/login?codekey={}".format(key)

    # 3. 打印二维码
    import qrcode
    qr = qrcode.QRCode()
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr.print_ascii()

    print("\n[*] 请用网易云音乐 App 扫码登录")
    print("[*] 二维码有效期约 3 分钟\n")

    # 4. 轮询（先快速等几秒预热 check 连接）
    time.sleep(2)
    api_get("/login/qr/check", "key={}&{}".format("dummy", BASE_PARAMS), retries=2)

    scanned = False
    for i in range(60):
        resp = api_get(
            "/login/qr/check",
            "key={}&{}".format(key, BASE_PARAMS),
            retries=3,
            timeout=60,
        )
        if not resp:
            sys.stdout.write(f"\r[*] 网络不稳定{'.' * ((i + 1) % 4):<8}")
            sys.stdout.flush()
            time.sleep(5)
            continue

        code = resp.get("code", -1)

        # 调试信息
        if code not in (801,):
            print(f"\n[DEBUG] code={code} msg={resp.get('message','')}")

        if code == 800:
            print("\n[!] 二维码已过期，请重新运行")
            sys.exit(1)
        if code == 801:
            msg = "等待扫码"
        elif code == 802:
            if not scanned:
                print("\n[✓] 已扫码，请在手机上确认登录")
                scanned = True
            msg = "等待确认"
        elif code == 803:
            cookie_str = resp.get("cookie", "")
            if not cookie_str:
                print(f"\n[-] 登录成功但 cookie 为空")
                sys.exit(1)
            with open(COOKIE_FILE, "w") as f:
                f.write(cookie_str)
            os.chmod(COOKIE_FILE, 0o600)
            print(f"\n[+] 登录成功！Cookie 已保存")
            return
        else:
            msg = "连接中"
        sys.stdout.write(f"\r[*] {msg}{'.' * ((i + 1) % 4):<4}")
        sys.stdout.flush()
        time.sleep(3)

    print("\n[!] 等待超时，请重新运行")


if __name__ == "__main__":
    main()
