"""100% local LAN HTTP bridge for Google Pixel 10 Pro -> HP EliteBook."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ADB_PATH = r"D:\DND\HomeAutomation\tools\platform-tools\adb.exe"
HOST = os.environ.get("PIXEL_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PIXEL_BRIDGE_PORT", "8765"))
AUTH_TOKEN = os.environ.get("PIXEL_BRIDGE_TOKEN", "")


def get_lan_ip() -> str:
    """Return the primary local LAN IPv4 address without external requests."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.168.0.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def run_adb_devices() -> list[str]:
    """Return lines from `adb devices -l`."""
    proc = subprocess.run(
        [ADB_PATH, "devices", "-l"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


class LocalBridgeHandler(BaseHTTPRequestHandler):
    """Minimal local-only JSON API handler."""

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not AUTH_TOKEN:
            return True
        return self.headers.get("X-Bridge-Token", "") == AUTH_TOKEN

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return

        if self.path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "host": socket.gethostname(),
                    "lan_ip": get_lan_ip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            return

        if self.path == "/devices":
            self._send_json(200, {"devices": run_adb_devices()})
            return

        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return

        if self.path != "/action":
            self._send_json(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        action = data.get("action")
        if action == "ping":
            self._send_json(200, {"ok": True, "reply": "pong"})
        elif action == "adb_devices":
            self._send_json(200, {"ok": True, "devices": run_adb_devices()})
        elif action == "switch_theme":
            theme = str(data.get("theme", "0"))
            subprocess.run(
                [ADB_PATH, "-s", "58311FDCH000CF", "shell", "am", "start", "-n", "com.dnd.minimaltrio/.MainActivity", "--ei", "theme", theme],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self._send_json(200, {"ok": True, "theme": theme})
        else:
            self._send_json(400, {"error": f"unknown_action: {action}"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), LocalBridgeHandler)
    lan_ip = get_lan_ip()
    print(f"Local Pixel Bridge listening on http://{lan_ip}:{PORT} (bind {HOST}:{PORT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down local bridge.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
