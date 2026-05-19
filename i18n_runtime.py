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
from core.design_tokens import AMBER as _ACCENT, SLATE_500 as _MUTED


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

    Approccio robusto: usa bottoni nativi Streamlit con label '🇮🇹 Italiano' /
    '🇬🇧 English' e li stila via CSS per apparire come card. Nessun trucco di
    bottoni nascosti (il vecchio approccio mostrava 'IT_HIDDEN'/'EN_HIDDEN'
    visibili in sidebar quando Streamlit cambiava il DOM dei widget).
    """
    import streamlit as st

    lang = st.session_state.get("lang", "it")
    accent = _ACCENT

    # CSS scoped ai due bottoni lingua via class injection sul wrapper-parent.
    st.sidebar.markdown(
        f"""
        <style>
        /* Header sezione lingua */
        .miq-lang-heading {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: #64748B;
            margin-left: 2px;
            margin-bottom: 4px;
        }}
        /* Stile dei bottoni lingua (basato sulla loro posizione nel sidebar) */
        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type
          [data-testid="stColumn"] .stButton button {{
            min-height: 56px !important;
            font-size: 0.85rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px !important;
            background: rgba(148,163,184,0.06) !important;
            border: 2px solid transparent !important;
            color: #475569 !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type
          [data-testid="stColumn"] .stButton button:hover {{
            background: rgba(148,163,184,0.14) !important;
            transform: translateY(-1px);
        }}
        /* Stato attivo via primary kind */
        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type
          [data-testid="stColumn"] .stButton button[kind="primary"] {{
            background: rgba(245,158,11,0.12) !important;
            border: 2px solid {accent} !important;
            color: {accent} !important;
        }}
        </style>
        <div class="miq-lang-heading">🌐 Language / Lingua</div>
        """,
        unsafe_allow_html=True,
    )

    _c1, _c2 = st.sidebar.columns(2)
    with _c1:
        if st.button(
            "🇮🇹 Italiano",
            key="btn_lang_it",
            use_container_width=True,
            type=("primary" if lang == "it" else "secondary"),
        ):
            st.session_state["lang"] = "it"
            st.rerun()
    with _c2:
        if st.button(
            "🇬🇧 English",
            key="btn_lang_en",
            use_container_width=True,
            type=("primary" if lang == "en" else "secondary"),
        ):
            st.session_state["lang"] = "en"
            st.rerun()

    return lang
