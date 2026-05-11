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

# Costanti normative/energetiche: importate dalla fonte di verità
# centralizzata core/constants.py (con alias per i nomi storici).
from core.constants import (  # noqa: E402
    LHV_BIOMETHANE_MJ_NM3                as LHV_BIOMETHANE,
    NM3_TO_MWH,
    GCAL_PER_CIC,
    MWH_PER_CIC,
    CIC_PRICE_DEFAULT_EUR                as CIC_PRICE_DEFAULT,
    ANNEX_IX_THRESHOLD,
    FER2_KWE_CAP,
    FER2_TARIFFA_BASE_DEFAULT_EUR_MWH    as FER2_TARIFFA_BASE_DEFAULT,
    FER2_PREMIO_MATRICE_DEFAULT_EUR_MWH  as FER2_PREMIO_MATRICE_DEFAULT,
    FER2_PREMIO_CAR_DEFAULT_EUR_MWH      as FER2_PREMIO_CAR_DEFAULT,
    FER2_FEEDSTOCK_REQ_THRESHOLD,
    FER2_PERIODO_ANNI,
    FER2_GHG_THRESHOLD,
    COMPARATOR_GRID_HEAT_GCO2_MJ         as FOSSIL_COMPARATOR,
)

FEEDSTOCK_DB: dict = {}
FEED_NAMES: list = []
FEEDSTOCK_CATEGORIES: dict = {}
MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
DEFAULT_AUX_FACTOR = 1.29
DEFAULT_PLANT_NET_SMCH = 300.0
COMPARATOR_BY_END_USE = {
    "Elettricità/calore/immissione rete (nuovo >=20/11/2023)": 80.0,
    "Trasporti (BioGNL/BioCNG)": 94.0,
}
END_USE_THRESHOLDS = {
    "Elettricità/calore/immissione rete (nuovo >=20/11/2023)": 0.80,
    "Trasporti (BioGNL/BioCNG)": 0.65,
}
EP_DIGESTATE: dict = {}
EP_UPGRADING: dict = {}
EP_OFFGAS: dict = {}
EP_HEAT: dict = {}
EP_ELEC: dict = {}
METHANE_SLIP: dict = {}
HEAT_DEMAND_UPGRADING: dict = {}
ELEC_DEMAND_UPGRADING: dict = {}
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
    s = s.replace(",", "§").replace(".", ",").replace("§", "'")
    return s + suffix


def parse_it(value) -> float:  # type: ignore[misc]
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("€", "").replace("%", "").replace("'", "").strip()
    if not s or s == "-":
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# LAZY LOOKUP WRAPPERS (FIX BUG sm3_gross=0)
# ---------------------------------------------------------------------------
# Le funzioni critiche di calcolo NON vanno copiate via globals() al momento
# dell'import (vecchio approccio): se il proxy viene importato PRIMA che
# app_mensile.py finisca di eseguire (race con import order), copiamo lo
# stub fallback e i calcoli ritornano zero.
#
# Soluzione: wrapper che cercano la vera funzione di app_mensile AD OGNI
# CHIAMATA. Lookup veloce in sys.modules["__main__"] (Streamlit runtime)
# o sys.modules["app_mensile"] (test isolato). Se trova → delega; se non
# trova → fallback stub (ritorna 0 ma logga un warning).
# ---------------------------------------------------------------------------

def _find_app_module():
    """Restituisce il modulo app_mensile vero (non lo stub), o None."""
    for _m in list(sys.modules.values()):
        _f = getattr(_m, "__file__", "") or ""
        if _f.endswith("app_mensile.py") and hasattr(_m, "FEEDSTOCK_DB"):
            return _m
    _m = sys.modules.get("app_mensile")
    if _m is not None and hasattr(_m, "FEEDSTOCK_DB"):
        return _m
    return None


def _live_call(_name, *args, _fallback=None, **kwargs):
    """Cerca _name in app_mensile e lo chiama. Fallback se non trovato."""
    _app = _find_app_module()
    if _app is not None:
        _fn = getattr(_app, _name, None)
        if _fn is not None and _fn is not globals().get(_name):
            return _fn(*args, **kwargs)
    return _fallback


def ghg_summary(masses, aux, ep=0.0, fossil_comparator=None):
    _r = _live_call(
        "ghg_summary", masses, aux=aux, ep=ep,
        fossil_comparator=fossil_comparator,
        _fallback={"e_w": 0.0, "saving": 0.0, "nm3_gross": 0.0,
                   "nm3_net": 0.0, "mwh_net": 0.0,
                   "mj_gross": 0.0, "mj_net": 0.0,
                   "sustainability_basis": "gross"},
    )
    return _r


def compute_aux_factor(*args, **kwargs):
    return _live_call("compute_aux_factor", *args, **kwargs,
                      _fallback={"aux_factor": DEFAULT_AUX_FACTOR,
                                 "f_heat": 0.0, "f_elec": 0.0,
                                 "f_slip": 0.0, "f_margin": 0.03,
                                 "f_tot": 0.03, "heat_need_gross": 0.0,
                                 "heat_recovered_chp": 0.0,
                                 "heat_need_residual": 0.0,
                                 "elec_need": 0.0, "elec_upgrading": 0.0,
                                 "elec_bop": 0.0, "elec_injection": 0.0})


def compute_business_plan(*args, **kwargs):
    return _live_call("compute_business_plan", *args, **kwargs, _fallback={})


def solve_1_unknown_production(*args, **kwargs):
    return _live_call("solve_1_unknown_production", *args, **kwargs, _fallback=0.0)


def solve_2_unknowns_dual(*args, **kwargs):
    return _live_call("solve_2_unknowns_dual", *args, **kwargs,
                      _fallback=({}, False, "app_mensile non disponibile"))


def find_optimal_pair(*args, **kwargs):
    return _live_call("find_optimal_pair", *args, **kwargs, _fallback=None)


def e_total_feedstock(name, ep=0.0):
    return _live_call("e_total_feedstock", name, ep, _fallback=0.0)


def _emission_factors_of(name, ep_default=0.0):
    return _live_call("_emission_factors_of", name, ep_default,
                      _fallback={"eec": 0.0, "esca": 0.0, "etd": 0.0,
                                 "ep": ep_default, "extra": 0.0,
                                 "source": "fallback"})


def _yield_of(name):
    return _live_call("_yield_of", name, _fallback=0.0)


def _feeds_by_category():
    return _live_call("_feeds_by_category", _fallback={})


# ---------------------------------------------------------------------------
# Step 2 — Sovrascrivi con valori reali
#   Priorità A: sys.modules["__main__"] se è app_mensile.py (Streamlit runtime)
#   Priorità B: import classico app_mensile (test isolati / shell)
# ---------------------------------------------------------------------------
# SOLO COSTANTI (dict/list/scalar). Le FUNZIONI del proxy sono già wrapper
# lazy (ghg_summary, _yield_of, ecc.) e si auto-delegano via _live_call —
# NON vanno sovrascritte qui, altrimenti il check anti-recursion del
# wrapper fallisce e i risultati restano a 0 (vedi bug sm3_gross=0
# diagnosticato il 2026-05-10).
_PROXY_NAMES = (
    "FEEDSTOCK_DB", "FEED_NAMES", "FEEDSTOCK_CATEGORIES",
    "MONTHS", "MONTH_HOURS", "LHV_BIOMETHANE", "NM3_TO_MWH",
    "DEFAULT_AUX_FACTOR", "DEFAULT_PLANT_NET_SMCH",
    "COMPARATOR_BY_END_USE", "END_USE_THRESHOLDS", "FOSSIL_COMPARATOR",
    "EP_DIGESTATE", "EP_UPGRADING", "EP_OFFGAS",
    "EP_HEAT", "EP_ELEC", "METHANE_SLIP", "HEAT_DEMAND_UPGRADING",
    "ELEC_DEMAND_UPGRADING",
    "BP_CAPEX_DEFAULTS_PER_SMCH", "BP_CAPEX_FORFAIT_DEFAULTS",
    "BP_OPEX_DEFAULTS_PER_SMCH_YEAR", "BP_OPEX_FORFAIT_DEFAULTS",
    "BP_FINANCE_DEFAULTS", "BP_TARIFFA_BASE_2026", "BP_RIBASSO_DEFAULT_PCT",
    "BP_DURATA_TARIFFA_ANNI", "BP_INFLAZIONE_DEFAULT_PCT",
    "BP_AMMORTAMENTO_ANNI", "BP_TAX_RATE_PCT",
    "BP_PNRR_QUOTA_PCT_DEFAULT", "BP_MASSIMALE_SPESA_EUR_PER_SMCH",
)

_APP_MOD = None
_APP_MENSILE_AVAILABLE = False

# Cerca il modulo app_mensile in sys.modules indipendentemente dal nome (Streamlit 1.30+ usa nomi generati)
for _m in list(sys.modules.values()):
    _m_file = getattr(_m, "__file__", "") or ""
    if _m_file.endswith("app_mensile.py") and hasattr(_m, "FEEDSTOCK_DB"):
        _APP_MOD = _m
        break

# Solo in test isolati (dove app_mensile non è caricato da Streamlit), prova import legacy
if _APP_MOD is None:
    # Verifichiamo se siamo nel mezzo di un caricamento per non fare circular import
    _in_streamlit = any("streamlit" in str(getattr(m, "__file__", "")) for m in sys.modules.values())
    if not _in_streamlit:
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
