# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/design_tokens.py — Design tokens condivisi Metan.iQ.

Singola fonte di verità per i colori del brand che ricorrono in più moduli
(UI Streamlit, generatore PDF, selettore lingua i18n_runtime). Esporta hex
strings pure (no dipendenze): chi le consuma le converte come gli serve
(string CSS per Streamlit, ``colors.HexColor(...)`` per reportlab).

NB: la palette completa NON è qui. Il tema Web (Material 3, blu petrolio
#006494) e il tema Print (Navy scuro #0F172A) divergono per scelta di
design (leggibilità schermo vs stampa). Qui stanno solo i token che sono
**identici per definizione** in entrambi i contesti.
"""
from __future__ import annotations

# Brand accent (warning/highlight)
AMBER         = "#F59E0B"
AMBER_DARK    = "#B45309"
AMBER_BG      = "#FEF3C7"

# Slate scale (Tailwind-compatible) — bordi, testo secondario, sfondi neutri
SLATE_50      = "#F8FAFC"
SLATE_100     = "#F1F5F9"
SLATE_200     = "#E2E8F0"
SLATE_400     = "#94A3B8"
SLATE_500     = "#64748B"
SLATE_600     = "#475569"
SLATE_700     = "#334155"
SLATE_800     = "#1E293B"
SLATE_900     = "#0F172A"

# Stati semantici
EMERALD       = "#10B981"   # success
RED           = "#DC2626"   # error
RED_BG_SOFT   = "#FFD6D6"   # alert background (cap autorizzativo violato)
RED_FG_SOFT   = "#B00020"   # alert foreground

# Neutri assoluti
WHITE         = "#FFFFFF"
BLACK         = "#000000"


# Dict comodo per chi vuole accedere by-name (es. CSS variables)
PALETTE: dict[str, str] = {
    "amber":       AMBER,
    "amber_dark":  AMBER_DARK,
    "amber_bg":    AMBER_BG,
    "slate_50":    SLATE_50,
    "slate_100":   SLATE_100,
    "slate_200":   SLATE_200,
    "slate_400":   SLATE_400,
    "slate_500":   SLATE_500,
    "slate_600":   SLATE_600,
    "slate_700":   SLATE_700,
    "slate_800":   SLATE_800,
    "slate_900":   SLATE_900,
    "emerald":     EMERALD,
    "red":         RED,
    "white":       WHITE,
    "black":       BLACK,
}


__all__ = [
    "AMBER", "AMBER_DARK", "AMBER_BG",
    "SLATE_50", "SLATE_100", "SLATE_200", "SLATE_400", "SLATE_500",
    "SLATE_600", "SLATE_700", "SLATE_800", "SLATE_900",
    "EMERALD", "RED", "RED_BG_SOFT", "RED_FG_SOFT",
    "WHITE", "BLACK",
    "PALETTE",
]
