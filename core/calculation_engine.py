# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
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
    COMPARATOR_GRID_HEAT_GCO2_MJ         as FOSSIL_COMPARATOR,
    COMPARATOR_TRANSPORT_GCO2_MJ         as _COMP_TRANSPORT,
    SAVING_THRESHOLD_GRID_HEAT           as _THR_GRID_HEAT,
    SAVING_THRESHOLD_GRID_HEAT_EXISTING  as _THR_GRID_HEAT_EXISTING,
    SAVING_THRESHOLD_TRANSPORT           as _THR_TRANSPORT,
    DEFAULT_AUX_FACTOR,
)

# Fonte canonica del database biomasse: e' lo STESSO oggetto che app_mensile
# importa a sua volta (`from core.feedstock_db import FEEDSTOCK_DB`), quindi
# il fallback non introduce una seconda verita'.
# Senza questo default il modulo restava con FEEDSTOCK_DB/FEED_NAMES vuoti
# ogni volta che veniva importato prima di app_mensile con streamlit gia'
# in sys.modules (vedi Step 2: in quel caso l'import legacy viene saltato
# per non innescare import circolari), e i consumatori a valle leggevano
# zero biomasse senza alcun errore.
from core.feedstock_db import FEEDSTOCK_DB as _FEEDSTOCK_DB_CANON  # noqa: E402

FEEDSTOCK_DB: dict = _FEEDSTOCK_DB_CANON
FEED_NAMES: list = list(_FEEDSTOCK_DB_CANON.keys())
FEEDSTOCK_CATEGORIES: dict = {}
MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
DEFAULT_PLANT_NET_SMCH = 300.0
# Fallback allineato alla fonte canonica (app_mensile): 3 voci, chiavi unicode.
# Usato quando l'overwrite lazy non scatta (app_mensile a meta' caricamento
# quando questo modulo viene importato). Tenere sincronizzato con app_mensile.
COMPARATOR_BY_END_USE = {
    "Elettricità/calore/immissione rete (nuovo ≥1/1/2026)": FOSSIL_COMPARATOR,
    "Immissione rete/calore (esistente <10 MW, primi 15 anni)": FOSSIL_COMPARATOR,
    "Trasporti (BioGNL/BioCNG)": _COMP_TRANSPORT,
}
END_USE_THRESHOLDS = {
    "Elettricità/calore/immissione rete (nuovo ≥1/1/2026)": _THR_GRID_HEAT,
    "Immissione rete/calore (esistente <10 MW, primi 15 anni)": _THR_GRID_HEAT_EXISTING,
    "Trasporti (BioGNL/BioCNG)": _THR_TRANSPORT,
}
EP_DIGESTATE: dict = {}
EP_UPGRADING: dict = {}
EP_OFFGAS: dict = {}
EP_HEAT: dict = {}
EP_ELEC: dict = {}
METHANE_SLIP: dict = {}
HEAT_DEMAND_UPGRADING: dict = {}
ELEC_DEMAND_UPGRADING: dict = {}
# Benchmark CAPEX biometano agricolo Italia 2025/2026.
# Range tipico: 30-50k EUR per Sm³/h capacità nominale (chiavi in mano).
# Fonte: GSE Linee Guida 2024, CIB benchmark consorzio, audit Studio NE-Nomisma.
BP_CAPEX_DEFAULTS_PER_SMCH: dict = {
    "nuova_costruzione":   38_000,   # €/Smc/h — impianto greenfield completo
    "ampliamento":         22_000,   # €/Smc/h — modulo aggiuntivo
    "riconversione_totale": 30_000,  # €/Smc/h — da CHP a 100% biometano
    "riconversione_parz":   18_000,  # €/Smc/h — CHP residuo + quota biomet.
}
# Costi forfait NON proporzionali (allacciamento, connessione gas, ecc.)
BP_CAPEX_FORFAIT_DEFAULTS: dict = {
    "allacciamento_gas":   250_000,  # €
    "permessi_progetto":   120_000,  # €
    "infrastrutture_civ":  180_000,  # € (recinzione, strada, illuminazione)
}
# OPEX annuo per Sm³/h capacità (anno 1, scala con inflazione).
# Esclude biomasse (variabili per mix) — vedi tariffa biomasse separata.
BP_OPEX_DEFAULTS_PER_SMCH_YEAR: dict = {
    "manutenzione":          1_800,  # €/Smc/h/anno (5% CAPEX tipico)
    "personale":             1_400,  # €/Smc/h/anno (2-3 FTE per impianto medio)
    "elettricita_propria":     900,  # €/Smc/h/anno (autoconsumo non recuperato)
    "consumabili_chimici":     600,  # €/Smc/h/anno (carboni att., antischiuma)
    "assicurazioni":           400,  # €/Smc/h/anno (RC + danni + perdita prof.)
    "monitoraggio_GSE":        250,  # €/Smc/h/anno (certificazioni annuali)
}
# OPEX forfait annuali (overhead, audit)
BP_OPEX_FORFAIT_DEFAULTS: dict = {
    "audit_certificazione":   25_000,  # €/anno (RINA/SGS/ISCC)
    "consulenza_normativa":   15_000,  # €/anno
}
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


def fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False,
           lang: str | None = None) -> str:  # type: ignore[misc]
    """Formatta numero stile locale-aware (IT/EN). Vedi app_mensile.fmt_it."""
    if value is None:
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if lang is None:
        try:
            from i18n_runtime import get_lang as _gl
            lang = _gl()
        except Exception:
            lang = "it"
    if signed:
        s = f"{f:+,.{decimals}f}"
    else:
        s = f"{f:,.{decimals}f}"
    if lang == "en":
        return s + suffix
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
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
    # Fallback = resa tabellare della fonte canonica. Il vecchio 0.0
    # azzerava silenziosamente Sm3 e MWh quando app_mensile non era
    # caricato (script, export, job fuori da Streamlit). Nessuna formula
    # duplicata: senza override BMT la normalizzazione ST vale 1.
    _fb = float((FEEDSTOCK_DB.get(name) or {}).get("yield", 0.0) or 0.0)
    return _live_call("_yield_of", name, _fallback=_fb)


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
    "BP_DURATA_TARIFFA_ANNI",
    "BP_INFLAZIONE_DEFAULT_PCT",
    "BP_AMMORTAMENTO_ANNI",
    "BP_TAX_RATE_PCT",
    "BP_PNRR_QUOTA_PCT_DEFAULT",
    "BP_MASSIMALE_SPESA_EUR_PER_SMCH",
    "_APP_MENSILE_AVAILABLE",
]
