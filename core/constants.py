# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
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

LHV_BIOMETHANE_MJ_NM3 = 35.24         # MJ/Nm³ biometano spec rete (UNI EN 16723-1, ~98% CH4)
PCI_BIOMETHANE_KWH_SMC = 9.79         # kWh/Sm³ PCI biometano spec rete (UNI EN 16723-1)
NM3_TO_MWH = 0.00979                  # MWh/Sm³ = PCI_BIOMETHANE_KWH_SMC / 1000 (letterale per esattezza float)
METHANE_PURITY_PCT = 98.0             # purezza biometano default (%) — spec rete

# ---------------------------------------------------------------------------
# Stoccaggio digestato - Emissioni fuggitive (gCO2eq/MJ biometano)
# UNI/TS 11567:2024 e Linee Guida GSE 2024.
# ---------------------------------------------------------------------------
EP_DIGESTATE_CHIUSO_60D = 0.0
EP_DIGESTATE_CHIUSO_30D = 1.6
EP_DIGESTATE_BREVE_TERMINE = 6.4
EP_DIGESTATE_APERTO = 15.0


# ---------------------------------------------------------------------------
# Comparator fossili (gCO2eq/MJ) e soglie saving (frazione 0..1)
# ---------------------------------------------------------------------------

COMPARATOR_GRID_HEAT_GCO2_MJ = 80.0      # RED III Annex VI Part B
COMPARATOR_TRANSPORT_GCO2_MJ = 94.0      # RED III Annex V Part C
COMPARATOR_CHP_EU_MIX_GCO2_MJ = 183.0    # RED III Annex VI

SAVING_THRESHOLD_GRID_HEAT = 0.80        # impianti in esercizio dal 1/1/2026 — art. 29(10)(d) Dir. 2018/2001 consolidata
SAVING_THRESHOLD_TRANSPORT = 0.65
SAVING_THRESHOLD_CHP = 0.80


# ---------------------------------------------------------------------------
# Manure credit (gCO2eq/MJ) — GSE LG 2024 / IPCC 2019 Vol.4 Cap.10
# ---------------------------------------------------------------------------
# NOTA AUDIT: questi sono i valori del "manure credit" puro (esca, beneficio
# da stoccaggio anaerobico). Il database operativo `FEEDSTOCK_DB` in
# app_mensile.py espone l'`eec` AGGREGATO (eec_baseline + esca + handling)
# secondo la prassi GSE LG 2024 di incorporarli nell'eec di filiera. Per la
# pollina ovaiole in stoccaggio aerobico l'`eec` operativo (+5.0) include le
# emissioni residue di gestione che il puro manure credit (=0.0) non copre.
# Allineare i due moduli quando si rifattorizza il calcolo eec.

MANURE_CREDIT_LIQUAME_SUINO = -45.0
MANURE_CREDIT_LIQUAME_BOVINO = -45.0
MANURE_CREDIT_LETAME_PALABILE = -30.0
MANURE_CREDIT_POLLINA_BROILER = -15.0
MANURE_CREDIT_POLLINA_OVAIOLE = 0.0  # vs FEEDSTOCK_DB eec=+5.0 (handling aerobico)


# ---------------------------------------------------------------------------
# Aux factor (netto -> lordo) — single source of truth
# ---------------------------------------------------------------------------
# Default JRC-CONCAWE per perdite upgrading + autoconsumi caldaia/RTO.
# Storicamente duplicato in app_mensile.py e core/calculation_engine.py;
# qui centralizzato per evitare divergenze al primo aggiornamento JEC WTT.
# (revisione 2026-06-06: cache-bust per Streamlit Cloud .pyc stale)
# (revisione 2026-06-09: cache-bust bis — ImportError PCI_BIOMETHANE_KWH_SMC
#  su Cloud con codice remoto corretto: stesso sintomo .pyc stale)
DEFAULT_AUX_FACTOR = 1.29


__all__ = [
    # riferimenti normativi
    "RED_III_DIRECTIVE",
    "DLGS_RED_III_RECEPIMENTO",
    "DLGS_RED_III_NUMERO",
    "DLGS_RED_III_DATA",
    "DLGS_RED_III_GU",
    "DLGS_RED_III_VIGORE",
    "UNI_TS_11567",
    "JEC_WTT_V5",
    # energetici
    "LHV_BIOMETHANE_MJ_NM3",
    "PCI_BIOMETHANE_KWH_SMC",
    "NM3_TO_MWH",
    "METHANE_PURITY_PCT",
    # comparator + soglie
    "COMPARATOR_GRID_HEAT_GCO2_MJ",
    "COMPARATOR_TRANSPORT_GCO2_MJ",
    "COMPARATOR_CHP_EU_MIX_GCO2_MJ",
    "SAVING_THRESHOLD_GRID_HEAT",
    "SAVING_THRESHOLD_TRANSPORT",
    "SAVING_THRESHOLD_CHP",
    # manure credits
    "MANURE_CREDIT_LIQUAME_SUINO",
    "MANURE_CREDIT_LIQUAME_BOVINO",
    "MANURE_CREDIT_LETAME_PALABILE",
    "MANURE_CREDIT_POLLINA_BROILER",
    "MANURE_CREDIT_POLLINA_OVAIOLE",
    # digestate storage
    "EP_DIGESTATE_CHIUSO_60D",
    "EP_DIGESTATE_CHIUSO_30D",
    "EP_DIGESTATE_BREVE_TERMINE",
    "EP_DIGESTATE_APERTO",
    # aux factor
    "DEFAULT_AUX_FACTOR",
]
