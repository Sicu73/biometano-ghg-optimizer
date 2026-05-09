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


# ---------------------------------------------------------------------------
# Bandiere SVG inline — rendering identico su Windows / macOS / Android.
# Usiamo SVG vettoriali sopra a bottoni Streamlit standard. Nessun JS bridge
# (che falliva intermittentemente nell'iframe sandbox di Streamlit Cloud) e
# nessuna dipendenza da emoji/font esterni.
# ---------------------------------------------------------------------------
_FLAG_IT_SVG = (
    "<svg width='40' height='27' viewBox='0 0 3 2' "
    "xmlns='http://www.w3.org/2000/svg' "
    "style='border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.25);"
    "vertical-align:middle;'>"
    "<rect width='1' height='2' fill='#009246'/>"
    "<rect x='1' width='1' height='2' fill='#FFFFFF'/>"
    "<rect x='2' width='1' height='2' fill='#CE2B37'/>"
    "</svg>"
)

_FLAG_GB_SVG = (
    "<svg width='40' height='27' viewBox='0 0 60 30' "
    "xmlns='http://www.w3.org/2000/svg' "
    "style='border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.25);"
    "vertical-align:middle;'>"
    "<clipPath id='gb-t'>"
    "<path d='M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z'/>"
    "</clipPath>"
    "<path d='M0,0 v30 h60 v-30 z' fill='#012169'/>"
    "<path d='M0,0 L60,30 M60,0 L0,30' stroke='#fff' stroke-width='6'/>"
    "<path d='M0,0 L60,30 M60,0 L0,30' clip-path='url(#gb-t)' "
    "stroke='#C8102E' stroke-width='4'/>"
    "<path d='M30,0 v30 M0,15 h60' stroke='#fff' stroke-width='10'/>"
    "<path d='M30,0 v30 M0,15 h60' stroke='#C8102E' stroke-width='6'/>"
    "</svg>"
)


def render_lang_selector() -> str:
    """Renderizza il selettore Italiano/English nella sidebar.

    Bandiere SVG inline (vettoriali, identiche su tutti i sistemi) sopra a
    bottoni Streamlit nativi. Niente JS bridge, niente font emoji.
    Chiamare una sola volta all'inizio di ``with st.sidebar:``.
    Ritorna la lingua corrente ('it' o 'en').
    """
    import streamlit as st

    if "lang" not in st.session_state:
        st.session_state["lang"] = "it"

    st.sidebar.markdown(
        "<div style='font-size:0.7rem;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;color:#64748B;margin-bottom:6px;"
        "padding-left:2px;'>🌐 Language / Lingua</div>",
        unsafe_allow_html=True,
    )

    _lc1, _lc2 = st.sidebar.columns(2)
    with _lc1:
        st.markdown(
            f"<div style='display:flex;justify-content:center;"
            f"margin-bottom:4px;line-height:0;'>{_FLAG_IT_SVG}</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Italiano",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "it" else "secondary",
            key="btn_lang_it",
        ):
            st.session_state["lang"] = "it"
            st.rerun()
    with _lc2:
        st.markdown(
            f"<div style='display:flex;justify-content:center;"
            f"margin-bottom:4px;line-height:0;'>{_FLAG_GB_SVG}</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "English",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "en" else "secondary",
            key="btn_lang_en",
        ):
            st.session_state["lang"] = "en"
            st.rerun()
    st.sidebar.markdown(
        "<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True
    )
    return st.session_state.get("lang", "it")
