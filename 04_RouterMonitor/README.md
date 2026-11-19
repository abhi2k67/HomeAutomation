# Sub-Project 04: Home Wi-Fi Router & LAN Monitor

100% local Windows monitoring suite (zero cloud relays, zero external dependencies — pure Python 3 stdlib + SQLite).

## Components

- `lan_scanner.py` — Concurrent `/24` LAN sweep, `arp -a` parser, reverse DNS, and offline OUI vendor lookup.
- `router_scraper.py` — Gateway HTTP latency check (`192.168.0.1`), UPnP IGD WAN byte counter (`GetTotalBytesReceived` / `GetTotalBytesSent`), and Windows `netstat -e` host NIC fallback.
- `dns_sinkhole.py` — Local UDP DNS sinkhole & domain-level query auditor (`blocklist.txt` + upstream forwarding) without inspecting TLS/HTTPS payloads.
- `dashboard_server.py` — Local web dashboard (`http://127.0.0.1:8040`) combining live LAN clients, bandwidth rates, and DNS query audit logs.
- `db.py` — SQLite persistence (`router_monitor.db`).

## Quick Start

### 1. Run Dashboard + DNS Sinkhole (Test Port 5354, no Admin required)
```powershell
cd D:\DND\HomeAutomation\04_RouterMonitor
py dashboard_server.py --dns-port 5354
```
Open `http://127.0.0.1:8040` in your browser.

### 2. Run DNS Sinkhole on Standard Port 53 (LAN-wide)
Port `53` requires an **Administrator PowerShell**:
```powershell
cd D:\DND\HomeAutomation\04_RouterMonitor
py dashboard_server.py --dns-port 53
```
Then, to audit & sinkhole DNS queries for your LAN devices:
- In your **TP-Link router (`http://192.168.0.1`) > DHCP Settings**, set **Primary DNS** to your EliteBook's LAN IP (`192.168.0.12`) and **Secondary DNS** to `192.168.0.1` (or set it per-device on the Pixel/TV/Watch).
- Allow UDP port `53` inbound on Windows Defender Firewall (Private network) if other LAN devices will query it.
