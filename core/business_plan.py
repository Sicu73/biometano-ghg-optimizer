# -*- coding: utf-8 -*-
"""core/business_plan.py — Facade per il calcolo del Business Plan biometano.

Estrae l'API pubblica del calcolo Business Plan / pro-forma dal monolite
``app_mensile.py`` (e dal modulo ponte ``core/calculation_engine.py``)
per renderla riutilizzabile da test, batch e futuri front-end.

Mantiene 100% backward compatibility:
  - se ``app_mensile`` espone ``compute_business_plan``, lo si re-esporta;
  - altrimenti si fallback su ``core.calculation_engine.compute_business_plan``;
  - se nessuno e' disponibile, ``compute_business_plan`` ritorna {} (no-crash).

Espone anche le costanti BP di default (tariffa base, durata, ammortamento,
inflazione, tax rate, PNRR cap, massimale spesa) come singolo punto di
verita' per la logica BP.
"""
from __future__ import annotations

from typing import Any, Callable

# ---------------------------------------------------------------------------
# Costanti di default Business Plan (singolo punto di verita')
# ---------------------------------------------------------------------------

BP_TARIFFA_BASE_2026_EUR_MWH = 131.0   # €/MWh (124,48 base 2024 + ISTAT)
BP_RIBASSO_DEFAULT_PCT = 1.0
BP_DURATA_TARIFFA_ANNI = 15            # DM 15/09/2022 — Decreto Biometano
BP_INFLAZIONE_DEFAULT_PCT = 2.5
BP_AMMORTAMENTO_ANNI = 22              # impianti biometano (10% media DLgs 38/2018)
BP_TAX_RATE_PCT = 24.0
BP_PNRR_QUOTA_PCT_DEFAULT = 40.0
BP_MASSIMALE_SPESA_EUR_PER_SMCH = 32817.23


# ---------------------------------------------------------------------------
# Risoluzione dinamica del calcolo BP (no import circolari forti)
# ---------------------------------------------------------------------------

def _resolve_bp_function() -> Callable[..., dict] | None:
    """Cerca compute_business_plan nei moduli di calcolo disponibili."""
    # 1) modulo storico app_mensile
    try:
        from app_mensile import compute_business_plan as _fn  # type: ignore
        return _fn
    except Exception:
        pass
    # 2) ponte core.calculation_engine
    try:
        from core.calculation_engine import compute_business_plan as _fn  # type: ignore
        return _fn
    except Exception:
        pass
    return None


def compute_business_plan(*args: Any, **kwargs: Any) -> dict:
    """Calcola il Business Plan biometano (facade).

    Delegato dinamico al motore di calcolo storico (``app_mensile`` o
    ``core.calculation_engine``). Se nessuna implementazione e' disponibile
    restituisce un dict vuoto, mai solleva eccezione di import.
    """
    fn = _resolve_bp_function()
    if fn is None:
        return {}
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - errore propagato in modo soft
        return {"_bp_error": str(exc)}


__all__ = [
    "BP_TARIFFA_BASE_2026_EUR_MWH",
    "BP_RIBASSO_DEFAULT_PCT",
    "BP_DURATA_TARIFFA_ANNI",
    "BP_INFLAZIONE_DEFAULT_PCT",
    "BP_AMMORTAMENTO_ANNI",
    "BP_TAX_RATE_PCT",
    "BP_PNRR_QUOTA_PCT_DEFAULT",
    "BP_MASSIMALE_SPESA_EUR_PER_SMCH",
    "compute_business_plan",
]
