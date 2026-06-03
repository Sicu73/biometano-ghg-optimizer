# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/version.py — Versione canonica software Metan.iQ.

Singolo punto di verita' per la versione, l'anno copyright e
la stringa di footer mostrata in UI / report / export.
"""
from __future__ import annotations

__version__ = "0.5.0"
__year__ = 2026
__product__ = "Metan.iQ"

FOOTER = f"{__product__} v{__version__} — © {__year__}"

# Riferimenti normativi canonici usati nei calcoli (per audit trail export)
NORMATIVE_REFERENCES = {
    "DM 15/9/2022": "Tariffe biometano immissione in rete (TR per scaglione di taglia, durata 15 anni)",
    "RED III": "Direttiva (UE) 2023/2413 — soglie saving GHG, metodologia Allegato V Parte C",
    "D.Lgs. 5/2026": "Recepimento italiano RED III",
    "UNI-TS 11567:2024": "Calcolo emissioni GHG biocombustibili (standard rese)",
    "GSE Linee Guida 2024": "Modalità operative attuative DM 2022",
    "JEC WTT v5": "Joint Research Centre Well-to-Tank dataset (fattori emissivi default)",
}

VALIDATION_WARNING = (
    "⚠️ I valori riportati sono il risultato di un calcolo basato sui dati "
    "inseriti dall'operatore e su parametri standard (UNI-TS 11567:2024, "
    "RED III, JEC WTT v5). Per certificazioni ufficiali GSE / autorità "
    "competenti, i dati devono essere validati da consulente tecnico "
    "qualificato (RINA, SGS, ISCC) o tramite audit interno dedicato."
)


def get_version() -> str:
    """Restituisce la versione canonica del software."""
    return __version__


def get_footer() -> str:
    """Stringa di footer (versione + copyright) per UI / PDF / Excel."""
    return FOOTER


__all__ = [
    "__version__",
    "__year__",
    "__product__",
    "FOOTER",
    "NORMATIVE_REFERENCES",
    "VALIDATION_WARNING",
    "get_version",
    "get_footer",
]
