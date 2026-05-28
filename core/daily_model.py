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
        hours_per_day: Ore di funzionamento del giorno (0-24, default 24.0).
    """
    date: date
    feedstocks: dict[str, float] = field(default_factory=dict)
    remi_vb: float = 0.0
    remi_e: float = 0.0
    remi_qb_max: float = 0.0
    remi_pci: float = 0.0
    remi_rho: float = 0.0
    notes: str = ""
    hours_per_day: float = 24.0


@dataclass
class DailyComputed:
    """Risultati calcolati per un singolo giorno.

    NB: `daily_saving_estimate` e' SOLO INFORMATIVO; la sostenibilita'
    ufficiale e' valutata sul totale mese.
    """
    date: date
    biomass_total_t: float = 0.0
    sm3_gross: float = 0.0          # Sm3 lordi (calcolati dalle rese teoriche biomasse)
    sm3_netti: float = 0.0          # Sm3 netti (reali misurati al REMI)
    sm3_gross_ora: float = 0.0
    sm3_netti_ora: float = 0.0
    mwh: float = 0.0                # Energia netta MWh
    eec: float = 0.0                # gCO2eq/MJ ponderato
    e_l: float = 0.0                # Land Use Change (RED III)
    esca: float = 0.0
    etd: float = 0.0
    ep: float = 0.0
    e_total: float = 0.0            # gCO2eq/MJ totale (e_w)
    daily_saving_estimate: float = 0.0  # %
    cap_ok: bool = True             # vincolo autorizzativo (Sm3/h capacita')
    feedstock_breakdown: dict[str, float] = field(default_factory=dict)

    remi_portata_media_smch: float = 0.0
    remi_potenza_media_mw: float = 0.0
    remi_energia_specifica_kwh_smc: float = 0.0

    # Raw REMI inputs for aggregation
    remi_vb: float = 0.0
    remi_e: float = 0.0
    remi_qb_max: float = 0.0
    remi_pci: float = 0.0
    remi_rho: float = 0.0
    hours_per_day: float = 24.0

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
    eec_w = e_l_w = esca_w = etd_w = ep_w = 0.0
    for name, m in masses.items():
        try:
            y = _yield_of(name)
            mj = m * y * LHV_BIOMETHANE
            ef = _emission_factors_of(name, ep_default=ep) or {}
            total_mj += mj
            eec_w += float(ef.get("eec") or 0.0) * mj
            e_l_w += float(ef.get("e_l") or 0.0) * mj
            esca_w += float(ef.get("esca") or 0.0) * mj
            etd_w += float(ef.get("etd") or 0.0) * mj
            ep_w += float(ef.get("ep") or ep) * mj
        except Exception:
            continue

    if total_mj > 0:
        eec_v = eec_w / total_mj
        e_l_v = e_l_w / total_mj
        esca_v = esca_w / total_mj
        etd_v = etd_w / total_mj
        ep_v = ep_w / total_mj
    else:
        eec_v = e_l_v = esca_v = etd_v = ep_v = 0.0

    sm3_gross = float(summary.get("nm3_gross") or 0.0)
    
    vb = getattr(entry, "remi_vb", 0.0)
    e_val = getattr(entry, "remi_e", 0.0)
    
    # NUOVA LOGICA: sm3_netti = dato inserito dall'utente
    sm3_net = vb
    mwh = e_val / 1000.0 if e_val > 0 else (sm3_net * NM3_TO_MWH)

    sm3_gross_ora = sm3_gross / hours_per_day if hours_per_day > 0 else 0.0
    sm3_net_ora = sm3_net / hours_per_day if hours_per_day > 0 else 0.0

    # Verifica cap autorizzativo: la produzione NETTA ORARIA REALE <= cap
    cap_ok = True
    if plant_net_smch > 0 and hours_per_day > 0:
        cap_ok = sm3_net_ora <= plant_net_smch * 1.0001  # tolleranza

    vb = getattr(entry, "remi_vb", 0.0)
    e_val = getattr(entry, "remi_e", 0.0)

    portata_media = vb / hours_per_day if hours_per_day > 0 else 0.0
    potenza_media = e_val / hours_per_day / 1000.0 if hours_per_day > 0 else 0.0
    energia_spec = e_val / vb if vb > 0 else 0.0

    return DailyComputed(
        date=entry.date,
        biomass_total_t=biomass_total,
        sm3_gross=sm3_gross,
        sm3_netti=sm3_net,
        sm3_gross_ora=sm3_gross_ora,
        sm3_netti_ora=sm3_net_ora,
        mwh=mwh,
        eec=eec_v,
        e_l=e_l_v,
        esca=esca_v,
        etd=etd_v,
        ep=ep_v,
        e_total=float(summary.get("e_w") or 0.0),
        daily_saving_estimate=float(summary.get("saving") or 0.0),
        cap_ok=cap_ok,
        feedstock_breakdown=dict(masses),
        remi_portata_media_smch=portata_media,
        remi_potenza_media_mw=potenza_media,
        remi_energia_specifica_kwh_smc=energia_spec,
        remi_vb=vb,
        remi_e=e_val,
        remi_qb_max=getattr(entry, "remi_qb_max", 0.0),
        remi_pci=getattr(entry, "remi_pci", 0.0),
        remi_rho=getattr(entry, "remi_rho", 0.0),
        hours_per_day=hours_per_day,
    )

__all__ = [
    "DailyEntry",
    "DailyComputed",
    "compute_daily",
]
