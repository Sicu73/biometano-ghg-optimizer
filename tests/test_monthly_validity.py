# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Validita' mensile nel percorso "dati reali da DB".

`MonthlyAggregate.to_dict()["Validita"]` finisce nella tabella mensile del
report PDF e alimenta `valid_months`, che il PDF stampa come:

    "Validita' mensile: N/12 mesi (tutti conformi) rispetto alle due
     condizioni RED III: saving GHG >= soglia e produzione <= tetto"

Segnalare "OK" per il solo fatto che il mese ha dei dati produce una
dichiarazione di conformita' falsa in un documento destinato all'audit OdC.
La semantica deve essere la stessa del simulatore (app_mensile ~6037):
saving >= soglia E produzione entro il cap autorizzativo.
"""
from __future__ import annotations

import datetime as _dt

from core.daily_model import DailyEntry, compute_daily
from core.monthly_aggregate import aggregate_month

# Coltura dedicata: eec alto -> saving sotto la soglia dell'80%.
FEED_LOW_SAVING = "Trinciato di mais"
# Effluente zootecnico con manure credit -> saving ampiamente sopra soglia.
FEED_HIGH_SAVING = "Liquame suino"

THRESHOLD = 0.80  # RED III rete/calore, impianti nuovi dal 1/1/2026


def _month(feed: str, qty_t: float, ctx: dict) -> object:
    days = [
        compute_daily(
            DailyEntry(
                date=_dt.date(2024, 1, day),
                feedstocks={feed: qty_t},
                hours_per_day=24.0,
                # 6.000 Sm3/giorno = 250 Sm3/h, entro il tetto di 300
                remi_vb=6_000.0,
                remi_pci=9.79,
            ),
            ctx=ctx,
        )
        for day in range(1, 29)
    ]
    return aggregate_month(days, ctx=ctx, year=2024, month=1)


def _ctx(threshold: float | None = THRESHOLD) -> dict:
    ctx = {"aux_factor": 1.29, "ep": 0.0, "fossil_comparator": 80.0,
           "plant_net_smch": 300.0}
    if threshold is not None:
        ctx["ghg_threshold"] = threshold
    return ctx


def test_month_below_threshold_is_not_marked_valid():
    agg = _month(FEED_LOW_SAVING, 90.0, _ctx())
    row = agg.to_dict()
    assert agg.saving_pct < THRESHOLD * 100, (
        f"scenario non valido per il test: saving {agg.saving_pct:.1f}% "
        "gia' sopra soglia"
    )
    assert not str(row["Validità"]).startswith("✅"), (
        f"mese con saving {agg.saving_pct:.1f}% (< {THRESHOLD*100:.0f}%) "
        f"marcato valido: {row['Validità']!r}"
    )
    assert "saving" in str(row["Validità"]).lower(), (
        "il motivo della non validita' deve essere esplicito"
    )


def test_month_above_threshold_is_marked_valid():
    agg = _month(FEED_HIGH_SAVING, 200.0, _ctx())
    row = agg.to_dict()
    assert agg.saving_pct >= THRESHOLD * 100, (
        f"scenario non valido per il test: saving {agg.saving_pct:.1f}%"
    )
    assert str(row["Validità"]).startswith("✅"), (
        f"mese conforme marcato non valido: {row['Validità']!r}"
    )


def test_month_over_authorised_cap_is_not_valid():
    """Seconda condizione: produzione oltre il tetto autorizzativo."""
    ctx = _ctx()
    days = [
        compute_daily(
            DailyEntry(
                date=_dt.date(2024, 1, day),
                feedstocks={FEED_HIGH_SAVING: 200.0},
                hours_per_day=24.0,
                remi_vb=12_000.0,   # 500 Sm3/h > 300 autorizzati
                remi_pci=9.79,
            ),
            ctx=ctx,
        )
        for day in range(1, 29)
    ]
    agg = aggregate_month(days, ctx=ctx, year=2024, month=1)
    label = str(agg.to_dict()["Validità"])
    assert not label.startswith("✅"), label
    assert "tetto" in label.lower()


def test_month_without_data_is_not_valid():
    agg = aggregate_month([], ctx=_ctx(), year=2024, month=1)
    assert not str(agg.to_dict()["Validità"]).startswith("✅")


def test_threshold_absent_keeps_legacy_behaviour():
    """Chiamanti che non passano la soglia non devono cambiare esito."""
    agg = _month(FEED_LOW_SAVING, 90.0, _ctx(threshold=None))
    row = agg.to_dict()
    assert str(row["Validità"]).startswith("✅")
