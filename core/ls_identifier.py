# -*- coding: utf-8 -*-
"""core/ls_identifier.py — Generatore ID Lotto di Sostenibilità (LS).

Conforme a UNI/TS 11567:2024 § Tracciabilità: ogni LS deve essere
identificato univocamente per periodo di rendicontazione e impianto.

Formato canonico:
    LS-{YYYY}-{MM}-{IMPIANTO_HASH}

dove IMPIANTO_HASH = primi 6 caratteri SHA1 del CUI (o, in fallback,
del nome impianto). Il formato e' stabile fra esecuzioni: dato lo stesso
CUI e periodo, l'ID e' identico (idempotente, audit-friendly).
"""
from __future__ import annotations

import hashlib
import re

_FALLBACK_PLANT_TOKEN = "NO-CUI"


def _slug6(value: str) -> str:
    v = (value or "").strip()
    if not v:
        v = _FALLBACK_PLANT_TOKEN
    return hashlib.sha1(v.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()


def build_ls_id(
    *,
    year: int,
    month: int,
    plant_cui: str = "",
    plant_name: str = "",
) -> str:
    """Costruisce un ID Lotto di Sostenibilità deterministico.

    Args:
        year: anno del periodo di rendicontazione (es. 2026).
        month: mese 1..12.
        plant_cui: codice CUI/GSE dell'impianto (preferito).
        plant_name: nome impianto (fallback se CUI assente).

    Returns:
        Stringa "LS-YYYY-MM-XXXXXX".

    Raises:
        ValueError: anno fuori range [2000-2099] o mese fuori [1-12].
    """
    if not (2000 <= int(year) <= 2099):
        raise ValueError(f"year fuori range 2000-2099: {year}")
    if not (1 <= int(month) <= 12):
        raise ValueError(f"month fuori range 1-12: {month}")
    token = plant_cui.strip() or plant_name.strip() or _FALLBACK_PLANT_TOKEN
    return f"LS-{int(year):04d}-{int(month):02d}-{_slug6(token)}"


def validate_ls_id(ls_id: str) -> bool:
    """Verifica formato canonico LS-YYYY-MM-XXXXXX (6 hex char)."""
    if not isinstance(ls_id, str):
        return False
    return bool(re.fullmatch(r"LS-\d{4}-(0[1-9]|1[0-2])-[0-9A-F]{6}", ls_id))


__all__ = ["build_ls_id", "validate_ls_id"]
