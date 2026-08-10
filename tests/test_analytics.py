# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Contatore visite: conteggio, idempotenza per sessione, degradazione."""
from __future__ import annotations

import os
from datetime import timedelta

import pytest

from core import analytics
from core.analytics import (
    SqliteBackend,
    VisitStats,
    get_stats,
    record_visit,
)


@pytest.fixture
def store(tmp_path):
    return SqliteBackend(tmp_path / "analytics.db")


def test_visit_is_recorded(store):
    assert record_visit(lang="it", backend=store, session_id="s1")
    st = get_stats(backend=store)
    assert st.total == 1
    assert st.today == 1
    assert st.backend == "sqlite"


def test_same_session_counts_once(store):
    for _ in range(5):
        record_visit(lang="it", backend=store, session_id="s1")
    assert get_stats(backend=store).total == 1, (
        "una sessione deve valere una visita: Streamlit rilancia lo script "
        "a ogni interazione"
    )


def test_distinct_sessions_are_counted(store):
    for i in range(4):
        record_visit(lang="it", backend=store, session_id=f"s{i}")
    assert get_stats(backend=store).total == 4


def test_language_breakdown(store):
    record_visit(lang="it", backend=store, session_id="a")
    record_visit(lang="en", backend=store, session_id="b")
    record_visit(lang="en", backend=store, session_id="c")
    st = get_stats(backend=store)
    assert st.by_lang == {"it": 1, "en": 2}


def test_time_windows(store):
    now = analytics._utcnow()
    # righe scritte direttamente per simulare il passato
    old = analytics._iso(now - timedelta(days=45))
    recent = analytics._iso(now - timedelta(days=3))
    store.record("old", old, "it", "test")
    store.record("recent", recent, "it", "test")
    record_visit(lang="it", backend=store, session_id="now")

    st = get_stats(backend=store)
    assert st.total == 3
    assert st.last_30d == 2, "la visita di 45 giorni fa non entra nei 30gg"
    assert st.last_7d == 2
    assert st.today == 1
    assert st.first_visit == old
    assert st.last_visit is not None


def test_no_personal_data_is_stored(store):
    """Il record non deve contenere IP, user agent o altro dato personale."""
    record_visit(lang="it", backend=store, session_id="s1")
    with store._conn() as c:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({analytics._TABLE})")]
    assert set(cols) == {"visit_id", "ts", "lang", "app_version"}, cols
    forbidden = ("ip", "addr", "agent", "email", "user", "cookie", "referer")
    for col in cols:
        assert not any(f in col.lower() for f in forbidden), col


def test_broken_backend_never_raises():
    """Un contatore rotto non deve mai propagare errori nell'app."""

    class Broken:
        name = "broken"

        def record(self, *a, **kw):
            raise RuntimeError("store down")

        def stats(self):
            raise RuntimeError("store down")

    assert record_visit(lang="it", backend=Broken(), session_id="s1") is False
    st = get_stats(backend=Broken())
    assert isinstance(st, VisitStats)
    assert st.backend == "none" and st.total == 0
    assert st.available is False


def test_backend_selection_prefers_supabase(monkeypatch):
    monkeypatch.setattr(
        analytics, "_secrets_section",
        lambda name: {"supabase_url": "https://x.supabase.co", "service_key": "k"},
    )
    assert analytics.get_backend().name == "supabase"


def test_backend_selection_defaults_to_abacus(monkeypatch):
    """Senza configurazione deve partire il contatore remoto, non il file
    locale: su Streamlit Cloud SQLite non sopravvive al riciclo."""
    monkeypatch.setattr(analytics, "_secrets_section", lambda name: {})
    monkeypatch.delenv("METANIQ_ANALYTICS_URL", raising=False)
    monkeypatch.delenv("METANIQ_ANALYTICS_KEY", raising=False)
    # override del guard anti-pytest (vedi get_backend)
    monkeypatch.setenv("METANIQ_ANALYTICS_REMOTE", "1")
    assert analytics.get_backend().name == "abacus"


def test_remote_backend_is_off_under_pytest(monkeypatch):
    """La suite non deve incrementare il contatore condiviso di produzione."""
    monkeypatch.setattr(analytics, "_secrets_section", lambda name: {})
    monkeypatch.delenv("METANIQ_ANALYTICS_REMOTE", raising=False)
    assert os.environ.get("PYTEST_CURRENT_TEST"), "atteso ambiente pytest"
    assert analytics.get_backend().name == "sqlite"


def test_backend_selection_falls_back_to_sqlite_when_remote_disabled(monkeypatch):
    monkeypatch.setattr(
        analytics, "_secrets_section", lambda name: {"disable_remote": "true"}
    )
    assert analytics.get_backend().name == "sqlite"


# ---------------------------------------------------------------------------
# Abacus — nessun test tocca la rete: le risposte HTTP sono simulate
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def abacus(monkeypatch):
    calls: list[str] = []
    state = {"value": 0}

    def fake_get(url, timeout=None, **kw):
        calls.append(url)
        if "/hit/" in url:
            state["value"] += 1
            return _FakeResponse(200, {"value": state["value"]})
        if "/get/" in url:
            if state["value"] == 0:
                return _FakeResponse(404, {"error": "Key not found"})
            return _FakeResponse(200, {"value": state["value"]})
        return _FakeResponse(500)

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(analytics, "_LAST_REMOTE_TOTAL", None)
    return analytics.AbacusBackend(), calls, state


def test_abacus_hit_increments(abacus):
    backend, calls, state = abacus
    assert record_visit(lang="it", backend=backend, session_id="s1")
    assert state["value"] == 1
    assert any("/hit/" in c for c in calls)


def test_abacus_reuses_hit_result_without_second_call(abacus):
    """Il badge non deve costare una seconda HTTP: `hit` torna gia' il totale."""
    backend, calls, _ = abacus
    record_visit(lang="it", backend=backend, session_id="s1")
    calls.clear()
    st = get_stats(backend=backend)
    assert st.total == 1
    assert st.backend == "abacus"
    assert calls == [], f"chiamate HTTP superflue: {calls}"


def test_abacus_reads_without_incrementing(abacus):
    backend, calls, state = abacus
    record_visit(lang="it", backend=backend, session_id="s1")
    monkeypatch_total = 1
    assert state["value"] == monkeypatch_total
    # forza la lettura remota
    import core.analytics as an
    an._LAST_REMOTE_TOTAL = None
    st = get_stats(backend=backend)
    assert st.total == 1
    assert state["value"] == 1, "get non deve incrementare il contatore"


def test_abacus_unknown_key_is_zero_not_error(abacus):
    backend, _, _ = abacus
    st = get_stats(backend=backend)
    assert st.total == 0
    assert st.backend == "abacus"


def test_abacus_exposes_only_total(abacus):
    """Niente finestre temporali inventate: il servizio non le fornisce."""
    backend, _, _ = abacus
    record_visit(lang="it", backend=backend, session_id="s1")
    st = get_stats(backend=backend)
    assert st.total == 1
    assert st.last_30d == 0 and st.last_7d == 0 and st.today == 0
    assert st.by_lang == {}
