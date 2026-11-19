"""Local Windows web dashboard for Home Routers, Devices, Websites & Blocking."""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import threading
import time
import urllib.parse
from typing import Any

import db
import dns_sinkhole
import lan_scanner
import router_scraper
import tplink_client

_STATE: dict[str, Any] = {
    "gateway": {"gateway_ip": "192.168.0.1", "reachable": False, "latency_ms": 0.0},
    "upnp_wan": None,
    "host_nic": None,
    "dns_running": False,
    "dns_port": None,
    "last_scan": 0.0,
}

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Home Wi-Fi &amp; Router Dashboard</title>
<style>
  :root {
    --bg: #0b0f14; --panel: #131a22; --border: #222d3a;
    --text: #e6edf3; --muted: #8b949e; --accent: #3fb950;
    --warn: #d29922; --danger: #f85149; --blue: #58a6ff;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: var(--bg); color: var(--text); }
  header { display: flex; justify-content: space-between; align-items: center; padding: 14px 22px; border-bottom: 1px solid var(--border); background: var(--panel); flex-wrap: wrap; gap: 10px; }
  header h1 { font-size: 16px; margin: 0; }
  .badge { font-size: 12px; padding: 3px 9px; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); }
  .badge.ok { color: var(--accent); border-color: rgba(63,185,80,.4); }
  .badge.bad { color: var(--danger); border-color: rgba(248,81,73,.4); }
  .badge.warn { color: var(--warn); border-color: rgba(210,153,34,.5); }
  main { padding: 18px 22px; max-width: 1360px; margin: 0 auto; display: grid; gap: 16px; }
  .alert { background: rgba(210,153,34,.12); border: 1px solid rgba(210,153,34,.5); border-radius: 8px; padding: 10px 14px; font-size: 13px; display: none; justify-content: space-between; align-items: center; gap: 10px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
  .panel-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .panel-head h2 { font-size: 14px; margin: 0; }
  .grid2 { display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; }
  @media (max-width: 980px) { .grid2 { grid-template-columns: 1fr; } }
  button, input, select { background: #0d131a; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 5px 10px; font-size: 12px; }
  button { cursor: pointer; }
  button:hover { border-color: var(--blue); }
  button.danger { border-color: rgba(248,81,73,.5); color: var(--danger); }
  button.ok { border-color: rgba(63,185,80,.5); color: var(--accent); }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot.online { background: var(--accent); }
  .dot.offline { background: var(--muted); }
  .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
  .scroll { max-height: 340px; overflow-y: auto; }
  .router-row { display: grid; grid-template-columns: 1.1fr 1fr 0.9fr 1fr auto; gap: 8px; align-items: center; margin-bottom: 8px; }
  @media (max-width: 800px) { .router-row { grid-template-columns: 1fr 1fr; } }
  .hint { font-size: 12px; color: var(--muted); margin-top: 6px; }
</style>
</head>
<body>
<header>
  <h1>Home Wi-Fi &amp; Router Dashboard <span class="badge" id="gwBadge">Router: ...</span></h1>
  <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
    <span class="badge" id="dnsBadge">Website Log: ...</span>
    <span class="badge" id="bwBadge">Speed: -</span>
    <button onclick="triggerScan()">Scan Wi-Fi Now</button>
  </div>
</header>

<main>
  <div class="alert" id="newAlert">
    <span id="newAlertText"></span>
    <button onclick="document.getElementById('newAlert').style.display='none'">Dismiss</button>
  </div>

  <!-- 1. Connected Devices + Block/Unblock -->
  <section class="panel">
    <div class="panel-head">
      <h2>1. Devices Connected to Wi-Fi (<span id="devCount">0</span>)</h2>
      <span class="badge" id="scanTime">Last scan: -</span>
    </div>
    <div class="scroll">
      <table>
        <thead>
          <tr><th>Status</th><th>Name / Alias</th><th>IP Address</th><th>MAC Address</th><th>Brand</th><th>Actions</th></tr>
        </thead>
        <tbody id="devRows"></tbody>
      </table>
    </div>
  </section>

  <!-- 2. Websites Visited (Per-Device + Live Log) -->
  <section class="grid2">
    <div class="panel">
      <div class="panel-head">
        <h2>2. Websites Visited <span id="selectedDevLabel" style="color:var(--blue)">(All Devices)</span></h2>
        <div style="display:flex; gap:6px;">
          <input id="dnsFilter" placeholder="Search website or IP..." oninput="loadDns()" />
          <button onclick="clearSelectedDevice()">Show All</button>
        </div>
      </div>
      <div class="scroll">
        <table>
          <thead><tr><th>Time</th><th>Device IP</th><th>Website / Domain</th><th>Status</th><th>Block</th></tr></thead>
          <tbody id="dnsRows"></tbody>
        </table>
      </div>
      <div class="hint">Tip: To see websites from phones &amp; TVs (not just this laptop), set your router's DHCP Primary DNS to <b>192.168.0.12</b> and run with <code>--dns-port 53</code> as Administrator.</div>
    </div>

    <!-- 3. Router Credentials & Dual-Router Status -->
    <div class="panel">
      <div class="panel-head">
        <h2>3. Wi-Fi Routers &amp; Credentials</h2>
        <div style="display:flex; gap:6px;">
          <button onclick="saveRouters()">Save</button>
          <button class="ok" onclick="testRouters()">Test Login</button>
        </div>
      </div>
      <div id="routerList"></div>
      <div id="routerTestOut" class="hint">Enter your router admin passwords locally (saved only on this laptop in <code>router_config.json</code>).</div>
    </div>
  </section>
</main>

<script>
let selectedIp = '';
let routersCfg = [];

const fmtTime = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString() : '-';
const fmtBps = (b) => !b || b <= 0 ? '0 Kbps' : (b > 1e6 ? (b/1e6).toFixed(1)+' Mbps' : (b/1e3).toFixed(0)+' Kbps');

async function loadOverview() {
  const r = await fetch('/api/overview');
  const d = await r.json();

  const gw = d.state.gateway || {};
  const gwB = document.getElementById('gwBadge');
  gwB.textContent = `Main Router ${gw.gateway_ip || ''}: ${gw.reachable ? gw.latency_ms + ' ms' : 'offline'}`;
  gwB.className = 'badge ' + (gw.reachable ? 'ok' : 'bad');

  const dnsB = document.getElementById('dnsBadge');
  dnsB.textContent = d.state.dns_running ? `Website Audit :${d.state.dns_port}` : 'Website Audit: off';
  dnsB.className = 'badge ' + (d.state.dns_running ? 'ok' : '');

  const hn = d.state.host_nic;
  if (hn) {
    document.getElementById('bwBadge').textContent = `Laptop ↓ ${fmtBps(hn.rx_bps)} ↑ ${fmtBps(hn.tx_bps)}`;
  }

  const online = d.devices.filter(x => x.status === 'online').length;
  document.getElementById('devCount').textContent = `${online} online / ${d.devices.length} total`;
  document.getElementById('scanTime').textContent = 'Last scan: ' + fmtTime(d.state.last_scan);

  const newDevs = d.devices.filter(x => x.is_new && x.status === 'online');
  const alertBox = document.getElementById('newAlert');
  if (newDevs.length > 0) {
    alertBox.style.display = 'flex';
    document.getElementById('newAlertText').textContent =
      `New device alert: ${newDevs.map(x => x.ip + ' (' + (x.vendor || x.mac) + ')').join(', ')} joined your Wi-Fi!`;
  } else {
    alertBox.style.display = 'none';
  }

  document.getElementById('devRows').innerHTML = d.devices.map(dev => {
    const blocked = !!dev.blocked;
    return `
      <tr>
        <td>
          <span class="dot ${dev.status}"></span>${dev.status}
          ${dev.is_new ? '<span class="badge warn" style="margin-left:4px">NEW</span>' : ''}
          ${blocked ? '<span class="badge bad" style="margin-left:4px">BLOCKED</span>' : ''}
        </td>
        <td><input value="${dev.alias || dev.hostname || ''}" placeholder="Name this device" onchange="setAlias('${dev.mac}', this.value)" style="width:140px" /></td>
        <td class="mono">${dev.ip}</td>
        <td class="mono">${dev.mac}</td>
        <td>${dev.vendor || '-'}</td>
        <td style="display:flex; gap:6px;">
          <button onclick="selectDevice('${dev.ip}', '${(dev.alias || dev.hostname || dev.ip).replace(/'/g, '')}')">Websites</button>
          <button class="${blocked ? 'ok' : 'danger'}" onclick="toggleBlockDevice('${dev.mac}', ${!blocked})">${blocked ? 'Unblock' : 'Block'}</button>
          ${dev.is_new ? `<button onclick="ackNew('${dev.mac}')">OK</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

async function loadDns() {
  const q = encodeURIComponent(selectedIp || document.getElementById('dnsFilter').value || '');
  const r = await fetch(`/api/dns?limit=80&q=${q}`);
  const rows = await r.json();
  document.getElementById('dnsRows').innerHTML = rows.map(x => `
    <tr>
      <td>${fmtTime(x.ts)}</td>
      <td class="mono">${x.client_ip}</td>
      <td class="mono">${x.domain}</td>
      <td style="color:${x.action === 'BLOCKED' ? 'var(--danger)' : 'var(--accent)'}; font-weight:600;">${x.action}</td>
      <td>${x.action === 'BLOCKED'
        ? `<button onclick="blockDomain('${x.domain}', 'remove')">Unblock</button>`
        : `<button onclick="blockDomain('${x.domain}', 'add')">Block</button>`}</td>
    </tr>
  `).join('');
}

async function loadRouters() {
  const r = await fetch('/api/routers');
  const data = await r.json();
  routersCfg = data.routers || [];
  renderRouters();
}

function renderRouters() {
  document.getElementById('routerList').innerHTML = routersCfg.map((rt, idx) => `
    <div class="router-row">
      <input value="${rt.name || ''}" placeholder="Label" onchange="routersCfg[${idx}].name=this.value" />
      <input value="${rt.ip || ''}" placeholder="Router IP" onchange="routersCfg[${idx}].ip=this.value" class="mono" />
      <input value="${rt.username || 'admin'}" placeholder="Username" onchange="routersCfg[${idx}].username=this.value" />
      <input type="password" value="${rt.password || ''}" placeholder="Password" onchange="routersCfg[${idx}].password=this.value" />
      <a href="http://${rt.ip}" target="_blank" style="color:var(--blue); font-size:12px;">Open</a>
    </div>
  `).join('');
}

async function saveRouters() {
  await fetch('/api/routers', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({routers: routersCfg})});
  document.getElementById('routerTestOut').textContent = 'Saved locally to router_config.json.';
}

async function testRouters() {
  await saveRouters();
  document.getElementById('routerTestOut').textContent = 'Testing login...';
  const r = await fetch('/api/routers/test', {method:'POST'});
  const res = await r.json();
  document.getElementById('routerTestOut').innerHTML = res.map(x =>
    `<div><b>${x.name} (${x.ip}):</b> ${x.ok ? '<span style="color:var(--accent)">Login OK</span>' : '<span style="color:var(--danger)">' + x.error + '</span>'}</div>`
  ).join('');
}

function selectDevice(ip, label) {
  selectedIp = ip;
  document.getElementById('selectedDevLabel').textContent = `(${label} - ${ip})`;
  loadDns();
}
function clearSelectedDevice() {
  selectedIp = '';
  document.getElementById('selectedDevLabel').textContent = '(All Devices)';
  loadDns();
}

async function triggerScan() { await fetch('/api/scan', {method:'POST'}); await loadOverview(); }
async function setAlias(mac, alias) {
  await fetch('/api/alias', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mac, alias})});
  await loadOverview();
}
async function toggleBlockDevice(mac, blocked) {
  await fetch('/api/device/block', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mac, blocked})});
  await loadOverview();
}
async function ackNew(mac) {
  await fetch('/api/device/ack', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mac})});
  await loadOverview();
}
async function blockDomain(domain, action) {
  await fetch('/api/blocklist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, domain})});
  await loadDns();
}

loadOverview(); loadDns(); loadRouters();
setInterval(() => { loadOverview(); loadDns(); }, 5000);
</script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, obj: Any, status: int = 200) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            raw = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if parsed.path == "/api/overview":
            self._send_json(
                {
                    "state": _STATE,
                    "devices": db.get_devices(),
                    "dns_summary": db.get_dns_summary(),
                }
            )
            return

        if parsed.path == "/api/dns":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = min(int(qs.get("limit", ["80"])[0]), 500)
            q = qs.get("q", [""])[0]
            action = qs.get("action", [""])[0]
            self._send_json(db.get_recent_dns(limit=limit, filter_text=q, action=action))
            return

        if parsed.path == "/api/routers":
            self._send_json(tplink_client.load_config())
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/scan":
            devices = lan_scanner.scan_lan()
            _STATE["last_scan"] = time.time()
            self._send_json({"count": len(devices)})
            return

        if parsed.path == "/api/alias":
            body = self._read_json()
            db.set_device_alias(body.get("mac", ""), body.get("alias", ""))
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/device/block":
            body = self._read_json()
            db.set_device_blocked(body.get("mac", ""), bool(body.get("blocked", False)))
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/device/ack":
            body = self._read_json()
            db.ack_new_device(body.get("mac", ""))
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/routers":
            body = self._read_json()
            tplink_client.save_config({"routers": body.get("routers", [])})
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/routers/test":
            self._send_json(tplink_client.test_all_routers())
            return

        if parsed.path == "/api/blocklist":
            body = self._read_json()
            act = body.get("action")
            dom = body.get("domain", "")
            if act == "add":
                dns_sinkhole.BLOCKLIST.add_domain(dom)
            elif act == "remove":
                dns_sinkhole.BLOCKLIST.remove_domain(dom)
            self._send_json({"ok": True})
            return

        self.send_error(404)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _lan_poll_loop(interval: int = 30) -> None:
    while True:
        try:
            lan_scanner.scan_lan()
            _STATE["last_scan"] = time.time()
        except Exception:
            pass
        time.sleep(interval)


def _bw_poll_loop(gateway_ip: str, interval: int = 10) -> None:
    while True:
        try:
            res = router_scraper.poll_all(gateway_ip)
            _STATE["gateway"] = res["gateway"]
            _STATE["upnp_wan"] = res["upnp_wan"]
            _STATE["host_nic"] = res["host_nic"]
        except Exception:
            pass
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Wi-Fi & Router Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind IP (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8040, help="Dashboard HTTP port (default 8040)")
    parser.add_argument("--gateway", default="192.168.0.1", help="Main Router IP (default 192.168.0.1)")
    parser.add_argument("--dns-port", type=int, default=5354, help="Local DNS port (53 requires Admin, 5354 default)")
    parser.add_argument("--no-dns", action="store_true", help="Disable embedded DNS sinkhole")
    args = parser.parse_args()

    db.init_db()

    if not args.no_dns:
        try:
            dns_sinkhole.start_dns_server("0.0.0.0", args.dns_port, args.gateway)
            _STATE["dns_running"] = True
            _STATE["dns_port"] = args.dns_port
        except PermissionError:
            print(f"[WARN] Could not bind DNS port {args.dns_port} (try --dns-port 5354 or run as Administrator).")

    threading.Thread(target=_lan_poll_loop, args=(30,), daemon=True).start()
    threading.Thread(target=_bw_poll_loop, args=(args.gateway, 10), daemon=True).start()

    httpd = ThreadedHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port} (DNS sinkhole: {_STATE['dns_running']} on port {_STATE['dns_port']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
