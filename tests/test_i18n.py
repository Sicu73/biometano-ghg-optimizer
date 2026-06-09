# -*- coding: utf-8 -*-
"""tests/test_i18n.py — Verifica del runtime i18n (i18n_runtime).

Nota storica: questo file testava anche core/i18n.py (catalogo key-based
IT/EN), implementazione parallela mai usata dall'app e rimossa nel
cleanup codice morto. Il runtime vivo e' i18n_runtime.t (substring
replacement su catalogo metaniq_i18n).
"""
from __future__ import annotations

from i18n_runtime import t as runtime_t


def test_runtime_i18n_does_not_retranslate_english_output():
    text = (
        "DM 15/9/2022 · pianificazione mensile e ottimizzazione GHG per "
        "biometano: tariffa diretta €/MWh, saving RED III/D.Lgs. 5/2026 "
        "per uso finale."
    )
    translated = runtime_t(text, "en")
    assert "monthly planning" in translated
    assert "plyearsng" not in translated


def test_runtime_i18n_it_passthrough():
    """Con lingua IT il testo italiano resta invariato."""
    text = "Pianificazione mensile e ottimizzazione GHG"
    assert runtime_t(text, "it") == text
