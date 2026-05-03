# -*- coding: utf-8 -*-
"""core/calendar.py — Utility calendario per la gestione giornaliera.

Funzioni di servizio per generare l'elenco di giorni di un mese
(con gestione corretta di anni bisestili) e produrre etichette mese
in italiano/inglese. NON usa Streamlit, e' testabile in isolamento.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date


_MONTH_LABELS_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
_MONTH_LABELS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def is_leap_year(year: int) -> bool:
    """True se l'anno e' bisestile (regola gregoriana)."""
    if year % 4 != 0:
        return False
    if year % 100 != 0:
        return True
    return year % 400 == 0


def days_in_month(year: int, month: int) -> int:
    """Restituisce il numero di giorni del mese (1-12), bisestili inclusi."""
    if month < 1 or month > 12:
        raise ValueError(f"month deve essere 1-12, ricevuto {month}")
    return monthrange(year, month)[1]


def generate_month_days(year: int, month: int) -> list[date]:
    """Genera la lista (ordinata) delle date del mese specificato.

    Gestisce automaticamente 28/29/30/31 giorni e l'anno bisestile.
    """
    n = days_in_month(year, month)
    return [date(year, month, d) for d in range(1, n + 1)]


def month_label(year: int, month: int, lang: str = "it") -> str:
    """Etichetta del mese, formato 'Mese AAAA' (es. 'Marzo 2024')."""
    if month < 1 or month > 12:
        raise ValueError(f"month deve essere 1-12, ricevuto {month}")
    labels = _MONTH_LABELS_EN if (lang or "it").lower().startswith("en") else _MONTH_LABELS_IT
    return f"{labels[month - 1]} {year}"


__all__ = [
    "is_leap_year",
    "days_in_month",
    "generate_month_days",
    "month_label",
]
