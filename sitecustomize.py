# -*- coding: utf-8 -*-
"""
sitecustomize.py — Compatibilità legacy Metan.iQ i18n.

Questo modulo era il precedente sistema di patching automatico di Streamlit.
Il nuovo sistema usa i18n_runtime.py (render_lang_selector + _t()).
Mantenuto per retrocompatibilità; non chiama più _patch() per evitare
conflitti con il selettore esplicito in app_mensile.py.

Per il dizionario di traduzione completo: metaniq_i18n.IT_EN
Per il runtime di traduzione: i18n_runtime
"""
from __future__ import annotations

# Importa il dizionario aggiornato dal nuovo modulo
try:
    from metaniq_i18n import IT_EN as TR
except ImportError:
    TR = {}


def _lang():
    try:
        import streamlit as st
        return st.session_state.get('lang', 'it')
    except Exception:
        return 'it'


def _t(x):
    """Traduce x IT->EN se lang=='en'. Compatibilità legacy."""
    if _lang() != 'en' or not isinstance(x, str):
        return x
    for a, b in sorted(TR.items(), key=lambda p: len(p[0]), reverse=True):
        x = x.replace(a, b)
    return x
