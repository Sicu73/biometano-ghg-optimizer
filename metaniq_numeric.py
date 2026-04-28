"""Metan.iQ — utility numeriche compliance-grade.

Modulo piccolo, isolato e testabile. Serve a togliere dal file Streamlit
la logica fragile di parsing/formattazione numerica.

Regole principali:
- virgola = separatore decimale italiano;
- punti prima della virgola = separatori migliaia;
- punto senza virgola = decimale, salvo casi inequivocabili di migliaia;
- `0.800` deve restare 0.8, non 800.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from numbers import Number

import math


def parse_it(value) -> float:
    """Converte input numerici italiani/anglosassoni in float.

    Esempi attesi:
    - "1.234,56" -> 1234.56
    - "1234,56"  -> 1234.56
    - "1234.56"  -> 1234.56
    - "0.800"    -> 0.8
    - "1.800"    -> 1800.0
    - "26.303"   -> 26303.0

    Nota: un singolo punto seguito da 3 cifre è trattato come migliaia
    solo se la parte sinistra è diversa da zero e ha 1-3 cifre.
    Questo preserva i decimali anglosassoni tipo 0.800.
    """
    if value is None:
        return 0.0

    if isinstance(value, Number):
        try:
            f = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(f) or math.isinf(f) else f

    s = str(value).strip()
    if not s or s == "-":
        return 0.0

    # Pulizia conservativa: togli simboli comuni, spazi e apostrofi migliaia.
    s = (
        s.replace("€", "")
        .replace("%", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("'", "")
        .strip()
    )

    if not s or s == "-":
        return 0.0

    # Formato italiano completo: 1.234,56 oppure 1234,56
    if "," in s:
        normalized = s.replace(".", "").replace(",", ".")
        return _safe_float(normalized)

    # Nessuna virgola: valutiamo il punto.
    if "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            # 1.234.567 -> migliaia, purché tutti i gruppi dopo il primo siano da 3 cifre.
            left = parts[0].lstrip("-")
            groups = parts[1:]
            if left.isdigit() and all(g.isdigit() and len(g) == 3 for g in groups):
                return _safe_float(s.replace(".", ""))
            return _safe_float(s)

        left_raw, right = parts
        left = left_raw.lstrip("-")
        if left.isdigit() and right.isdigit():
            # Caso critico: 0.800 deve essere decimale.
            if left == "0":
                return _safe_float(s)

            # 1.800 / 26.303 come migliaia; 1234.567 come decimale tecnico.
            if len(right) == 3 and 1 <= len(left) <= 3:
                return _safe_float(s.replace(".", ""))

        return _safe_float(s)

    return _safe_float(s)


def _safe_float(normalized: str) -> float:
    """Conversione robusta via Decimal, fallback 0.0."""
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError):
        return 0.0


def fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:
    """Formatta un numero in stile italiano: 1.234.567,89."""
    if value is None:
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "-"
    if math.isnan(f) or math.isinf(f):
        return "-"
    s = f"{f:+,.{decimals}f}" if signed else f"{f:,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".") + suffix
