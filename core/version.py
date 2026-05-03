# -*- coding: utf-8 -*-
"""core/version.py — Versione canonica software Metan.iQ.

Singolo punto di verita' per la versione, l'anno copyright e
la stringa di footer mostrata in UI / report / export.
"""
from __future__ import annotations

__version__ = "0.4.0"
__year__ = 2026
__product__ = "Metan.iQ"

FOOTER = f"{__product__} v{__version__} — © {__year__}"


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
    "get_version",
    "get_footer",
]
