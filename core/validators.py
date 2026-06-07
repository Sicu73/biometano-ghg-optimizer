# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/validators.py — Validatori input per Metan.iQ.

Funzioni di validazione che operano su dati di input gia' raccolti
dalla UI (sidebar, data_editor). Restituiscono liste di errori/warning
senza toccare Streamlit.

Tutte le funzioni seguono la convenzione:
  validate_*(data) -> tuple[bool, list[str], list[str]]
  returns: (is_valid, errors, warnings)

Le funzioni sono SENZA effetti collaterali (no state mutation,
no st.* calls) e sono testabili in isolamento.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Validazione INPUT GIORNALIERO (gestione operativa)
# ---------------------------------------------------------------------------

def validate_daily_entry(
    entry_date: Any,
    feedstocks: dict,
    allowed_feeds: list | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Valida un singolo input giornaliero.

    Args:
        entry_date:     data del giorno (datetime.date o stringa ISO).
        feedstocks:     {tipologia: quantita_t}, t/giorno.
        allowed_feeds:  elenco tipologie ammesse (se None: nessun controllo).

    Returns:
        (is_valid, errors, warnings)
    """
    from datetime import date as _date

    errors: list[str] = []
    warnings: list[str] = []

    d_obj = entry_date
    if isinstance(entry_date, str):
        try:
            d_obj = _date.fromisoformat(entry_date)
        except ValueError:
            errors.append(f"Data non valida: '{entry_date}' (formato ISO atteso).")
            d_obj = None
    if d_obj is not None and not isinstance(d_obj, _date):
        errors.append("Data: tipo non riconosciuto, atteso datetime.date.")

    if not isinstance(feedstocks, dict):
        errors.append("Feedstocks: deve essere un dizionario.")
        return (False, errors, warnings)

    for fname, qty in feedstocks.items():
        if qty is None:
            continue
        try:
            qv = float(qty)
        except (TypeError, ValueError):
            errors.append(f"Quantita' non numerica per '{fname}': {qty!r}.")
            continue
        if qv < 0:
            errors.append(
                f"Quantita' negativa non ammessa per '{fname}': {qv:g} t."
            )
        if allowed_feeds is not None and fname not in allowed_feeds:
            warnings.append(
                f"Tipologia '{fname}' non riconosciuta nel database biomasse."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings
