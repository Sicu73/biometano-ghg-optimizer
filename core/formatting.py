# -*- coding: utf-8 -*-
"""core/formatting.py — Helpers di formattazione locale-aware (IT/EN).

API pubblica:
  fmt_num(value, decimals, suffix, signed, lang)  -> stringa numero localizzata
  fmt_date(d, lang)                                -> stringa data localizzata

Convenzioni:
  - IT: "1.234.567,89" (punto migliaia, virgola decimale), date "25/05/2026"
  - EN: "1,234,567.89" (virgola migliaia, punto decimale), date "May 25, 2026"

`lang` segue ordine:
  1. parametro esplicito
  2. i18n_runtime.get_lang() (Streamlit session_state["lang"])
  3. default "it"
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def _detect_lang(lang: str | None) -> str:
    if lang in ("it", "en"):
        return lang
    try:
        from i18n_runtime import get_lang
        v = get_lang()
        return v if v in ("it", "en") else "it"
    except Exception:  # noqa: BLE001
        return "it"


def fmt_num(
    value: Any,
    decimals: int = 0,
    suffix: str = "",
    signed: bool = False,
    lang: str | None = None,
) -> str:
    """Formatta numero in stile italiano o inglese (locale-aware).

    Args:
        value: numero (int, float, str numerica). None / NaN / Inf → '-'.
        decimals: cifre decimali.
        suffix: stringa appesa (es. ' Sm³', '%').
        signed: True → prefisso '+' anche per positivi.
        lang: 'it' / 'en' / None (auto).

    Examples:
        >>> fmt_num(1234.56, 2, lang="it")
        '1.234,56'
        >>> fmt_num(1234.56, 2, lang="en")
        '1,234.56'
        >>> fmt_num(0.123, 1, '%', lang="en")
        '0.1%'
        >>> fmt_num(None)
        '-'
    """
    import math
    if value is None:
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f) or math.isinf(f):
        return "-"

    lang = _detect_lang(lang)
    if signed:
        s = f"{f:+,.{decimals}f}"
    else:
        s = f"{f:,.{decimals}f}"
    if lang == "en":
        return s + suffix
    # IT: swap "," ↔ "." via placeholder per evitare collisioni
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def fmt_date(d: Any, lang: str | None = None) -> str:
    """Formatta data locale-aware.

    Accetta `datetime.date` / `datetime.datetime` / `pd.Timestamp` / stringa
    parsabile. Restituisce '' se non parsabile.

    Examples:
        >>> from datetime import date
        >>> fmt_date(date(2026, 5, 25), 'it')
        '25/05/2026'
        >>> fmt_date(date(2026, 5, 25), 'en')
        'May 25, 2026'
    """
    if d is None:
        return ""
    lang = _detect_lang(lang)
    if isinstance(d, str):
        try:
            d = pd.to_datetime(d, errors="coerce")
            if pd.isna(d):
                return ""
        except Exception:  # noqa: BLE001
            return ""
    try:
        if lang == "en":
            return d.strftime("%b %d, %Y")
        return d.strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001
        return str(d)


# Backward-compat aliases (vecchi nomi usati nel codice legacy).
fmt_it = fmt_num
_it_num = lambda value, decimals=2: fmt_num(value, decimals)  # noqa: E731


__all__ = ["fmt_num", "fmt_date", "fmt_it", "_it_num"]
