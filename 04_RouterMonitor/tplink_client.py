"""TP-Link router local config & RSA+AES (/cgi/login, /cgi_gdpr) client."""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CONFIG_PATH = Path(__file__).resolve().parent / "router_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "routers": [
        {"name": "Main Router", "ip": "192.168.0.1", "username": "admin", "password": ""},
        {"name": "Secondary Router / AP", "ip": "192.168.0.4", "username": "admin", "password": ""},
    ]
}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _rsa_encrypt_no_pad(plaintext: bytes, n_hex: str, e_hex: str) -> str:
    """TP-Link's raw RSA encryption over UTF-8 bytes (512-bit / 64-byte blocks)."""
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    key_bytes = (n.bit_length() + 7) // 8
    out_hex = []
    # TP-Link pads/chunks per key_bytes
    for i in range(0, len(plaintext), key_bytes):
        chunk = plaintext[i : i + key_bytes]
        if len(chunk) < key_bytes:
            chunk = chunk.ljust(key_bytes, b"\x00")
        m = int.from_bytes(chunk, "big")
        c = pow(m, e, n)
        out_hex.append(format(c, f"0{key_bytes * 2}x"))
    return "".join(out_hex)


def _aes_encrypt_b64(plaintext: str, key: str, iv: str) -> str:
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.CBC(iv.encode("utf-8")))
    enc = cipher.encryptor()
    ct = enc.update(padded) + enc.finalize()
    return base64.b64encode(ct).decode("ascii")


def _aes_decrypt_b64(b64_text: str, key: str, iv: str) -> str:
    ct = base64.b64decode(b64_text)
    cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.CBC(iv.encode("utf-8")))
    dec = cipher.decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    raw = unpadder.update(padded) + unpadder.finalize()
    return raw.decode("utf-8", errors="replace")


class TPLinkClient:
    def __init__(self, ip: str, username: str, password: str) -> None:
        self.ip = ip.strip()
        self.username = username.strip() or "admin"
        self.password = password
        self.base = f"http://{self.ip}"
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.token_id = ""
        self.aes_key = ""
        self.aes_iv = ""
        self.seq = 0

    def _req(self, path: str, data: bytes | None = None, content_type: str = "text/plain") -> str:
        headers = {"Referer": f"{self.base}/", "Origin": self.base}
        if data is not None:
            headers["Content-Type"] = content_type
        if self.token_id:
            headers["TokenID"] = self.token_id
        req = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers)
        with self.opener.open(req, timeout=4.0) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def login(self) -> dict[str, Any]:
        if not self.password:
            return {"ok": False, "error": "Password not set"}
        try:
            parm_js = self._req("/cgi/getParm")
        except (OSError, urllib.error.URLError) as exc:
            return {"ok": False, "error": f"Router unreachable: {exc}"}

        ee = re.search(r'var ee="([0-9a-fA-F]+)"', parm_js)
        nn = re.search(r'var nn="([0-9a-fA-F]+)"', parm_js)
        seq = re.search(r'var seq="(\d+)"', parm_js)
        if not (ee and nn and seq):
            return {"ok": False, "error": "Unsupported TP-Link firmware (missing getParm RSA params)"}

        self.seq = int(seq.group(1))
        seed = str(int(time.time() * 1000)) + str(int.from_bytes(os.urandom(4), "big"))
        self.aes_key = seed[:16]
        self.aes_iv = (seed[::-1] + "0123456789abcdef")[:16]

        login_payload = f"{self.username}\n{self.password}"
        enc_data = _aes_encrypt_b64(login_payload, self.aes_key, self.aes_iv)

        h = hashlib.md5(f"{self.username}{self.password}".encode("utf-8")).hexdigest()
        s_val = self.seq + len(enc_data)
        sign_plain = f"key={self.aes_key}&iv={self.aes_iv}&h={h}&s={s_val}".encode("utf-8")
        enc_sign = _rsa_encrypt_no_pad(sign_plain, nn.group(1), ee.group(1))

        body = f"sign={urllib.parse.quote(enc_sign)}&data={urllib.parse.quote(enc_data)}".encode("utf-8")
        try:
            res = self._req("/cgi/login", data=body, content_type="application/x-www-form-urlencoded")
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"Login HTTP {exc.code}"}

        tok = re.search(r'var token="([0-9a-fA-F]+)"', res)
        if tok:
            self.token_id = tok.group(1)

        if "$.ret=0" in res or self.token_id or any(c.name == "JSESSIONID" for c in self.cj):
            return {"ok": True, "token": bool(self.token_id)}
        return {"ok": False, "error": "Invalid username or password"}


def test_all_routers() -> list[dict[str, Any]]:
    cfg = load_config()
    out: list[dict[str, Any]] = []
    for r in cfg.get("routers", []):
        ip = r.get("ip", "")
        pw = r.get("password", "")
        if not pw:
            out.append({"name": r.get("name"), "ip": ip, "ok": False, "error": "Password not configured"})
            continue
        client = TPLinkClient(ip, r.get("username", "admin"), pw)
        res = client.login()
        out.append({"name": r.get("name"), "ip": ip, **res})
    return out
