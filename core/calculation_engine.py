# -*- coding: utf-8 -*-
"""core/calculation_engine.py — Motore di calcolo GHG / biometano / biogas CHP.

Questo modulo ESPONE (proxy) le funzioni di calcolo che risiedono in
app_mensile.py, senza duplicarne la logica. I nuovi moduli (output/,
export/, tests/) importano da qui, non direttamente da app_mensile.

Strategia proxy (fase 1):
  - Le funzioni originali rimangono in app_mensile.py per non toccare
    la UI Streamlit.
  - Questo modulo le importa e le ri-espone con lo stesso nome.

Resilienza al runtime Streamlit:
  - A runtime, Streamlit esegue app_mensile.py come ``__main__`` (NON
    come modulo ``app_mensile``). Un naive ``from app_mensile import ...``
    causerebbe una seconda esecuzione completa del file (Python lo carica
    come modulo distinto), riallocando widget Streamlit con le stesse key
    (es. ``btn_lang_it``) e rompendo l'app con duplicate-key errors.
  - Per evitarlo: cerchiamo prima i simboli in ``sys.modules['__main__']``
    quando ``__main__.__file__`` punta a app_mensile.py. Solo in test
    isolati (no Streamlit) ricadiamo su ``import app_mensile``.

NB: NON modificare la logica delle funzioni sottostanti.
    NON duplicare formule o costanti normative.
"""
from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Step 1 — Fallback minimali SEMPRE definiti (test isolati e safety net)
# ---------------------------------------------------------------------------
import numpy as np  # noqa: F401  (alcune funzioni reali ne dipendono)

FEEDSTOCK_DB: dict = {}
FEED_NAMES: list = []
FEEDSTOCK_CATEGORIES: dict = {}
MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
LHV_BIOMETHANE = 35.9
NM3_TO_MWH = 0.00997
DEFAULT_AUX_FACTOR = 1.29
DEFAULT_PLANT_NET_SMCH = 300.0
FOSSIL_COMPARATOR = 80.0
COMPARATOR_BY_END_USE = {
    "Elettricità/calore/immissione rete (nuovo >=20/11/2023)": 80.0,
    "Trasporti (BioGNL/BioCNG)": 94.0,
}
END_USE_THRESHOLDS = {
    "Elettricità/calore/immissione rete (nuovo >=20/11/2023)": 0.80,
    "Trasporti (BioGNL/BioCNG)": 0.65,
}
MWH_PER_CIC = 11.628
GCAL_PER_CIC = 10.0
CIC_PRICE_DEFAULT = 375.0
ANNEX_IX_THRESHOLD = 0.70
EP_DIGESTATE: dict = {}
EP_UPGRADING: dict = {}
EP_OFFGAS: dict = {}
EP_HEAT: dict = {}
EP_ELEC: dict = {}
METHANE_SLIP: dict = {}
HEAT_DEMAND_UPGRADING: dict = {}
ELEC_DEMAND_UPGRADING: dict = {}
FER2_KWE_CAP = 300.0
FER2_TARIFFA_BASE_DEFAULT = 256.0
FER2_PREMIO_MATRICE_DEFAULT = 30.0
FER2_PREMIO_CAR_DEFAULT = 10.0
FER2_FEEDSTOCK_REQ_THRESHOLD = 0.80
FER2_PERIODO_ANNI = 20
FER2_GHG_THRESHOLD = 0.80
BP_CAPEX_DEFAULTS_PER_SMCH: dict = {}
BP_CAPEX_FORFAIT_DEFAULTS: dict = {}
BP_OPEX_DEFAULTS_PER_SMCH_YEAR: dict = {}
BP_OPEX_FORFAIT_DEFAULTS: dict = {}
BP_FINANCE_DEFAULTS: dict = {
    "lt_tasso": 4.0, "lt_durata": 15, "lt_leva": 80.0,
    "equity_tasso": 4.0, "equity_durata": 15,
    "anticipo_tasso": 5.0, "anticipo_durata": 1,
    "tempo_incasso_gg": 60, "tempo_pagam_biomassa": 365,
    "tempo_pagam_altri": 60,
}
BP_TARIFFA_BASE_2026 = 131.0
BP_RIBASSO_DEFAULT_PCT = 1.0
BP_DURATA_TARIFFA_ANNI = 15
BP_INFLAZIONE_DEFAULT_PCT = 2.5
BP_AMMORTAMENTO_ANNI = 22
BP_TAX_RATE_PCT = 24.0
BP_PNRR_QUOTA_PCT_DEFAULT = 40.0
BP_MASSIMALE_SPESA_EUR_PER_SMCH = 32817.23


def fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:  # type: ignore[misc]
    if value is None:
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if signed:
        s = f"{f:+,.{decimals}f}"
    else:
        s = f"{f:,.{decimals}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def parse_it(value) -> float:  # type: ignore[misc]
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("€", "").replace("%", "").strip()
    if not s or s == "-":
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def ghg_summary(masses: dict, aux: float, ep: float = 0.0,  # type: ignore[misc]
                fossil_comparator: float | None = None) -> dict:
    return {"e_w": 0.0, "saving": 0.0, "nm3_gross": 0.0,
            "nm3_net": 0.0, "mwh_net": 0.0}


def compute_aux_factor(*args, **kwargs) -> dict:  # type: ignore[misc]
    return {"aux_factor": DEFAULT_AUX_FACTOR, "f_heat": 0.0,
            "f_elec": 0.0, "f_slip": 0.0, "f_margin": 0.03,
            "f_tot": 0.03, "heat_need_gross": 0.0,
            "heat_recovered_chp": 0.0, "heat_need_residual": 0.0,
            "elec_need": 0.0, "elec_upgrading": 0.0,
            "elec_bop": 0.0, "elec_injection": 0.0}


def compute_business_plan(*args, **kwargs) -> dict:  # type: ignore[misc]
    return {}


def solve_1_unknown_production(*args, **kwargs) -> float:  # type: ignore[misc]
    return 0.0


def solve_2_unknowns_dual(*args, **kwargs):  # type: ignore[misc]
    return {}, False, "app_mensile non disponibile"


def find_optimal_pair(*args, **kwargs):  # type: ignore[misc]
    return None


def e_total_feedstock(name: str, ep: float = 0.0) -> float:  # type: ignore[misc]
    return 0.0


def _emission_factors_of(name: str, ep_default: float = 0.0) -> dict:  # type: ignore[misc]
    return {"eec": 0.0, "esca": 0.0, "etd": 0.0, "ep": ep_default,
            "extra": 0.0, "source": "fallback"}


def _yield_of(name: str) -> float:  # type: ignore[misc]
    return 0.0


def _feeds_by_category() -> dict:  # type: ignore[misc]
    return {}


# ---------------------------------------------------------------------------
# Step 2 — Sovrascrivi con valori reali
#   Priorità A: sys.modules["__main__"] se è app_mensile.py (Streamlit runtime)
#   Priorità B: import classico app_mensile (test isolati / shell)
# ---------------------------------------------------------------------------
_PROXY_NAMES = (
    "compute_business_plan", "compute_aux_factor", "ghg_summary",
    "solve_1_unknown_production", "solve_2_unknowns_dual", "find_optimal_pair",
    "e_total_feedstock", "_emission_factors_of", "_yield_of", "_feeds_by_category",
    "fmt_it", "parse_it",
    "FEEDSTOCK_DB", "FEED_NAMES", "FEEDSTOCK_CATEGORIES",
    "MONTHS", "MONTH_HOURS", "LHV_BIOMETHANE", "NM3_TO_MWH",
    "DEFAULT_AUX_FACTOR", "DEFAULT_PLANT_NET_SMCH",
    "COMPARATOR_BY_END_USE", "END_USE_THRESHOLDS", "FOSSIL_COMPARATOR",
    "MWH_PER_CIC", "GCAL_PER_CIC", "CIC_PRICE_DEFAULT",
    "ANNEX_IX_THRESHOLD", "EP_DIGESTATE", "EP_UPGRADING", "EP_OFFGAS",
    "EP_HEAT", "EP_ELEC", "METHANE_SLIP", "HEAT_DEMAND_UPGRADING",
    "ELEC_DEMAND_UPGRADING",
    "FER2_KWE_CAP", "FER2_TARIFFA_BASE_DEFAULT", "FER2_PREMIO_MATRICE_DEFAULT",
    "FER2_PREMIO_CAR_DEFAULT", "FER2_FEEDSTOCK_REQ_THRESHOLD",
    "FER2_PERIODO_ANNI", "FER2_GHG_THRESHOLD",
    "BP_CAPEX_DEFAULTS_PER_SMCH", "BP_CAPEX_FORFAIT_DEFAULTS",
    "BP_OPEX_DEFAULTS_PER_SMCH_YEAR", "BP_OPEX_FORFAIT_DEFAULTS",
    "BP_FINANCE_DEFAULTS", "BP_TARIFFA_BASE_2026", "BP_RIBASSO_DEFAULT_PCT",
    "BP_DURATA_TARIFFA_ANNI", "BP_INFLAZIONE_DEFAULT_PCT",
    "BP_AMMORTAMENTO_ANNI", "BP_TAX_RATE_PCT",
    "BP_PNRR_QUOTA_PCT_DEFAULT", "BP_MASSIMALE_SPESA_EUR_PER_SMCH",
)

_APP_MOD = None
_APP_MENSILE_AVAILABLE = False

# Priorità A: __main__ è app_mensile.py?
_main = sys.modules.get("__main__")
if _main is not None:
    _main_file = getattr(_main, "__file__", "") or ""
    if _main_file.endswith("app_mensile.py") or hasattr(_main, "FEEDSTOCK_DB"):
        _APP_MOD = _main

# Priorità B: import classico (solo se A ha fallito E __main__ NON è app_mensile)
# (evita di rieseguire app_mensile.py mentre è in mid-execution come __main__)
if _APP_MOD is None:
    _main_is_app_mensile = (
        _main is not None
        and (getattr(_main, "__file__", "") or "").endswith("app_mensile.py")
    )
    if not _main_is_app_mensile:
        try:
            import app_mensile as _APP_MOD  # type: ignore[no-redef]
        except ImportError:
            _APP_MOD = None

if _APP_MOD is not None:
    _APP_MENSILE_AVAILABLE = True
    for _n in _PROXY_NAMES:
        if hasattr(_APP_MOD, _n):
            globals()[_n] = getattr(_APP_MOD, _n)


__all__ = [
    "compute_business_plan",
    "compute_aux_factor",
    "ghg_summary",
    "solve_1_unknown_production",
    "solve_2_unknowns_dual",
    "find_optimal_pair",
    "e_total_feedstock",
    "_emission_factors_of",
    "_yield_of",
    "_feeds_by_category",
    "fmt_it",
    "parse_it",
    "FEEDSTOCK_DB",
    "FEED_NAMES",
    "FEEDSTOCK_CATEGORIES",
    "MONTHS",
    "MONTH_HOURS",
    "LHV_BIOMETHANE",
    "NM3_TO_MWH",
    "DEFAULT_AUX_FACTOR",
    "DEFAULT_PLANT_NET_SMCH",
    "COMPARATOR_BY_END_USE",
    "END_USE_THRESHOLDS",
    "FOSSIL_COMPARATOR",
    "MWH_PER_CIC",
    "GCAL_PER_CIC",
    "CIC_PRICE_DEFAULT",
    "ANNEX_IX_THRESHOLD",
    "FER2_KWE_CAP",
    "FER2_TARIFFA_BASE_DEFAULT",
    "FER2_PREMIO_MATRICE_DEFAULT",
    "FER2_PREMIO_CAR_DEFAULT",
    "FER2_FEEDSTOCK_REQ_THRESHOLD",
    "FER2_PERIODO_ANNI",
    "FER2_GHG_THRESHOLD",
    "BP_DURATA_TARIFFA_ANNI",
    "BP_INFLAZIONE_DEFAULT_PCT",
    "BP_AMMORTAMENTO_ANNI",
    "BP_TAX_RATE_PCT",
    "BP_PNRR_QUOTA_PCT_DEFAULT",
    "BP_MASSIMALE_SPESA_EUR_PER_SMCH",
    "_APP_MENSILE_AVAILABLE",
]
