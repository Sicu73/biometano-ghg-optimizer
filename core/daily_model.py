# -*- coding: utf-8 -*-
"""core/daily_model.py — Modello dati e calcoli giornalieri.

Contiene le dataclass `DailyEntry` (input utente) e `DailyComputed`
(risultati derivati) e la funzione `compute_daily` che alimenta la
gestione operativa giorno per giorno.

REGOLA DI COMPLIANCE:
  - I valori giornalieri (in particolare `daily_saving_estimate`)
    sono SOLO INFORMATIVI. La sostenibilita' ufficiale e' calcolata
    a livello mensile (vedi core/monthly_aggregate + core/sustainability).

Riusa funzioni esistenti dal motore di calcolo (`core.calculation_engine`)
per non duplicare formule. Se app_mensile non e' importabile (es. test
isolati), il fallback minimale del calculation_engine garantisce che
i moduli/test caricano comunque.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from core.calculation_engine import (
    LHV_BIOMETHANE,
    NM3_TO_MWH,
    DEFAULT_AUX_FACTOR,
    FOSSIL_COMPARATOR,
    _emission_factors_of,
    _yield_of,
    e_total_feedstock,
    ghg_summary,
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class DailyEntry:
    """Input giornaliero inserito dall'operatore.

    Attributes:
        date: Data del giorno (datetime.date).
        feedstocks: Mappa {tipologia_biomassa: quantita_t}. Tonnellate/giorno.
        notes: Annotazioni libere (opzionali).
    """
    date: date
    feedstocks: dict[str, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class DailyComputed:
    """Risultati calcolati per un singolo giorno.

    NB: `daily_saving_estimate` e' SOLO INFORMATIVO; la sostenibilita'
    ufficiale e' valutata sul totale mese.
    """
    date: date
    biomass_total_t: float = 0.0
    sm3_gross: float = 0.0          # Sm3 lordi (resa biomassa)
    sm3_netti: float = 0.0          # Sm3 netti (lordi / aux_factor)
    mwh: float = 0.0                # Energia netta MWh
    eec: float = 0.0                # gCO2eq/MJ ponderato
    esca: float = 0.0
    etd: float = 0.0
    ep: float = 0.0
    e_total: float = 0.0            # gCO2eq/MJ totale (e_w)
    daily_saving_estimate: float = 0.0  # %
    cap_ok: bool = True             # vincolo autorizzativo (Sm3/h capacita')
    feedstock_breakdown: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Calcolo giornaliero
# ---------------------------------------------------------------------------

def compute_daily(entry: DailyEntry, ctx: dict[str, Any] | None = None) -> DailyComputed:
    """Calcola le metriche giornaliere per un `DailyEntry`.

    Args:
        entry: il giorno con biomasse alimentate (t).
        ctx: contesto opzionale con chiavi:
            - 'aux_factor':   float, default DEFAULT_AUX_FACTOR
            - 'ep':           float gCO2eq/MJ contributo processing
            - 'fossil_comparator': float gCO2eq/MJ (default FOSSIL_COMPARATOR)
            - 'plant_net_smch':    float Sm3/h, capacita' autorizzata
            - 'hours_per_day':     float ore/giorno (default 24.0)

    Returns:
        DailyComputed.
    """
    ctx = ctx or {}
    aux = float(ctx.get("aux_factor") or DEFAULT_AUX_FACTOR) or DEFAULT_AUX_FACTOR
    ep = float(ctx.get("ep") or 0.0)
    fossil_cmp = ctx.get("fossil_comparator")
    plant_net_smch = float(ctx.get("plant_net_smch") or 0.0)
    hours_per_day = float(ctx.get("hours_per_day") or 24.0)

    # Filtro feedstock validi (>0)
    masses = {n: float(q) for n, q in (entry.feedstocks or {}).items()
              if q is not None and float(q) > 0}
    biomass_total = sum(masses.values())

    if not masses:
        return DailyComputed(date=entry.date, biomass_total_t=0.0,
                             feedstock_breakdown=dict(masses), cap_ok=True)

    # Riusa la stessa funzione del motore (no duplicazioni di formule)
    try:
        summary = ghg_summary(masses, aux=aux, ep=ep, fossil_comparator=fossil_cmp)
    except Exception:
        summary = {"e_w": 0.0, "saving": 0.0, "nm3_gross": 0.0,
                   "nm3_net": 0.0, "mwh_net": 0.0}

    # Decomposizione delle componenti emissive (medie pesate sulla MJ)
    total_mj = 0.0
    eec_w = esca_w = etd_w = ep_w = 0.0
    for name, m in masses.items():
        try:
            y = _yield_of(name)
            mj = m * y * LHV_BIOMETHANE
            ef = _emission_factors_of(name, ep_default=ep) or {}
            total_mj += mj
            eec_w += float(ef.get("eec") or 0.0) * mj
            esca_w += float(ef.get("esca") or 0.0) * mj
            etd_w += float(ef.get("etd") or 0.0) * mj
            ep_w += float(ef.get("ep") or ep) * mj
        except Exception:
            continue

    if total_mj > 0:
        eec_v = eec_w / total_mj
        esca_v = esca_w / total_mj
        etd_v = etd_w / total_mj
        ep_v = ep_w / total_mj
    else:
        eec_v = esca_v = etd_v = ep_v = 0.0

    sm3_gross = float(summary.get("nm3_gross") or 0.0)
    sm3_net = float(summary.get("nm3_net") or 0.0)
    mwh = float(summary.get("mwh_net") or sm3_net * NM3_TO_MWH)

    # Verifica cap autorizzativo (sm3 lordi/giorno vs capacita' giornaliera)
    cap_ok = True
    if plant_net_smch > 0 and hours_per_day > 0:
        max_gross_day = plant_net_smch * aux * hours_per_day
        cap_ok = sm3_gross <= max_gross_day * 1.0001  # tolleranza arrotondamento

    return DailyComputed(
        date=entry.date,
        biomass_total_t=biomass_total,
        sm3_gross=sm3_gross,
        sm3_netti=sm3_net,
        mwh=mwh,
        eec=eec_v,
        esca=esca_v,
        etd=etd_v,
        ep=ep_v,
        e_total=float(summary.get("e_w") or 0.0),
        daily_saving_estimate=float(summary.get("saving") or 0.0),
        cap_ok=cap_ok,
        feedstock_breakdown=dict(masses),
    )


__all__ = [
    "DailyEntry",
    "DailyComputed",
    "compute_daily",
]
