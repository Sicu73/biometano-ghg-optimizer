# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/sustainability.py — Verifica sostenibilita' MENSILE.

REGOLA FONDAMENTALE:
  La sostenibilita' e' MENSILE, NON giornaliera.
  Si applica al totale mese, anche se singoli giorni risultano sotto soglia.

La funzione principale `evaluate_monthly_sustainability` ritorna un dict
con esito booleano, saving, soglia, margine e elenco vincoli specifici
del regime attivo.
"""
from __future__ import annotations

from typing import Any

from core.monthly_aggregate import MonthlyAggregate


def _normalize_threshold(threshold: float | None, default: float = 80.0) -> float:
    """Converte una soglia in punti percentuali (es. 0.80 -> 80.0)."""
    if threshold is None:
        return default
    t = float(threshold)
    if 0 < t <= 1.0:
        return t * 100.0
    return t


def evaluate_monthly_sustainability(
    monthly_agg: MonthlyAggregate,
    regime: str = "RED III",
    threshold: float | None = 80.0,
    regime_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Valuta la sostenibilita' del mese aggregato.

    Args:
        monthly_agg:        aggregato mese da `aggregate_month`.
        regime:             etichetta regime ("RED III", "DM 2018", "FER2", "FER X")
        threshold:          soglia saving GHG (% o frazione 0..1).
        regime_constraints: dict con vincoli specifici, es:
            {
              "fer2_byproduct_min_share": 0.80,      # FER2 80% sottoprodotti
              "dedicated_crops_max_share": 0.30,     # cap colture dedicate
              "annex_ix_min_share": 0.70,            # Annex IX (CIC avanzato)
              "max_sm3h_authorized": 300,            # cap autorizzativo (Sm3/h)
              "max_mwh_year": 0,                     # cap MWh/anno (informativo)
              "feed_categories": {feed_name: cat},   # mappa categoria
              "annex_ix_feeds": [feed_name, ...],    # elenco feed Annex IX
              "byproduct_feeds": [feed_name, ...],   # elenco sottoprodotti
              "dedicated_feeds": [feed_name, ...],   # colture dedicate
            }

    Returns:
        {
          "compliant": bool,
          "saving": float,            # % saving mensile
          "threshold": float,         # % soglia
          "margin": float,            # punti % vs soglia (positivo = OK)
          "constraints_status": [
              {"name": str, "ok": bool, "value": float, "limit": float, "msg": str},
              ...
          ],
          "regime": str,
        }
    """
    rc = regime_constraints or {}
    th = _normalize_threshold(threshold, default=80.0)
    saving = float(getattr(monthly_agg, "saving_pct", 0.0))
    margin = saving - th

    # Vincolo principale: saving GHG mese >= soglia
    constraints_status: list[dict[str, Any]] = []
    constraints_status.append({
        "name": "Soglia saving GHG mensile",
        "ok": saving >= th,
        "value": saving,
        "limit": th,
        "msg": (
            f"Saving mensile {saving:.2f}% "
            f"({'>=' if saving >= th else '<'} soglia {th:.2f}%)"
        ),
    })

    feed_totals = getattr(monthly_agg, "feedstock_totals_t", {}) or {}
    total_t = sum(feed_totals.values()) if feed_totals else 0.0

    # Helper share calc
    def _share_in(names: list[str]) -> float:
        if total_t <= 0 or not names:
            return 0.0
        s = sum(feed_totals.get(n, 0.0) for n in names)
        return s / total_t

    # Vincolo: cap colture dedicate (es. 30% RED III su biomasse)
    dedicated = rc.get("dedicated_feeds") or []
    cap_dedicated = rc.get("dedicated_crops_max_share")
    if cap_dedicated is not None and dedicated:
        share = _share_in(dedicated)
        ok = share <= float(cap_dedicated) + 1e-9
        constraints_status.append({
            "name": "Cap colture dedicate",
            "ok": ok,
            "value": share * 100.0,
            "limit": float(cap_dedicated) * 100.0,
            "msg": (
                f"Quota colture dedicate {share*100:.2f}% "
                f"({'<=' if ok else '>'} cap {float(cap_dedicated)*100:.2f}%)"
            ),
        })

    # Vincolo FER2: quota minima sottoprodotti/effluenti (default 80%)
    byproducts = rc.get("byproduct_feeds") or []
    min_byproduct = rc.get("fer2_byproduct_min_share")
    if min_byproduct is not None and byproducts:
        share = _share_in(byproducts)
        ok = share >= float(min_byproduct) - 1e-9
        constraints_status.append({
            "name": "FER2 - quota sottoprodotti/effluenti",
            "ok": ok,
            "value": share * 100.0,
            "limit": float(min_byproduct) * 100.0,
            "msg": (
                f"Quota sottoprodotti {share*100:.2f}% "
                f"({'>=' if ok else '<'} min {float(min_byproduct)*100:.2f}%)"
            ),
        })

    # Vincolo CIC Annex IX
    annex = rc.get("annex_ix_feeds") or []
    annex_min = rc.get("annex_ix_min_share")
    if annex_min is not None and annex:
        share = _share_in(annex)
        ok = share >= float(annex_min) - 1e-9
        constraints_status.append({
            "name": "CIC Annex IX - quota minima",
            "ok": ok,
            "value": share * 100.0,
            "limit": float(annex_min) * 100.0,
            "msg": (
                f"Quota Annex IX {share*100:.2f}% "
                f"({'>=' if ok else '<'} min {float(annex_min)*100:.2f}%)"
            ),
        })

    # Vincolo cap autorizzativo: verifica MENSILE su base aggregata.
    # NORMATIVA DM 2022 / RED III: la conformità è valutata sul TOTALE MENSILE,
    # non sui singoli giorni. Cap autorizzato = portata oraria media mensile,
    # calcolata come Sm³ netti totali / ore di funzionamento effettive.
    # I giorni di picco oltre cap NON costituiscono violazione se la media
    # mensile rimane sotto soglia (operatore può concentrare produzione).
    cap_value = rc.get("max_sm3h_authorized")
    if cap_value:
        cap_value = float(cap_value)
        sm3_netti_tot = float(getattr(monthly_agg, "sm3_netti", 0.0))
        # Ore di funzionamento effettive: somma ore dei giorni con produzione > 0.
        # `monthly_agg` espone `total_hours` (vedi monthly_aggregate.py:159+);
        # fallback su giorni con dati × 24h.
        hours_run = float(getattr(monthly_agg, "total_hours", 0.0) or 0.0)
        if hours_run <= 0:
            n_days = int(getattr(monthly_agg, "n_days_with_data", 0) or 0)
            hours_run = float(n_days) * 24.0
        sm3h_mensile_medio = (sm3_netti_tot / hours_run) if hours_run > 0 else 0.0
        ok = sm3h_mensile_medio <= cap_value * 1.0001  # tolleranza num. ~0.01%
        # Info aggiuntiva: numero giorni di picco (solo per audit, non blocca).
        cap_peak_days = list(getattr(monthly_agg, "cap_violation_days", []) or [])
        peak_note = ""
        if cap_peak_days:
            peak_note = f" (info: {len(cap_peak_days)} giorno/i di picco sopra cap, non bloccanti — la verifica è mensile)"
        constraints_status.append({
            "name": "Cap autorizzativo Sm3/h (media mensile)",
            "ok": ok,
            "value": float(sm3h_mensile_medio),
            "limit": cap_value,
            "msg": (
                f"Portata media mensile {sm3h_mensile_medio:.1f} Sm³/h "
                f"{'≤' if ok else '>'} cap {cap_value:.0f} Sm³/h{peak_note}"
            ),
        })

    # Vincolo cap MWh/anno (informativo, da confrontare a ann. base)
    max_mwh_year = rc.get("max_mwh_year") or 0
    mwh_mese = float(getattr(monthly_agg, "mwh", 0.0))
    if max_mwh_year and max_mwh_year > 0:
        # Stima proporzionale: media mese -> annuo
        # Limite mensile = max_mwh_year/12; warning, non blocco
        monthly_limit = float(max_mwh_year) / 12.0
        ok = mwh_mese <= monthly_limit * 1.20  # tolleranza 20% per stagionalita'
        constraints_status.append({
            "name": "Cap MWh/anno (proporzionale mensile)",
            "ok": ok,
            "value": mwh_mese,
            "limit": monthly_limit,
            "msg": (
                f"MWh mese {mwh_mese:.1f} vs media mensile attesa "
                f"{monthly_limit:.1f} (cap annuo {float(max_mwh_year):.0f})"
            ),
        })

    constraints_ok = all(c["ok"] for c in constraints_status)
    saving_ok = saving >= th

    return {
        "compliant": bool(saving_ok and constraints_ok),
        "saving": saving,
        "threshold": th,
        "margin": margin,
        "constraints_status": constraints_status,
        "regime": regime,
    }


__all__ = [
    "evaluate_monthly_sustainability",
]
