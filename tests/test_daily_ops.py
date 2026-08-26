# -*- coding: utf-8 -*-
"""tests/test_daily_ops.py — Test gestione giornaliera + sostenibilita' mensile."""
from __future__ import annotations

import os
import sys
from datetime import date

import pytest

# Garantisce import dei moduli del progetto
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.calendar import (
    days_in_month, generate_month_days, is_leap_year, month_label,
)
from core.daily_model import DailyComputed, DailyEntry, compute_daily
from core.monthly_aggregate import aggregate_month, progressive_to_date
from core.persistence import (
    delete_month, init_db, list_saved_months, load_month, save_month,
)
from core.sustainability import evaluate_monthly_sustainability
from core.validators import validate_daily_entry


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def test_generate_month_days_31():
    days = generate_month_days(2025, 1)
    assert len(days) == 31
    assert days[0] == date(2025, 1, 1)
    assert days[-1] == date(2025, 1, 31)


def test_generate_month_days_february_leap():
    assert is_leap_year(2024) is True
    days = generate_month_days(2024, 2)
    assert len(days) == 29
    assert days[-1] == date(2024, 2, 29)


def test_generate_month_days_february_non_leap():
    assert is_leap_year(2023) is False
    days = generate_month_days(2023, 2)
    assert len(days) == 28
    assert days[-1] == date(2023, 2, 28)


def test_is_leap_year_centuries():
    # 1900 not leap; 2000 leap (gregorian)
    assert is_leap_year(1900) is False
    assert is_leap_year(2000) is True


def test_month_label_it_en():
    assert month_label(2024, 3, "it") == "Marzo 2024"
    assert month_label(2024, 3, "en") == "March 2024"


def test_days_in_month_invalid():
    with pytest.raises(ValueError):
        days_in_month(2024, 13)


# ---------------------------------------------------------------------------
# Aggregate / sustainability
# ---------------------------------------------------------------------------

def _mk_dc(d: date, biomass_t=10.0, sm3=2000.0, mwh=20.0, eec=15.0,
           saving=0.85, breakdown=None):
    return DailyComputed(
        date=d,
        biomass_total_t=biomass_t,
        sm3_gross=sm3 * 1.29,
        sm3_netti=sm3,
        mwh=mwh,
        eec=eec,
        esca=0.0,
        etd=1.0,
        ep=2.0,
        e_total=eec + 1.0 + 2.0,
        daily_saving_estimate=saving * 100.0,
        cap_ok=True,
        feedstock_breakdown=dict(breakdown or {"FeedA": biomass_t}),
    )


def test_aggregate_month_sum_equals_total():
    daily = [
        _mk_dc(date(2025, 1, 1), biomass_t=10.0, breakdown={"A": 6.0, "B": 4.0}),
        _mk_dc(date(2025, 1, 2), biomass_t=5.0,  breakdown={"A": 5.0}),
        _mk_dc(date(2025, 1, 3), biomass_t=8.0,  breakdown={"B": 8.0}),
    ]
    agg = aggregate_month(daily, ctx={"aux_factor": 1.29}, year=2025, month=1)
    assert agg.feedstock_totals_t["A"] == pytest.approx(11.0)
    assert agg.feedstock_totals_t["B"] == pytest.approx(12.0)
    assert agg.biomass_total_t == pytest.approx(23.0)
    assert agg.n_days_with_data == 3


def test_aggregate_month_remi():
    daily = [
        DailyComputed(date=date(2025, 1, 1), biomass_total_t=10.0,
                      remi_vb=1000.0, remi_e=10000.0, remi_qb_max=100.0,
                      hours_per_day=24.0),
        DailyComputed(date=date(2025, 1, 2), biomass_total_t=10.0,
                      remi_vb=2000.0, remi_e=20000.0, remi_qb_max=150.0,
                      hours_per_day=12.0),
    ]
    agg = aggregate_month(daily, year=2025, month=1)
    
    assert agg.remi_vb_total == pytest.approx(3000.0)
    assert agg.remi_e_total == pytest.approx(30000.0)
    assert agg.remi_qb_max_month == pytest.approx(150.0)
    # Total hours = 24 + 12 = 36
    # Portata media = 3000 / 36 = 83.33
    assert agg.remi_portata_media_smch == pytest.approx(3000.0 / 36.0)
    # Potenza media = 30000 / 36 / 1000 = 0.833
    assert agg.remi_potenza_media_mw == pytest.approx(30000.0 / 36.0 / 1000.0)
    # Energia specifica = 30000 / 3000 = 10.0
    assert agg.remi_energia_specifica_kwh_smc == pytest.approx(10.0)


def test_monthly_sustainability_compliant():
    # Mock aggregato gia' calcolato con saving > soglia
    from core.monthly_aggregate import MonthlyAggregate
    agg = MonthlyAggregate(year=2025, month=1, biomass_total_t=100.0,
                           feedstock_totals_t={"FeedX": 100.0},
                           sm3_netti=20000, mwh=200,
                           saving_pct=85.0, e_total=12.0)
    res = evaluate_monthly_sustainability(agg, regime="RED III", threshold=80.0)
    assert res["compliant"] is True
    assert res["saving"] == pytest.approx(85.0)
    assert res["margin"] == pytest.approx(5.0)


def test_monthly_sustainability_non_compliant():
    from core.monthly_aggregate import MonthlyAggregate
    agg = MonthlyAggregate(year=2025, month=1, biomass_total_t=100.0,
                           feedstock_totals_t={"FeedX": 100.0},
                           sm3_netti=20000, mwh=200,
                           saving_pct=70.0, e_total=24.0)
    res = evaluate_monthly_sustainability(agg, regime="RED III", threshold=80.0)
    assert res["compliant"] is False
    assert res["margin"] == pytest.approx(-10.0)


def test_sustainability_isolated_bad_day_but_month_ok():
    """Regola: anche con giorni 'bad', se l'aggregato mese e' OK -> compliant."""
    from core.monthly_aggregate import MonthlyAggregate
    # Simulo un mese il cui totale aggregato (calcolato fuori) supera la soglia
    agg = MonthlyAggregate(
        year=2025, month=2, biomass_total_t=300.0,
        feedstock_totals_t={"Buona": 270.0, "Scarsa": 30.0},
        sm3_netti=60000, mwh=600,
        saving_pct=82.5,  # > 80%
        e_total=14.0,
        cap_violation_days=[],
    )
    res = evaluate_monthly_sustainability(agg, regime="RED III", threshold=80.0)
    assert res["compliant"] is True, (
        "Anche se singoli giorni potrebbero risultare 'non sostenibili', "
        "il totale mese aggregato supera la soglia -> compliant."
    )


def test_progressive_to_date_subset():
    daily = [
        _mk_dc(date(2025, 1, 1), biomass_t=10.0, breakdown={"A": 10.0}),
        _mk_dc(date(2025, 1, 2), biomass_t=5.0,  breakdown={"A": 5.0}),
        _mk_dc(date(2025, 1, 3), biomass_t=8.0,  breakdown={"A": 8.0}),
    ]
    p = progressive_to_date(daily, date(2025, 1, 2), year=2025, month=1)
    assert p.biomass_total_t == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_save_load_roundtrip(tmp_path):
    db = str(tmp_path / "test_metaniq_daily.db")
    init_db(db)
    entries = [
        DailyEntry(date=date(2025, 5, 1),
                   feedstocks={"FeedA": 10.0, "FeedB": 5.0}, notes="ok"),
        DailyEntry(date=date(2025, 5, 2),
                   feedstocks={"FeedA": 12.0}),
    ]
    n = save_month(2025, 5, entries, plant_id="P1",
                   regime="RED III", threshold=0.80, path=db)
    assert n == 3  # 3 record (FeedA+FeedB+FeedA)
    loaded = load_month(2025, 5, plant_id="P1", path=db)
    assert len(loaded) == 2
    by_date = {e.date: e for e in loaded}
    assert by_date[date(2025, 5, 1)].feedstocks == {"FeedA": 10.0, "FeedB": 5.0}
    assert by_date[date(2025, 5, 1)].notes == "ok"
    assert by_date[date(2025, 5, 2)].feedstocks == {"FeedA": 12.0}

    months = list_saved_months("P1", path=db)
    assert (2025, 5) in months

    deleted = delete_month(2025, 5, plant_id="P1", path=db)
    assert deleted == 3
    assert load_month(2025, 5, plant_id="P1", path=db) == []


def test_persistence_empty_days(tmp_path):
    db = str(tmp_path / "empty.db")
    init_db(db)
    entries = [
        DailyEntry(date=date(2025, 6, 1), feedstocks={}),
        DailyEntry(date=date(2025, 6, 2),
                   feedstocks={"FeedA": 0.0, "FeedB": None}),
    ]
    n = save_month(2025, 6, entries, plant_id="P1", path=db)
    assert n == 0
    loaded = load_month(2025, 6, plant_id="P1", path=db)
    assert loaded == []


def test_persistence_remi_only_roundtrip(tmp_path):
    """Un giorno con SOLA lettura REMI (Vb>0) senza biomasse deve sopravvivere
    a salva+ricarica: regressione sul bug per cui load_month iterava solo i
    giorni con feedstock, scartando i giorni REMI-only scritti in daily_hours."""
    db = str(tmp_path / "remi_only.db")
    init_db(db)
    entries = [
        DailyEntry(date=date(2025, 9, 1), feedstocks={"FeedA": 10.0}),
        DailyEntry(date=date(2025, 9, 2), feedstocks={}, remi_vb=1234.0, remi_e=9800.0),
    ]
    save_month(2025, 9, entries, plant_id="P1", path=db)
    loaded = load_month(2025, 9, plant_id="P1", path=db)
    by_date = {e.date: e for e in loaded}
    assert date(2025, 9, 2) in by_date, "il giorno REMI-only non deve sparire"
    assert by_date[date(2025, 9, 2)].remi_vb == 1234.0
    assert by_date[date(2025, 9, 2)].feedstocks == {}


def test_persistence_hours_roundtrip(tmp_path):
    """Le ore di funzionamento vengono salvate e ricaricate correttamente."""
    db = str(tmp_path / "hours.db")
    init_db(db)
    entries = [
        DailyEntry(date=date(2025, 7, 1), feedstocks={"FeedA": 10.0}, hours_per_day=16.5),
        DailyEntry(date=date(2025, 7, 2), feedstocks={"FeedA": 12.0}, hours_per_day=24.0),
        DailyEntry(date=date(2025, 7, 3), feedstocks={"FeedA": 8.0},  hours_per_day=8.0),
    ]
    save_month(2025, 7, entries, plant_id="P1", path=db)
    loaded = load_month(2025, 7, plant_id="P1", path=db)
    by_date = {e.date: e for e in loaded}
    assert by_date[date(2025, 7, 1)].hours_per_day == 16.5
    assert by_date[date(2025, 7, 2)].hours_per_day == 24.0
    assert by_date[date(2025, 7, 3)].hours_per_day == 8.0


def test_persistence_hours_default_when_missing(tmp_path):
    """Giorni senza ore salvate ritornano con default 24.0."""
    db = str(tmp_path / "hours_def.db")
    init_db(db)
    # Salva senza specificare hours_per_day (usa default 24.0)
    entries = [DailyEntry(date=date(2025, 8, 1), feedstocks={"FeedA": 5.0})]
    save_month(2025, 8, entries, plant_id="P1", path=db)
    loaded = load_month(2025, 8, plant_id="P1", path=db)
    assert loaded[0].hours_per_day == 24.0


def test_persistence_hours_clamped(tmp_path):
    """Le ore fuori range [0, 24] sono aggiustate al salvataggio."""
    db = str(tmp_path / "hours_clamp.db")
    init_db(db)
    entries = [
        DailyEntry(date=date(2025, 9, 1), feedstocks={"FeedA": 5.0}, hours_per_day=999.0),
        DailyEntry(date=date(2025, 9, 2), feedstocks={"FeedA": 5.0}, hours_per_day=-1.0),
    ]
    save_month(2025, 9, entries, plant_id="P1", path=db)
    loaded = load_month(2025, 9, plant_id="P1", path=db)
    by_date = {e.date: e for e in loaded}
    assert by_date[date(2025, 9, 1)].hours_per_day == 24.0
    assert by_date[date(2025, 9, 2)].hours_per_day == 0.0


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validator_negative_quantity_rejected():
    ok, errs, warns = validate_daily_entry(
        date(2025, 1, 1),
        {"FeedA": -5.0},
    )
    assert ok is False
    assert any("negativa" in e.lower() for e in errs)


def test_validator_positive_quantity_accepted():
    ok, errs, warns = validate_daily_entry(
        date(2025, 1, 1),
        {"FeedA": 10.0, "FeedB": 0.0},
    )
    assert ok is True
    assert errs == []


def test_validator_unknown_feed_warns():
    ok, errs, warns = validate_daily_entry(
        date(2025, 1, 1),
        {"FeedX": 5.0},
        allowed_feeds=["FeedA", "FeedB"],
    )
    assert ok is True  # warning, non errore
    assert any("FeedX" in w for w in warns)


def test_validator_invalid_date_string():
    ok, errs, warns = validate_daily_entry(
        "non-una-data",
        {"FeedA": 1.0},
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Compute_daily smoke test (no app_mensile -> usa fallback)
# ---------------------------------------------------------------------------

def test_compute_daily_empty():
    e = DailyEntry(date=date(2025, 1, 1), feedstocks={})
    c = compute_daily(e)
    assert c.biomass_total_t == 0.0
    assert c.cap_ok is True


def test_compute_daily_remi_only_no_biomass():
    """Giorno con sola lettura REMI (nessun carico biomassa) deve propagare
    vb/sm3 netti, non scartarli con un early-return (regressione audit)."""
    e = DailyEntry(date=date(2026, 1, 2), feedstocks={},
                   remi_vb=5000.0, remi_e=49000.0)
    c = compute_daily(e, {"plant_net_smch": 300.0})
    assert c.biomass_total_t == 0.0
    assert c.remi_vb == pytest.approx(5000.0)
    assert c.sm3_netti == pytest.approx(5000.0)


def test_aggregate_total_hours_counts_biomass_and_remi_days():
    """total_hours (base del cap autorizzativo) conta i giorni con biomassa O
    lettura REMI, non solo i giorni REMI (regressione audit cap/portata)."""
    daily = [
        DailyComputed(date=date(2026, 1, 1), biomass_total_t=10.0,
                      remi_vb=6000.0, remi_e=58000.0, hours_per_day=24.0),
        DailyComputed(date=date(2026, 1, 2), biomass_total_t=10.0,
                      remi_vb=0.0, remi_e=0.0, hours_per_day=24.0),
    ]
    agg = aggregate_month(daily, year=2026, month=1)
    assert agg.total_hours == pytest.approx(48.0)
