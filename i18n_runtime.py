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

    Cross-platform flag rendering:
        Le bandiere unicode (🇮🇹 🇬🇧) sono "Regional Indicator Symbols". Il
        rendering nativo varia per OS:
          - macOS/iOS: Apple Color Emoji → bandiere disegnate
          - Android: Noto Color Emoji → bandiere disegnate
          - Windows: Segoe UI Emoji NON disegna le bandiere (mostra "IT/GB"
            in quadratini)
        Iniettiamo Google Fonts "Noto Color Emoji" e una font-family con
        fallback ordinato (prima i font color emoji, poi sistema) sui bottoni
        della sidebar, così la bandiera è visibile su tutti i dispositivi.
    """
    import streamlit as st

    if "lang" not in st.session_state:
        st.session_state["lang"] = "it"

    st.sidebar.markdown(
        """
        <style>
        /* Nascondiamo il testo interno ai bottoni della lingua */
        div:has(#lang_anchor) ~ div button p {
            color: transparent !important;
        }
        /* Stile base bottoni lingua */
        div:has(#flag_it) + div button, div:has(#flag_en) + div button {
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            border-radius: 6px !important;
            height: 60px !important; /* Aumentato da 40 a 60 per proporzioni migliori */
            border: 1px solid rgba(0,0,0,0.2) !important;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        div:has(#flag_it) + div button:hover, div:has(#flag_en) + div button:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            border-color: #94A3B8 !important;
        }
        /* Bandiera Italiana (Ancorata) */
        div:has(#flag_it) + div button {
            background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzIDIiPjxyZWN0IHdpZHRoPSIxIiBoZWlnaHQ9IjIiIGZpbGw9IiMwMDhDNDUiLz48cmVjdCB3aWR0aD0iMSIgaGVpZ2h0PSIyIiB4PSIxIiBmaWxsPSIjRjRGNUYwIi8+PHJlY3Qgd2lkdGg9IjEiIGhlaWdodD0iMiIgeD0iMiIgZmlsbD0iI0NEMjEyQSIvPjwvc3ZnPg==') !important;
        }
        /* Bandiera UK (Ancorata) */
        div:has(#flag_en) + div button {
            background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2MCAzMCI+PGNsaXBQYXRoIGlkPSJ0Ij48cGF0aCBkPSJNMzAsMTUgaDMwIHYxNSB6IHYxNSBoLTMwIHogaC0zMCB2LTE1IHogdi0xNSBoMzAgeiIvPjwvY2xpcFBhdGg+PHBhdGggZD0iTTAsMCB2MzAgaDYwIHYtMzAgeiIgZmlsbD0iIzAxMjE2OSIvPjxwYXRoIGQ9Ik0wLDAgTDYwLDMwIE02MCwwIEwwLDMwIiBzdHJva2U9IiNmZmYiIHN0cm9rZS13aWR0aD0iNiIvPjxwYXRoIGQ9Ik0wLDAgTDYwLDMwIE02MCwwIEwwLDMwIiBjbGlwLXBhdGg9InVybCgjdCkiIHN0cm9rZT0iI0M4MTAyRSIgc3Ryb2tlLXdpZHRoPSI0Ii8+PHBhdGggZD0iTTMwLDAgdjMwIE0wLDE1IGg2MCIgc3Ryb2tlPSIjZmZmIiBzdHJva2Utd2lkdGg9IjEwIi8+PHBhdGggZD0iTTMwLDAgdjMwIE0wLDE1IGg2MCIgc3Ryb2tlPSIjQzgxMDJFIiBzdHJva2Utd2lkdGg9IjYiLz48L3N2Zz4=') !important;
        }
        /* Opacità per la lingua NON attiva */
        div:has(#flag_it) + div button[kind="secondary"], div:has(#flag_en) + div button[kind="secondary"] {
            opacity: 0.3 !important;
            filter: grayscale(80%) !important;
        }
        div:has(#flag_it) + div button[kind="primary"], div:has(#flag_en) + div button[kind="primary"] {
            opacity: 1.0 !important;
            border: 2px solid #0F172A !important;
            box-shadow: 0 0 0 2px rgba(255,255,255,0.5);
            filter: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        "<div id='lang_anchor' style='font-size:0.7rem;font-weight:600;letter-spacing:1px;"
        "text-transform:uppercase;color:#64748B;margin-bottom:4px;"
        "padding-left:2px;'>🌐 Language / Lingua</div>",
        unsafe_allow_html=True,
    )
    _lc1, _lc2 = st.sidebar.columns(2)
    with _lc1:
        st.markdown("<div id='flag_it'></div>", unsafe_allow_html=True)
        if st.button(
            "IT",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "it" else "secondary",
            key="btn_lang_it",
            help="Italiano",
        ):
            st.session_state["lang"] = "it"
            st.rerun()
    with _lc2:
        st.markdown("<div id='flag_en'></div>", unsafe_allow_html=True)
        if st.button(
            "EN",
            use_container_width=True,
            type="primary" if st.session_state["lang"] == "en" else "secondary",
            key="btn_lang_en",
            help="English",
        ):
            st.session_state["lang"] = "en"
            st.rerun()
    st.sidebar.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)
    return st.session_state.get("lang", "it")
