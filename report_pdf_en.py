# -*- coding: utf-8 -*-
"""
report_pdf_en.py — Wrapper English per il generatore PDF Metan.iQ.

Garantisce che il PDF sia sempre in inglese passando lang='en' nel ctx,
anche se la session_state non è disponibile (es. test standalone).

Uso:
    from report_pdf_en import build_metaniq_pdf_en
    buf = build_metaniq_pdf_en(ctx)

In app_mensile.py il ctx contiene già 'lang' dalla session_state;
questo modulo è utile per test, CI/CD o generazione batch in inglese.
"""
from __future__ import annotations
from io import BytesIO
from report_pdf import build_metaniq_pdf


def build_metaniq_pdf_en(ctx: dict) -> BytesIO:
    """Genera il PDF Metan.iQ in inglese.

    Forza lang='en' nel ctx (copia difensiva: non altera il dict originale).
    """
    ctx_en = dict(ctx)
    ctx_en["lang"] = "en"
    return build_metaniq_pdf(ctx_en)
