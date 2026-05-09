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
    """Renderizza il selettore Italiano/English nella sidebar."""
    import streamlit as st
    import base64

    lang = st.session_state.get("lang", "it")

    # SVG bandiere con viewBox corretti
    # Italia (3:2)
    FLAG_IT = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 3 2'>
      <rect width='1' height='2' fill='#009246'/>
      <rect x='1' width='1' height='2' fill='#FFFFFF'/>
      <rect x='2' width='1' height='2' fill='#CE2B37'/>
    </svg>"""

    # UK (2:1) - Usiamo una versione pulita
    FLAG_UK = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30'>
      <path d='M0,0 v30 h60 v-30 z' fill='#012169'/>
      <path d='M0,0 L60,30 M60,0 L0,30' stroke='#fff' stroke-width='6'/>
      <path d='M0,0 L60,30 M60,0 L0,30' stroke='#C8102E' stroke-width='4' clip-path='polygon(30 15, 60 15, 60 30, 30 15, 0 15, 0 0, 30 15)'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#fff' stroke-width='10'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#C8102E' stroke-width='6'/>
    </svg>"""

    flag_it_b64 = base64.b64encode(FLAG_IT.encode()).decode()
    flag_uk_b64 = base64.b64encode(FLAG_UK.encode()).decode()

    # Colore accento dinamico (Amber)
    accent = "#F59E0B"

    style_it = f"border: 2px solid {accent if lang=='it' else 'transparent'}; opacity: {1 if lang=='it' else 0.4};"
    style_en = f"border: 2px solid {accent if lang=='en' else 'transparent'}; opacity: {1 if lang=='en' else 0.4};"

    st.sidebar.markdown(
        f"""
        <style>
        .miq-lang-container {{
            margin-bottom: 20px;
        }}
        .miq-flag-row {{
            display: flex;
            gap: 10px;
            margin-top: 8px;
        }}
        .miq-flag-card {{
            flex: 1;
            cursor: pointer;
            background: rgba(148, 163, 184, 0.05);
            border-radius: 8px;
            padding: 4px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .miq-flag-card:hover {{
            background: rgba(148, 163, 184, 0.12);
            transform: translateY(-1px);
        }}
        .miq-flag-img-wrapper {{
            width: 100%;
            aspect-ratio: 2 / 1;
            border-radius: 4px;
            overflow: hidden;
            background: rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .miq-flag-img-wrapper img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            filter: drop-shadow(0 1px 2px rgba(0,0,0,0.1));
        }}
        .miq-lang-text {{
            font-size: 0.65rem;
            font-weight: 700;
            margin-top: 5px;
            color: #64748B;
            letter-spacing: 0.5px;
        }}
        /* Nascondi bottoni Streamlit */
        .miq-lang-hidden-wrapper,
        .miq-lang-hidden-wrapper button {{
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        </style>

        <div class="miq-lang-container">
            <div style='font-size:0.7rem; font-weight:700; letter-spacing:1px;
                 text-transform:uppercase; color:#64748B; margin-left:2px;'>
                 🌐 Language / Lingua
            </div>
            <div class="miq-flag-row">
                <div class="miq-flag-card" style="{style_it}" onclick="window.parent.document.querySelectorAll('button').forEach(b=>{{ if(b.innerText.trim()==='IT_HIDDEN') b.click(); }})">
                    <div class="miq-flag-img-wrapper">
                        <img src="data:image/svg+xml;base64,{flag_it_b64}"/>
                    </div>
                    <div class="miq-lang-text">ITALIANO</div>
                </div>
                <div class="miq-flag-card" style="{style_en}" onclick="window.parent.document.querySelectorAll('button').forEach(b=>{{ if(b.innerText.trim()==='EN_HIDDEN') b.click(); }})">
                    <div class="miq-flag-img-wrapper">
                        <img src="data:image/svg+xml;base64,{flag_uk_b64}"/>
                    </div>
                    <div class="miq-lang-text">ENGLISH</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Bottoni nascosti per gestire il click
    with st.sidebar:
        # Usiamo un container per nasconderli
        with st.container():
            st.markdown('<div class="miq-lang-hidden-wrapper">', unsafe_allow_html=True)
            _hc1, _hc2 = st.columns(2)
            with _hc1:
                if st.button("IT_HIDDEN", key="btn_lang_it"):
                    st.session_state["lang"] = "it"
                    st.rerun()
            with _hc2:
                if st.button("EN_HIDDEN", key="btn_lang_en"):
                    st.session_state["lang"] = "en"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    return lang
