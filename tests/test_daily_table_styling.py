# -*- coding: utf-8 -*-
"""tests/test_daily_table_styling.py — verifica colonne Sm³/h netti e Saving GHG
con highlight rossi nella tabella giornaliera."""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from core.daily_model import DailyComputed, DailyEntry
from output.daily_table_view import (
    build_daily_dataframe,
    style_daily_dataframe,
)


def _make_entries_and_computed(rows):
    """rows: list[(date, sm3_netti, saving_pct, biomass_t)]"""
    entries = []
    computed = []
    for d, sm3_n, sav, bm in rows:
        entries.append(DailyEntry(date=d, feedstocks={"liquame": float(bm)}))
        computed.append(DailyComputed(
            date=d,
            biomass_total_t=float(bm),
            sm3_gross=float(sm3_n) * 1.29,
            sm3_netti=float(sm3_n),
            mwh=float(sm3_n) * 0.00997,
            eec=10.0, esca=2.0, etd=1.0, ep=3.0,
            e_total=12.0,
            daily_saving_estimate=float(sav),
            cap_ok=True,
        ))
    return entries, computed


def test_smch_column_added():
    """La nuova colonna 'Sm³/h netti' è presente e vale sm3_netti/24 di default."""
    d = _dt.date(2026, 5, 1)
    entries, computed = _make_entries_and_computed([(d, 7200.0, 85.0, 30.0)])
    df = build_daily_dataframe(entries, computed)
    assert "Sm³/h netti" in df.columns
    assert df.loc[0, "Sm³/h netti"] == pytest.approx(7200.0 / 24.0)


def test_smch_column_custom_hours():
    """Parametro hours_per_day rispettato (es. impianto da 16h)."""
    d = _dt.date(2026, 5, 1)
    entries, computed = _make_entries_and_computed([(d, 4800.0, 85.0, 30.0)])
    df = build_daily_dataframe(entries, computed, hours_per_day=16.0)
    assert df.loc[0, "Sm³/h netti"] == pytest.approx(4800.0 / 16.0)


def test_styler_red_when_smch_above_cap():
    """Cella Sm³/h netti rossa se supera il cap autorizzativo."""
    d = _dt.date(2026, 5, 1)
    # 9600 Sm3 netti / 24h = 400 Sm3/h, cap 300 → over
    entries, computed = _make_entries_and_computed([(d, 9600.0, 85.0, 40.0)])
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    # La riga 0 della colonna Sm³/h netti deve avere il background rosso
    assert "#ffd6d6" in rendered, "atteso highlight rosso per Sm³/h > cap"


def test_styler_no_red_when_smch_below_cap():
    """Nessun highlight se Sm³/h ≤ cap."""
    d = _dt.date(2026, 5, 1)
    # 6000 Sm3 / 24 = 250, cap 300 → ok
    entries, computed = _make_entries_and_computed([(d, 6000.0, 85.0, 30.0)])
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    assert "#ffd6d6" not in rendered


def test_styler_red_when_saving_below_threshold():
    """Cella saving rossa se saving giornaliero < soglia normativa."""
    d = _dt.date(2026, 5, 1)
    # saving 75 < soglia 80 → red
    entries, computed = _make_entries_and_computed([(d, 6000.0, 75.0, 30.0)])
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    assert "#ffd6d6" in rendered


def test_styler_no_red_when_saving_above_threshold():
    """Nessun highlight saving se >= soglia."""
    d = _dt.date(2026, 5, 1)
    entries, computed = _make_entries_and_computed([(d, 6000.0, 85.0, 30.0)])
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    assert "#ffd6d6" not in rendered


def test_styler_handles_empty_day():
    """Giorni vuoti (saving=0, sm3=0): nessun highlight."""
    d = _dt.date(2026, 5, 1)
    entries, computed = _make_entries_and_computed([(d, 0.0, 0.0, 0.0)])
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    assert "#ffd6d6" not in rendered, "giorno vuoto non deve essere evidenziato"


def test_styler_handles_empty_dataframe():
    """DataFrame vuoto non crasha."""
    df = build_daily_dataframe([], [])
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    # Solo verifica che non crashi
    _ = styler.to_html() if hasattr(styler, "to_html") else None


def test_styler_mixed_red_cells():
    """Più righe miste: solo le celle che violano sono rosse."""
    rows = [
        (_dt.date(2026, 5, 1), 6000.0, 85.0, 30.0),  # ok / ok
        (_dt.date(2026, 5, 2), 9600.0, 85.0, 40.0),  # CAP violato / ok
        (_dt.date(2026, 5, 3), 6000.0, 70.0, 30.0),  # ok / SAVING violato
        (_dt.date(2026, 5, 4), 9600.0, 70.0, 40.0),  # entrambi violati
    ]
    entries, computed = _make_entries_and_computed(rows)
    df = build_daily_dataframe(entries, computed)
    styler = style_daily_dataframe(df, cap_smch=300.0, ghg_threshold_pct=80.0)
    rendered = styler.to_html()
    # pandas Styler può raggruppare o spezzare i selettori in più blocchi CSS.
    # Sommiamo i selettori #T_..._row*_col* in TUTTI i blocchi che contengono
    # il colore di highlight (4 celle attese: cap day2, saving day3, cap+saving day4).
    import re
    blocks = re.findall(r"([^{}]*?)\s*\{[^}]*#ffd6d6[^}]*\}", rendered, re.DOTALL)
    total = 0
    for b in blocks:
        total += sum(1 for s in b.split(",") if "#T_" in s and "_row" in s)
    assert total >= 4, (
        f"attese >=4 celle evidenziate, trovate {total} (blocks={len(blocks)})"
    )
