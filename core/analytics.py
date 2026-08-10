# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/analytics.py — Contatore visite dell'app.

Perche' esiste: su Streamlit Community Cloud il filesystem e' effimero, il
container viene riciclato dopo un periodo di inattivita' e con lui sparisce
qualunque contatore su file o su SQLite locale. Per avere un numero che
sopravviva serve uno store esterno.

Backend, scelti automaticamente:

  1. Supabase (REST)  se ``st.secrets["analytics"]["supabase_url"]`` e
                      ``["service_key"]`` sono configurati. Persistente,
                      e' quello da usare in produzione. Nessuna dipendenza
                      nuova: usa ``requests``, gia' richiesto da streamlit.
  2. SQLite locale    fallback sempre disponibile (``data/analytics.db``).
                      Utile in sviluppo e in self-hosting; su Cloud si
                      azzera a ogni riciclo del container.

GDPR: si registra una riga per SESSIONE con un identificativo casuale
generato al volo, il timestamp UTC, la lingua UI e la versione app. Nessun
indirizzo IP, nessun user agent, nessun cookie, nessun dato che permetta di
risalire alla persona: e' un conteggio aggregato, non un profilo. Per questo
non richiede banner di consenso.

Ogni errore dello store e' silenzioso: un contatore non deve mai impedire
all'app di funzionare.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.logging_setup import get_logger

_LOG = get_logger(__name__)

_TIMEOUT_S = 2.5          # lo store non deve rallentare il primo render
_TABLE = "visits"


# ============================================================================
# MODELLO
# ============================================================================
@dataclass
class VisitStats:
    """Aggregati del contatore. Tutti i campi sono conteggi, mai identita'."""
    total: int = 0
    last_30d: int = 0
    last_7d: int = 0
    today: int = 0
    first_visit: str | None = None
    last_visit: str | None = None
    backend: str = "none"
    by_lang: dict[str, int] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.backend != "none"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


# ============================================================================
# BACKEND — SQLite locale
# ============================================================================
class SqliteBackend:
    """Fallback locale. Su Streamlit Cloud non sopravvive al riciclo."""

    name = "sqlite"

    def __init__(self, path: str | os.PathLike | None = None):
        if path is None:
            # override utile a test e self-hosting con volume dedicato
            path = os.environ.get("METANIQ_ANALYTICS_DB", "").strip() or None
        if path is None:
            base = Path(__file__).resolve().parent.parent / "data"
            base.mkdir(parents=True, exist_ok=True)
            path = base / "analytics.db"
        self.path = str(path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_TABLE} (
                    visit_id    TEXT PRIMARY KEY,
                    ts          TEXT NOT NULL,
                    lang        TEXT,
                    app_version TEXT
                )
                """
            )
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_visits_ts ON {_TABLE}(ts)")

    def record(self, visit_id: str, ts: str, lang: str, app_version: str) -> bool:
        with self._conn() as c:
            c.execute(
                f"INSERT OR IGNORE INTO {_TABLE} "
                "(visit_id, ts, lang, app_version) VALUES (?, ?, ?, ?)",
                (visit_id, ts, lang, app_version),
            )
        return True

    def stats(self) -> VisitStats:
        now = _utcnow()
        with self._conn() as c:
            total = c.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]

            def since(days: int) -> int:
                cut = _iso(now - timedelta(days=days))
                return c.execute(
                    f"SELECT COUNT(*) FROM {_TABLE} WHERE ts >= ?", (cut,)
                ).fetchone()[0]

            row = c.execute(
                f"SELECT MIN(ts), MAX(ts) FROM {_TABLE}"
            ).fetchone()
            by_lang = {
                r[0] or "?": r[1]
                for r in c.execute(
                    f"SELECT lang, COUNT(*) FROM {_TABLE} GROUP BY lang"
                )
            }
            return VisitStats(
                total=total,
                last_30d=since(30),
                last_7d=since(7),
                today=since(1),
                first_visit=row[0],
                last_visit=row[1],
                backend=self.name,
                by_lang=by_lang,
            )


# ============================================================================
# BACKEND — Supabase (REST)
# ============================================================================
class SupabaseBackend:
    """Store persistente via PostgREST. Vedi docstring del modulo per lo schema."""

    name = "supabase"

    def __init__(self, url: str, service_key: str):
        self.base = url.rstrip("/") + f"/rest/v1/{_TABLE}"
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def record(self, visit_id: str, ts: str, lang: str, app_version: str) -> bool:
        import requests

        resp = requests.post(
            self.base,
            headers={**self.headers, "Prefer": "return=minimal,resolution=ignore-duplicates"},
            json={"visit_id": visit_id, "ts": ts, "lang": lang,
                  "app_version": app_version},
            timeout=_TIMEOUT_S,
        )
        return resp.status_code < 300

    def _count(self, params: dict) -> int:
        import requests

        resp = requests.get(
            self.base,
            headers={**self.headers, "Prefer": "count=exact", "Range": "0-0"},
            params={"select": "visit_id", **params},
            timeout=_TIMEOUT_S,
        )
        # PostgREST risponde con Content-Range: 0-0/<totale>
        rng = resp.headers.get("content-range", "")
        if "/" in rng:
            tail = rng.split("/")[-1]
            if tail.isdigit():
                return int(tail)
        return 0

    def stats(self) -> VisitStats:
        import requests

        now = _utcnow()
        total = self._count({})
        st_ = VisitStats(
            total=total,
            last_30d=self._count({"ts": f"gte.{_iso(now - timedelta(days=30))}"}),
            last_7d=self._count({"ts": f"gte.{_iso(now - timedelta(days=7))}"}),
            today=self._count({"ts": f"gte.{_iso(now - timedelta(days=1))}"}),
            backend=self.name,
        )
        # primo/ultimo accesso: due letture da una riga
        for order, attr in (("ts.asc", "first_visit"), ("ts.desc", "last_visit")):
            r = requests.get(
                self.base, headers=self.headers,
                params={"select": "ts", "order": order, "limit": 1},
                timeout=_TIMEOUT_S,
            )
            rows = r.json() if r.status_code < 300 else []
            if rows:
                setattr(st_, attr, rows[0].get("ts"))
        return st_


# ============================================================================
# SELEZIONE BACKEND
# ============================================================================
def _secrets_section(name: str) -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get(name, {}) or {})
    except Exception:
        return {}


def get_backend():
    """Supabase se configurato, altrimenti SQLite locale, altrimenti None."""
    cfg = _secrets_section("analytics")
    url = str(cfg.get("supabase_url", "") or os.environ.get("METANIQ_ANALYTICS_URL", "")).strip()
    key = str(cfg.get("service_key", "") or os.environ.get("METANIQ_ANALYTICS_KEY", "")).strip()
    if url and key:
        try:
            return SupabaseBackend(url, key)
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("analytics: backend Supabase non inizializzabile: %s", exc)
    try:
        return SqliteBackend()
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("analytics: backend SQLite non inizializzabile: %s", exc)
        return None


# ============================================================================
# API PUBBLICA
# ============================================================================
def _app_version() -> str:
    try:
        from core.version import __version__
        return str(__version__)
    except Exception:
        return "?"


def record_visit(lang: str = "it", backend=None, session_id: str | None = None) -> bool:
    """Registra UNA visita per sessione browser.

    Streamlit riesegue lo script a ogni interazione: senza il guard su
    session_state un singolo utente conterebbe decine di visite. La chiave
    di sessione e' un uuid4 casuale, non derivato da IP o browser.
    """
    if session_id is None:
        try:
            import streamlit as st
            if st.session_state.get("_visit_recorded"):
                return False
            session_id = st.session_state.get("_visit_id") or uuid.uuid4().hex
            st.session_state["_visit_id"] = session_id
            st.session_state["_visit_recorded"] = True
        except Exception:
            session_id = uuid.uuid4().hex

    store = backend if backend is not None else get_backend()
    if store is None:
        return False
    try:
        return bool(store.record(session_id, _iso(_utcnow()), lang, _app_version()))
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("analytics: visita non registrata (%s)", exc)
        return False


def get_stats(backend=None) -> VisitStats:
    """Aggregati per la UI. Non solleva mai: in caso di errore -> backend 'none'."""
    store = backend if backend is not None else get_backend()
    if store is None:
        return VisitStats()
    try:
        return store.stats()
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("analytics: statistiche non disponibili (%s)", exc)
        return VisitStats()


__all__ = [
    "VisitStats",
    "SqliteBackend",
    "SupabaseBackend",
    "get_backend",
    "record_visit",
    "get_stats",
]
