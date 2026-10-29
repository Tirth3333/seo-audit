"""Tiny SQLite store for audit results (one JSON document per audit)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .models import AuditResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    id TEXT PRIMARY KEY,
    start_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audits_created ON audits(created_at DESC);
"""


class AuditStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def save(self, audit: AuditResult) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audits (id, start_url, domain, status, created_at, data) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (audit.id, audit.start_url, audit.domain, audit.status, audit.created_at, audit.model_dump_json()),
            )
            self._conn.commit()

    def get(self, audit_id: str) -> AuditResult | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM audits WHERE id=?", (audit_id,)).fetchone()
        return AuditResult.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM audits ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for (data,) in rows:
            d = json.loads(data)
            out.append({k: d.get(k) for k in ("id", "start_url", "domain", "status", "created_at",
                                               "finished_at", "data_label", "error")}
                       | {"summary": d.get("summary"), "progress": d.get("progress")})
        return out

    def delete(self, audit_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM audits WHERE id=?", (audit_id,))
            self._conn.commit()
            return cur.rowcount > 0
