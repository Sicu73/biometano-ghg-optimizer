# -*- coding: utf-8 -*-
"""Override estetico editoriale per Metan.iQ. Inietta CSS con !important
DOPO il design system esistente. Non tocca la logica: solo aspetto."""
import streamlit as st


def _tokens(is_dark: bool) -> dict:
    if is_dark:
        return dict(
            PAPER="#15140F", PAPER2="#1A1813", SURFACE="#1E1C16",
            INK="#E8E3D5", INK2="#C7C1B0", NAVY="#11202A", NAVY2="#1B2F3A",
            BRASS="#B59450", BRASS2="#C9A968", BRASS_SOFT="#3A3320",
            FOREST="#5AA37F", FOREST_SOFT="#1E2E25", FOREST_LINE="#375546",
            LINE="#33302A", LINE_SOFT="#2A2822", MUTED="#9A9486", MUTED2="#6F6A5E",
        )
    return dict(
        PAPER="#F7F4EC", PAPER2="#FBF9F3", SURFACE="#FFFFFF",
        INK="#1C1B16", INK2="#3A382F", NAVY="#15242E", NAVY2="#1F343F",
        BRASS="#9A7B3C", BRASS2="#B59450", BRASS_SOFT="#EFE7D4",
        FOREST="#3C6A52", FOREST_SOFT="#E9F0EA", FOREST_LINE="#C6D9CA",
        LINE="#E4DDCD", LINE_SOFT="#EEE9DC", MUTED="#726C5E", MUTED2="#A49D8C",
    )


def inject_editorial_theme(is_dark: bool = False):
    t = _tokens(is_dark)
    st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Outfit:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
html, body, .stApp, [class*="css"] {{ font-family:'Outfit', system-ui, sans-serif !important; }}
.stApp {{ background:{t['PAPER']} !important; color:{t['INK']} !important; }}
.block-container {{ padding-top:2rem !important; max-width:1220px !important; }}
header[data-testid="stHeader"] {{ background:transparent !important; height:0 !important; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{ font-family:'Spectral', Georgia, serif !important; font-weight:600 !important; letter-spacing:-.01em !important; }}
section[data-testid="stSidebar"] {{ background:{t['PAPER2']} !important; border-right:1px solid {t['LINE']} !important; }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{ font-family:'Spectral', serif !important; }}
section[data-testid="stSidebar"] [data-baseweb="select"] > div, section[data-testid="stSidebar"] textarea {{ background:{t['SURFACE']} !important; border:1px solid {t['LINE']} !important; border-radius:8px !important; color:{t['INK']} !important; }}
/* Input di testo/numero in sidebar: sfondo carta. MA NON l'input interno del
   multiselect/select, che deve restare trasparente: con sfondo bianco si
   sovrapponeva ai tag e ne copriva le prime lettere. */
section[data-testid="stSidebar"] [data-baseweb="input"] input, section[data-testid="stSidebar"] [data-baseweb="base-input"] input {{ background:{t['SURFACE']} !important; color:{t['INK']} !important; }}
section[data-testid="stSidebar"] [data-baseweb="select"] input {{ background:transparent !important; box-shadow:none !important; }}
.methaniq-header, .metaniq-header, div[class*="header"][style*="gradient"] {{ background:{t['NAVY']} !important; background-image:none !important; border:1px solid #243743 !important; border-radius:10px !important; box-shadow:none !important; position:relative !important; overflow:hidden !important; padding:38px 42px !important; }}
.methaniq-header::before {{ content:"" !important; position:absolute !important; top:0 !important; left:0 !important; right:0 !important; height:2px !important; background:linear-gradient(90deg, {t['BRASS']}, {t['BRASS2']}) !important; }}
.methaniq-header::after {{ display:none !important; }}
.methaniq-header h1 {{ font-family:'Outfit', sans-serif !important; font-size:2.9rem !important; font-weight:700 !important; letter-spacing:-.035em !important; color:#F7F4EC !important; }}
.methaniq-header p, .methaniq-header .tagline {{ font-family:'Spectral', serif !important; color:rgba(244,241,232,.80) !important; font-size:1.1rem !important; font-weight:400 !important; }}
/* Brand card navy in sidebar: SEMPRE navy -> testo chiaro in entrambi i temi.
   La regola sidebar che forza il testo a TEXT_SECOND la sovrascriveva (scuro
   su navy). Ripristino esplicito dei colori chiari; l'accento ottone resta. */
section[data-testid="stSidebar"] .metaniq-brandcard,
section[data-testid="stSidebar"] .metaniq-brandcard div,
section[data-testid="stSidebar"] .metaniq-brandcard span,
section[data-testid="stSidebar"] .metaniq-brandcard small,
section[data-testid="stSidebar"] .metaniq-brandcard b {{ color:#E5DFCF !important; }}
section[data-testid="stSidebar"] .metaniq-brandcard span[style*="9A7B3C"],
section[data-testid="stSidebar"] .metaniq-brandcard span[style*="B59450"] {{ color:#C9A968 !important; }}
[data-testid="stMetric"] {{ background:{t['SURFACE']} !important; border:1px solid {t['LINE']} !important; border-radius:10px !important; padding:18px 20px !important; box-shadow:none !important; position:relative !important; overflow:hidden !important; }}
[data-testid="stMetric"]::before {{ content:"" !important; position:absolute !important; left:20px !important; top:16px !important; width:12px !important; height:2px !important; background:{t['BRASS']} !important; }}
[data-testid="stMetricLabel"] p {{ text-transform:uppercase !important; letter-spacing:.12em !important; font-size:.7rem !important; font-weight:600 !important; color:{t['MUTED']} !important; padding-top:10px !important; }}
/* Label metriche: Streamlit le tronca con ellipsi (nowrap+overflow:hidden) quando
   la colonna è stretta -> testo "non si vede". Forziamo il wrap su più righe. */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ white-space:normal !important; overflow:visible !important; text-overflow:clip !important; }}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{ overflow:visible !important; text-overflow:clip !important; }}
[data-testid="stMetricValue"] {{ font-family:'Spectral', serif !important; font-weight:500 !important; font-size:2rem !important; letter-spacing:-.02em !important; color:{t['INK']} !important; }}
[data-testid="stMetricDelta"] {{ color:{t['FOREST']} !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap:28px !important; border-bottom:1px solid {t['LINE']} !important; }}
.stTabs [data-baseweb="tab"] {{ background:transparent !important; border:0 !important; border-radius:0 !important; padding:0 0 13px !important; font-family:'Outfit' !important; font-weight:500 !important; color:{t['MUTED']} !important; }}
.stTabs [aria-selected="true"] {{ color:{t['INK']} !important; font-weight:600 !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:{t['BRASS']} !important; height:2px !important; }}
.stTabs [data-baseweb="tab-border"] {{ background:{t['LINE']} !important; }}
.stButton button, .stDownloadButton button {{ border-radius:8px !important; border:1px solid {t['LINE']} !important; padding:9px 18px !important; font-weight:600 !important; box-shadow:none !important; transform:none !important; transition:filter .15s, border-color .15s !important; }}
.stButton button:hover, .stDownloadButton button:hover {{ transform:none !important; border-color:{t['NAVY']} !important; box-shadow:none !important; }}
.stButton button[kind="primary"] {{ background:{t['NAVY']} !important; border-color:{t['NAVY']} !important; color:#F4F1E8 !important; }}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{ border-radius:8px !important; border-color:{t['LINE']} !important; }}
div[data-testid="stExpander"] {{ background:{t['SURFACE']} !important; border:1px solid {t['LINE']} !important; border-radius:10px !important; box-shadow:none !important; }}
[data-testid="stTable"] thead th, [data-testid="stDataFrame"] thead th {{ text-transform:uppercase !important; letter-spacing:.1em !important; font-size:.66rem !important; color:{t['MUTED']} !important; border-bottom:1px solid {t['INK']} !important; background:transparent !important; }}
[data-testid="stTable"] tbody td, [data-testid="stDataFrame"] td {{ font-family:'IBM Plex Mono', monospace !important; color:{t['INK2']} !important; border-bottom:1px solid {t['LINE_SOFT']} !important; }}
[data-testid="stDataFrame"] {{ border:1px solid {t['LINE']} !important; border-radius:10px !important; }}
[data-testid="stAlert"] {{ border-radius:8px !important; }}
/* --- Polish editoriale rifinito --- */
.methaniq-header .eyebrow {{ font-family:'IBM Plex Mono', monospace !important; color:{t['BRASS2']} !important; letter-spacing:.22em !important; font-size:.7rem !important; font-weight:600 !important; text-transform:uppercase !important; }}
.methaniq-header .pills {{ gap:8px !important; }}
.methaniq-header .pill {{ background:rgba(255,255,255,.04) !important; border:1px solid rgba(201,169,104,.32) !important; color:#E5DFCF !important; border-radius:6px !important; letter-spacing:.04em !important; font-family:'IBM Plex Mono', monospace !important; font-size:.68rem !important; padding:4px 10px !important; }}
.methaniq-header .pill.accent {{ background:rgba(201,169,104,.18) !important; border-color:rgba(201,169,104,.55) !important; color:#F1E7CF !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within > div {{ border-color:{t['BRASS']} !important; box-shadow:0 0 0 1px {t['BRASS']} !important; }}
div[data-testid="stExpander"] summary {{ font-family:'Outfit', sans-serif !important; font-weight:600 !important; background:{t['SURFACE']} !important; color:{t['INK']} !important; }}
div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary span {{ color:{t['INK']} !important; }}
div[data-testid="stExpander"] summary:hover, div[data-testid="stExpander"] summary:hover * {{ color:{t['BRASS']} !important; }}
.stApp a {{ color:{t['BRASS']} !important; text-decoration-color:rgba(154,123,60,.4) !important; }}
.stApp code {{ font-family:'IBM Plex Mono', monospace !important; }}
hr {{ border-color:{t['LINE']} !important; opacity:1 !important; }}
/* --- Fix contrasto componenti --- */
/* Bottoni primary / form-submit nel CONTENUTO PRINCIPALE: testo chiaro su navy.
   Escluso il sidebar, dove i toggle primary lingua/tema hanno sfondo chiaro. */
[data-testid="stMain"] .stButton button[kind^="primary"],
[data-testid="stMain"] .stButton button[kind^="primary"] *,
[data-testid="stMain"] .stFormSubmitButton button[kind^="primary"],
[data-testid="stMain"] .stFormSubmitButton button[kind^="primary"] * {{ color:#F4F1E8 !important; }}
/* Download button: TUTTI navy + crema (sfondo scuro in entrambi i temi -> testo
   sempre ad alto contrasto). Specificita' alta per battere le regole esistenti. */
.stApp div[data-testid="stDownloadButton"].stDownloadButton button[kind] {{ background:#15242E !important; border-color:#15242E !important; }}
.stApp div[data-testid="stDownloadButton"].stDownloadButton button[kind],
.stApp div[data-testid="stDownloadButton"].stDownloadButton button[kind] * {{ color:#F4F1E8 !important; }}
/* st.text(): lo span interno usa un colore Streamlit di default non tematizzato
   -> forziamo il token INK (corretto per tema). */
.stText, .stText * {{ color:{t['INK']} !important; }}
/* Multiselect/select baseweb: placeholder, "Clear all", icone -> token leggibili. */
div[data-baseweb="select"] div, div[data-baseweb="select"] span {{ color:{t['INK']} !important; }}
div[data-baseweb="select"] svg {{ color:{t['MUTED']} !important; fill:currentColor !important; }}
[data-baseweb="popover"] li, [data-baseweb="popover"] li * {{ color:{t['INK']} !important; }}
/* Tag biomassa (multiselect): pillola brass piena, testo scuro leggibile, e
   NESSUN riquadro chiaro sopra il nome. Alcune build di Streamlit inseriscono un
   handle/icona di riordino a sinistra del tag con sfondo chiaro che copriva le
   prime lettere: azzeriamo lo sfondo di ogni figlio e fissiamo il padding sx. */
.stApp span[data-baseweb="tag"][role="button"], section[data-testid="stSidebar"] span[data-baseweb="tag"][role="button"] {{ background-color:{t['BRASS']} !important; background-image:none !important; color:#1C1B16 !important; padding-left:10px !important; overflow:visible !important; }}
span[data-baseweb="tag"][role="button"] {{ background:{t['BRASS']} !important; color:#1C1B16 !important; padding-left:10px !important; overflow:visible !important; }}
span[data-baseweb="tag"][role="button"] > span, span[data-baseweb="tag"][role="button"] > span * {{ color:#1C1B16 !important; background:transparent !important; margin-left:0 !important; }}
/* Nome biomassa nel tag: niente troncamento con ellipsi -> mostra il nome intero
   (il tag si allarga / va a capo). */
span[data-baseweb="tag"][role="button"] span[title], span[data-baseweb="tag"][role="button"] span[title] * {{ white-space:normal !important; overflow:visible !important; text-overflow:clip !important; max-width:none !important; }}
span[data-baseweb="tag"][role="button"] [aria-hidden="true"], span[data-baseweb="tag"][role="button"] [role="presentation"] {{ background:transparent !important; }}
span[data-baseweb="tag"][role="button"] svg {{ fill:#1C1B16 !important; color:#1C1B16 !important; background:transparent !important; }}
</style>
""", unsafe_allow_html=True)


EDITORIAL_PALETTE = ["#15242E", "#9A7B3C", "#3C6A52", "#1F343F", "#B59450", "#5C5849"]


def style_plotly(fig, is_dark: bool = False):
    t = _tokens(is_dark)
    grid = "rgba(232,227,213,.10)" if is_dark else "rgba(28,27,22,.07)"
    fig.update_layout(
        colorway=EDITORIAL_PALETTE,
        font=dict(family="Outfit, sans-serif", color=t["INK"], size=13),
        title_font=dict(family="Spectral, serif", size=18, color=t["INK"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        separators=",.",
        hoverlabel=dict(bgcolor=t["NAVY"], bordercolor=t["BRASS"],
                        font=dict(family="IBM Plex Mono, monospace", color="#F4F1E8")),
        legend=dict(font=dict(family="IBM Plex Mono, monospace", size=11)),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(family="IBM Plex Mono", size=11), linecolor=t["LINE"])
    fig.update_yaxes(gridcolor=grid, tickfont=dict(family="IBM Plex Mono", size=11), zeroline=False)
    return fig
