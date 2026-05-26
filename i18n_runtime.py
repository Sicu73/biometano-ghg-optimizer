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
import re

from metaniq_i18n import IT_EN
from core.design_tokens import AMBER as _ACCENT, SLATE_500 as _MUTED


# Word-boundary lookbehind/lookahead: previene matching all'interno di parole
# (fix typo classico: "anni" -> "years" matchato dentro "planning" = "plyearsng").
# Usiamo `(?<!\w)` / `(?!\w)` invece di `\b` perché molte chiavi includono
# caratteri non-word (es. "Sm³ lordi", "€/MWh", "DM 15/9/2022 art. 5") e `\b`
# Unicode-aware in Python si comporta in modo inconsistente con simboli.
_IT_EN_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(k) for k in sorted(IT_EN, key=len, reverse=True))
    + r")(?!\w)"
)


def get_lang() -> str:
    try:
        import streamlit as st
        return str(st.session_state.get("lang", "it"))
    except Exception:
        return "it"


def t(text: object, lang: str | None = None) -> object:
    """Traduce text IT->EN. Se lang è None usa get_lang().

    La sostituzione è one-pass sull'input originale: così una traduzione già
    prodotta non viene tradotta di nuovo da chiavi più corte (es. "planning"
    non può diventare "plyearsng" se esiste una chiave "anni" -> "years").
    """
    if lang is None:
        lang = get_lang()
    if lang != "en" or not isinstance(text, str):
        return text
    if text in IT_EN:
        return IT_EN[text]
    return _IT_EN_PATTERN.sub(lambda match: IT_EN[match.group(0)], text)


def translate_df(df, lang: str | None = None):
    """Restituisce copia del DataFrame con colonne tradotte."""
    if lang is None:
        lang = get_lang()
    if lang != "en":
        return df
    return df.rename(columns={c: t(str(c), lang) for c in df.columns})


def render_lang_selector() -> str:
    """Renderizza il selettore Italiano/English nella sidebar.

    Layout: due colonne, bandiera SVG renderizzata sopra (decorativa) + bottone
    nativo Streamlit sotto (cliccabile, label 'Italiano' / 'English'). Stato
    attivo via type='primary' (bordo accent amber).
    """
    import streamlit as st
    import base64

    lang = st.session_state.get("lang", "it")
    accent = _ACCENT

    # SVG bandiere
    FLAG_IT = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 3 2'>
      <rect width='1' height='2' fill='#009246'/>
      <rect x='1' width='1' height='2' fill='#FFFFFF'/>
      <rect x='2' width='1' height='2' fill='#CE2B37'/>
    </svg>"""
    FLAG_UK = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30'>
      <clipPath id='t'><path d='M30,15 h30 v15 z v-15 h-30 z h-30 v-15 z v15 h30 z'/></clipPath>
      <path d='M0,0 v30 h60 v-30 z' fill='#012169'/>
      <path d='M0,0 L60,30 M60,0 L0,30' stroke='#fff' stroke-width='6'/>
      <path d='M0,0 L60,30 M60,0 L0,30' clip-path='url(#t)' stroke='#C8102E' stroke-width='4'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#fff' stroke-width='10'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#C8102E' stroke-width='6'/>
    </svg>"""
    flag_it_b64 = base64.b64encode(FLAG_IT.encode()).decode()
    flag_uk_b64 = base64.b64encode(FLAG_UK.encode()).decode()

    border_it = accent if lang == "it" else "transparent"
    border_en = accent if lang == "en" else "transparent"
    opacity_it = "1" if lang == "it" else "0.55"
    opacity_en = "1" if lang == "en" else "0.55"

    st.sidebar.markdown(
        f"""
        <style>
        .miq-lang-heading {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: #64748B;
            margin-left: 2px;
            margin-bottom: 8px;
        }}
        .miq-flag-img {{
            width: 100%;
            aspect-ratio: 2 / 1.2;
            border-radius: 6px;
            overflow: hidden;
            display: block;
            box-shadow: 0 1px 4px rgba(0,0,0,0.10);
            margin-bottom: 6px;
        }}
        .miq-flag-img img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type
          [data-testid="stColumn"] .stButton button[kind="primary"] {{
            background: rgba(245,158,11,0.14) !important;
            border: 2px solid {accent} !important;
            color: {accent} !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:first-of-type
          [data-testid="stColumn"] .stButton button {{
            font-weight: 700 !important;
        }}
        </style>
        <div class="miq-lang-heading">🌐 Language / Lingua</div>
        """,
        unsafe_allow_html=True,
    )

    _c1, _c2 = st.sidebar.columns(2)
    with _c1:
        st.markdown(
            f"""
            <div class="miq-flag-img" style="border:2px solid {border_it}; opacity:{opacity_it};">
                <img src="data:image/svg+xml;base64,{flag_it_b64}"/>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Italiano",
            key="btn_lang_it",
            use_container_width=True,
            type=("primary" if lang == "it" else "secondary"),
        ):
            st.session_state["lang"] = "it"
            st.rerun()
    with _c2:
        st.markdown(
            f"""
            <div class="miq-flag-img" style="border:2px solid {border_en}; opacity:{opacity_en};">
                <img src="data:image/svg+xml;base64,{flag_uk_b64}"/>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "English",
            key="btn_lang_en",
            use_container_width=True,
            type=("primary" if lang == "en" else "secondary"),
        ):
            st.session_state["lang"] = "en"
            st.rerun()

    return lang
