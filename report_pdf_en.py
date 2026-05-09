# -*- coding: utf-8 -*-
"""report_pdf_en.py — Wrapper English per il generatore PDF Metan.iQ.

Mantenuto per compatibilità con test e script batch che necessitano
di forzare la lingua inglese senza modificare il ctx originale.
Per uso in produzione prefer build_pdf_from_output (export/pdf_export.py).
"""
from __future__ import annotations
from io import BytesIO
from report_pdf import build_metaniq_pdf


def build_metaniq_pdf_en(ctx: dict) -> BytesIO:
    """Genera il PDF in inglese (copia difensiva del ctx, forza lang='en')."""
    return build_metaniq_pdf({**ctx, "lang": "en"})
