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

    lang = st.session_state.get("lang", "it")

    # SVG bandiere inline (encoded)
    FLAG_IT = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 3 2'>
      <rect width='1' height='2' fill='#009246'/>
      <rect x='1' width='1' height='2' fill='#FFFFFF'/>
      <rect x='2' width='1' height='2' fill='#CE2B37'/>
    </svg>"""

    FLAG_UK = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30'>
      <clipPath id='s'><path d='M0,0 v30 h60 v-30 z'/></clipPath>
      <clipPath id='t'><path d='M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z'/></clipPath>
      <path d='M0,0 v30 h60 v-30 z' fill='#012169'/>
      <path d='M0,0 L60,30 M60,0 L0,30' stroke='#fff' stroke-width='6'/>
      <path d='M0,0 L60,30 M60,0 L0,30' clip-path='url(#t)' stroke='#C8102E' stroke-width='4'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#fff' stroke-width='10'/>
      <path d='M30,0 v30 M0,15 h60' stroke='#C8102E' stroke-width='6'/>
    </svg>"""

    import base64
    flag_it_b64 = base64.b64encode(FLAG_IT.encode()).decode()
    flag_uk_b64 = base64.b64encode(FLAG_UK.encode()).decode()

    active_it  = "border: 3px solid #0F172A; box-shadow: 0 0 0 1px #0F172A; opacity:1;"
    inactive   = "opacity: 0.35; filter: grayscale(70%);"
    style_it   = active_it  if lang == "it" else inactive
    style_en   = active_it  if lang == "en" else inactive

    st.sidebar.markdown(
        f"""
        <style>
        /* Nascondi bottoni reali Streamlit ma mantienili nel DOM */
        div[data-testid='stSidebar'] .miq-lang-btn-row button {{
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
            clip: rect(0,0,0,0) !important;
            white-space: nowrap !important;
            border: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}
        .miq-flag-box {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            margin-top: 4px;
        }}
        .miq-flag {{
            flex: 1;
            cursor: pointer;
            border-radius: 6px;
            overflow: hidden;
            transition: transform 0.15s, box-shadow 0.15s;
            line-height: 0;
        }}
        .miq-flag:hover {{
            transform: scale(1.04);
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        }}
        .miq-flag img {{
            width: 100%;
            height: 54px;
            object-fit: cover;
            display: block;
            border-radius: 5px;
        }}
        .miq-lang-label {{
            font-size: 0.62rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            text-align: center;
            margin-top: 3px;
            color: #64748B;
        }}
        </style>

        <div style='font-size:0.7rem;font-weight:600;letter-spacing:1px;
             text-transform:uppercase;color:#64748B;margin-bottom:6px;'>
             🌐 Language / Lingua
        </div>
        <div class='miq-flag-box'>
          <div class='miq-flag' style='{style_it}; border-radius:6px;'
               onclick="document.querySelector('button[data-testid=\\'btn_lang_it\\']') && document.querySelector('button[data-testid=\\'btn_lang_it\\']').click(); window.parent.document.querySelectorAll('button').forEach(b=>{{ if(b.innerText.trim()==='IT') b.click(); }});">
            <img src='data:image/svg+xml;base64,{flag_it_b64}' alt='Italiano'/>
            <div class='miq-lang-label'>🇮🇹 IT</div>
          </div>
          <div class='miq-flag' style='{style_en}; border-radius:6px;'
               onclick="window.parent.document.querySelectorAll('button').forEach(b=>{{ if(b.innerText.trim()==='EN') b.click(); }});">
            <img src='data:image/svg+xml;base64,{flag_uk_b64}' alt='English'/>
            <div class='miq-lang-label'>🇬🇧 EN</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Bottoni reali Streamlit (nascosti via CSS ma cliccabili via JS)
    _lc1, _lc2 = st.sidebar.columns(2)
    with _lc1:
        if st.button("IT", use_container_width=True, key="btn_lang_it", help="Italiano"):
            st.session_state["lang"] = "it"
            st.rerun()
    with _lc2:
        if st.button("EN", use_container_width=True, key="btn_lang_en", help="English"):
            st.session_state["lang"] = "en"
            st.rerun()

    return lang

