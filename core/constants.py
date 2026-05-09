# -*- coding: utf-8 -*-
"""core/constants.py — Costanti normative, soglie e fattori cablati.

Singolo punto di verita' per le costanti regolatorie e i parametri
quantitativi cablati nei calcoli (RED III, DM Biometano, FER 2,
fattori energetici). Il modulo non importa Streamlit per essere
usabile in test e batch headless.

Le costanti qui esposte SONO le stesse usate in app_mensile.py /
core.calculation_engine: non sono duplicazioni separate. Il modulo
serve come "contratto" stabile e versionato per riferimenti futuri,
audit e per i test sui riferimenti normativi.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Riferimenti normativi (stringhe canoniche)
# ---------------------------------------------------------------------------

# RED III (Direttiva UE 2023/2413)
RED_III_DIRECTIVE = "Direttiva (UE) 2023/2413 — RED III"

# Recepimento italiano RED III
DLGS_RED_III_RECEPIMENTO = (
    "D.Lgs. 9 gennaio 2026, n. 5 (GU n. 15 del 20/01/2026), "
    "entrata in vigore 04/02/2026"
)
DLGS_RED_III_NUMERO = "5/2026"
DLGS_RED_III_DATA = "2026-01-09"
DLGS_RED_III_GU = "GU n. 15 del 20/01/2026"
DLGS_RED_III_VIGORE = "2026-02-04"

# DM Biometano (CIC)
DM_BIOMETANO_2018 = "DM 2 marzo 2018 (CIC) — DM 15/09/2022 (Decreto Biometano)"

# FER 2
DM_FER2 = "DM 19/06/2024 — Decreto FER 2"
DM_FER2_AVVISO_GU = "24A04589"
DM_FER2_REGOLE_OPERATIVE = "24A06795"
DM_FER2_DESCRIZIONE = (
    f"{DM_FER2} (avviso GU {DM_FER2_AVVISO_GU}; "
    f"regole operative GSE {DM_FER2_REGOLE_OPERATIVE})"
)

# DM 2012 — biogas CHP agricolo
DM_BIOGAS_2012 = "DM 6/7/2012 — biogas CHP agricolo (≤1 MW)"

# Norme tecniche
UNI_TS_11567 = "UNI/TS 11567:2024"
JEC_WTT_V5 = "JEC Well-to-Tank v5 (JRC-CONCAWE-EUCAR)"


# ---------------------------------------------------------------------------
# Fattori energetici
# ---------------------------------------------------------------------------

LHV_BIOMETHANE_MJ_NM3 = 35.9          # MJ/Nm³ CH4 (RED III default)
NM3_TO_MWH = 0.00997                  # PCI biometano 97% CH4
METHANE_PURITY_PCT = 97.0             # purezza biometano default (%)


# ---------------------------------------------------------------------------
# Comparator fossili (gCO2eq/MJ) e soglie saving (frazione 0..1)
# ---------------------------------------------------------------------------

COMPARATOR_GRID_HEAT_GCO2_MJ = 80.0      # RED III Annex VI Part B
COMPARATOR_TRANSPORT_GCO2_MJ = 94.0      # RED III Annex V Part C
COMPARATOR_CHP_EU_MIX_GCO2_MJ = 183.0    # RED III Annex VI

SAVING_THRESHOLD_GRID_HEAT = 0.80        # nuovi impianti dal 20/11/2023
SAVING_THRESHOLD_TRANSPORT = 0.65
SAVING_THRESHOLD_CHP = 0.80


# ---------------------------------------------------------------------------
# Sistema CIC (DM 2018 / D.Lgs. 199/2021)
# ---------------------------------------------------------------------------

GCAL_PER_CIC = 10.0
MWH_PER_CIC = 11.628
CIC_PRICE_DEFAULT_EUR = 375.0
ANNEX_IX_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# FER 2 — DM 19/06/2024 (cap, tariffe, soglie)
# ---------------------------------------------------------------------------

FER2_KWE_CAP = 300.0                    # taglia massima kWe
FER2_TARIFFA_BASE_DEFAULT_EUR_MWH = 256.0
FER2_PREMIO_MATRICE_DEFAULT_EUR_MWH = 30.0
FER2_PREMIO_CAR_DEFAULT_EUR_MWH = 10.0
FER2_FEEDSTOCK_REQ_THRESHOLD = 0.80    # quota minima sottoprodotti/effluenti
FER2_PERIODO_ANNI = 20
FER2_GHG_THRESHOLD = 0.80
FER2_CAP_COLTURE_DEDICATE = 0.20


# ---------------------------------------------------------------------------
# Manure credit (gCO2eq/MJ) — GSE LG 2024 / IPCC 2019 Vol.4 Cap.10
# ---------------------------------------------------------------------------

MANURE_CREDIT_LIQUAME_SUINO = -45.0
MANURE_CREDIT_LIQUAME_BOVINO = -45.0
MANURE_CREDIT_LETAME_PALABILE = -30.0
MANURE_CREDIT_POLLINA_BROILER = -15.0
MANURE_CREDIT_POLLINA_OVAIOLE = 0.0


__all__ = [
    # riferimenti normativi
    "RED_III_DIRECTIVE",
    "DLGS_RED_III_RECEPIMENTO",
    "DLGS_RED_III_NUMERO",
    "DLGS_RED_III_DATA",
    "DLGS_RED_III_GU",
    "DLGS_RED_III_VIGORE",
    "DM_BIOMETANO_2018",
    "DM_FER2",
    "DM_FER2_AVVISO_GU",
    "DM_FER2_REGOLE_OPERATIVE",
    "DM_FER2_DESCRIZIONE",
    "DM_BIOGAS_2012",
    "UNI_TS_11567",
    "JEC_WTT_V5",
    # energetici
    "LHV_BIOMETHANE_MJ_NM3",
    "NM3_TO_MWH",
    "METHANE_PURITY_PCT",
    # comparator + soglie
    "COMPARATOR_GRID_HEAT_GCO2_MJ",
    "COMPARATOR_TRANSPORT_GCO2_MJ",
    "COMPARATOR_CHP_EU_MIX_GCO2_MJ",
    "SAVING_THRESHOLD_GRID_HEAT",
    "SAVING_THRESHOLD_TRANSPORT",
    "SAVING_THRESHOLD_CHP",
    # CIC
    "GCAL_PER_CIC",
    "MWH_PER_CIC",
    "CIC_PRICE_DEFAULT_EUR",
    "ANNEX_IX_THRESHOLD",
    # FER 2
    "FER2_KWE_CAP",
    "FER2_TARIFFA_BASE_DEFAULT_EUR_MWH",
    "FER2_PREMIO_MATRICE_DEFAULT_EUR_MWH",
    "FER2_PREMIO_CAR_DEFAULT_EUR_MWH",
    "FER2_FEEDSTOCK_REQ_THRESHOLD",
    "FER2_PERIODO_ANNI",
    "FER2_GHG_THRESHOLD",
    "FER2_CAP_COLTURE_DEDICATE",
    # manure credits
    "MANURE_CREDIT_LIQUAME_SUINO",
    "MANURE_CREDIT_LIQUAME_BOVINO",
    "MANURE_CREDIT_LETAME_PALABILE",
    "MANURE_CREDIT_POLLINA_BROILER",
    "MANURE_CREDIT_POLLINA_OVAIOLE",
]
