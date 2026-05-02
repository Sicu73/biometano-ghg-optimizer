# -*- coding: utf-8 -*-
"""
metaniq_numeric.py — Formattazione numerica lang-aware per Metan.iQ.

API:
  fmt_it(v, dec, suffix, signed)        -> "1.234,56"
  fmt_en(v, dec, suffix, signed)        -> "1,234.56"
  fmt_num(v, dec, suffix, signed, lang) -> lang-aware
  parse_it(text)                        -> float
"""
from __future__ import annotations


def fmt_it(value: float, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if (signed and v > 0) else ""
    fmt = f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{fmt}{suffix}"


def fmt_en(value: float, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if (signed and v > 0) else ""
    return f"{sign}{v:,.{decimals}f}{suffix}"


def fmt_num(value: float, decimals: int = 0, suffix: str = "", signed: bool = False,
            lang: str = "it") -> str:
    return fmt_en(value, decimals, suffix, signed) if lang == "en" \
        else fmt_it(value, decimals, suffix, signed)


def parse_it(text: object) -> float:
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0
