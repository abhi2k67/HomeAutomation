"""Local LAN client discovery using concurrent ARP sweep + reverse DNS."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import re
import socket
import subprocess
from typing import Any

import db

# Common home-LAN OUI prefixes (XX-XX-XX) for instant offline vendor identification
OUI_VENDORS: dict[str, str] = {
    "98-03-8E": "TP-Link",
    "50-C7-BF": "TP-Link",
    "B0-BE-76": "TP-Link",
    "C0-06-C3": "TP-Link",
    "E8-48-B8": "TP-Link",
    "B8-DE-5E": "Xiaomi / Redmi",
    "64-CC-2E": "Xiaomi",
    "78-11-DC": "Xiaomi",
    "28-6C-07": "Xiaomi",
    "F4-F5-D8": "Google",
    "54-60-09": "Google",
    "D8-6C-63": "Google",
    "A4-77-33": "Google",
    "DC-A6-32": "Raspberry Pi",
    "B8-27-EB": "Raspberry Pi",
    "E4-5F-01": "Raspberry Pi",
    "24-0A-C4": "Espressif (ESP32)",
    "30-AE-A4": "Espressif (ESP32)",
    "CC-50-E3": "Espressif (ESP32)",
    "00-1A-79": "HP / Intel",
    "3C-52-82": "HP",
    "F0-18-98": "Apple",
    "A4-83-E7": "Apple",
    "3C-22-FB": "Apple",
    "8C-85-90": "Apple",
    "BC-14-85": "Samsung",
    "CC-07-AB": "Samsung",
}


def lookup_vendor(mac: str) -> str:
    norm = mac.upper().replace(":", "-")
    prefix = norm[:8]
    if prefix in OUI_VENDORS:
        return OUI_VENDORS[prefix]
    # Locally administered (randomized) MAC check: 2nd hex nibble in {2, 6, A, E}
    if len(norm) >= 2 and norm[1] in ("2", "6", "A", "E"):
        return "Randomized MAC"
    return ""


def get_local_ipv4_and_prefix() -> tuple[str, ipaddress.IPv4Network]:
    """Detect the primary LAN IPv4 address and /24 network."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.168.0.1", 80))
        local_ip = sock.getsockname()[0]
    except OSError:
        local_ip = "127.0.0.1"
    finally:
        sock.close()

    net = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
    return local_ip, net


def _probe_ip(ip: str) -> None:
    """Send a lightweight UDP packet to trigger ARP resolution on the LAN."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.15)
    try:
        s.sendto(b"\x00", (ip, 9))
    except OSError:
        pass
    finally:
        s.close()


def _resolve_hostname(ip: str) -> str:
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(0.4)
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except OSError:
        return ""
    finally:
        socket.setdefaulttimeout(old_timeout)


def parse_arp_table(subnet: ipaddress.IPv4Network) -> list[dict[str, str]]:
    """Read Windows ARP table filtered to the target IPv4 subnet."""
    out = subprocess.check_output(["arp", "-a"], text=True, errors="ignore")
    pattern = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)", re.MULTILINE)
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for ip_str, mac_str, arp_type in pattern.findall(out):
        if arp_type.lower() == "static" and mac_str.lower() == "ff-ff-ff-ff-ff-ff":
            continue
        ip_obj = ipaddress.IPv4Address(ip_str)
        if ip_obj not in subnet or ip_obj == subnet.broadcast_address:
            continue
        mac_norm = mac_str.upper().replace(":", "-")
        if mac_norm in seen:
            continue
        seen.add(mac_norm)
        results.append({"ip": ip_str, "mac": mac_norm})
    return results


def scan_lan() -> list[dict[str, Any]]:
    """Sweep the /24 LAN, parse ARP, resolve hostnames, and update SQLite."""
    local_ip, subnet = get_local_ipv4_and_prefix()
    hosts = [str(ip) for ip in subnet.hosts() if str(ip) != local_ip]

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        pool.map(_probe_ip, hosts)

    entries = parse_arp_table(subnet)

    def enrich(entry: dict[str, str]) -> dict[str, str]:
        entry["hostname"] = _resolve_hostname(entry["ip"])
        entry["vendor"] = lookup_vendor(entry["mac"])
        return entry

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        enriched = list(pool.map(enrich, entries))

    db.upsert_devices(enriched)
    return db.get_devices()


if __name__ == "__main__":
    db.init_db()
    devices = scan_lan()
    for d in devices:
        print(f"{d['ip']:15s} {d['mac']:17s} {d['status']:7s} {d['vendor']:18s} {d['hostname']}")
