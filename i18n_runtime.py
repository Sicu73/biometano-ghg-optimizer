# -*- coding: utf-8 -*-
"""
i18n_runtime.py — Runtime lingua Metan.iQ.

API pubblica:
  t(text, lang=None)           -> testo tradotto IT->EN se lang='en'
  get_lang()                   -> 'it' o 'en' da session_state
  render_lang_selector()       -> renderizza pulsanti Italiano/English in sidebar
  translate_df(df, lang=None)  -> DataFrame con colonne tradotte
"""
from __future__ import annotations
from metaniq_i18n import IT_EN


def get_lang() -> str:
    try:
        import streamlit as st
        return str(st.session_state.get("lang", "it"))
    except Exception:
        return "it"


def t(text: object, lang: str | None = None) -> object:
    """Traduce text IT->EN. Se lang è None usa get_lang()."""
    if lang is None:
        lang = get_lang()
    if lang != "en" or not isinstance(text, str):
        return text
    for k, v in sorted(IT_EN.items(), key=lambda p: -len(p[0])):
        text = text.replace(k, v)
    return text


def translate_df(df, lang: str | None = None):
    """Restituisce copia del DataFrame con colonne tradotte."""
    if lang is None:
        lang = get_lang()
    if lang != "en":
        return df
    return df.rename(columns={c: t(str(c), lang) for c in df.columns})


def render_lang_selector() -> str:
    """Renderizza il selettore Italiano/English nella sidebar.

    Chiamare una sola volta all'inizio di ``with st.sidebar:``.
    Ritorna la lingua corrente ('it' o 'en').
    """
    import streamlit as st

    if "lang" not in st.session_state:
        st.session_state["lang"] = "it"

    st.sidebar.markdown(
        "<div style='font-size:0.7rem;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;color:#64748B;margin-bottom:4px;"
        "padding-left:2px;'>🌐 Language / Lingua</div>",
        unsafe_allow_html=True,
    )
    _lc1, _lc2 = st.sidebar.columns(2)
    with _lc1:
        if st.button(
            "🇮🇹 Italiano",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "it" else "secondary",
            key="btn_lang_it",
        ):
            st.session_state["lang"] = "it"
            st.rerun()
    with _lc2:
        if st.button(
            "🇬🇧 English",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "en" else "secondary",
            key="btn_lang_en",
        ):
            st.session_state["lang"] = "en"
            st.rerun()
    st.sidebar.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)
    return st.session_state.get("lang", "it")
