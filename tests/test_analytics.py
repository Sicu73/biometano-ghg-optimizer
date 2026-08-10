# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Contatore visite: conteggio, idempotenza per sessione, degradazione."""
from __future__ import annotations

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


def test_backend_selection_falls_back_to_sqlite(monkeypatch):
    monkeypatch.setattr(analytics, "_secrets_section", lambda name: {})
    monkeypatch.delenv("METANIQ_ANALYTICS_URL", raising=False)
    monkeypatch.delenv("METANIQ_ANALYTICS_KEY", raising=False)
    assert analytics.get_backend().name == "sqlite"
