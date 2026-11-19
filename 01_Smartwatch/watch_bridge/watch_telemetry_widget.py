"""Modern Glass-UI Local Telemetry Widget & Two-Way LAN Bridge for Xiaomi Watch 2 Pro."""

from __future__ import annotations

import ctypes
import json
import re
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ADB_PATH = Path(r"D:\DND\HomeAutomation\tools\platform-tools\adb.exe")
CACHE_PATH = Path(__file__).resolve().parent / "telemetry_cache.json"
BRIDGE_PORT = 8765
POLL_INTERVAL_SEC = 20


def run_adb(args: list[str], timeout: int = 5) -> tuple[int, str]:
    """Execute an adb command without spawning a console window."""
    if not ADB_PATH.exists():
        return 1, "adb.exe not found"
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [str(ADB_PATH), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creation_flags,
        )
        return proc.returncode, (proc.stdout or proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "timeout"
    except Exception as exc:
        return 1, str(exc)


def find_watch_serial() -> str | None:
    """Return the active ADB serial for Xiaomi Watch 2 Pro, preferring IP:Port."""
    code, out = run_adb(["devices", "-l"])
    if code != 0:
        return None
    mdns_fallback = None
    for line in out.splitlines():
        if " device " not in line:
            continue
        if "Xiaomi_Watch_2_Pro" not in line and "_adb-tls-connect" not in line and "192.168." not in line:
            continue
        serial = line.split(" device ", 1)[0].strip()
        if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial):
            return serial
        if mdns_fallback is None:
            mdns_fallback = serial
    return mdns_fallback


def parse_battery(raw: str) -> dict[str, Any]:
    """Parse dumpsys battery output into clean fields."""
    level = None
    status = "Unknown"
    temp_c = None
    voltage_v = None

    if m := re.search(r"level:\s*(\d+)", raw):
        level = int(m.group(1))
    if m := re.search(r"temperature:\s*(\d+)", raw):
        temp_c = round(int(m.group(1)) / 10.0, 1)
    if m := re.search(r"voltage:\s*(\d+)", raw):
        mv = int(m.group(1))
        voltage_v = round(mv / 1000.0, 2) if mv > 100 else round(mv, 2)
    if m := re.search(r"status:\s*(\d+)", raw):
        code = int(m.group(1))
        status = {2: "Charging", 3: "Discharging", 4: "Not charging", 5: "Full"}.get(code, "Unknown")

    return {"battery_pct": level, "battery_status": status, "temp_c": temp_c, "voltage_v": voltage_v}


def parse_network_location(raw_wifi: str, serial: str) -> dict[str, str | None]:
    """Extract local Wi-Fi SSID, RSSI, and IP from dumpsys wifi / serial."""
    ssid = None
    rssi = None
    ip = serial.split(":")[0] if ":" in serial and serial[0].isdigit() else None

    if m := re.search(r'SSID:\s*"?([^",\r\n]+)"?', raw_wifi):
        val = m.group(1).strip()
        if val and val != "<unknown ssid>":
            ssid = val
    if m := re.search(r"RSSI:\s*(-\d+)", raw_wifi):
        rssi = f"{m.group(1)} dBm"
    if ip is None and (m := re.search(r"ipAddress=(\d+\.\d+\.\d+\.\d+)", raw_wifi)):
        ip = m.group(1)

    return {"wifi_ssid": ssid, "wifi_rssi": rssi, "watch_ip": ip}


class WatchState:
    """Thread-safe shared telemetry and bridge state."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {
            "connected": False,
            "serial": None,
            "last_ip_port": "192.168.0.11:35773",
            "battery_pct": None,
            "battery_status": "Waiting...",
            "temp_c": None,
            "voltage_v": None,
            "wifi_ssid": None,
            "wifi_rssi": None,
            "watch_ip": "192.168.0.11",
            "last_seen": None,
            "last_event": f"LAN Bridge :{BRIDGE_PORT} ready",
        }
        self._load_cache()

    def _load_cache(self) -> None:
        if CACHE_PATH.exists():
            try:
                cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                self.data.update({k: v for k, v in cached.items() if k in self.data and v is not None})
                self.data["connected"] = False
            except Exception:
                pass

    def save_cache(self) -> None:
        with self.lock:
            payload = dict(self.data)
        try:
            CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def update(self, **kwargs: Any) -> None:
        with self.lock:
            self.data.update(kwargs)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.data)


STATE = WatchState()


def execute_laptop_action(action: str) -> tuple[bool, str]:
    """Execute a local Windows action triggered from the watch or LAN."""
    if action == "lock":
        ctypes.windll.user32.LockWorkStation()
        return True, "Workstation locked"
    if action == "media_play_pause":
        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
        return True, "Toggled media play/pause"
    if action == "vol_mute":
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        return True, "Toggled system mute"
    if action == "ping":
        return True, f"Ping received at {datetime.now().strftime('%H:%M:%S')}"
    return False, f"Unknown action: {action}"


class BridgeHandler(BaseHTTPRequestHandler):
    """Lightweight local LAN HTTP endpoint for watch -> laptop triggers."""

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/status":
            self._send_json(200, STATE.snapshot())
            return
        if self.path.startswith("/trigger/"):
            action = self.path.split("/trigger/", 1)[1].strip("/")
            ok, msg = execute_laptop_action(action)
            STATE.update(last_event=f"LAN -> {msg}")
            self._send_json(200 if ok else 404, {"ok": ok, "message": msg})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        self.do_GET()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


class GlassTelemetryWidget:
    """Modern frosted-glass dark floating Windows widget."""

    BG_OUTER = "#0D1017"
    BG_GLASS = "#151A24"
    BG_INPUT = "#1C2230"
    BORDER = "#2A3244"
    FG = "#F3F4F6"
    MUTED = "#8B95A8"
    GOLD = "#D4AF6A"
    EMERALD = "#34D399"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Watch 2 Pro · Glass Telemetry")
        self.root.geometry("340x330+36+36")
        self.root.overrideredirect(True)
        self.root.configure(bg=self.BORDER)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()
        self._start_bridge_server()
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self._refresh_ui()

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=self.BG_OUTER)
        shell.pack(fill="both", expand=True, padx=1, pady=1)

        # Draggable Title Bar
        title_bar = tk.Frame(shell, bg=self.BG_OUTER, cursor="fleur")
        title_bar.pack(fill="x", padx=14, pady=(10, 6))
        title_bar.bind("<Button-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._on_drag)

        tk.Label(
            title_bar, text="XIAOMI WATCH 2 PRO", fg=self.GOLD, bg=self.BG_OUTER,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        close_btn = tk.Label(
            title_bar, text="✕", fg=self.MUTED, bg=self.BG_OUTER,
            font=("Segoe UI", 9, "bold"), cursor="hand2", padx=4,
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _e: self.root.destroy())

        self.pin_lbl = tk.Label(
            title_bar, text="PIN", fg=self.GOLD, bg=self.BG_INPUT,
            font=("Segoe UI", 7, "bold"), cursor="hand2", padx=6, pady=2,
        )
        self.pin_lbl.pack(side="right", padx=(0, 6))
        self.pin_lbl.bind("<Button-1>", lambda _e: self._toggle_pin())

        self.status_lbl = tk.Label(
            title_bar, text="● SLEEPING", fg=self.MUTED, bg=self.BG_OUTER,
            font=("Segoe UI", 8, "bold"),
        )
        self.status_lbl.pack(side="right", padx=(0, 8))

        # Glass Hero Card: Battery + Progress Bar + Last Update
        hero = tk.Frame(shell, bg=self.BG_GLASS, highlightbackground=self.BORDER, highlightthickness=1)
        hero.pack(fill="x", padx=14, pady=(2, 8))

        top_row = tk.Frame(hero, bg=self.BG_GLASS)
        top_row.pack(fill="x", padx=14, pady=(10, 4))

        self.bat_lbl = tk.Label(top_row, text="--%", fg=self.FG, bg=self.BG_GLASS, font=("Segoe UI Light", 30))
        self.bat_lbl.pack(side="left")

        right_info = tk.Frame(top_row, bg=self.BG_GLASS)
        right_info.pack(side="right", anchor="e")
        self.state_lbl = tk.Label(right_info, text="Waiting...", fg=self.GOLD, bg=self.BG_GLASS, font=("Segoe UI", 9, "bold"))
        self.state_lbl.pack(anchor="e")
        self.updated_lbl = tk.Label(right_info, text="Updated: --", fg=self.MUTED, bg=self.BG_GLASS, font=("Segoe UI", 8))
        self.updated_lbl.pack(anchor="e")

        # Sleek Battery Bar
        self.bar_canvas = tk.Canvas(hero, height=5, bg="#222836", highlightthickness=0)
        self.bar_canvas.pack(fill="x", padx=14, pady=(2, 10))
        self.bar_fill = self.bar_canvas.create_rectangle(0, 0, 0, 5, fill=self.GOLD, width=0)

        # Stats & Location Glass Card
        stats = tk.Frame(shell, bg=self.BG_GLASS, highlightbackground=self.BORDER, highlightthickness=1)
        stats.pack(fill="x", padx=14, pady=(0, 8))

        self.stats_lbl = tk.Label(
            stats, text="Temp: --°C  ·  Volt: --V  ·  RSSI: --",
            fg=self.FG, bg=self.BG_GLASS, font=("Segoe UI", 8), anchor="w",
        )
        self.stats_lbl.pack(fill="x", padx=12, pady=(8, 2))

        self.loc_lbl = tk.Label(
            stats, text="Location: Home Wi-Fi  ·  IP: 192.168.0.11",
            fg=self.MUTED, bg=self.BG_GLASS, font=("Segoe UI", 8), anchor="w",
        )
        self.loc_lbl.pack(fill="x", padx=12, pady=(0, 8))

        # Remembered IP:Port + Connect Row
        conn_row = tk.Frame(shell, bg=self.BG_OUTER)
        conn_row.pack(fill="x", padx=14, pady=(0, 8))

        self.ip_var = tk.StringVar(value=STATE.snapshot().get("last_ip_port") or "192.168.0.11:35773")
        self.ip_entry = tk.Entry(
            conn_row, textvariable=self.ip_var, bg=self.BG_INPUT, fg=self.FG,
            insertbackground=self.GOLD, relief="flat", font=("Consolas", 9),
            highlightbackground=self.BORDER, highlightthickness=1,
        )
        self.ip_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        self.ip_entry.bind("<Return>", lambda _e: self._connect_target())

        btn_kw = {
            "bd": 0, "font": ("Segoe UI", 8, "bold"), "padx": 10, "pady": 5, "cursor": "hand2",
        }
        tk.Button(
            conn_row, text="Connect", command=self._connect_target,
            bg=self.GOLD, fg="#0D1017", activebackground="#E5C27E", **btn_kw,
        ).pack(side="right")

        # Action Buttons: Ring Watch + Poll Now
        actions = tk.Frame(shell, bg=self.BG_OUTER)
        actions.pack(fill="x", padx=14, pady=(0, 6))

        tk.Button(
            actions, text="🔔 Ring Watch", command=self._ring_watch,
            bg="#262D3D", fg=self.FG, activebackground="#333C52", **btn_kw,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        tk.Button(
            actions, text="↻ Poll Live", command=self._manual_poll,
            bg=self.BG_INPUT, fg=self.GOLD, activebackground="#262D3D", **btn_kw,
        ).pack(side="right", fill="x", expand=True)

        self.event_lbl = tk.Label(
            shell, text=f"Bridge :{BRIDGE_PORT} ready", fg=self.MUTED, bg=self.BG_OUTER,
            font=("Segoe UI", 8), anchor="w",
        )
        self.event_lbl.pack(fill="x", padx=14, pady=(2, 8))

    def _start_bridge_server(self) -> None:
        server = ThreadingHTTPServer(("0.0.0.0", BRIDGE_PORT), BridgeHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def _poll_once(self) -> None:
        serial = find_watch_serial()
        if not serial:
            last_ip = STATE.snapshot().get("last_ip_port")
            if last_ip:
                run_adb(["connect", last_ip], timeout=3)
                serial = find_watch_serial()

        if not serial:
            STATE.update(connected=False)
            return

        _, bat_raw = run_adb(["-s", serial, "shell", "dumpsys", "battery"])
        _, wifi_raw = run_adb(["-s", serial, "shell", "dumpsys wifi | grep -E 'SSID:|RSSI:|ipAddress=' | head -n 10"])
        bat_info = parse_battery(bat_raw)
        net_info = parse_network_location(wifi_raw, serial)
        now_str = datetime.now().strftime("%H:%M:%S")

        updates: dict[str, Any] = {
            "connected": True,
            "serial": serial,
            "last_seen": now_str,
            "battery_status": bat_info["battery_status"],
            "temp_c": bat_info["temp_c"],
            "voltage_v": bat_info["voltage_v"],
        }
        if bat_info["battery_pct"] is not None:
            updates["battery_pct"] = bat_info["battery_pct"]
        if net_info["wifi_ssid"]:
            updates["wifi_ssid"] = net_info["wifi_ssid"]
        if net_info["wifi_rssi"]:
            updates["wifi_rssi"] = net_info["wifi_rssi"]
        if net_info["watch_ip"]:
            updates["watch_ip"] = net_info["watch_ip"]
        if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial):
            updates["last_ip_port"] = serial

        STATE.update(**updates)
        STATE.save_cache()

    def _poll_loop(self) -> None:
        while True:
            self._poll_once()
            time.sleep(POLL_INTERVAL_SEC)

    def _connect_target(self) -> None:
        target = self.ip_var.get().strip()
        if not target:
            return
        STATE.update(last_ip_port=target, last_event=f"Connecting to {target}...")
        STATE.save_cache()

        def worker() -> None:
            _, out = run_adb(["connect", target], timeout=5)
            STATE.update(last_event=out.splitlines()[0] if out else f"Tried {target}")
            self._poll_once()

        threading.Thread(target=worker, daemon=True).start()

    def _manual_poll(self) -> None:
        STATE.update(last_event="Polling watch...")
        threading.Thread(target=self._poll_once, daemon=True).start()

    def _ring_watch(self) -> None:
        def worker() -> None:
            serial = find_watch_serial() or STATE.snapshot().get("serial")
            if not serial:
                STATE.update(last_event="Watch offline — enter IP:Port & Connect")
                return
            run_adb(["-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"])
            run_adb([
                "-s", serial, "shell",
                "cmd", "notification", "post", "-S", "bigtext",
                "-t", "Find My Watch", "ring_watch", "Ping from HP EliteBook",
            ])
            # Also trigger vibrator pulse for 800ms if permitted
            run_adb(["-s", serial, "shell", "cmd", "vibrator", "vibrate", "800", "FindWatch"])
            STATE.update(last_event=f"Rang watch at {datetime.now().strftime('%H:%M:%S')}")

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_pin(self) -> None:
        current = bool(self.root.attributes("-topmost"))
        self.root.attributes("-topmost", not current)
        self.pin_lbl.config(fg=self.GOLD if not current else self.MUTED)

    def _refresh_ui(self) -> None:
        snap = STATE.snapshot()
        if snap["connected"]:
            self.status_lbl.config(text="● ONLINE", fg=self.EMERALD)
        else:
            self.status_lbl.config(text="○ SLEEPING", fg=self.MUTED)

        pct = snap["battery_pct"]
        self.bat_lbl.config(text=f"{pct}%" if pct is not None else "--%")
        self.state_lbl.config(text=snap["battery_status"] or "Cached")
        self.updated_lbl.config(text=f"Updated: {snap['last_seen'] or '--'}")

        # Update battery progress bar width
        bar_w = max(1, self.bar_canvas.winfo_width())
        fill_w = int(bar_w * (pct / 100.0)) if pct is not None else 0
        self.bar_canvas.coords(self.bar_fill, 0, 0, fill_w, 5)

        temp = f"{snap['temp_c']}°C" if snap["temp_c"] is not None else "--°C"
        volt = f"{snap['voltage_v']}V" if snap["voltage_v"] is not None else "--V"
        rssi = snap["wifi_rssi"] or "--"
        self.stats_lbl.config(text=f"Temp: {temp}  ·  Volt: {volt}  ·  Signal: {rssi}")

        ssid = snap["wifi_ssid"] or "Home Wi-Fi"
        ip = snap["watch_ip"] or "192.168.0.11"
        self.loc_lbl.config(text=f"Location: {ssid}  ·  IP: {ip}")

        self.event_lbl.config(text=snap["last_event"])
        self.root.after(1000, self._refresh_ui)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    GlassTelemetryWidget().run()
