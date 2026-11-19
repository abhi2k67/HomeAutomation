"""Router & WAN/Host bandwidth telemetry via UPnP IGD and Windows netstat fallback."""

from __future__ import annotations

import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

import db


def _ssdp_discover_igd(timeout: float = 1.5) -> str | None:
    """Discover UPnP InternetGatewayDevice description XML URL on the LAN."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 1\r\n"
        "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n"
    ).encode("ascii")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    try:
        sock.sendto(msg, ("239.255.255.250", 1900))
        while True:
            data, _ = sock.recvfrom(4096)
            text = data.decode("utf-8", errors="ignore")
            m = re.search(r"(?im)^LOCATION:\s*(.+)$", text)
            if m:
                return m.group(1).strip()
    except OSError:
        return None
    finally:
        sock.close()


def _find_upnp_service_url(desc_url: str, service_type_prefix: str) -> tuple[str, str] | None:
    try:
        with urllib.request.urlopen(desc_url, timeout=2.0) as resp:
            xml_bytes = resp.read()
    except OSError:
        return None

    root = ET.fromstring(xml_bytes)
    parsed = urllib.parse.urlparse(desc_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for svc in root.iter():
        if svc.tag.endswith("service"):
            stype = ""
            ctrl = ""
            for child in svc:
                if child.tag.endswith("serviceType") and child.text:
                    stype = child.text.strip()
                elif child.tag.endswith("controlURL") and child.text:
                    ctrl = child.text.strip()
            if stype.startswith(service_type_prefix) and ctrl:
                return urllib.parse.urljoin(base, ctrl), stype
    return None


def _soap_call(control_url: str, service_type: str, action: str) -> dict[str, str]:
    body = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        f'<u:{action} xmlns:u="{service_type}"/>'
        "</s:Body></s:Envelope>"
    ).encode("utf-8")

    req = urllib.request.Request(
        control_url,
        data=body,
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service_type}#{action}"',
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    out: dict[str, str] = {}
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if elem.text and elem.text.strip():
            out[tag] = elem.text.strip()
    return out


def poll_upnp_wan() -> dict[str, Any] | None:
    """Query WAN RX/TX bytes from router via UPnP IGD if enabled."""
    desc_url = _ssdp_discover_igd()
    if not desc_url:
        return None
    svc = _find_upnp_service_url(desc_url, "urn:schemas-upnp-org:service:WANCommonInterfaceConfig")
    if not svc:
        return None
    ctrl_url, stype = svc
    try:
        rx = int(_soap_call(ctrl_url, stype, "GetTotalBytesReceived").get("NewTotalBytesReceived", 0))
        tx = int(_soap_call(ctrl_url, stype, "GetTotalBytesSent").get("NewTotalBytesSent", 0))
        sample = db.record_bandwidth("router_upnp", rx, tx)
        sample["upnp_url"] = desc_url
        return sample
    except (OSError, ValueError, ET.ParseError):
        return None


def poll_host_netstat() -> dict[str, Any]:
    """Read local Windows interface RX/TX bytes via `netstat -e`."""
    out = subprocess.check_output(["netstat", "-e"], text=True, errors="ignore")
    for line in out.splitlines():
        if line.strip().lower().startswith("bytes"):
            parts = line.split()
            if len(parts) >= 3:
                rx = int(parts[1])
                tx = int(parts[2])
                return db.record_bandwidth("host_nic", rx, tx)
    return db.record_bandwidth("host_nic", 0, 0)


def check_gateway_http(gateway_ip: str = "192.168.0.1") -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"http://{gateway_ip}", timeout=2.0) as resp:
            ms = round((time.perf_counter() - t0) * 1000.0, 1)
            return {"gateway_ip": gateway_ip, "reachable": True, "http_status": resp.status, "latency_ms": ms}
    except urllib.error.URLError as exc:
        return {"gateway_ip": gateway_ip, "reachable": False, "error": str(exc.reason), "latency_ms": 0.0}


def poll_all(gateway_ip: str = "192.168.0.1") -> dict[str, Any]:
    upnp = poll_upnp_wan()
    host = poll_host_netstat()
    gw = check_gateway_http(gateway_ip)
    return {"gateway": gw, "upnp_wan": upnp, "host_nic": host}


if __name__ == "__main__":
    db.init_db()
    print(poll_all())
