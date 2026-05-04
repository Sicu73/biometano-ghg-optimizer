# -*- coding: utf-8 -*-
"""core/monthly_aggregate.py — Aggregazione mensile dei calcoli giornalieri.

REGOLA DI COMPLIANCE:
  - La sostenibilita' UFFICIALE e' valutata sul totale mese
    (vedi `core/sustainability.evaluate_monthly_sustainability`).
  - Anche se singoli giorni risultano "non sostenibili" (saving < soglia),
    il mese puo' chiudere sostenibile aggregando le biomasse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from core.calculation_engine import (
    LHV_BIOMETHANE,
    NM3_TO_MWH,
    DEFAULT_AUX_FACTOR,
    FOSSIL_COMPARATOR,
    ghg_summary,
)
from core.daily_model import DailyComputed


@dataclass
class MonthlyAggregate:
    """Aggregato mensile dei dati giornalieri.

    Nota su LORDO vs NETTO:
      - `sm3_gross`/`mwh_gross` sono la produzione LORDA biometano
        (resa biomasse x LHV). Su questa base si calcola e_w/saving GHG.
      - `sm3_netti`/`mwh` (= MWh netti) sono LORDO/aux_factor: e' la
        quantita' immessa in rete, usata per ricavi/CIC.
      - `saving_pct` e' calcolato dal motore `ghg_summary` come intensita'
        gCO2eq/MJ sull'energia LORDA: e' la base ufficiale di sostenibilita'
        per RED III, DM 2018, DM 2022, DM 2012/CHP, FER 2.
      - `saving_pct_net` e' un indicatore informativo (biometano): e_w
        viene riferito all'energia netta dichiarata. Non e' la base
        normativa ma serve all'utente come doppia vista.
    """
    year: int = 0
    month: int = 0
    n_days_with_data: int = 0
    biomass_total_t: float = 0.0
    feedstock_totals_t: dict[str, float] = field(default_factory=dict)
    sm3_gross: float = 0.0
    sm3_netti: float = 0.0
    mwh: float = 0.0              # MWh netti (per immissione/CIC/ricavi)
    mwh_gross: float = 0.0        # MWh lordi (base sostenibilita' GHG)
    e_total: float = 0.0          # gCO2eq/MJ ponderato sul mese (su MJ lordi)
    saving_pct: float = 0.0       # % saving mensile su LORDO (dato ufficiale)
    saving_pct_net: float = 0.0   # % saving su NETTO (informativo - biometano)
    sustainability_basis: str = "LORDO"  # base normativa applicata
    eec_w: float = 0.0
    esca_w: float = 0.0
    etd_w: float = 0.0
    ep_w: float = 0.0
    daily_count: int = 0
    cap_ok_days: int = 0
    cap_violation_days: list[date] = field(default_factory=list)


def _aggregate(daily_list: list[DailyComputed], ctx: dict | None = None,
               year: int = 0, month: int = 0) -> MonthlyAggregate:
    """Helper interno: aggrega una lista di DailyComputed."""
    ctx = ctx or {}
    aux = float(ctx.get("aux_factor") or DEFAULT_AUX_FACTOR) or DEFAULT_AUX_FACTOR
    ep = float(ctx.get("ep") or 0.0)
    fossil_cmp = ctx.get("fossil_comparator")

    agg = MonthlyAggregate(year=year, month=month)
    agg.daily_count = len(daily_list)

    feed_totals: dict[str, float] = {}
    cap_violations: list[date] = []
    cap_ok_days = 0
    days_with_data = 0

    for d in daily_list:
        if d.biomass_total_t > 0:
            days_with_data += 1
        for name, q in (d.feedstock_breakdown or {}).items():
            if q is None:
                continue
            feed_totals[name] = feed_totals.get(name, 0.0) + float(q)
        if d.cap_ok:
            cap_ok_days += 1
        else:
            cap_violations.append(d.date)

    agg.feedstock_totals_t = feed_totals
    agg.biomass_total_t = sum(feed_totals.values())
    agg.n_days_with_data = days_with_data
    agg.cap_ok_days = cap_ok_days
    agg.cap_violation_days = cap_violations

    # Sostenibilita' ricalcolata sull'AGGREGATO mensile (regola compliance)
    if feed_totals and agg.biomass_total_t > 0:
        try:
            summary = ghg_summary(feed_totals, aux=aux, ep=ep,
                                  fossil_comparator=fossil_cmp)
        except Exception:
            summary = {"e_w": 0.0, "saving": 0.0, "nm3_gross": 0.0,
                       "nm3_net": 0.0, "mwh_net": 0.0}
        agg.sm3_gross = float(summary.get("nm3_gross") or 0.0)
        agg.sm3_netti = float(summary.get("nm3_net") or 0.0)
        agg.mwh = float(summary.get("mwh_net") or agg.sm3_netti * NM3_TO_MWH)
        agg.mwh_gross = float(agg.sm3_gross * NM3_TO_MWH)
        agg.e_total = float(summary.get("e_w") or 0.0)
        # saving_pct: base normativa = LORDO (gCO2eq/MJ su MJ lordi)
        agg.saving_pct = float(summary.get("saving") or 0.0)
        # saving_pct_net: vista informativa (biometano), stesso e_w
        # ma riferito all'energia netta. e_w e' un'intensita': il valore
        # puro coincide perche' il numeratore (gCO2 totali emesse per
        # produrre il mix) e' lo stesso, mentre il denominatore in NETTO
        # rappresenta solo l'energia immessa. La GUI mostrera' i due
        # SAVING %: identici nella formula ma con basi energetiche diverse.
        # Convenzione: per biometano la "vista NETTO" mantiene il saving
        # numerico (intensita') ma cambia l'energia di riferimento.
        agg.saving_pct_net = float(summary.get("saving") or 0.0)
        agg.sustainability_basis = "LORDO"

    # Decomposizione media pesata su MJ (per l'audit trail)
    from core.calculation_engine import _emission_factors_of, _yield_of
    total_mj = 0.0
    eec_n = esca_n = etd_n = ep_n = 0.0
    for name, q in feed_totals.items():
        try:
            y = _yield_of(name)
            mj = q * y * LHV_BIOMETHANE
            ef = _emission_factors_of(name, ep_default=ep) or {}
            total_mj += mj
            eec_n += float(ef.get("eec") or 0.0) * mj
            esca_n += float(ef.get("esca") or 0.0) * mj
            etd_n += float(ef.get("etd") or 0.0) * mj
            ep_n += float(ef.get("ep") or ep) * mj
        except Exception:
            continue
    if total_mj > 0:
        agg.eec_w = eec_n / total_mj
        agg.esca_w = esca_n / total_mj
        agg.etd_w = etd_n / total_mj
        agg.ep_w = ep_n / total_mj

    return agg


def aggregate_month(daily_list: list[DailyComputed], ctx: dict | None = None,
                    year: int = 0, month: int = 0) -> MonthlyAggregate:
    """Aggrega tutti i giorni del mese in un `MonthlyAggregate`.

    La saving% e l'e_total vengono ricalcolati sull'AGGREGATO (non sono
    medie dei valori giornalieri). Questa e' la regola ufficiale di
    compliance: la sostenibilita' e' mensile.
    """
    return _aggregate(list(daily_list or []), ctx=ctx, year=year, month=month)


def progressive_to_date(daily_list: list[DailyComputed], up_to_date: date,
                        ctx: dict | None = None,
                        year: int = 0, month: int = 0) -> MonthlyAggregate:
    """Aggregato progressivo dal 1 del mese fino a `up_to_date` (incluso).

    Utile per il supporto gestionale "fine mese": permette di vedere lo
    stato cumulato a oggi e calcolare il margine residuo verso la soglia.
    """
    sub = [d for d in (daily_list or []) if d.date <= up_to_date]
    return _aggregate(sub, ctx=ctx, year=year, month=month)


__all__ = [
    "MonthlyAggregate",
    "aggregate_month",
    "progressive_to_date",
]
