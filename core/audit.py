# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/audit.py — Audit log immutabile SQLite (Fase 2.5 IMPLEMENTATA).

Append-only log per tracciabilità GDPR/sicurezza/compliance. Silent failure su
errori DB (audit non deve mai bloccare le azioni utente).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "audit.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                payload TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_log(tenant_id, created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at DESC)")


def log(
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Registra evento. Silent failure su errori."""
    # Auto-fill da current_user se non passato
    if user_id is None or tenant_id is None:
        try:
            from core.auth import current_user
            u = current_user()
            if u:
                user_id = user_id or u.id
                tenant_id = tenant_id or u.tenant_id
        except Exception:
            pass
    try:
        _init()
        with _conn() as c:
            c.execute("""
                INSERT INTO audit_log (id, tenant_id, user_id, action, resource_type,
                                       resource_id, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), tenant_id, user_id, action, resource_type,
                  resource_id, json.dumps(payload or {}, default=str)))
    except Exception:
        # Audit non deve mai bloccare. Log su Sentry/stderr ma non ri-raise.
        try:
            from core.logging_setup import get_logger
            get_logger("audit").exception("Audit log failed for action=%s", action)
        except Exception:
            pass


def query(
    tenant_id: str | None = None,
    *,
    user_id: str | None = None,
    action: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Restituisce eventi filtrabili ordinati DESC."""
    _init()
    sql = "SELECT * FROM audit_log WHERE 1=1"
    params: list[Any] = []
    if tenant_id:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    if action:
        sql += " AND action = ?"
        params.append(action)
    if since:
        sql += " AND created_at >= ?"
        params.append(since)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload"] or "{}")
        except Exception:
            pass
        out.append(d)
    return out


def export_user_log(user_id: str) -> bytes:
    """GDPR right of access: esporta tutto il log dell'utente in JSON."""
    rows = query(user_id=user_id, limit=10_000)
    return json.dumps(rows, indent=2, default=str).encode("utf-8")


__all__ = ["log", "query", "export_user_log"]
