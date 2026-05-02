# -*- coding: utf-8 -*-
"""
metaniq_numeric.py — Utilità di formattazione numerica per Metan.iQ.

Fornisce:
  - fmt_it(value, decimals, suffix, signed)  : formato italiano (1.234,56)
  - fmt_en(value, decimals, suffix, signed)  : formato inglese  (1,234.56)
  - fmt_num(value, decimals, suffix, signed, lang) : lang-aware
  - parse_it(text)  : parse dal formato italiano (con euristica 3-cifre)
  - parse_en(text)  : parse dal formato inglese
  - parse_num(text, lang) : lang-aware

Nota: app_mensile.py definisce internamente fmt_it/parse_it per compatibilità
storica — questi sono funzioni equivalenti esportabili per i moduli secondari.
"""
from __future__ import annotations


def fmt_it(value: float, decimals: int = 0, suffix: str = "",
           signed: bool = False) -> str:
    """Formato italiano: separatore migliaia = '.', decimale = ','."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if (signed and v > 0) else ""
    fmt = f"{v:,.{decimals}f}"
    # Converti da formato Python (1,234.56) a italiano (1.234,56)
    formatted = fmt.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{formatted}{suffix}"


def fmt_en(value: float, decimals: int = 0, suffix: str = "",
           signed: bool = False) -> str:
    """Formato inglese: separatore migliaia = ',', decimale = '.'."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if (signed and v > 0) else ""
    formatted = f"{v:,.{decimals}f}"
    return f"{sign}{formatted}{suffix}"


def fmt_num(value: float, decimals: int = 0, suffix: str = "",
            signed: bool = False, lang: str = "it") -> str:
    """Formato numero lang-aware."""
    if lang == "en":
        return fmt_en(value, decimals, suffix, signed)
    return fmt_it(value, decimals, suffix, signed)


def parse_it(text: object) -> float:
    """Parsa un numero in formato italiano (1.234,56 → 1234.56).

    Euristica identica a app_mensile.parse_it:
      - Virgola presente → punto = migliaia, virgola = decimale
        es. '1.234,56' → 1234.56,  '1234,56' → 1234.56
      - Solo punto, più di un punto → tutti separatori migliaia
        es. '1.234.567' → 1234567
      - Solo un punto + ESATTAMENTE 3 cifre a destra E parte intera ≠ '0'
        → separatore migliaia: '1.800' → 1800, '26.303' → 26303
      - Parte intera = '0' con 3 cifre decimali → decimale:
        '0.800' → 0.8 (non 800!), '0.100' → 0.1
      - Altrimenti il punto è decimale: '1234.56' → 1234.56, '0.05' → 0.05
    """
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace("��", "").replace("%", "").strip()
    if not s or s == "-":
        return 0.0
    has_comma = "," in s
    if has_comma:
        # Italiano completo: punti = migliaia, virgola = decimale
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        many_dots = len(parts) > 2
        single_thousand = (
            len(parts) == 2
            and len(parts[1]) == 3
            and parts[0].lstrip("-").isdigit()
            and parts[1].isdigit()
            and parts[0].lstrip("-") != "0"  # '0.800' è 0.8, non 800
        )
        if many_dots or single_thousand:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_en(text: object) -> float:
    """Parsa un numero in formato inglese (1,234.56 → 1234.56)."""
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_num(text: object, lang: str = "it") -> float:
    """Parse numero lang-aware."""
    if lang == "en":
        return parse_en(text)
    return parse_it(text)
