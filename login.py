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
BASE_PARAMS = "realIP={}".format(REAL_IP)


class ApiClient:
    """保持 cookie 的 API 客户端"""

    def __init__(self):
        self.cookies = ""

    def get(self, path, params_str="", retries=5, timeout=90):
        url = path
        if params_str:
            url = path + "?" + params_str

        for attempt in range(retries):
            try:
                conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=timeout)
                headers = {}
                if self.cookies:
                    headers["Cookie"] = self.cookies
                conn.request("GET", url, headers=headers)
                r = conn.getresponse()

                # 保存服务端返回的 cookie
                set_cookie = r.getheader("Set-Cookie")
                if set_cookie:
                    # 合并新 cookie
                    new_cookies = set_cookie.split(";")[0]
                    # 覆盖同名 cookie
                    existing = dict(
                        item.split("=", 1)
                        for item in self.cookies.split("; ")
                        if "=" in item
                    ) if self.cookies else {}
                    key, val = new_cookies.split("=", 1)
                    existing[key] = val
                    self.cookies = "; ".join(
                        "{}={}".format(k, v) for k, v in existing.items()
                    )

                data = json.loads(r.read().decode("utf-8"))
                conn.close()
                code = data.get("code")
                if code in (200, 800, 801, 802, 803):
                    return data
            except Exception:
                pass
            if attempt < retries - 1:
                wait = min(5 * (attempt + 1), 30)
                sys.stdout.write(f"\r  [重试 {attempt+1}/{retries}]")
                sys.stdout.flush()
                time.sleep(wait)
        return None


def main():
    print("=" * 50)
    print("网易云音乐 - 扫码登录")
    print("=" * 50)

    api = ApiClient()

    # 预热
    print("\n[*] 预热连接...")
    api.get("/cloudsearch", "keywords=warmup&" + BASE_PARAMS, retries=2, timeout=90)

    # 1. 获取 key
    print("[*] 获取二维码 key...")
    resp = api.get("/login/qr/key", BASE_PARAMS)
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
    resp = api.get("/login/qr/create", "key={}&{}".format(key, BASE_PARAMS))
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

    # 4. 预连接 check 接口
    api.get("/login/qr/check", "key={}&{}".format(key, BASE_PARAMS), retries=2)

    # 5. 轮询
    scanned = False
    for i in range(60):
        resp = api.get(
            "/login/qr/check",
            "key={}&{}".format(key, BASE_PARAMS),
            retries=3,
            timeout=60,
        )
        if not resp:
            sys.stdout.write(f"\r[*] 网络不稳定{' .' * ((i + 1) % 4):<8}")
            sys.stdout.flush()
            time.sleep(5)
            continue

        code = resp.get("code", -1)
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
            raw_cookie = resp.get("cookie", "")
            if not raw_cookie:
                print("\n[-] 登录成功但 cookie 为空")
                sys.exit(1)
            # 过滤掉 Set-Cookie 属性（Max-Age, Expires, Path, Domain, Secure, HttpOnly）
            clean_pairs = []
            for part in raw_cookie.split(";"):
                part = part.strip()
                if "=" in part and part.split("=", 1)[0].strip() not in (
                    "Max-Age", "Expires", "Path", "Domain",
                    "Secure", "HttpOnly", "SameSite", "Comment",
                ):
                    clean_pairs.append(part)
            cookie_str = "; ".join(clean_pairs)
            with open(COOKIE_FILE, "w") as f:
                f.write(cookie_str)
            os.chmod(COOKIE_FILE, 0o600)
            print("\n[+] 登录成功！Cookie 已保存")
            return
        else:
            msg = "连接中"
        sys.stdout.write(f"\r[*] {msg}{'.' * ((i + 1) % 4):<4}")
        sys.stdout.flush()
        time.sleep(3)

    print("\n[!] 等待超时，请重新运行")


if __name__ == "__main__":
    main()
