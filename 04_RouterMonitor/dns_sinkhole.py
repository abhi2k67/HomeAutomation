"""Pure-Python local UDP DNS sinkhole & domain-level query auditor."""

from __future__ import annotations

import argparse
import socket
import socketserver
import struct
import threading
import time
from pathlib import Path

import db

BLOCKLIST_PATH = Path(__file__).resolve().parent / "blocklist.txt"

QTYPE_NAMES = {
    1: "A",
    2: "NS",
    5: "CNAME",
    6: "SOA",
    12: "PTR",
    15: "MX",
    16: "TXT",
    28: "AAAA",
    33: "SRV",
    65: "HTTPS",
    255: "ANY",
}


class BlocklistManager:
    def __init__(self, path: Path = BLOCKLIST_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._domains: set[str] = set()
        self._mtime: float = 0.0
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self._domains = set()
            return
        mtime = self.path.stat().st_mtime
        if mtime == self._mtime:
            return
        with self._lock:
            domains: set[str] = set()
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip().lower()
                if not line or line.startswith("#"):
                    continue
                domains.add(line.rstrip("."))
            self._domains = domains
            self._mtime = mtime

    def is_blocked(self, domain: str) -> bool:
        self.reload()
        d = domain.lower().rstrip(".")
        parts = d.split(".")
        with self._lock:
            for i in range(len(parts)):
                candidate = ".".join(parts[i:])
                if candidate in self._domains:
                    return True
        return False

    def list_domains(self) -> list[str]:
        self.reload()
        with self._lock:
            return sorted(self._domains)

    def add_domain(self, domain: str) -> None:
        d = domain.strip().lower().rstrip(".")
        if not d:
            return
        with self._lock:
            if d not in self._domains:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(f"\n{d}")
                self._mtime = 0.0
        self.reload()

    def remove_domain(self, domain: str) -> None:
        d = domain.strip().lower().rstrip(".")
        if not self.path.exists():
            return
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            kept = [ln for ln in lines if ln.strip().lower().rstrip(".") != d]
            self.path.write_text("\n".join(kept) + "\n", encoding="utf-8")
            self._mtime = 0.0
        self.reload()


BLOCKLIST = BlocklistManager()


def parse_dns_question(packet: bytes) -> tuple[int, str, int, int]:
    """Return (tx_id, qname, qtype, question_end_offset)."""
    if len(packet) < 12:
        raise ValueError("DNS packet too short")
    tx_id = struct.unpack("!H", packet[:2])[0]
    offset = 12
    labels: list[str] = []
    while offset < len(packet):
        length = packet[offset]
        offset += 1
        if length == 0:
            break
        if (length & 0xC0) == 0xC0:
            offset += 1
            break
        labels.append(packet[offset : offset + length].decode("utf-8", errors="replace"))
        offset += length
    if offset + 4 > len(packet):
        raise ValueError("Truncated DNS question")
    qtype, _qclass = struct.unpack("!HH", packet[offset : offset + 4])
    offset += 4
    return tx_id, ".".join(labels), qtype, offset


def build_sinkhole_response(query: bytes, tx_id: int, qtype: int, q_end: int) -> bytes:
    """Build a valid DNS response returning 0.0.0.0 (A), :: (AAAA), or NXDOMAIN."""
    rd = query[2] & 0x01
    if qtype in (1, 28):
        flags = 0x8180 | (rd << 8)  # Standard response, no error
        ancount = 1
        header = struct.pack("!HHHHHH", tx_id, flags, 1, ancount, 0, 0)
        question = query[12:q_end]
        if qtype == 1:
            rdata = b"\x00\x00\x00\x00"
            answer = struct.pack("!HHHIH", 0xC00C, 1, 1, 60, 4) + rdata
        else:
            rdata = b"\x00" * 16
            answer = struct.pack("!HHHIH", 0xC00C, 28, 1, 60, 16) + rdata
        return header + question + answer

    # NXDOMAIN for other record types
    flags = 0x8183 | (rd << 8)
    header = struct.pack("!HHHHHH", tx_id, flags, 1, 0, 0, 0)
    return header + query[12:q_end]


class DNSHandler(socketserver.BaseRequestHandler):
    upstream_ip: str = "192.168.0.1"
    upstream_port: int = 53

    def handle(self) -> None:
        data, sock = self.request
        client_ip = self.client_address[0]
        t0 = time.perf_counter()

        try:
            tx_id, domain, qtype, q_end = parse_dns_question(data)
        except ValueError:
            return

        qtype_name = QTYPE_NAMES.get(qtype, str(qtype))

        if domain and (db.is_ip_blocked(client_ip) or BLOCKLIST.is_blocked(domain)):
            resp = build_sinkhole_response(data, tx_id, qtype, q_end)
            sock.sendto(resp, self.client_address)
            ms = (time.perf_counter() - t0) * 1000.0
            db.log_dns_query(client_ip, domain, qtype_name, "BLOCKED", ms)
            return

        # Forward to upstream DNS
        up_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up_sock.settimeout(2.5)
        try:
            up_sock.sendto(data, (self.upstream_ip, self.upstream_port))
            resp, _ = up_sock.recvfrom(4096)
            sock.sendto(resp, self.client_address)
            ms = (time.perf_counter() - t0) * 1000.0
            if domain:
                db.log_dns_query(client_ip, domain, qtype_name, "ALLOWED", ms)
        except OSError:
            pass
        finally:
            up_sock.close()


class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_dns_server(host: str = "0.0.0.0", port: int = 53, upstream: str = "192.168.0.1") -> ThreadedUDPServer:
    DNSHandler.upstream_ip = upstream
    server = ThreadedUDPServer((host, port), DNSHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Local DNS Sinkhole & Query Auditor")
    parser.add_argument("--host", default="0.0.0.0", help="Bind IP (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=53, help="UDP port (default 53; use 5354 for unprivileged test)")
    parser.add_argument("--upstream", default="192.168.0.1", help="Upstream DNS IP (default 192.168.0.1)")
    args = parser.parse_args()

    db.init_db()
    try:
        srv = start_dns_server(args.host, args.port, args.upstream)
    except PermissionError:
        print(f"Permission denied binding {args.host}:{args.port}. Run PowerShell as Administrator for port 53, or pass --port 5354.")
        raise SystemExit(1)

    print(f"DNS Sinkhole listening on {args.host}:{args.port} -> upstream {args.upstream}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
