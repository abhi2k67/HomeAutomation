"""SQLite persistence layer for Home Router & LAN Monitor."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "router_monitor.db"
_LOCK = threading.Lock()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK, get_conn() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS devices (
                mac TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                hostname TEXT DEFAULT '',
                vendor TEXT DEFAULT '',
                alias TEXT DEFAULT '',
                status TEXT DEFAULT 'online',
                blocked INTEGER DEFAULT 0,
                is_new INTEGER DEFAULT 1,
                router_ip TEXT DEFAULT '',
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dns_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                client_ip TEXT NOT NULL,
                domain TEXT NOT NULL,
                qtype TEXT NOT NULL,
                action TEXT NOT NULL,
                latency_ms REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_dns_ts ON dns_queries(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_dns_domain ON dns_queries(domain);

            CREATE TABLE IF NOT EXISTS bandwidth_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                source TEXT NOT NULL,
                rx_bytes INTEGER NOT NULL,
                tx_bytes INTEGER NOT NULL,
                rx_bps REAL DEFAULT 0.0,
                tx_bps REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_bw_ts ON bandwidth_samples(ts DESC);
            """
        )
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)").fetchall()}
        if "blocked" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN blocked INTEGER DEFAULT 0")
        if "is_new" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN is_new INTEGER DEFAULT 0")
        if "router_ip" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN router_ip TEXT DEFAULT ''")


def upsert_devices(found: list[dict[str, str]]) -> None:
    """Update seen devices and mark unseen ones offline."""
    now = time.time()
    seen_macs: set[str] = set()
    with _LOCK, get_conn() as conn:
        for d in found:
            mac = d["mac"].upper()
            seen_macs.add(mac)
            conn.execute(
                """
                INSERT INTO devices (mac, ip, hostname, vendor, status, first_seen, last_seen)
                VALUES (?, ?, ?, ?, 'online', ?, ?)
                ON CONFLICT(mac) DO UPDATE SET
                    ip = excluded.ip,
                    hostname = CASE WHEN excluded.hostname != '' THEN excluded.hostname ELSE devices.hostname END,
                    vendor = CASE WHEN excluded.vendor != '' THEN excluded.vendor ELSE devices.vendor END,
                    status = 'online',
                    last_seen = excluded.last_seen
                """,
                (mac, d["ip"], d.get("hostname", ""), d.get("vendor", ""), now, now),
            )

        if seen_macs:
            placeholders = ",".join("?" for _ in seen_macs)
            conn.execute(
                f"UPDATE devices SET status = 'offline' WHERE mac NOT IN ({placeholders})",
                tuple(seen_macs),
            )


def set_device_alias(mac: str, alias: str) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute("UPDATE devices SET alias = ?, is_new = 0 WHERE mac = ?", (alias.strip(), mac.upper()))


def set_device_blocked(mac: str, blocked: bool) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute("UPDATE devices SET blocked = ?, is_new = 0 WHERE mac = ?", (1 if blocked else 0, mac.upper()))


def ack_new_device(mac: str) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute("UPDATE devices SET is_new = 0 WHERE mac = ?", (mac.upper(),))


def is_ip_blocked(ip: str) -> bool:
    with _LOCK, get_conn() as conn:
        row = conn.execute("SELECT blocked FROM devices WHERE ip = ? LIMIT 1", (ip,)).fetchone()
    return bool(row and row["blocked"])


def get_device_domains(ip: str, limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK, get_conn() as conn:
        rows = conn.execute(
            "SELECT domain, COUNT(*) AS hits, MAX(ts) AS last_ts, "
            "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_hits "
            "FROM dns_queries WHERE client_ip = ? "
            "GROUP BY domain ORDER BY last_ts DESC LIMIT ?",
            (ip, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_devices() -> list[dict[str, Any]]:
    with _LOCK, get_conn() as conn:
        rows = conn.execute(
            "SELECT mac, ip, hostname, vendor, alias, status, blocked, is_new, router_ip, first_seen, last_seen "
            "FROM devices ORDER BY status DESC, is_new DESC, ip ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def log_dns_query(
    client_ip: str, domain: str, qtype: str, action: str, latency_ms: float
) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute(
            "INSERT INTO dns_queries (ts, client_ip, domain, qtype, action, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), client_ip, domain.lower().rstrip("."), qtype, action, round(latency_ms, 2)),
        )


def get_recent_dns(limit: int = 100, filter_text: str = "", action: str = "") -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filter_text:
        clauses.append("(domain LIKE ? OR client_ip LIKE ?)")
        like = f"%{filter_text.lower()}%"
        params.extend([like, like])
    if action in ("ALLOWED", "BLOCKED"):
        clauses.append("action = ?")
        params.append(action)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT id, ts, client_ip, domain, qtype, action, latency_ms "
        f"FROM dns_queries {where} ORDER BY id DESC LIMIT ?"
    )
    params.append(limit)
    with _LOCK, get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_dns_summary() -> dict[str, Any]:
    since = time.time() - 86400
    with _LOCK, get_conn() as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked "
            "FROM dns_queries WHERE ts >= ?",
            (since,),
        ).fetchone()
        top_domains = conn.execute(
            "SELECT domain, COUNT(*) AS hits, "
            "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_hits "
            "FROM dns_queries WHERE ts >= ? GROUP BY domain ORDER BY hits DESC LIMIT 10",
            (since,),
        ).fetchall()
        top_clients = conn.execute(
            "SELECT client_ip, COUNT(*) AS hits FROM dns_queries WHERE ts >= ? "
            "GROUP BY client_ip ORDER BY hits DESC LIMIT 10",
            (since,),
        ).fetchall()
    return {
        "total_24h": totals["total"] or 0,
        "blocked_24h": totals["blocked"] or 0,
        "top_domains": [dict(r) for r in top_domains],
        "top_clients": [dict(r) for r in top_clients],
    }


def record_bandwidth(source: str, rx_bytes: int, tx_bytes: int) -> dict[str, Any]:
    now = time.time()
    with _LOCK, get_conn() as conn:
        prev = conn.execute(
            "SELECT ts, rx_bytes, tx_bytes FROM bandwidth_samples "
            "WHERE source = ? ORDER BY id DESC LIMIT 1",
            (source,),
        ).fetchone()
        rx_bps = 0.0
        tx_bps = 0.0
        if prev and now > prev["ts"] and rx_bytes >= prev["rx_bytes"] and tx_bytes >= prev["tx_bytes"]:
            dt = now - prev["ts"]
            rx_bps = ((rx_bytes - prev["rx_bytes"]) * 8.0) / dt
            tx_bps = ((tx_bytes - prev["tx_bytes"]) * 8.0) / dt

        conn.execute(
            "INSERT INTO bandwidth_samples (ts, source, rx_bytes, tx_bytes, rx_bps, tx_bps) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (now, source, rx_bytes, tx_bytes, round(rx_bps, 1), round(tx_bps, 1)),
        )
    return {
        "ts": now,
        "source": source,
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes,
        "rx_bps": round(rx_bps, 1),
        "tx_bps": round(tx_bps, 1),
    }


def get_bandwidth_history(limit: int = 60) -> list[dict[str, Any]]:
    with _LOCK, get_conn() as conn:
        rows = conn.execute(
            "SELECT ts, source, rx_bytes, tx_bytes, rx_bps, tx_bps "
            "FROM bandwidth_samples ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]
