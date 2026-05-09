# -*- coding: utf-8 -*-
"""core/design_tokens.py — Colori brand Metan.iQ (singolo punto di verita').

Stringhe hex senza '#': compatibili con openpyxl PatternFill / Font.
Per reportlab usare: colors.HexColor("#" + NAVY)
"""
from __future__ import annotations

NAVY      = "0F172A"
NAVY_2    = "1E293B"
AMBER     = "F59E0B"
AMBER_DK  = "B45309"
AMBER_BG  = "FEF3C7"
SLATE_50  = "F8FAFC"
SLATE_100 = "F1F5F9"
SLATE_200 = "E2E8F0"
SLATE_400 = "94A3B8"
SLATE_500 = "64748B"
SLATE_700 = "334155"
EMERALD_BG = "D1FAE5"
EMERALD_FG = "065F46"
RED_BG    = "FECACA"
RED_FG    = "991B1B"
WHITE     = "FFFFFF"

__all__ = [
    "NAVY", "NAVY_2",
    "AMBER", "AMBER_DK", "AMBER_BG",
    "SLATE_50", "SLATE_100", "SLATE_200", "SLATE_400", "SLATE_500", "SLATE_700",
    "EMERALD_BG", "EMERALD_FG",
    "RED_BG", "RED_FG",
    "WHITE",
]
