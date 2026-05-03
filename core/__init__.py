# -*- coding: utf-8 -*-
"""core/ — Motore di calcolo e validatori Metan.iQ.

Questo pacchetto espone le funzioni di calcolo GHG, rese biomasse,
fattori emissivi, business plan, CIC e FER2.

In questa iterazione le funzioni sono definite (o proxate) qui in modo
che i moduli output/ ed export/ possano importarle senza dipendere
direttamente da app_mensile.py, che rimane il file principale Streamlit.
"""
from .calculation_engine import (  # noqa: F401
    compute_business_plan,
    compute_aux_factor,
    ghg_summary,
    solve_1_unknown_production,
    solve_2_unknowns_dual,
    find_optimal_pair,
    e_total_feedstock,
    fmt_it,
    parse_it,
    FEEDSTOCK_DB,
    MONTHS,
    MONTH_HOURS,
    LHV_BIOMETHANE,
    NM3_TO_MWH,
)
