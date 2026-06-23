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
    """Renderizza il selettore Italiano/English nella sidebar."""
    import streamlit as st

    lang = st.session_state.get("lang", "it")
    accent = _ACCENT

    st.sidebar.markdown(
        f"""
        <style>
        .miq-lang-container {{
            margin-bottom: 20px;
        }}
        .miq-lang-active-note {{
            color: {_MUTED};
            font-size: 0.72rem;
            margin: 6px 0 8px 2px;
        }}
        </style>

        <div class="miq-lang-container">
            <div style='font-size:0.7rem; font-weight:700; letter-spacing:1px;
                 text-transform:uppercase; color:#64748B; margin-left:2px;'>
                 🌐 Language / Lingua
            </div>
            <div class="miq-lang-active-note">
                Lingua attiva: <b style="color:{accent};">{'Italiano' if lang == 'it' else 'English'}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        _hc1, _hc2 = st.columns(2)
        with _hc1:
            if st.button(
                "IT",
                key="btn_lang_it",
                use_container_width=True,
                type="primary" if lang == "it" else "secondary",
                help="Italiano",
            ):
                st.session_state["lang"] = "it"
                st.rerun()
        with _hc2:
            if st.button(
                "EN",
                key="btn_lang_en",
                use_container_width=True,
                type="primary" if lang == "en" else "secondary",
                help="English",
            ):
                st.session_state["lang"] = "en"
                st.rerun()

    return lang
