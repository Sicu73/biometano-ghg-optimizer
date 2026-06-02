# -*- coding: utf-8 -*-
"""
BioMethane Monthly Planner - Dual-Constraint Solver
---------------------------------------------------
Impianto 300 Sm3/h NETTI (DM 15/09/2022, PNRR).
Biomasse: Trinciato di mais, Trinciato di sorgo da foraggio, Pollina ovaiole, Liquame suino.

Due modalita':
  A) 2 biomasse fisse + 2 calcolate -> soddisfa SIA produzione SIA saving 81%
  B) 3 biomasse fisse + 1 calcolata -> soddisfa solo produzione (saving residuo)

Riferimenti:
- RED III (Dir. 2023/2413) Allegato V Parte C
- UNI/TS 11567:2024
- DM 07/08/2024 (implementazione nazionale)
- Parametri feedstock: letteratura tecnica e valori tipici Consorzio Monviso
"""

import html as _html
import json
import urllib.request
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from report_pdf import build_metaniq_pdf
from excel_export import build_metaniq_xlsx

# === Refactor output (Fase 2) — output_model unificato ======================
# Carica le funzioni nuove con fallback per non rompere il vecchio percorso.
try:
    from output.output_builder import build_output_model as _build_output_model
    from output.tables import (
        build_feedstock_table as _build_feedstock_table_om,
        build_ghg_table       as _build_ghg_table_om,
        build_audit_table     as _build_audit_table_om,
    )
    from output.explanations import (
        explain_yield_origin            as _explain_yield_origin,
        explain_emission_factor_origin  as _explain_emission_factor_origin,
        explain_ghg_method              as _explain_ghg_method,
        explain_regulatory_basis        as _explain_regulatory_basis,
    )
    from export.csv_export import build_csv_from_output as _build_csv_from_output
    _HAS_OUTPUT_MODEL = True
    _OM_IMPORT_ERR = ""
except Exception as _om_imp_exc:  # noqa: BLE001
    _HAS_OUTPUT_MODEL = False
    _OM_IMPORT_ERR = str(_om_imp_exc)

# ── Logging strutturato per produzione (audit robustezza #3) ────────────────
from core.logging_setup import get_logger
_LOG = get_logger("app")

# ── i18n: selettore lingua + funzione di traduzione ──────────────────────────
from i18n_runtime import t as _t, get_lang, render_lang_selector, translate_df

# ── Versione canonica software ──────────────────────────────────────────────
try:
    from core.version import __version__ as _APP_VERSION, FOOTER as _APP_FOOTER
except Exception:  # noqa: BLE001
    _APP_VERSION = "0.4.0"
    _APP_FOOTER = "Metan.iQ v0.4.0 — © 2026"

# ── BMT (Biochemical Methane Test) — override resa certificata laboratorio ──
from bmt_override import (
    BMTCertificate,
    validate_bmt_override,
    resolve_biomass_yield,
    build_yield_audit_row,
    ALLOWED_CERT_EXTS,
    BMT_DEVIATION_WARN_THRESHOLD,
    YIELD_UNIT as BMT_YIELD_UNIT,
    SOURCE_BMT,
    SOURCE_STD as BMT_SOURCE_STD,
)

# ── Override fattori emissivi reali da relazione tecnica ────────────────────
from emission_factors_override import (
    EmissionFactorReport,
    validate_real_emission_factor_override,
    resolve_emission_factors,
    build_emission_factor_audit_row,
    calculate_emission_total,
    ALLOWED_REPORT_EXTS,
    EMISSION_DEVIATION_WARN_THRESHOLD,
    EMISSION_UNIT,
    SOURCE_REAL as EF_SOURCE_REAL,
    SOURCE_STD as EF_SOURCE_STD,
)

# ============================================================
# REGISTRO NORMATIVA
# ============================================================
# Il file normativa_versions.json contiene tutte le norme (RED III,
# DM 2018, DM 2022, DM 2012, FER 2, GSE LG, UNI/TS, JEC) cablate nel
# codice + i valori-chiave codificati. Aggiornarlo (commit) quando si
# applica una modifica al codice o si aggiunge una nuova norma.
NORMATIVA_LOCAL_PATH = Path(__file__).parent / "normativa_versions.json"


def _load_normativa_local() -> dict:
    """Carica il JSON normativa locale dal repo (sempre disponibile)."""
    try:
        with open(NORMATIVA_LOCAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"File locale non trovato: {exc}"}


# ============================================================
# FORMATO ITALIANO: punto = migliaia, virgola = decimali
# ============================================================
# ============================================================
# Metan.iQ chart theme — palette consulting-grade Navy/Amber
# Applicato a tutti i Plotly figs via apply_metaniq_theme(fig)
# ============================================================
# Palette editoriale "consulting report": navy/ottone/foresta, monocromatica.
METANIQ_PALETTE = [
    "#15242E",  # navy (primary ink)
    "#9A7B3C",  # brass (accent)
    "#3C6A52",  # forest
    "#1F343F",  # navy 2
    "#B59450",  # brass 2 (light)
    "#5C5849",  # taupe / muted ink
    "#2E5141",  # forest deep
    "#7A6230",  # brass deep
    "#3A4A55",  # slate navy
    "#8C8470",  # warm grey
]

def apply_metaniq_theme(fig, *, dark: bool = False):
    """Applica palette + tipografia editoriale Metan.iQ a una figure Plotly."""
    text_color = "#E8E3D5" if dark else "#1C1B16"
    grid_color = "rgba(232, 227, 213, 0.10)" if dark else "rgba(28, 27, 22, 0.07)"
    axis_color = "#A49D8C" if dark else "#726C5E"
    fig.update_layout(
        font=dict(family="Outfit, -apple-system, sans-serif",
                  color=text_color, size=12),
        title_font=dict(family="Spectral, Georgia, serif",
                        size=16, color=text_color),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=METANIQ_PALETTE,
        margin=dict(l=50, r=20, t=60, b=40),
        legend=dict(
            font=dict(family="Outfit, sans-serif", size=11, color=text_color),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            font=dict(family="IBM Plex Mono, monospace", size=11),
            bgcolor="#15242E",
            bordercolor="#9A7B3C",
            font_color="#F7F4EC",
        ),
        separators=",.",
    )
    fig.update_xaxes(
        gridcolor=grid_color, gridwidth=1,
        zerolinecolor=grid_color,
        tickfont=dict(family="IBM Plex Mono, monospace",
                      size=10, color=axis_color),
        title_font=dict(family="Outfit, sans-serif",
                        size=11, color=axis_color),
        showline=True, linewidth=1, linecolor=grid_color,
    )
    fig.update_yaxes(
        gridcolor=grid_color, gridwidth=1,
        zerolinecolor=grid_color,
        tickfont=dict(family="IBM Plex Mono, monospace",
                      size=10, color=axis_color),
        title_font=dict(family="Outfit, sans-serif",
                        size=11, color=axis_color),
        showline=False,
    )
    return fig


def fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False,
           lang: str | None = None) -> str:
    """Formatta numero stile locale-aware.

    - IT: 1.234.567,89  (punto migliaia, virgola decimale)
    - EN: 1,234,567.89  (virgola migliaia, punto decimale — UK/US standard)

    Nome storico mantenuto per backcompat (289 call sites). Se `lang` è None,
    legge il valore corrente dal session_state via i18n_runtime.get_lang().

    signed=True -> prefisso '+' anche per valori positivi.
    """
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "-"
    # Rilevamento lang dinamico (se non passato esplicitamente).
    if lang is None:
        try:
            from i18n_runtime import get_lang as _gl
            lang = _gl()
        except Exception:
            lang = "it"
    # Python f-string produce nativamente formato EN (virgola migliaia, punto
    # decimale): 1,234,567.89. Lo usiamo direttamente per EN.
    if signed:
        s = f"{value:+,.{decimals}f}"
    else:
        s = f"{value:,.{decimals}f}"
    if lang == "en":
        return s + suffix
    # IT: swap virgola <-> punto (placeholder § per evitare collisioni).
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def fmt_date(d, lang: str | None = None) -> str:
    """Formatta data secondo lang corrente.

    - IT: 25/05/2026
    - EN: May 25, 2026

    Accetta datetime.date / datetime / pd.Timestamp / stringa ISO. Restituisce
    stringa vuota se non parsabile.
    """
    if d is None:
        return ""
    if lang is None:
        try:
            from i18n_runtime import get_lang as _gl
            lang = _gl()
        except Exception:
            lang = "it"
    # Normalizza
    if isinstance(d, str):
        try:
            d = pd.to_datetime(d, errors="coerce")
            if pd.isna(d):
                return ""
        except Exception:
            return ""
    try:
        if lang == "en":
            return d.strftime("%b %d, %Y")  # May 25, 2026
        return d.strftime("%d/%m/%Y")        # 25/05/2026
    except Exception:
        return str(d)


def saving_annuale_pesato(df, *, saving_col: str = "Saving %",
                          energy_col: str = "MWh netti",
                          comparator: float | None = None) -> float:
    """Calcola il saving GHG ANNUALE corretto normativamente (RED III / DM 2022).

    NON usare `df["Saving %"].mean()`: la media aritmetica dei saving mensili NON
    coincide col saving ricalcolato sui totali annuali (intensità g/MJ pesata
    sull'energia prodotta). Per audit GSE/DM 2022 vale il ricalcolo sui totali.

    Implementazione (equivalente al ricalcolo sui totali):
        e_w_m       = comparator * (1 - saving_m/100)        # intensità mensile g/MJ
        e_w_anno    = Σ(e_w_m × MWh_m) / Σ(MWh_m)            # media pesata sull'energia
        saving_anno = (comparator - e_w_anno) / comparator × 100

    Args:
        df: DataFrame con almeno le colonne `saving_col` e `energy_col` (1 riga/mese).
        saving_col: nome colonna saving mensile in % (0-100).
        energy_col: nome colonna energia mensile (MWh netti), usata come peso.
        comparator: comparatore fossile gCO2eq/MJ (default: globale FOSSIL_COMPARATOR).

    Returns:
        Saving annuale in % (0-100), o `mean()` semplice in fallback se
        l'energia totale è zero o le colonne mancano.
    """
    try:
        if comparator is None:
            comparator = FOSSIL_COMPARATOR  # noqa: F821 (definito più sotto, lazy resolve)
        if df is None or df.empty or saving_col not in df.columns or energy_col not in df.columns:
            return 0.0
        sav = pd.to_numeric(df[saving_col], errors="coerce").fillna(0.0)
        en  = pd.to_numeric(df[energy_col], errors="coerce").fillna(0.0)
        # Considera solo mesi con energia > 0 (escludere zeri NON è una distorsione
        # qui: i mesi senza produzione hanno peso 0, non entrano nella media pesata).
        mask = en > 0
        if not mask.any():
            return 0.0
        e_w = float(comparator) * (1.0 - sav.loc[mask] / 100.0)
        weighted_e_w = float((e_w * en.loc[mask]).sum() / en.loc[mask].sum())
        return float((float(comparator) - weighted_e_w) / float(comparator) * 100.0)
    except Exception:
        # Fallback grazioso: mean semplice (vecchio comportamento) se qualcosa rompe
        try:
            return float(df[saving_col].mean()) if df is not None and not df.empty else 0.0
        except Exception:
            return 0.0


def parse_it(value) -> float:
    """Parse di un numero scritto all'italiana.

    Accetta:
      - '1.234,56'   (italiano completo: . migliaia, , decimali)
      - '1234,56'    (italiano semplice)
      - '1234.56'    (stile C / anglosassone)
      - '1.800'      (italiano con migliaia, senza decimali -> 1800.0)
      - '26.303'     (idem -> 26303.0)
      - '0.800'      (zero virgola ottocentesimi -> 0.8 - NON migliaia!)
    Euristica: se non c'e' virgola e c'e' almeno un punto, e gli eventuali
    gruppi dopo il punto hanno esattamente 3 cifre E la parte intera e' != 0,
    i punti sono separatori di migliaia. Se la parte intera e' 0 il punto
    e' sempre decimale (es. 0.800 = 0.8, non 800).
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return 0.0
        return float(value)
    s = str(value).strip().replace("€", "").replace("%", "").replace("'", "").strip()
    if not s or s == "-":
        return 0.0
    has_comma = "," in s
    if has_comma:
        # Italiano: punti = migliaia, virgola = decimali
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        # Piu' di un punto -> sicuramente migliaia (es. "1.234.567")
        # Un solo punto + gruppo a destra di esattamente 3 cifre -> migliaia
        # (es. "1.800", "26.303"). Altrimenti resta decimale (es. "1.5").
        many_dots = len(parts) > 2
        single_thousand = (len(parts) == 2 and len(parts[1]) == 3
                           and parts[0].lstrip("-").isdigit()
                           and parts[1].isdigit()
                           and parts[0].lstrip("-") != "0")  # 0.800=0.8 not 800
        if many_dots or single_thousand:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

# ============================================================
# COSTANTI RED III
# ============================================================
# Comparator fossile - dipende da destinazione d'uso dell'energia rinnovabile:
#   - Biometano -> trasporti (BioCNG/BioGNL):    94 gCO2eq/MJ (diesel sostituito)
#     [RED III Annex V Part C - fossil fuel comparator for transport]
#   - Biometano -> rete / elettricita' / calore: 80 gCO2eq/MJ (NG sostituito)
#     [RED III Annex VI Part B - natural gas reference]
#   - Biogas CHP (elettricita' diretta da motore): 183 gCO2eq/MJ (mix elettrico EU)
#     [RED III Annex VI - electricity generation]
COMPARATOR_BY_END_USE = {
    "Elettricità/calore/immissione rete (nuovo ≥20/11/2023)": 80.0,
    "Elettricità/calore (esistente <10 MW, primi 15 anni)":   80.0,
    "Trasporti (BioGNL/BioCNG)":                              94.0,
}
# Costanti normative/energetiche: fonte di verità centralizzata in
# core/constants.py (importate qui con i nomi storici dell'app).
from core.constants import (
    LHV_BIOMETHANE_MJ_NM3            as LHV_BIOMETHANE,
    NM3_TO_MWH,
    COMPARATOR_GRID_HEAT_GCO2_MJ     as _COMP_GRID_HEAT,
)

FOSSIL_COMPARATOR = _COMP_GRID_HEAT
DEFAULT_AUX_FACTOR = 1.29                      # netto -> lordo (perdite upgrading + caldaia)
DEFAULT_PLANT_NET_SMCH = 300.0                 # Sm3/h netti autorizzati (default)

# ============================================================
# SOGLIE RED III per destinazione d'uso biometano
# (impianti nuovi >= 20/11/2023; per vecchi vedi D.Lgs. 5/2026 art. transitorio)
# ============================================================
END_USE_THRESHOLDS = {
    "Elettricità/calore/immissione rete (nuovo ≥20/11/2023)": 0.80,
    "Elettricità/calore (esistente <10 MW, primi 15 anni)": 0.70,
    "Trasporti (BioGNL/BioCNG)": 0.65,
}



# ============================================================
# DM 15/09/2022 BIOMETANO — STRUTTURA TARIFFARIA COMPLETA
# Fonte: DM 15/9/2022 + Regole Applicative GSE + bandi PNRR 2024
# ============================================================

# --- Tipologie di impianto (cambiano la tariffa base) -------
BP_PLANT_TYPES = {
    "Nuova costruzione":        {"label": "🆕 Nuova costruzione",       "tr_factor": 1.00},
    "Riconversione totale":     {"label": "🔄 Riconversione totale",    "tr_factor": 0.90},
    "Riconversione parziale":   {"label": "⚡ Riconversione parziale",  "tr_factor": 0.85},
    "Ampliamento":              {"label": "📈 Ampliamento",             "tr_factor": 1.00},
}
BP_PLANT_TYPE_DEFAULT = "Nuova costruzione"

# --- Destinazione d'uso biometano ---------------------------
BP_DEST_USE = {
    "Rete gas / industria / calore":        {"ghg_thr": 0.80, "cmp": 80.0,  "cic": False},
    "Trasporti (Bio-CNG / Bio-GNL)":       {"ghg_thr": 0.65, "cmp": 94.0,  "cic": False},
    "Uso termico residenziale/terziario":   {"ghg_thr": 0.80, "cmp": 80.0,  "cic": False},
}
BP_DEST_USE_DEFAULT = "Rete gas / industria / calore"

# --- Tariffe di riferimento DM 2022 per fascia + tipo -------
# (€/MWh, aggiornate al 4° bando PNRR 2024 con adeguamento ISTAT)
# Fascia A: ≤ 250 Smc/h  |  Fascia B: > 250 Smc/h
BP_TARIFFE_REF = {
    # Fascia A (≤ 250 Smc/h) — Tariffa Omnicomprensiva disponibile
    "Nuova costruzione":      {"fascia_a": 131.0, "fascia_b": 118.0},
    "Riconversione totale":   {"fascia_a": 118.0, "fascia_b": 107.0},
    "Riconversione parziale": {"fascia_a": 112.0, "fascia_b": 100.0},
    "Ampliamento":            {"fascia_a": 131.0, "fascia_b": 118.0},
}
BP_TARIFFA_BASE_2026          = 131.0    # €/MWh fallback (nuova costruzione fascia A)
BP_SOGLIA_FASCIA_SMCH         = 250.0   # soglia Smc/h tra fascia A e B

# --- Meccanismo tariffa (TO vs TP) --------------------------
# TO = Omnicomprensiva (GSE ritira gas + GO incluse) → solo ≤ 250 Smc/h
# TP = Premio (differenziale tra TR e prezzo gas + GO) → obbligatorio > 250 Smc/h
BP_MECCA_TO    = "Tariffa Omnicomprensiva (TO)"
BP_MECCA_TP    = "Tariffa Premio (TP)"
BP_PREZZO_GAS_DEFAULT   = 35.0   # €/MWh gas naturale mercato (PSV riferimento)
BP_PREZZO_GO_DEFAULT    = 2.5    # €/MWh GO biometano (valore medio mercato)

# --- Premi cumulabili DM 2022 -------------------------------
BP_PREMIO_MATRICE_DEFAULT      = 8.0    # €/MWh (> 70% Annex IX avanzato)
BP_PREMIO_UPGRADING_DEFAULT    = 5.0    # €/MWh (membrane o amminico)
BP_PREMIO_UPGRADING_TECNO = ("Membrane (slip ~0.5%)", "Amminico - chimico (slip ~0.1%)")

# --- Altri parametri BP -------------------------------------
BP_RIBASSO_DEFAULT_PCT        = 1.0      # % ribasso d'asta tipico (0-30%)
BP_DURATA_TARIFFA_ANNI        = 15       # DM 2022
BP_INFLAZIONE_DEFAULT_PCT     = 2.5      # % annua per OPEX
BP_AMMORTAMENTO_ANNI          = 22       # impianti biometano (10% media DLgs 38/2018)
BP_TAX_RATE_PCT               = 24.0     # IRES
BP_PNRR_QUOTA_PCT_DEFAULT     = 40.0     # % contributo a fondo perduto (M2C2)
BP_MASSIMALE_SPESA_EUR_PER_SMCH = 32817.23  # massimale GSE €/(Smc/h)


def compute_revenues(
    plant_smch: float,
    tariffa_eur_mwh: float,
    durata_tariffa: int = BP_DURATA_TARIFFA_ANNI,
    ore_anno: float = 8500.0,
    pci_kwh_per_smc: float = 9.79,
    ch4_in_biogas_pct: float = 54.25,         # % CH4 nel biogas (tipico)
) -> dict:
    """Calcolo Ricavi biometano DM 2022 (15 anni standard)."""
    biometano_smc_anno = plant_smch * ore_anno
    # 1 Smc biometano (97% CH4) ~= 9,97 kWh -> tariffa €/Smc = €/MWh / 1000 * 9,97
    tariffa_eur_smc = tariffa_eur_mwh / 1000.0 * pci_kwh_per_smc
    ricavo_annuo = biometano_smc_anno * tariffa_eur_smc
    biometano_mwh_anno = biometano_smc_anno * pci_kwh_per_smc / 1000.0

    return {
        "plant_smch":          plant_smch,
        "ore_anno":            ore_anno,
        "tariffa_eur_mwh":     tariffa_eur_mwh,
        "tariffa_eur_smc":     tariffa_eur_smc,
        "biometano_smc_anno":  biometano_smc_anno,
        "biometano_mwh_anno":  biometano_mwh_anno,
        "ricavo_annuo":        ricavo_annuo,
        "ricavi_totali":       ricavo_annuo * durata_tariffa,
        "durata_tariffa":      durata_tariffa,
    }

# ============================================================
# EP (processing) - contributi impiantistici [gCO2eq/MJ biometano]
# Valori medi da letteratura JRC-CONCAWE v5, UNI/TS 11567:2024, default RED III.
# NB: valori indicativi; per certificazione GSE servono misure reali d'impianto.
# ============================================================
# Stoccaggio digestato - RED III All. V Parte C + GSE Linee Guida 2024.
# La normativa riconosce SOLO due stati (no soglie temporali):
#   - APERTO:  emissioni secondo fattori IPCC 2019 Vol.4 Cap.10, tipicamente
#              +12 / +18 gCO2eq/MJ biometano per clima mediterraneo
#              (MCF 25-30% su digestato liquido). Default JEC WTT v5 = +15.
#   - CHIUSO con recupero gas convogliato all'upgrading: 0 gCO2eq/MJ.
#              Il gas recuperato NON da' un bonus negativo: semplicemente
#              confluisce nel biogas lordo e aumenta la resa yield.
EP_DIGESTATE = {
    "CHIUSO con recupero gas residuo (minimo 60 giorni)":             0.0,
    "CHIUSO con recupero gas residuo (minimo 30 giorni)":             1.6,
    "BREVE TERMINE (massimo 3 giorni)":                               6.4,
    "APERTO (senza recupero) - declassamento d'ufficio":             15.0,
}
EP_UPGRADING = {
    "PSA (methane slip ~1.5%)":                         +12.0,
    "Membrane (slip ~0.5%)":                             +5.0,
    "Amminico - chimico (slip ~0.1%)":                   +3.0,
    "Scrubber ad acqua pressurizzata (slip ~1%)":        +8.0,
}
EP_OFFGAS = {
    "Sì - RTO / ossidatore termico (riduce slip)":       -8.0,
    "Sì - Flare/torcia":                                 -4.0,
    "No - off-gas rilasciato in atmosfera":               0.0,
}
EP_HEAT = {
    "Autoconsumo biogas/biometano":                       0.0,
    "Teleriscaldamento / biomassa solida":               +1.0,
    "Caldaia gas naturale":                              +3.0,
}
EP_ELEC = {
    "Rete nazionale (mix IT)":                           +4.0,
    "Autoproduzione FV/cogenerazione":                   +1.0,
}

# ============================================================
# BILANCIO ENERGETICO -> aux_factor AUTOMATICO
# ============================================================
# Fabbisogni termici di processo [kWh_t / Sm3 biometano netto]
# (riscaldamento digestori + rigenerazione/calore upgrading)
# Fonte: JRC-CONCAWE v5, UNI/TS 11567:2024, handbook IEA Bioenergy T37
HEAT_DEMAND_UPGRADING = {
    "PSA (methane slip ~1.5%)":                          0.30,
    "Membrane (slip ~0.5%)":                             0.60,
    "Amminico - chimico (slip ~0.1%)":                   1.30,
    "Scrubber ad acqua pressurizzata (slip ~1%)":        0.40,
}
HEAT_DIGESTORE = 0.30   # kWh_t/Sm3 biometano (mesofilo, clima IT)

# Fabbisogni elettrici [kWh_e / Sm3 biometano netto]
ELEC_DEMAND_UPGRADING = {
    "PSA (methane slip ~1.5%)":                          0.25,
    "Membrane (slip ~0.5%)":                             0.35,
    "Amminico - chimico (slip ~0.1%)":                   0.15,
    "Scrubber ad acqua pressurizzata (slip ~1%)":        0.45,
}
# BOP - Balance of Plant: tutti gli ausiliari elettrici oltre l'upgrading core.
# Valori in kWh_e per Sm3 biometano netto (tipici impianti IT 300-500 Sm3/h).
#
# PRETRATTAMENTO BIOGAS (linea gas PRIMA dell'upgrading):
#   - Caricatore tramoggia / feeder biomasse a digestore: ~0.01
#   - Torre desolforazione (chimica con ricircolo reagenti, o biologica
#     con soffianti aria): ~0.03
#   - Filtro carboni attivi (solo perdita carico, minimo): ~0.01
ELEC_PRETREATMENT  = 0.05   # caricatore tramoggia + desolfo + carboni attivi
# BIOLOGIA / FERMENTAZIONE:
#   - Agitatori digestori (mesofilo, 24h): ~0.08-0.12
#   - Pompe ricircolo substrato + carico/scarico: ~0.04-0.06
ELEC_BIOLOGY       = 0.15   # agitatori digestori + pompe substrato
# PLC + CONTROLLO + SERVIZI:
#   - Quadri elettrici, UPS, strumentazione/analizzatori gas CH4/CO2/H2S
#   - Illuminazione, HVAC sala controllo, antincendio
ELEC_PLC_CONTROLS  = 0.03   # PLC, UPS, illuminazione, strumentazione
ELEC_AUX_BOP       = ELEC_PRETREATMENT + ELEC_BIOLOGY + ELEC_PLC_CONTROLS  # = 0.23

# Compressione per iniezione in rete gas (dipende dalla pressione di consegna)
# [kWh_e / Sm3 biometano netto]. Booster elettrico bi-stadio tipico.
INJECTION_PRESSURE = {
    "Bassa pressione (distribuzione 0,5-5 bar)":         0.05,
    "Media pressione (5-24 bar)":                        0.15,
    "Alta pressione (SRG/Snam 24-70 bar)":               0.25,
    "Nessuna iniezione (liquefazione/bio-CNG in loco)":  0.10,
}

# Methane slip per tecnologia (frazione di biometano lordo persa come CH4)
METHANE_SLIP = {
    "PSA (methane slip ~1.5%)":                          0.015,
    "Membrane (slip ~0.5%)":                             0.005,
    "Amminico - chimico (slip ~0.1%)":                   0.001,
    "Scrubber ad acqua pressurizzata (slip ~1%)":        0.010,
}

# Rendimenti conversione (letteratura)
ETA_BOILER_BIOGAS = 0.88     # caldaia a biogas/biometano
ETA_CHP_ELEC      = 0.40     # cogeneratore - efficienza elettrica
ETA_CHP_THERM     = 0.45     # cogeneratore - efficienza termica (calore recuperato)
LHV_BIOMETHANE_KWH = LHV_BIOMETHANE / 3.6   # 35.24 MJ/Sm3 = 9.79 kWh/Sm3 (UNI EN 16723-1)

HEAT_IS_INTERNAL = "Autoconsumo biogas/biometano"
ELEC_IS_INTERNAL = "Autoproduzione FV/cogenerazione"


def compute_aux_factor(upgrading_opt: str, heat_opt: str, elec_opt: str,
                        injection_opt: str = "Media pressione (5-24 bar)",
                        margin: float = 0.03,
                        cogen_fraction: float = 0.6,
                        recover_chp_heat: bool = True) -> dict:
    """
    Calcola aux_factor = Sm3_biometano_lordo / Sm3_biometano_netto
    dal bilancio materiale/energetico dell'impianto.

    aux_factor = 1 / (1 - f_calore - f_elettrico - f_slip - f_margine)

    Il modello contabilizza TUTTI gli autoconsumi reali d'impianto:
      - Pretrattamento biogas: caricatore tramoggia + desolfo + carboni attivi
      - Biologia: agitatori digestori + pompe ricircolo substrato
      - Upgrading core: PSA / membrane / amminico / scrubber acqua
      - Compressione iniezione rete (dipende dalla pressione di consegna)
      - PLC + controllo + strumentazione + servizi
      - Riscaldamento digestori (mesofilo) + eventuale calore upgrading

    Parametri:
      upgrading_opt:    tecnologia upgrading (da EP_UPGRADING)
      heat_opt:         fonte calore (da EP_HEAT). Se interna (biogas
                        autoconsumo) -> pesa, altrimenti no.
      elec_opt:         fonte elettricita' (da EP_ELEC). "Autoproduzione
                        FV/cogenerazione" -> pesa in proporzione alla
                        cogen_fraction (resto FV, non pesa).
      injection_opt:    pressione iniezione rete gas (da INJECTION_PRESSURE)
      margin:           perdite fisse + downtime (default 3%)
      cogen_fraction:   quota elettricita' autoprodotta coperta dal CHP
                        biogas (resto da FV); tipico 0.6.
      recover_chp_heat: se True, il calore cogenerato dal CHP copre parte
                        del fabbisogno termico dei digestori (default ON).
    """
    # --- FABBISOGNO TERMICO -------------------------------------------------
    heat_upgrading_need = HEAT_DEMAND_UPGRADING[upgrading_opt]
    heat_digestore_need = HEAT_DIGESTORE
    heat_need_gross = heat_upgrading_need + heat_digestore_need

    # --- FABBISOGNO ELETTRICO -----------------------------------------------
    elec_upgrading = ELEC_DEMAND_UPGRADING[upgrading_opt]
    elec_bop       = ELEC_AUX_BOP  # pretrattamento + biologia + PLC
    elec_injection = INJECTION_PRESSURE[injection_opt]
    elec_need      = elec_upgrading + elec_bop + elec_injection

    # --- RECUPERO CALORE COGENERATO DAL CHP ---------------------------------
    # Il CHP biogas che produce elettricita' genera anche calore di recupero
    # (η_term ~ 45%). In un impianto ben progettato, questo calore copre il
    # riscaldamento digestori + una quota dell'upgrading prima di attingere
    # alla caldaia dedicata. Si conta solo se l'elettricita' e' da cogen.
    heat_recovered = 0.0
    if recover_chp_heat and elec_opt == ELEC_IS_INTERNAL and cogen_fraction > 0:
        elec_from_chp = elec_need * cogen_fraction
        # calore cogenerato = elettr * (η_t / η_e)
        heat_recovered = elec_from_chp * (ETA_CHP_THERM / ETA_CHP_ELEC)
    heat_need_residual = max(heat_need_gross - heat_recovered, 0.0)

    # --- FRAZIONI AUTOCONSUMO (rispetto al biometano lordo) -----------------
    if heat_opt == HEAT_IS_INTERNAL:
        # calore residuo coperto da caldaia biogas dedicata
        f_heat = heat_need_residual / (LHV_BIOMETHANE_KWH * ETA_BOILER_BIOGAS)
    else:
        f_heat = 0.0

    if elec_opt == ELEC_IS_INTERNAL:
        f_elec = (elec_need * cogen_fraction) / (LHV_BIOMETHANE_KWH * ETA_CHP_ELEC)
    else:
        f_elec = 0.0

    f_slip   = METHANE_SLIP[upgrading_opt]
    f_margin = max(margin, 0.0)

    f_tot = f_heat + f_elec + f_slip + f_margin
    f_tot = min(f_tot, 0.50)  # clamp di sicurezza

    aux = 1.0 / (1.0 - f_tot)
    return {
        "aux_factor": aux,
        "f_heat": f_heat,
        "f_elec": f_elec,
        "f_slip": f_slip,
        "f_margin": f_margin,
        "f_tot": f_tot,
        # dettaglio per breakdown UI / relazione GSE
        "heat_need_gross":    heat_need_gross,
        "heat_recovered_chp": heat_recovered,
        "heat_need_residual": heat_need_residual,
        "elec_need":          elec_need,
        "elec_upgrading":     elec_upgrading,
        "elec_bop":           elec_bop,
        "elec_injection":     elec_injection,
    }

# ============================================================
# DATABASE FEEDSTOCK
# Convenzione: il "manure credit" RED III (-45 gCO2/MJ per letami/deiezioni
# animali) e' incorporato direttamente nell'eec, come da prassi GSE.
# Valori tipici da letteratura, UNI/TS 11567:2024 e parametri Consorzio Monviso.
# ============================================================
FEEDSTOCK_DB = {
    # =========================================================
    # COLTURE DEDICATE (cap 30% RED III, eec alto da coltivazione)
    # Valori eec: UNI/TS 11567:2024 + JEC WTT v5 (cat. "energy crops")
    # NB: NON sono Annex IX -> single counting CIC, no premio DM 2018
    # =========================================================
    # NB: per le colture dedicate il campo `e_l` (Land Use Change) ha
    # default 0.0 ma RICHIEDE dichiarazione no-LUC NUTS-2 del fornitore
    # per essere effettivamente assumibile come zero (RED III All. V,
    # UNI/TS 11567:2024). In assenza, l'OdC puo' imputare valori
    # punitivi tabellari. La UI mostra warning quando si selezionano.
    "Trinciato di mais": {
        "eec": 29.0, "esca": 0.0, "etd": 0.8, "yield": 116.1, "dry_matter_std": 0.35,
        "color": "#F5C518", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.5, eec=29); ST agronomica (CRPA/KTBL)",
    },
    # SORGO — la UNI/TS 11567:2024 (Prosp. A.1) tabula un'unica voce "Sorgo"
    # (580 Nm3 biogas/t ST · 52% CH4 -> 301,6 Nm3 CH4/t ST) ed eec standard 26
    # (Prosp. A.5). La norma NON differenzia i tipi: la distinzione e' agronomica
    # sulla sostanza secca, che riscala la resa per t tal quale via la
    # normalizzazione A.1 (resa = 301,6 × ST_std). Manteniamo la resa specifica
    # normativa come ancora e differenziamo solo ST e la destinazione d'uso.
    "Trinciato di sorgo da foraggio": {
        # Sorgo zuccherino/da foraggio: ST piu' bassa (raccolta lattea-cerosa).
        "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 81.4, "dry_matter_std": 0.27,
        "color": "#9CCC65", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.1/A.5); ST agronomica foraggio (CRPA/KTBL)",
    },
    "Trinciato di sorgo uso energetico (biodigestori)": {
        # Sorgo da biomassa/fibra dedicato a digestione anaerobica: ST piu' alta,
        # ibridi ad alta produzione di sostanza secca per ettaro. Resa specifica
        # mantenuta sul valore normativo UNI/TS (la norma non differenzia).
        "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 90.5, "dry_matter_std": 0.30,
        "color": "#689F38", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.1/A.5); ST agronomica sorgo da biomassa (CRPA/KTBL)",
    },
    "Triticale insilato": {
        "eec": 20.0, "esca": 0.0, "etd": 0.8, "yield": 106.1, "dry_matter_std": 0.35,
        "color": "#AED581", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec da JEC v5/KTBL (non in Prosp. A.5); ST agronomica (CRPA/KTBL)",
    },
    "Segale insilata": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 80.0, "dry_matter_std": 0.35,
        "color": "#C5E1A5", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5 / KTBL",
    },
    "Orzo insilato": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 82.0, "dry_matter_std": 0.35,
        "color": "#DCEDC8", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5",
    },
    "Loietto insilato (ryegrass)": {
        "eec": 18.0, "esca": 0.0, "etd": 0.8, "yield": 93.7, "dry_matter_std": 0.35,
        "color": "#9CCC65", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec JEC v5/KTBL (non in Prosp. A.5); ST agronomica (CRPA/KTBL)",
    },
    "Erba medica insilata": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 70.0, "dry_matter_std": 0.35,
        "color": "#7CB342", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5 (azotofissazione)",
    },
    "Doppia coltura (2° raccolto)": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 95.0, "dry_matter_std": 0.35,
        "color": "#689F38", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "GSE LG 2024 (art. doppia coltura)",
    },
    "Erbaio misto insilato": {
        # Miscuglio graminacee+leguminose (es. loiessa/orzo + veccia/trifoglio)
        # insilato a raccolta lattea-cerosa. L'azotofissazione delle leguminose
        # abbassa il concime azotato -> eec tra loietto (18) ed erba medica (15).
        # Resa: 560 Nm3 biogas/t ST x 52% CH4 x 0,22 ST ~= 64 Nm3 CH4/t t.q.
        "eec": 16.0, "esca": 0.0, "etd": 0.8, "yield": 64.0, "dry_matter_std": 0.22,
        "color": "#8BC34A", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec JEC v5/KTBL (non in Prosp. A.5); ST agronomica erbaio misto (CRPA/KTBL)",
    },
    "Barbabietola da zucchero": {
        "eec": 12.0, "esca": 0.0, "etd": 0.8, "yield": 105.0, "dry_matter_std": 0.23,
        "color": "#CE93D8", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5",
    },
    # =========================================================
    # EFFLUENTI ZOOTECNICI (manure credit RED III Annex VI)
    # All. IX RED II/III parte A lett. (d): "letame animale e fanghi
    # di depurazione". Tutti -> AVANZATI con double counting CIC.
    # Credit eec proporzionale al beneficio di stoccaggio anaerobico
    # rispetto al baseline (lagone/vasca). Liquame liquido: -45.
    # Letami palabili (minore emissione CH4 baseline): -20/-30.
    # Pollina broiler/tacchini (lettiera): -10/-15.
    # Ovaiole stoccaggio aerobico su nastro: 0 (no credit).
    # =========================================================
    "Liquame suino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#8D6E63", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto (decomposizione anaerobica spontanea)",
        "baseline_warning": "Se il fornitore ha vasca coperta con captazione/N-stripping, il credit -45 va ridotto o annullato (richiede dichiarazione fornitore).",
        "e_l": 0.0,
    },
    "Liquame bovino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#795548", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto",
        "baseline_warning": "Verificare assenza vasca coperta in stalla per validare il credit.",
        "e_l": 0.0,
    },
    "Liquame bufalino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#6D4C41", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto",
        "baseline_warning": "Verificare assenza vasca coperta in stalla per validare il credit.",
        "e_l": 0.0,
    },
    "Letame bovino palabile": {
        "eec": -30.0, "esca": 0.0, "etd": 0.8, "yield": 35.0, "dry_matter_std": 0.25,
        "color": "#A1887F", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019 Vol.4 Cap.10 + GSE",
        "baseline_assumption": "cumulo solido in stoccaggio (decomposizione parzialmente anaerobica)",
        "baseline_warning": "Se il fornitore usa compostaggio aerobico controllato, il credit va ridotto.",
        "e_l": 0.0,
    },
    "Letame equino": {
        "eec": -20.0, "esca": 0.0, "etd": 0.8, "yield": 42.0, "dry_matter_std": 0.30,
        "color": "#BCAAA4", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "JEC v5",
        "baseline_assumption": "cumulo solido in scuderia/box",
        "baseline_warning": "Verificare modalità stoccaggio per validare il credit.",
        "e_l": 0.0,
    },
    "Pollina ovaiole (aerobico)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 84.0, "dry_matter_std": 0.60,
        "color": "#FF9800", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "GSE (no credit anaerobico)",
        "baseline_assumption": "essiccatore aerobico su nastro (gabbie arricchite moderne)",
        "baseline_warning": "Se il fornitore stocca in fossa anaerobica sotto le gabbie, il valore +5 va rivisto verso negativo (credit) come per pollina broiler (-15).",
        "e_l": 0.0,
    },
    "Pollina broiler (lettiera)": {
        "eec": -15.0, "esca": 0.0, "etd": 0.8, "yield": 105.0, "dry_matter_std": 0.60,
        "color": "#FFA726", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "lettiera in capannone (decomposizione parzialmente anaerobica)",
        "baseline_warning": "Verificare frequenza rimozione lettiera per validare il credit.",
        "e_l": 0.0,
    },
    "Pollina tacchini": {
        "eec": -10.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.60,
        "color": "#FFB74D", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019",
        "baseline_assumption": "lettiera in capannone",
        "baseline_warning": "Verificare modalità stoccaggio per validare il credit.",
        "e_l": 0.0,
    },
    "Deiezioni conigli": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 75.0, "dry_matter_std": 0.50,
        "color": "#FFCC80", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "eec JEC v5 (std A.5=0); All. IX RED III parte A",
        "baseline_assumption": "fossa di stoccaggio in conigliera",
        "baseline_warning": "Verificare modalità stoccaggio per validare l'eec.",
        "e_l": 0.0,
    },
    # =========================================================
    # SOTTOPRODOTTI AGROINDUSTRIALI (All. IX RED II/III)
    # Tutti -> AVANZATI con double counting CIC.
    # - Sanse, vinacce, raspi, fecce, lolla -> All. IX A (h, i, k, m)
    # - Scarti caseari, panificazione, ortofrutta -> All. IX A (c, m)
    # - UCO, scarti macellazione cat. 3 -> All. IX B (oli/grassi)
    # =========================================================
    "Sansa di olive umida": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 120.0, "dry_matter_std": 0.30,
        "color": "#6A1B9A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5 / All. IX RED III",
    },
    "Sansa vergine": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 140.0, "dry_matter_std": 0.50,
        "color": "#7B1FA2", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Pastazzo di agrumi": {
        "eec": 6.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.18,
        "color": "#FFB300", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Vinaccia (con raspi)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 130.0, "dry_matter_std": 0.30,
        "color": "#880E4F", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Raspi d'uva": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 70.0, "dry_matter_std": 0.35,
        "color": "#AD1457", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Feccia vinicola": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.10,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Siero di latte": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 30.0, "dry_matter_std": 0.06,
        "color": "#FFF9C4", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Scotta (siero residuo)": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 22.0, "dry_matter_std": 0.06,
        "color": "#FFF59D", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Trebbie di birra": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 140.0, "dry_matter_std": 0.25,
        "color": "#D4A574", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Lolla/pula di riso": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 50.0, "dry_matter_std": 0.90,
        "color": "#F5DEB3", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Melasso": {
        "eec": 8.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.75,
        "color": "#5D4037", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Scarti panificazione/pasticceria": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 280.0, "dry_matter_std": 0.80,
        "color": "#D7CCC8", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5, alta resa zuccheri (non in Prosp. A.5)",
    },
    "Grassi esausti / UCO": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 700.0, "dry_matter_std": 0.99,
        "color": "#FFE082", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",
        "src": "JEC v5 (lipidi, All. IX parte B)",
    },
    "Scarti macellazione (cat. 3)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.30,
        "color": "#EF5350", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",
        "src": "JEC v5 / Reg. 1069/2009",
    },
    "Sottoprodotti ortofrutticoli": {
        "eec": 7.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.15,
        "color": "#66BB6A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Scarti caseari vari": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 40.0, "dry_matter_std": 0.15,
        "color": "#E1BEE7", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Fanghi agro-industriali": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 55.0, "dry_matter_std": 0.10,
        "color": "#90A4AE", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Polpe di barbabietola fresche": {
        "eec": 0.0, "esca": 0.0, "etd": 2.0, "yield": 50.0, "dry_matter_std": 0.22,
        "color": "#F48FB1", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 by-product allocation (non in Prosp. A.5)",
    },
    "Polpe di barbabietola insilate": {
        "eec": 0.0, "esca": 0.0, "etd": 2.5, "yield": 75.0, "dry_matter_std": 0.28,
        "color": "#EC407A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 (non in Prosp. A.5)",
    },
    "Melasso di barbabietola": {
        "eec": 0.0, "esca": 0.0, "etd": 1.5, "yield": 280.0, "dry_matter_std": 0.75,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 (non in Prosp. A.5)",
    },
    # =========================================================
    # FORSU / RIFIUTI (All. IX RED II/III, parte A)
    # All. IX A (c): bio-waste · (d): sewage sludge
    # Tutti -> AVANZATI con double counting CIC.
    # =========================================================
    "FORSU selezionata": {
        # Resa da UNI/TS A.3: 450 Nm3 biogas/t ST x 60% CH4 x 0,24 ST = 64,8 Nm3 CH4/t t.q.
        "eec": 0.0, "esca": 0.0, "etd": 0.8, "yield": 64.8, "dry_matter_std": 0.24,
        "color": "#546E7A", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024 (Prosp. A.5 eec=0; resa A.3: 450x60%x0,24)",
    },
    "Fanghi depurazione": {
        # Resa da UNI/TS A.3: 350 Nm3 biogas/t ST x 62% CH4 x 0,06 ST = 13,0 Nm3 CH4/t t.q.
        "eec": 0.0, "esca": 0.0, "etd": 0.8, "yield": 13.0, "dry_matter_std": 0.06,
        "color": "#78909C", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024 (Prosp. A.5 eec=0; resa A.3: 350x62%x0,06)",
    },
}

# Tutti i feedstock disponibili (per retrocompatibilita' solver).
FEED_NAMES = list(FEEDSTOCK_DB.keys())


# =============================================================================
# Classificazione "tier" difendibilita' valore eec (audit-ready, non attaccabile)
# -----------------------------------------------------------------------------
# Unica sorgente di verita' usata da UI + export PDF/Excel/dossier.
# Un certificatore (RINA/OdC) contesta solo i valori FAVOREVOLI e non provati.
# Ogni eec ricade in uno di questi stati, tutti difendibili per costruzione:
#   A  Default normativo   -> UNI/TS A.5 / RED III All. V-VI (mais, sorgo, =0 rifiuti)
#   B  Zero da regola      -> residuo/rifiuto Annex IX: eec=0 fino a raccolta (RED III)
#   C  Conservativo (lett.) -> JEC v5/KTBL, eec>=0 = stima a SFAVORE -> non contestabile
#   D  Credito da provare  -> manure credit negativo: richiede dichiarazione baseline
# Solo il tier D necessita documento esterno; tutti gli altri sono auto-difesi.
# =============================================================================
def eec_tier(meta: dict) -> dict:
    """Ritorna {code, label, defendable, note} per una voce FEEDSTOCK_DB."""
    src = (meta.get("src") or "").strip()
    sl = src.lower()
    eec = float(meta.get("eec", 0.0) or 0.0)
    if src.startswith("UNI-TS"):
        if eec == 0.0:
            return {"code": "A", "label": "Default normativo (A.5, rifiuto eec=0)",
                    "defendable": True,
                    "note": "Valore tabellato UNI/TS 11567:2024 Prosp. A.5."}
        return {"code": "A", "label": "Default normativo (A.5)",
                "defendable": True,
                "note": "Valore tabellato UNI/TS 11567:2024 Prosp. A.5."}
    if "manure credit red iii" in sl or (eec < 0 and "manure" in sl):
        return {"code": "D", "label": "Credito stoccaggio (da dichiarazione)",
                "defendable": False,
                "note": "Manure credit RED III All. VI: applicabile SOLO con "
                        "dichiarazione baseline di stoccaggio del fornitore."}
    if eec < 0:
        return {"code": "D", "label": "Credito negativo (da documentare)",
                "defendable": False,
                "note": "eec negativo: richiede giustificazione documentale."}
    if eec == 0.0:
        return {"code": "B", "label": "Zero da regola (residuo/rifiuto)",
                "defendable": True,
                "note": "Annex IX RED III: residui/rifiuti = 0 emissioni a monte "
                        "fino alla raccolta. Difendibile per regola."}
    return {"code": "C", "label": "Stima conservativa (letteratura)",
            "defendable": True,
            "note": "Valore JEC v5/KTBL con eec>0: stima a sfavore dell'operatore "
                    "(riduce il saving) -> nessun incentivo alla contestazione."}

# Raggruppamento per categoria (per UI multiselect strutturato).
def _feeds_by_category():
    cats = {}
    for name, d in FEEDSTOCK_DB.items():
        cats.setdefault(d.get("cat", "Altro"), []).append(name)
    return cats

FEEDSTOCK_CATEGORIES = _feeds_by_category()


# ============================================================
# BMT OVERRIDE — Resa effettiva (BMT certificato vs tabella standard)
# ============================================================
# `_EFFECTIVE_YIELDS` viene popolato dalla UI sidebar all'inizio di ogni
# Streamlit run, DOPO che l'utente ha definito eventuali override BMT
# certificati (vedi bmt_override.py). Tutte le funzioni di calcolo
# (ghg_summary, solve_*, lp_optimize) e tutte le tabelle/export (UI,
# CSV, Excel, PDF) leggono la resa via `_yield_of(name)` invece di
# `FEEDSTOCK_DB[name]["yield"]`, in modo che l'override BMT venga
# applicato in modo coerente ovunque. La tabella standard NON viene
# mai modificata: l'override e' solo un "sovrascrittura runtime"
# tracciabile per la singola biomassa.
_EFFECTIVE_YIELDS: dict[str, float] = {}
_EFFECTIVE_DRY_MATTERS: dict[str, float] = {}


def _yield_of(name: str) -> float:
    """Resa effettiva [Nm3 CH4/t] = (override BMT se attivo, altrimenti tabella)
    normalizzata in base al rapporto tra sostanza secca reale e standard.
    """
    if name in _EFFECTIVE_YIELDS:
        base_yield = float(_EFFECTIVE_YIELDS[name])
    else:
        base_yield = float(FEEDSTOCK_DB[name]["yield"])

    sts = float(FEEDSTOCK_DB[name].get("dry_matter_std", 1.0))
    sta = float(_EFFECTIVE_DRY_MATTERS[name]) if name in _EFFECTIVE_DRY_MATTERS else sts

    if sts > 0:
        return base_yield * (sta / sts)
    return base_yield


# Default biomasse attive: mix iniziale diversificato (colture + effluenti).
DEFAULT_ACTIVE_FEEDS = [
    "Trinciato di mais",
    "Trinciato di sorgo da foraggio",
    "Pollina ovaiole (aerobico)",
    "Liquame suino",
]

MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]


# ============================================================
# FUNZIONI DI CALCOLO
# ============================================================
# ============================================================
# OVERRIDE FATTORI EMISSIVI REALI — runtime cache
# ============================================================
# `_EMISSION_OVERRIDES` viene popolato dalla UI sidebar all'inizio di
# ogni Streamlit run, DOPO che l'utente ha caricato eventuali relazioni
# tecniche (vedi emission_factors_override.py). Tutte le funzioni di
# calcolo (e_total_feedstock, ghg_summary, solve_*, lp_optimize) e i
# siti di display (database UI, audit, export) leggono i fattori
# tramite e_total_feedstock() / _emission_factors_of() che consulta
# automaticamente l'override quando attivo. La tabella standard
# FEEDSTOCK_DB NON viene mai modificata.
#
# Struttura: {name: {"eec":..., "esca":..., "etd":..., "ep":...,
#                    "extra":..., "source": str, "e_total": float}}
_EMISSION_OVERRIDES: dict[str, dict] = {}


def _manure_credit_allowed() -> bool:
    """True = manure credit (eec<0) applicato sui valori standard.

    Default True: il credito da stoccaggio anaerobico evitato e' la prassi
    GSE/RED III All. VI standard per gli effluenti zootecnici, ed e' il
    comportamento atteso del calcolo GHG. La dichiarazione baseline del
    fornitore e' un requisito DOCUMENTALE per l'audit, non un interruttore
    del calcolo: la sua assenza non deve azzerare il credito (renderebbe il
    saving artificiosamente penalizzante). L'utente puo' comunque disattivarlo
    esplicitamente (es. per uno scenario ultra-conservativo) togliendo la
    spunta. Difensivo fuori dal contesto Streamlit (test): ritorna True.
    """
    try:
        return bool(st.session_state.get("manure_credit_declared", True))
    except Exception:  # noqa: BLE001
        return True


def _emission_factors_of(name: str, ep_default: float = 0.0) -> dict:
    """Fattori emissivi effettivi per una biomassa.

    Se esiste un override REALE attivo (relazione tecnica caricata),
    ritorna una COPIA dei fattori reali (la cache non viene mai
    mutata da chiamanti esterni). Altrimenti ritorna i fattori
    standard tabellari (FEEDSTOCK_DB) + ep impianto-wide.

    Output dict: eec, e_l, esca, etd, ep, extra, source.
    NB: e_l (Land Use Change) default 0 per Annex IX/sottoprodotti;
    per food/feed crops va dichiarato dal fornitore (no-LUC NUTS-2)
    altrimenti puo' essere imputato come default punitivo dall'OdC.
    """
    if name in _EMISSION_OVERRIDES:
        # Defensive shallow copy: previene che eventuali mutazioni nei
        # consumer (display, audit, etc.) corrompano la cache runtime.
        return dict(_EMISSION_OVERRIDES[name])
    d = FEEDSTOCK_DB[name]
    eec_val = float(d["eec"])
    # Gating manure credit (tier D) sui SOLI valori standard.
    # Un eec negativo (credito da stoccaggio anaerobico evitato) e'
    # contestabile dall'OdC se non c'e' la dichiarazione baseline del
    # fornitore. Senza attestazione -> azzerato a 0 (residuo Annex IX,
    # conservativo e inattaccabile per costruzione). Con valori CERTIFICATI
    # (override relazione tecnica) il ramo sopra ritorna prima: il credito
    # resta perche' gia' coperto dalla certificazione delle emissioni.
    _gated = False
    if eec_val < 0 and not _manure_credit_allowed():
        eec_val = 0.0
        _gated = True
    return {
        "eec":   eec_val,
        "e_l":   float(d.get("e_l", 0.0)),
        "esca":  float(d["esca"]),
        "etd":   float(d["etd"]),
        "ep":    float(ep_default),
        "extra": 0.0,
        "source": EF_SOURCE_STD,
        "manure_credit_gated": _gated,
        "requires_no_luc_declaration": bool(d.get("requires_no_luc_declaration", False)),
    }


def e_total_feedstock(name: str, ep: float = 0.0) -> float:
    """Emissioni totali gCO2eq/MJ per singolo feedstock.

    Formula RED III All. V Parte C (componenti applicate):
        e_total = eec + e_l + etd + ep - esca - crediti_extra

    Convenzione segno:
      - eec puo' essere negativo (manure credit gia' incorporato)
      - e_l (Land Use Change): 0 per residui/sottoprodotti Annex IX;
        per food/feed richiede dichiarazione no-LUC NUTS-2 fornitore
      - esca e' un credito positivo SOTTRATTO una sola volta
      - crediti_extra: crediti AGGIUNTIVI dichiarati nella relazione
        tecnica (default 0); MAI doppia sottrazione di voci gia' in esca

    Se l'utente ha attivato un override REALE da relazione tecnica
    per questa biomassa, usa i valori reali. Altrimenti usa i
    valori standard FEEDSTOCK_DB[name] e ep impianto-wide passato.
    """
    f = _emission_factors_of(name, ep)
    # Compatibilità deploy: se Streamlit Cloud serve ancora una versione
    # cached di emission_factors_override senza il parametro e_l (Patch 8),
    # ricadiamo sulla firma legacy. e_l e' addizionato manualmente al
    # totale per preservare la correttezza RED III All. V Parte C.
    _e_l = float(f.get("e_l") or 0.0)
    try:
        return calculate_emission_total(
            f["eec"], f["esca"], f["etd"], f["ep"], f.get("extra", 0.0),
            e_l=_e_l,
        )
    except TypeError:
        return calculate_emission_total(
            f["eec"], f["esca"], f["etd"], f["ep"], f.get("extra", 0.0),
        ) + _e_l


def ghg_summary(masses: dict, aux: float, ep: float = 0.0,
                fossil_comparator: float | None = None):
    """
    Calcola il bilancio GHG del biometano secondo RED III / Allegato V Parte C.

    PRINCIPIO NORMATIVO (RED III + GSE Regole Applicative DM 2022):
    ─────────────────────────────────────────────────────────────────
    • La SOSTENIBILITÀ va verificata su TUTTA la biomassa consumata
      (comprensiva degli autoconsumi per caldaia, CHP interno, upgrading):
        → GHG saving = f(e_w calcolato sul LORDO)
    • L'INCENTIVO (tariffa €/MWh) si applica ai Sm³ NETTI immessi in rete
        → Ricavi = nm3_net × NM3_TO_MWH × tariffa
    • Il coefficiente SA (Servizi Ausiliari) del GSE è l'equivalente di (aux - 1)
      applicato sulla quota di autoconsumo energetico dell'impianto.
    • Fonte: D.Lgs. 199/2021 All.V Parte C, GSE Regole Applicative DM 2022
             Rev. maggio 2024 (Decreto n.248/2024)

    Parametri:
      masses: {feedstock_name: massa_t}  — biomasse del periodo
      aux:    aux_factor = Sm³_lordi / Sm³_netti  (da compute_aux_factor)
      ep:     contributo processing impianto [gCO2eq/MJ] (upgrading+calore+elettr.)
      fossil_comparator: comparator fossile [gCO2eq/MJ]; se None usa FOSSIL_COMPARATOR

    Ritorna dict con:
      e_w           — emissioni ponderate [gCO2eq/MJ] (sul lordo, norma RED III)
      saving        — saving GHG [%] rispetto al comparator fossile
      nm3_gross     — Sm³ biogas lordo totale (da biomassa → fermentatori)
      nm3_net       — Sm³ biometano netto (a valle upgrading + autoconsumi)
      mwh_net       — MWh biometano netto (base ricavi incentivo)
      mj_gross      — MJ energia biogas lordo (base calcolo sostenibilità)
      mj_net        — MJ energia biometano netto
      sustainability_basis — 'gross' (conferma che il GHG è calcolato sul lordo)
    """
    total_mj = 0.0
    total_e_mj = 0.0
    total_nm3 = 0.0
    for name, m in masses.items():
        if m is None or m <= 0:
            continue
        nm3 = m * _yield_of(name)  # Sm³ biogas lordo da questa biomassa
        mj  = nm3 * LHV_BIOMETHANE  # MJ sul lordo (PCI biometano spec rete UNI EN 16723-1)
        e   = e_total_feedstock(name, ep)
        total_mj   += mj
        total_e_mj += e * mj
        total_nm3  += nm3
    if total_mj <= 0:
        e_w    = 0.0
        saving = 0.0
    else:
        e_w    = total_e_mj / total_mj   # gCO2eq/MJ — calcolato sul LORDO (norma)
        _cmp   = fossil_comparator if fossil_comparator is not None else FOSSIL_COMPARATOR
        saving = (_cmp - e_w) / _cmp * 100
    # Netto: Sm³ e MJ a valle upgrading + autoconsumi (base ricavi)
    nm3_net = total_nm3 / aux if aux > 0 else 0.0
    mj_net  = nm3_net * LHV_BIOMETHANE
    return {
        "e_w":                e_w,
        "saving":             saving,
        "nm3_gross":          total_nm3,    # lordo: base sostenibilità RED III
        "nm3_net":            nm3_net,      # netto: base ricavi/incentivo
        "mwh_net":            nm3_net * NM3_TO_MWH,
        "mj_gross":           total_mj,     # MJ lordo (per audit GHG)
        "mj_net":             mj_net,       # MJ netto (per PCI check)
        "sustainability_basis": "gross",    # conferma normativa
    }


def solve_1_unknown_production(fixed_masses: dict, unknown: str,
                                hours: float, aux: float,
                                plant_net: float = DEFAULT_PLANT_NET_SMCH) -> float:
    """
    Modalita' (N-1)+1: risolve 1 incognita soddisfando SOLO la produzione lorda.
    Generalizzato per N biomasse: itera sulle chiavi di fixed_masses.
    plant_net: taglia netta autorizzata (Sm3/h); default 300.
    """
    gross_target = plant_net * aux * hours
    covered = sum(
        (fixed_masses.get(n) or 0.0) * _yield_of(n)
        for n in fixed_masses.keys() if n != unknown
    )
    remaining = gross_target - covered
    return remaining / _yield_of(unknown)


def solve_2_unknowns_dual(fixed_masses: dict, unknowns: list,
                           hours: float, aux: float,
                           plant_net: float = DEFAULT_PLANT_NET_SMCH,
                           ep: float = 0.0,
                           target_e_max: float = 17.86):
    """
    Modalita' 2+2: risolve sistema lineare 2x2.
      Eq.1 (produzione):
          sum(mass_i * yield_i) = plant_net * aux * hours
      Eq.2 (saving target, cioe' e_w = target_e_max):
          sum((e_i - target_e_max) * yield_i * mass_i) = 0
    ep: contributo processing impianto, applicato a ciascun feedstock.
    target_e_max: emissioni target [gCO2eq/MJ] per raggiungere saving target.
    """
    gross_target = plant_net * aux * hours
    # RHS, togliendo contributi delle 2 fisse
    rhs_prod = gross_target
    rhs_sust = 0.0
    for n, m in fixed_masses.items():
        if m is None:
            m = 0.0
        d = FEEDSTOCK_DB[n]
        y = _yield_of(n)  # resa effettiva (BMT override se attivo)
        e = e_total_feedstock(n, ep)
        rhs_prod -= m * y
        rhs_sust -= m * y * (e - target_e_max)

    x, y_name = unknowns
    dx = FEEDSTOCK_DB[x]; dy = FEEDSTOCK_DB[y_name]
    yx = _yield_of(x); yy = _yield_of(y_name)
    ex = e_total_feedstock(x, ep) - target_e_max
    ey = e_total_feedstock(y_name, ep) - target_e_max

    A = np.array([[yx, yy],
                  [yx * ex, yy * ey]], dtype=float)
    b = np.array([rhs_prod, rhs_sust], dtype=float)

    if abs(np.linalg.det(A)) < 1e-9:
        return {x: 0.0, y_name: 0.0}, False, _t("Sistema singolare: le 2 biomasse incognite sono linearmente dipendenti.")

    sol = np.linalg.solve(A, b)
    mx, my = float(sol[0]), float(sol[1])

    # Check feasibility
    if mx >= -1e-6 and my >= -1e-6:
        return {x: max(mx, 0), y_name: max(my, 0)}, True, ""

    # Infeasibile: forza il negativo a 0 e ricalcola l'altro con sola produzione
    note = []
    if mx < 0:
        note.append(f"**{_t(x)}** {_t('richiederebbe')} {fmt_it(mx, 1)} {_t('t (<0)')}")
        mx = 0.0
        my = rhs_prod / yy
        if my < 0:
            my = 0.0
            note.append(f"{_t('anche')} **{_t(y_name)}** <0: {_t('entrambe azzerate')}")
    elif my < 0:
        note.append(f"**{_t(y_name)}** {_t('richiederebbe')} {fmt_it(my, 1)} {_t('t (<0)')}")
        my = 0.0
        mx = rhs_prod / yx
        if mx < 0:
            mx = 0.0
            note.append(f"{_t('anche')} **{_t(x)}** <0: {_t('entrambe azzerate')}")
    msg = _t("Infeasibile:") + " " + "; ".join(note) + ". " + _t("Saving e/o produzione non saranno entrambi soddisfatti.")
    return {x: mx, y_name: my}, False, msg


def find_optimal_pair(aux: float, plant_net: float, ep: float,
                      target_e_max: float, feed_list: list = None):
    """
    Trova il mix di biomasse (1 o 2 attive, le altre a 0) che MINIMIZZA la
    massa totale rispettando:
      - produzione lorda = plant_net * aux * ore (vincolo di uguaglianza)
      - e_w <= target_e_max  (saving GHG >= target solver, leggermente sopra
        la soglia RED III)

    feed_list: lista delle N biomasse attive nell'impianto del cliente.
               Se None, usa tutte quelle nel DB (retrocompatibilita').
               Enumerazione combinatoria su C(N, 2) coppie.

    Ritorna (pair, total_per_hour, masses_per_hour) o None se infeasibile.
    `pair` e' sempre una tuple di 2 nomi (se mono, il 2o nome e' incluso ma
    con massa 0) per retrocompatibilita' con il codice chiamante.

    Teoria LP: con 2 vincoli (produzione = equality, saving = inequality) e
    N variabili non-negative, l'ottimo e' su un vertice con <=2 variabili
    positive.  Due famiglie di vertici:
      (a) MONO: 1 sola biomassa attiva; richiede che il suo e_total sia gia'
          <= target_e_max (saving >= target).  Massa = gross_target / yield.
      (b) COPPIA: 2 biomasse attive, vincolo saving attivo (=target).
          Sistema 2x2 risolto da solve_2_unknowns_dual.
    Il teorema LP garantisce che enumerare MONO + tutte le coppie C(N,2) e'
    sufficiente per trovare l'ottimo globale (vertice della regione ammissibile).

    Complessita': O(N^2). Per N=30: 435 coppie, <50ms. Scalabile.

    NB: la coppia ottimale NON dipende dalle ore: la soluzione scala
    linearmente, quindi il mix migliore per 1 h e' lo stesso per ogni mese.
    """
    from itertools import combinations

    if feed_list is None:
        feed_list = FEED_NAMES
    if len(feed_list) < 1:
        return None

    gross_target = plant_net * aux * 1.0  # per 1 ora
    best = None  # (pair_tuple, total_per_hour, masses_per_hour)

    # --- (a) MONO: enumera N singole biomasse attive -------------------------
    # Con vincolo saving in forma di DISUGUAGLIANZA, se una singola biomassa
    # ha gia' e_total <= target_e_max (over-performance rispetto alla soglia)
    # allora soddisfa entrambi i vincoli da sola, e la sua massa e'
    # gross_target / yield.  Candidato naturale per minima massa totale.
    for n in feed_list:
        e_n = e_total_feedstock(n, ep)
        if e_n <= target_e_max + 1e-9:  # saving >= target
            y_n = _yield_of(n)  # resa effettiva (BMT override se attivo)
            if y_n <= 0:
                continue
            m_n = gross_target / y_n
            masses_h = {k: 0.0 for k in feed_list}
            masses_h[n] = m_n
            total_h = m_n
            # Per banner/UI: completa con un "secondo nome" (la biomassa a
            # massa zero con e_total minima, la piu' "amica" come fallback).
            others = [x for x in feed_list if x != n]
            other = (
                min(others, key=lambda x: e_total_feedstock(x, ep))
                if others else n
            )
            pair_tuple = (n, other)
            if best is None or total_h < best[1] - 1e-9:
                best = (pair_tuple, total_h, masses_h)

    # --- (b) COPPIE: enumera C(N,2) vertici con saving=target ----------------
    # Per N=4: 6 coppie. N=10: 45. N=20: 190. N=30: 435. Sempre fattibile.
    for pair in combinations(feed_list, 2):
        fixed0 = {n: 0.0 for n in feed_list if n not in pair}
        sol, feas, _ = solve_2_unknowns_dual(
            fixed_masses=fixed0, unknowns=list(pair),
            hours=1.0, aux=aux, plant_net=plant_net,
            ep=ep, target_e_max=target_e_max,
        )
        if not feas:
            continue
        if any(v < -1e-6 for v in sol.values()):
            continue
        masses_h = {**fixed0, **{k: max(v, 0.0) for k, v in sol.items()}}
        total_h = sum(masses_h.values())
        if best is None or total_h < best[1] - 1e-9:
            best = (pair, total_h, masses_h)

    return best  # (pair, total_per_hour, masses_per_hour) o None


# ===========================================================
# UI
# ===========================================================
st.set_page_config(
    page_title="Metan.iQ — Biometano DM 2022 (RED III)",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===========================================================
# Metan.iQ Theme Switcher (light / dark)
# ===========================================================
# =============================================================================
# AUTH GATE (Fase 2.1) — bypass se demo_mode (default true). Quando l'utente
# attiva auth in produzione (`secrets.toml` → [auth] demo_mode=false), questo
# blocco mostra il form login/signup PRIMA del rendering del main panel.
# =============================================================================
try:
    from core.auth_ui import render_auth_gate, render_account_widget
    if not render_auth_gate():
        st.stop()
except ImportError:
    # Auth module non disponibile (es. deploy senza bcrypt installato) → skip
    pass

if "methaniq_theme" not in st.session_state:
    st.session_state.methaniq_theme = "light"

# Nota: il selettore lingua è renderizzato in sidebar SUBITO DOPO il brand
# badge (Metan.iQ / Carlo Sicurini / Biometano), così la testata della
# sidebar mostra prima l'identità del prodotto e poi le impostazioni utente.
# Vedi `_LANG = render_lang_selector()` dopo `with st.sidebar:` brand block.
_LANG = get_lang()  # bootstrap iniziale dal session_state per i moduli a valle
MONTHS = [_t(m) for m in MONTHS]

# ── Colori provvisori per sidebar (definiti prima del Design System completo) ──
AMBER       = "#9A7B3C"   # provvisorio -> BRASS editoriale
ACCENT      = AMBER
BORDER      = "#E4DDCD"
TEXT_MUTED   = "#726C5E"
_SIDEBAR_PRE_DARK = st.session_state.methaniq_theme == "dark"
_SIDEBAR_PRE_LABEL = "#CBD5E1" if _SIDEBAR_PRE_DARK else "#64748B"

# =============================================================================
# BRAND BADGE — in cima alla sidebar (identità del prodotto prima delle
# impostazioni). Colori hardcoded perché PRIMARY/SECONDARY/ACCENT vengono
# definite a riga 1597+ (dopo questa posizione). Hard-code coerenti col tema
# dark navy del badge originale.
# =============================================================================
_BRAND_PRIMARY = "#15242E"      # editorial NAVY (flat)
_BRAND_SECONDARY = "#1F343F"    # NAVY 2
_BRAND_ACCENT = "#B59450"       # BRASS 2 (su fondo scuro)
_brand_badge_label = "Biometano · DM 2022"  # match _MODE['badge'] biometano

with st.sidebar:
    st.markdown(
        f"""
        <div class="metaniq-brandcard" style='
            padding: 20px 18px;
            background: {_BRAND_PRIMARY};
            border-radius: 10px;
            margin-bottom: 18px;
            border: 1px solid rgba(181,148,80,0.22);
            border-top: 3px solid {_BRAND_ACCENT};
            overflow: hidden;
            position: relative;
        '>
            <div style='
                font-family: "Outfit", sans-serif;
                color: {_BRAND_ACCENT};
                font-size: 0.62em;
                font-weight: 600;
                letter-spacing: 2.5px;
                text-transform: uppercase;
                margin-bottom: 8px;
            '>PLATFORM</div>
            <div style='
                font-family: "Outfit", sans-serif;
                color: #F7F4EC;
                font-size: 1.55em;
                font-weight: 700;
                letter-spacing: -0.6px;
                line-height: 1;
            '>Metan<span style="color:{_BRAND_ACCENT};">.</span>iQ</div>
            <div style='
                font-size: 0.72em;
                color: #A49D8C;
                margin-top: 7px;
                font-weight: 400;
            '>by <span style='color:#E4DDCD; font-weight:600;'>Carlo Sicurini</span></div>
            <div style='
                margin-top: 13px;
                padding-top: 11px;
                border-top: 1px solid rgba(181,148,80,0.18);
                font-size: 0.62em;
                color: #C9C3B2;
                font-weight: 500;
                letter-spacing: 1.5px;
                text-transform: uppercase;
            '>{_brand_badge_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Widget account (sidebar) per utente loggato — no-op in demo_mode.
try:
    render_account_widget()
except (NameError, Exception):  # noqa: BLE001
    pass

# Selettore Italiano / English subito sotto il brand badge.
_LANG = render_lang_selector()

with st.sidebar:
    st.markdown(
        f"""
        <div style='font-size:0.85rem; font-weight:800; letter-spacing:1.5px;
             text-transform:uppercase; color:{AMBER}; margin-bottom:15px; border-bottom: 2px solid {AMBER}; padding-bottom:4px; margin-top:18px;'>
             ⚙️ Settings / Opzioni
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style='font-size:0.7rem; font-weight:700; letter-spacing:1px; 
             text-transform:uppercase; color:{_SIDEBAR_PRE_LABEL}; margin-bottom:8px; margin-left:2px;'>
             🎨 Tema / Appearance
        </div>
        """,
        unsafe_allow_html=True,
    )
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        if st.button(
            "☀️ Light",
            use_container_width=True,
            type="primary" if st.session_state.methaniq_theme == "light" else "secondary",
            key="btn_theme_light",
        ):
            st.session_state.methaniq_theme = "light"
            st.rerun()
    with _tc2:
        if st.button(
            "🌙 Dark",
            use_container_width=True,
            type="primary" if st.session_state.methaniq_theme == "dark" else "secondary",
            key="btn_theme_dark",
        ):
            st.session_state.methaniq_theme = "dark"
            st.rerun()
    st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

    # =======================================================
    # ANAGRAFICA SIMULAZIONE
    # ----------------------------------------------------------
    # Dati identificativi azienda + impianto. Usati per:
    #   - intestazione report PDF/Excel/CSV
    #   - auto-popolamento ID impianto in tab Operatività Giornaliera
    # I dati restano nella sessione corrente (non persistiti su disco
    # per evitare commit di dati cliente nel repo o problemi di privacy
    # su Streamlit Cloud — ephemeral storage).
    # =======================================================
    st.markdown(
        f"<div style='font-size:0.7rem; font-weight:700; letter-spacing:1px;"
        f" text-transform:uppercase; color:{_SIDEBAR_PRE_LABEL}; margin-bottom:6px;"
        f" margin-left:2px;'>🏢 {_t('Anagrafica simulazione')}</div>",
        unsafe_allow_html=True,
    )
    with st.expander(_t("Dati azienda e impianto"), expanded=False):
        company_name = st.text_input(
            _t("Nome azienda"),
            value=st.session_state.get("company_name", ""),
            key="company_name",
            placeholder=_t("Es. Bioenergia Valpadana S.r.l."),
        )
        company_legal_address = st.text_input(
            _t("Sede legale"),
            value=st.session_state.get("company_legal_address", ""),
            key="company_legal_address",
            placeholder=_t("Via, civico, CAP, città (PR)"),
        )
        plant_name = st.text_input(
            _t("Nome impianto"),
            value=st.session_state.get("plant_name", ""),
            key="plant_name",
            placeholder=_t("Es. Impianto Cascina San Giorgio"),
        )
        plant_operational_address = st.text_input(
            _t("Sede operativa"),
            value=st.session_state.get("plant_operational_address", ""),
            key="plant_operational_address",
            placeholder=_t("Indirizzo dell'impianto"),
        )
        # === Identificativi obbligatori per audit OdC UNI/TS 11567:2024 ===
        _col_id1, _col_id2 = st.columns(2)
        with _col_id1:
            company_vat = st.text_input(
                "P.IVA / " + _t("Codice Fiscale"),
                value=st.session_state.get("company_vat", ""),
                key="company_vat",
                placeholder="IT01234567890",
                help=_t("Obbligatorio per dichiarazione di sostenibilità."),
            )
        with _col_id2:
            plant_cui = st.text_input(
                "CUI / " + _t("Codice GSE"),
                value=st.session_state.get("plant_cui", ""),
                key="plant_cui",
                placeholder="IT00X-YYYY-NNNN",
                help=_t("Codice Unico Impianto (Portale GSE)."),
            )
        responsible_name = st.text_input(
            _t("Responsabile sostenibilità (nome e qualifica)"),
            value=st.session_state.get("responsible_name", ""),
            key="responsible_name",
            placeholder=_t("Es. Mario Rossi — Resp. Sostenibilità"),
            help=_t("Firma del Lotto di Sostenibilità per audit OdC."),
        )
        st.caption(
            "ℹ️ " + _t("Questi dati appaiono nell'intestazione dei report "
                       "esportati (PDF/Excel/CSV) e identificano l'impianto "
                       "nel database della Gestione Giornaliera. P.IVA, CUI e "
                       "Responsabile sono richiesti per la conformità "
                       "UNI/TS 11567:2024 in fase di audit OdC.")
        )

    # NB: 'Registro fornitori' e 'Backup & Restore' sono temporaneamente
    # disabilitati. Il primo deploy con `st.data_editor` ha causato
    # rerun-loop su Streamlit Cloud (sidebar non renderizzata).
    # Re-introdurli con pattern session_state-safe in patch dedicate.
    # Il PDF mostra placeholder warning quando suppliers_registry e' vuoto.
    st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

# Espone le variabili a livello modulo (anche se non compilate sono "")
COMPANY_NAME              = st.session_state.get("company_name", "")
COMPANY_LEGAL_ADDRESS     = st.session_state.get("company_legal_address", "")
PLANT_NAME                = st.session_state.get("plant_name", "")
PLANT_OPERATIONAL_ADDRESS = st.session_state.get("plant_operational_address", "")
COMPANY_VAT               = st.session_state.get("company_vat", "")
PLANT_CUI                 = st.session_state.get("plant_cui", "")
RESPONSIBLE_NAME          = st.session_state.get("responsible_name", "")

# ===========================================================
# Metan.iQ Mode - DM 2022 (RED III)
# ===========================================================
st.session_state.app_mode = "biometano"
APP_MODE       = "biometano"

if APP_MODE != "biometano":
    raise RuntimeError(
        f"Mode '{APP_MODE}' non supportato. L'app supporta solo biometano "
        "DM 2022 (RED III). Vedi tag 'pre-cleanup-legacy-modes' per la "
        "versione multi-mode storica."
    )

with st.sidebar:
    # ============================================================
    # 📋 Normative applicate
    # ============================================================
    with st.expander(
        "📋 " + _t("Normative applicate"),
        expanded=False,
    ):
        _norm_local = _load_normativa_local()
        if "_error" in _norm_local:
            st.error(f"❌ {_norm_local['_error']}")
        else:
            st.caption(
                f"**Versione registry: {_norm_local.get('version', '?')}**  ·  "
                f"Ultima revisione: {_norm_local.get('last_review', 'n/d')}  ·  "
                f"Reviewer: {_norm_local.get('reviewer', 'n/d')}"
            )

            # Lista compatta delle norme applicate
            _norme = _norm_local.get("norme", [])
            st.markdown(f"**🟢 {len(_norme)} norme cablate nel codice:**")
            for n in _norme:
                _badge = "✅" if n.get("applicato_in_app") else "⚪"
                st.markdown(
                    f"<div style='font-size:0.78rem; padding:3px 0; "
                    f"border-bottom:1px solid {BORDER};'>"
                    f"{_badge} <b>{n.get('titolo', 'n/d')}</b><br/>"
                    f"<span style='color:{TEXT_MUTED}; font-size:0.72rem;'>"
                    f"📍 {n.get('ambito', '')} · "
                    f"rev {n.get('ultima_revisione', 'n/d')}"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )
            st.caption(
                "ℹ️ Software fornito **«così com'è»**. Le norme cablate "
                "rispecchiano il rilascio corrente. "
                "L'utente verifica autonomamente la coerenza con la "
                "normativa vigente prima di usare i risultati per "
                "certificazioni o adempimenti."
            )
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)


# Stringhe mode-specific (tagline/pill/badge/label) per header, sidebar, export.
# App mono-mode (DM 15/09/2022, RED III): mantengo il dict _MODE per i lettori
# esistenti (_MODE["tagline"], _MODE["badge"], ecc.) senza ulteriori refactor.
_MODE: dict = {
    "tagline":   "DM 15/9/2022 · pianificazione mensile e ottimizzazione GHG per biometano: tariffa diretta €/MWh, saving RED III/D.Lgs. 5/2026 per uso finale.",
    "pill_main": "BIOMETANO · DM 15/9/2022",
    "pill_norm": "RED III · D.LGS 5/2026",
    "badge":     "Biometano · DM 2022",
    "label":     "Biometano DM 2022",
}

IS_DARK = st.session_state.methaniq_theme == "dark"

# ============================================================
# Metan.iQ Design System v3 — "Google Material 3 / Material You"
# ============================================================
# Brand tokens condivisi (Web + PDF + i18n) importati da core/design_tokens.py
from core.design_tokens import (
    AMBER       as ACCENT,    # alias semantico Material 3
    AMBER_DARK  as AMBER_DK,
    EMERALD     as SUCCESS,
)

PRIMARY     = "#15242E"  # Editorial NAVY (ink primario)
SECONDARY   = "#1F343F"  # NAVY 2 (navy soft)
TERTIARY    = "#3C6A52"  # FOREST (verde istituzionale)

# Accento editoriale: ottone (brass). Override dell'import AMBER del design
# system, mantenendo i nomi token cosi' i call-site a valle non cambiano.
ACCENT      = "#9A7B3C"   # BRASS
AMBER       = ACCENT      # alias legacy -> brass
NAVY        = PRIMARY
NAVY_2      = SECONDARY
BRAND       = TERTIARY
BRAND_2     = TERTIARY

if IS_DARK:
    # Editorial DARK — carta scura calda, inchiostro avorio, ottone caldo.
    BG_APP        = "#15140F"   # PAPER dark
    BG_SURFACE    = "#1E1C16"   # SURFACE dark
    BG_SURFACE_2  = "#26241C"   # PAPER 2 dark
    TEXT_PRIMARY  = "#E8E3D5"   # INK dark
    TEXT_SECOND   = "#C9C3B2"   # INK 2 dark
    TEXT_MUTED    = "#A49D8C"   # MUTED dark
    BORDER        = "#33302A"   # LINE dark
    BORDER_HOVER  = "#C9A968"   # BRASS 2 dark
    INPUT_BG      = "#1E1C16"
    SIDEBAR_BG    = "#15140F"
    HEADING_COLOR = "#E8E3D5"
    CODE_BG       = "#26241C"
    CODE_COLOR    = "#C9A968"
    SHADOW_CARD   = "none"
    SHADOW_HOVER  = "none"
    CREDIT_BG     = "#1E1C16"
    SECTION_PILL_BG = "rgba(201, 169, 104, 0.16)"
    SECTION_PILL_COLOR = "#E8E3D5"
    ACCENT        = "#C9A968"   # brass piu' chiaro su fondo scuro
    AMBER         = ACCENT
    HERO_BG       = "#15242E"
    HERO_TEXT     = "#FFFFFF"
    HERO_TAGLINE  = "#F7F4EC"
    HERO_EYEBROW  = "#FFFFFF"
    HERO_DOT      = "#F2C76B"
else:
    # Editorial LIGHT — carta avorio, inchiostro caldo, ottone.
    BG_APP        = "#F7F4EC"   # PAPER
    BG_SURFACE    = "#FFFFFF"   # SURFACE
    BG_SURFACE_2  = "#FBF9F3"   # PAPER 2
    TEXT_PRIMARY  = "#1C1B16"   # INK
    TEXT_SECOND   = "#3A382F"   # INK 2
    TEXT_MUTED    = "#726C5E"   # MUTED
    BORDER        = "#E4DDCD"   # LINE
    BORDER_HOVER  = "#9A7B3C"   # BRASS
    INPUT_BG      = "#FFFFFF"
    SIDEBAR_BG    = "#FBF9F3"
    HEADING_COLOR = "#1C1B16"
    CODE_BG       = "#EEE9DC"   # LINE SOFT
    CODE_COLOR    = "#9A7B3C"
    SHADOW_CARD   = "none"
    SHADOW_HOVER  = "none"
    CREDIT_BG     = "#FFFFFF"
    SECTION_PILL_BG = "#EFE7D4"   # BRASS SOFT
    SECTION_PILL_COLOR = "#15242E"
    HERO_BG       = "#102A36"
    HERO_TEXT     = "#FFFFFF"
    HERO_TAGLINE  = "#FFFFFF"
    HERO_EYEBROW  = "#FFFFFF"
    HERO_DOT      = "#F2C76B"

st.markdown(
    f"""
    <style>
    /* Editorial type system: Spectral (serif display), Outfit (UI/sans),
       IBM Plex Mono (numeri tabellari). */
    @import url('https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    /* Material Symbols: necessario altrimenti i glifi appaiono come testo
       'keyboard_arrow_right', 'keyboard_double_arrow_left' (a11y issue). */
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=block');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=block');

    /* ---------- Editorial Global Reset ---------- */
    html, body, .stApp, .stMarkdown, .stText,
    .stButton button, .stSelectbox label, .stNumberInput label,
    .stSlider label, .stCheckbox label, .stRadio label,
    .stExpander, .stDataFrame, .stTabs, .stAlert,
    p {{
        font-family: 'Outfit', 'Inter', -apple-system, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }}
    /* Titoli e display: serif editoriale Spectral. */
    h1, h2, h3, h4 {{
        font-family: 'Spectral', Georgia, 'Times New Roman', serif !important;
        letter-spacing: -0.01em;
        -webkit-font-smoothing: antialiased;
    }}
    h5, h6 {{
        font-family: 'Outfit', sans-serif !important;
    }}
    /* Numeri tabellari (metriche, tabelle, codice) in mono. */
    [data-testid="stMetricValue"], code, pre,
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        font-feature-settings: "tnum" 1;
    }}

    .stApp {{ background-color: {BG_APP}; color: {TEXT_PRIMARY}; }}

    /* ---------- Editorial Buttons (squadrati, hairline, niente ombre) ---------- */
    .stButton button {{
        border-radius: 6px !important;
        padding: 9px 22px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
        transition: all 0.18s ease !important;
        border: 1px solid {BORDER} !important;
        background-color: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
        box-shadow: none !important;
    }}
    .stButton button:hover {{
        background-color: {BG_SURFACE_2} !important;
        border-color: {ACCENT} !important;
        box-shadow: none !important;
        transform: none;
    }}
    .stButton button[kind="primary"] {{
        background-color: {PRIMARY} !important;
        color: #F7F4EC !important;
        border: 1px solid {PRIMARY} !important;
    }}
    .stButton button[kind="primary"]:hover {{
        background-color: {SECONDARY} !important;
        border-color: {ACCENT} !important;
    }}

    /* ---------- Editorial Inputs ---------- */
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
        border-radius: 8px !important;
        background-color: {BG_SURFACE} !important;
        border: 1px solid {BORDER} !important;
        color: {TEXT_PRIMARY} !important;
        box-shadow: none !important;
    }}
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="input"] > div:focus-within {{
        border-color: {ACCENT} !important;
    }}

    /* ---------- Cards & Expanders (hairline, niente ombre) ---------- */
    div[data-testid="stExpander"] {{
        background-color: {BG_SURFACE} !important;
        border-radius: 10px !important;
        border: 1px solid {BORDER} !important;
        box-shadow: none !important;
        margin-bottom: 1.1rem !important;
        padding: 4px !important;
    }}
    div[data-testid="stExpander"] > div:first-child {{
        border: none !important;
        background: transparent !important;
    }}
    
    /* ---------- Sidebar Modernization ---------- */
    section[data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG} !important;
        border-right: 1px solid {BORDER} !important;
    }}
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] small,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: {TEXT_SECOND} !important;
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] strong,
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] div[data-testid="stExpander"] summary * {{
        color: {TEXT_PRIMARY} !important;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        color: {TEXT_PRIMARY} !important;
        background-color: {BG_SURFACE} !important;
        border-color: {BORDER} !important;
    }}
    section[data-testid="stSidebar"] .stButton button[kind="primary"] {{
        color: #FFFFFF !important;
        background-color: {PRIMARY} !important;
        border-color: {PRIMARY} !important;
    }}
    
    [data-testid="stSidebarNav"] li div[aria-selected="true"] {{
        background-color: {SECTION_PILL_BG} !important;
        border-radius: 24px !important;
        margin: 4px 8px !important;
    }}

    /* ---------- Sidebar toggle (chevron) — forza visibilita' ----------
       Streamlit moderno rende il toggle come GLIFO font Material Symbols
       (span[data-testid="stIconMaterial"]), non SVG. Una regola globale
       a valle rende quello span trasparente se il font non carica -> la
       freccia "spariva". Forziamo qui un pill ottone con glifo scuro
       SEMPRE visibile (span + svg), piu' un fallback testuale a chevron. */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stExpandSidebarButton"],
    button[kind="header"][aria-label*="sidebar" i],
    button[kind="headerNoPadding"][aria-label*="sidebar" i],
    button[aria-label*="sidebar" i],
    button[aria-label*="navigation" i] {{
        background-color: {ACCENT} !important;
        color: #15242E !important;
        border: 1px solid #7A6230 !important;
        border-radius: 6px !important;
        opacity: 1 !important;
        visibility: visible !important;
        z-index: 1000 !important;
        box-shadow: none !important;
    }}
    /* Glifo interno (span Material) + eventuale SVG: colore scuro forte,
       NON trasparente, dimensione garantita (annulla il reset a font-size:0). */
    [data-testid="stSidebarCollapseButton"] span[data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapsedControl"] span[data-testid="stIconMaterial"],
    [data-testid="collapsedControl"] span[data-testid="stIconMaterial"],
    button[aria-label*="sidebar" i] span[data-testid="stIconMaterial"],
    button[aria-label*="navigation" i] span[data-testid="stIconMaterial"] {{
        color: #15242E !important;
        fill: #15242E !important;
        opacity: 1 !important;
        font-size: 1.35rem !important;
        line-height: 1 !important;
        visibility: visible !important;
    }}
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg,
    button[aria-label*="sidebar" i] svg,
    button[aria-label*="navigation" i] svg {{
        fill: #15242E !important;
        color: #15242E !important;
        stroke: #15242E !important;
        opacity: 1 !important;
        width: 1.25rem !important;
        height: 1.25rem !important;
    }}
    [data-testid="stSidebarCollapseButton"]:hover,
    [data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="collapsedControl"]:hover,
    button[aria-label*="sidebar" i]:hover {{
        background-color: #B59450 !important;
        border-color: #9A7B3C !important;
    }}

    /* Hiding utility language buttons */
    div[data-testid="stColumn"] button[id*="it-hidden"], 
    div[data-testid="stColumn"] button[id*="uk-hidden"] {{
        display: none !important;
    }}
    /* Target via specific labels if IDs aren't enough */
    button:has(div:contains("it-hidden")), 
    button:has(div:contains("uk-hidden")) {{
        display: none !important;
    }}
    /* Keep Streamlit Material icon glyphs as icons instead of readable fallback text. */
    span[data-testid="stIconMaterial"],
    .material-icons,
    .material-symbols-rounded,
    .material-symbols-outlined {{
        font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 1.15rem !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        direction: ltr !important;
        -webkit-font-feature-settings: "liga" !important;
        -webkit-font-smoothing: antialiased !important;
        font-feature-settings: "liga" !important;
    }}

    /* ---------- Hero Header (Editorial / Institutional) ---------- */
    .methaniq-header {{
        background: {HERO_BG};
        padding: 48px 52px;
        border-radius: 12px;
        color: {HERO_TEXT};
        margin-bottom: 30px;
        position: relative;
        overflow: hidden;
        box-shadow: none;
        border: 1px solid rgba(154, 123, 60, 0.30);
        border-top: 4px solid {ACCENT};
    }}
    .methaniq-header::after {{
        content: "";
        position: absolute;
        top: 0; bottom: 0; right: 0;
        width: 1px;
        background: rgba(154,123,60,0.18);
        pointer-events: none;
        z-index: 0;
    }}
    .methaniq-header > * {{ position: relative; z-index: 1; }}
    .methaniq-header .eyebrow {{
        font-family: 'Outfit', sans-serif;
        color: {HERO_EYEBROW} !important;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 3px;
        text-transform: uppercase;
        display: block;
        margin-bottom: 14px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.35);
    }}
    .methaniq-header h1 {{
        font-family: 'Spectral', Georgia, serif !important;
        color: {HERO_TEXT} !important;
        font-size: 3.4rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        margin: 0 !important;
        line-height: 1.05 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.38);
    }}
    .methaniq-header .tagline {{
        color: {HERO_TAGLINE} !important;
        font-size: 1.18rem;
        margin-top: 16px;
        max-width: 720px;
        font-weight: 400;
        line-height: 1.55;
        text-shadow: 0 1px 2px rgba(0,0,0,0.35);
    }}
    .methaniq-header .pills {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 28px;
    }}
    .methaniq-header .pill {{
        background: rgba(247, 244, 236, 0.06);
        padding: 7px 16px;
        border-radius: 6px;
        font-family: 'Outfit', sans-serif;
        font-size: 0.78rem;
        font-weight: 500;
        letter-spacing: 0.02em;
        border: 1px solid rgba(247, 244, 236, 0.14);
        color: #E4DDCD !important;
    }}
    .methaniq-header .pill.accent {{
        background: rgba(154, 123, 60, 0.18);
        border-color: rgba(181, 148, 80, 0.45);
        color: #EFE7D4 !important;
    }}
    
    /* ---------- Tabs (Editorial underline, niente pill) ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px !important;
        background-color: transparent !important;
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        border-bottom: 1px solid {BORDER} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 0 !important;
        padding: 9px 18px !important;
        background-color: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.18s ease !important;
        color: {TEXT_MUTED} !important;
        font-weight: 500 !important;
        min-width: max-content !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: {TEXT_PRIMARY} !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: transparent !important;
        color: {TEXT_PRIMARY} !important;
        border-bottom: 2px solid {ACCENT} !important;
        font-weight: 600 !important;
    }}

    /* ---------- DataFrames & Tables ---------- */
    [data-testid="stDataFrame"] {{
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid {BORDER} !important;
    }}

    /* ---------- Metrics ---------- */
    [data-testid="stMetric"] {{
        background-color: {BG_SURFACE} !important;
        padding: 18px 20px !important;
        border-radius: 8px !important;
        border: 1px solid {BORDER} !important;
        box-shadow: none !important;
    }}

    /* ---------- Credit Box ---------- */
    .methaniq-credit {{
        background: {BG_SURFACE};
        border-radius: 8px;
        border: 1px solid {BORDER};
        border-left: 3px solid {ACCENT};
        padding: 20px 24px;
        margin: 28px 0;
        box-shadow: none;
        font-size: 0.92rem;
        color: {TEXT_SECOND};
    }}
    @media (max-width: 760px) {{
        .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}
        .methaniq-header {{
            padding: 30px 22px;
            border-radius: 24px;
            margin-bottom: 24px;
        }}
        .methaniq-header h1 {{
            font-size: 2.4rem !important;
        }}
        .methaniq-header .tagline {{
            font-size: 1rem;
            line-height: 1.55;
        }}
        .methaniq-header .pill {{
            font-size: 0.72rem;
            padding: 7px 12px;
        }}
        .methaniq-credit {{
            padding: 18px;
            border-radius: 18px;
        }}
        [data-testid="stDataFrame"] {{
            overflow-x: auto !important;
        }}
    }}
    </style>
    <div class="methaniq-header">
        <span class="eyebrow">// Decision Intelligence Platform</span>
        <h1>Metan<span style="color:""" + HERO_DOT + """; font-weight:700;">.</span>iQ</h1>
        <div class="tagline">""" + _t(_MODE["tagline"]) + """</div>
        <div class="pills">
            <span class="pill accent">""" + _MODE["pill_main"] + """</span>
            <span class="pill">""" + _MODE["pill_norm"] + """</span>
            <span class="pill">GSE LG 2024</span>
            <span class="pill">UNI-TS 11567:2024</span>
            <span class="pill">JEC WTT v5</span>
            <span class="pill">LP OPTIMIZER</span>
        </div>
    </div>
    <div class="methaniq-credit">
        """ + _t("Ideato e sviluppato da") + """ <b>Carlo Sicurini</b> &nbsp;·&nbsp; © 2026 &nbsp;·&nbsp;
        """ + _t("Pianificazione mensile e ottimizzazione GHG per impianti di biometano da digestione anaerobica con immissione in rete (DM 2022 / RED III).") + """
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# DESIGN POLISH v4 — micro-animazioni, KPI cards, hover, tab pills attivi
# Iniettato come blocco additivo dopo il theme principale per restyling subtile
# senza riscrivere il design system esistente (Material 3 Outfit).
# =============================================================================
st.markdown(
    f"""
    <style>
    /* --- Animazioni globali --- */
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(12px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes pulseDot {{
        0%, 100% {{ box-shadow: 0 0 0 0 rgba(154,123,60,0.6); }}
        50%      {{ box-shadow: 0 0 0 7px rgba(154,123,60,0); }}
    }}
    @keyframes shimmer {{
        0% {{ background-position: -200% center; }}
        100% {{ background-position: 200% center; }}
    }}

    /* --- Hero header: solo entrance animation, NO text gradient
       (rompeva leggibilità del logo in tema light) --- */
    .methaniq-header {{
        animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        position: relative;
    }}
    .methaniq-header::before {{
        content: "● LIVE";
        position: absolute;
        top: 18px; right: 22px;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: #B59450;
        background: rgba(181,148,80,0.12);
        border: 1px solid rgba(181,148,80,0.40);
        padding: 4px 10px;
        border-radius: 999px;
        animation: pulseDot 2s infinite;
        z-index: 2;
    }}

    /* --- Tab principali: indicator gradient sotto il tab attivo
       (solo overlay decorativo, NIENTE override colori testo) --- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        transition: all 0.2s ease !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background: transparent !important;
    }}
    /* Underline editoriale gia' gestito dal blocco principale (border-bottom
       brass su [aria-selected]); qui nessun overlay decorativo per non
       sovrapporre due indicatori. */

    /* --- st.metric: solo border + hover sottile (NIENTE override colori) --- */
    div[data-testid="stMetric"] {{
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 16px 18px;
        transition: border-color 0.2s ease;
        animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: none;
        border-color: {ACCENT};
        box-shadow: none;
    }}
    /* Niente ellipsis '...' sui valori (unita' lunghe come "kWh/Sm³"
       venivano troncate in colonne strette). Permette wrap del valore
       su 2 righe se serve. */
    div[data-testid="stMetricValue"] {{
        font-family: 'Spectral', Georgia, serif !important;
        font-weight: 600 !important;
        font-variant-numeric: tabular-nums;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        word-break: keep-all;
        line-height: 1.15 !important;
        font-size: 1.7rem !important;
    }}
    div[data-testid="stMetricLabel"] {{
        white-space: normal !important;
        overflow: visible !important;
        line-height: 1.15 !important;
    }}

    /* --- Alert (info/warning/success/error): bordo accent left --- */
    div[data-testid="stAlert"] {{
        border-radius: 12px !important;
        border-left-width: 4px !important;
        animation: fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}

    /* --- Expander: smooth + hover --- */
    .streamlit-expanderHeader {{
        transition: all 0.2s ease;
        border-radius: 10px !important;
    }}
    .streamlit-expanderHeader:hover {{
        background: rgba(154,123,60,0.05) !important;
    }}

    /* --- Sidebar headings: NIENTE override colore (rompeva leggibilità in
       tema light/dark). Lasciato al theme di Streamlit. --- */

    /* --- DataFrame: rounded + shadow leggera --- */
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{
        border-radius: 8px;
        overflow: hidden;
        box-shadow: none;
    }}

    /* --- Download button: ottone pieno, squadrato, niente glow --- */
    div[data-testid="stDownloadButton"] button {{
        background: {ACCENT} !important;
        color: #1C1B16 !important;
        border: 1px solid {ACCENT} !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        box-shadow: none !important;
    }}
    div[data-testid="stDownloadButton"] button:hover {{
        transform: none;
        background: #B59450 !important;
        border-color: #B59450 !important;
        box-shadow: none !important;
    }}
    div[data-testid="stDownloadButton"] button:disabled {{
        background: {BG_SURFACE_2} !important;
        color: {TEXT_MUTED} !important;
        border-color: {BORDER} !important;
        box-shadow: none !important;
        cursor: not-allowed;
    }}

    /* --- A11Y: icone Material non renderizzate -> hidden via accessibility.
       Se il browser non riesce a caricare il font Material Symbols, il glifo
       cade in testo grezzo ("keyboard_arrow_right"). Lo nascondiamo da screen
       reader e visivamente, lasciando il bottone clickabile. --- */
    span[data-testid="stIconMaterial"] {{
        speak: none;
    }}
    /* Se font Material non disponibile (.notdef tofu), nascondi testo */
    @supports not (font-variation-settings: "liga") {{
        span[data-testid="stIconMaterial"]:not([data-loaded]) {{
            color: transparent !important;
            font-size: 0 !important;
        }}
    }}

    /* --- DARK MODE: contrast fix per HTML inline custom.
       I miei banner navy-on-navy (es. brand badge sidebar, banner mensile,
       riga TOTALE MESE) hanno colori hardcoded che in dark mode (sfondo già
       scuro) diventano illeggibili. Override forzato per dark theme. --- */
    [data-theme="dark"] .methaniq-credit,
    [data-theme="dark"] section[data-testid="stSidebar"] details summary,
    .stApp[data-theme="dark"] .methaniq-credit {{
        color: #E2E8F0 !important;
    }}
    [data-theme="dark"] section[data-testid="stSidebar"] [aria-expanded] {{
        color: #CBD5E1 !important;
    }}
    /* Disabled/collapsed states più visibili in dark */
    [data-theme="dark"] .stExpander[data-testid="stExpander"] details:not([open]) summary {{
        color: #94A3B8 !important;
        opacity: 0.95 !important;
    }}
    /* Button disabled in dark: più visibile (era quasi invisibile) */
    [data-theme="dark"] button:disabled,
    [data-theme="dark"] div[data-testid="stButton"] button:disabled {{
        color: #64748B !important;
        opacity: 0.7 !important;
        border-color: #475569 !important;
    }}

    /* --- RESPONSIVE: aggiustamenti per viewport stretti (mobile/tablet) --- */
    @media (max-width: 768px) {{
        .methaniq-header h1 {{
            font-size: 2.4rem !important;
        }}
        .methaniq-header .tagline {{
            font-size: 1rem !important;
        }}
        .methaniq-header::after {{
            width: 180px !important;
            height: 180px !important;
        }}
        .methaniq-header::before {{
            top: 10px !important;
            right: 12px !important;
            font-size: 0.55rem !important;
            padding: 3px 8px !important;
        }}
        .methaniq-header .pill {{
            font-size: 0.75rem !important;
            padding: 6px 14px !important;
        }}
        /* Stack i metric in colonne più strette */
        div[data-testid="stMetricValue"] {{
            font-size: 1.1rem !important;
        }}
        /* Tabella riga TOTALE MESE: scroll orizzontale invece di troncare */
        .stMarkdown table {{
            font-size: 0.65rem !important;
        }}
    }}
    @media (max-width: 480px) {{
        .methaniq-header h1 {{
            font-size: 2rem !important;
        }}
        .methaniq-header .pill {{
            font-size: 0.7rem !important;
            padding: 5px 12px !important;
        }}
    }}

    /* --- Footer fisso minimal --- */
    .methaniq-fixed-footer {{
        position: fixed;
        bottom: 8px; right: 14px;
        font-size: 0.65rem;
        opacity: 0.45;
        font-weight: 600;
        letter-spacing: 0.8px;
        color: #9A7B3C;
        background: rgba(0,0,0,0.04);
        padding: 4px 10px;
        border-radius: 999px;
        z-index: 100;
        pointer-events: none;
        font-family: 'Outfit', sans-serif;
    }}
    </style>
    <div class="methaniq-fixed-footer">METAN.iQ · v0.4.0</div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# DESIGN POLISH v5 — rifinitura editoriale "consulting report"
# Blocco additivo: tipografia editoriale, righelli ottone, didascalie maiuscole,
# intestazioni tabelle navy, scrollbar e divider raffinati. Solo estetica.
# =============================================================================
st.markdown(
    f"""
    <style>
    /* --- Impaginazione "documento": respiro e larghezza da report --- */
    .block-container {{
        max-width: 1180px !important;
        padding-top: 2.4rem !important;
        padding-bottom: 4rem !important;
    }}

    /* --- Gerarchia titoli editoriale + righello ottone sui h2 --- */
    .stApp h2 {{
        font-size: 1.55rem !important;
        font-weight: 600 !important;
        margin-top: 0.4rem !important;
        padding-bottom: 0.45rem !important;
        border-bottom: 1px solid {BORDER} !important;
        position: relative;
    }}
    .stApp h2::after {{
        content: "";
        position: absolute;
        left: 0; bottom: -1px;
        width: 46px; height: 2px;
        background: {ACCENT};
    }}
    .stApp h3 {{
        font-size: 1.22rem !important;
        font-weight: 600 !important;
        color: {TEXT_PRIMARY} !important;
    }}
    .stApp h4 {{
        font-size: 1.02rem !important;
        font-weight: 600 !important;
        color: {TEXT_SECOND} !important;
    }}

    /* --- Didascalia metrica: maiuscoletto spaziato (caption editoriale) --- */
    div[data-testid="stMetricLabel"] p,
    div[data-testid="stMetricLabel"] {{
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        color: {TEXT_MUTED} !important;
    }}
    div[data-testid="stMetricDelta"] {{
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.8rem !important;
    }}

    /* --- Divider / hr: filo sottile su carta --- */
    hr, .stApp hr {{
        border: none !important;
        border-top: 1px solid {BORDER} !important;
        margin: 1.6rem 0 !important;
    }}

    /* --- Intestazioni tabelle/dataframe: banda navy, testo avorio --- */
    [data-testid="stDataFrame"] [role="columnheader"],
    .stApp thead th {{
        background-color: {PRIMARY} !important;
        color: #F7F4EC !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        border-bottom: 2px solid {ACCENT} !important;
    }}
    /* Celle numeriche in mono per allineamento da tabella finanziaria */
    [data-testid="stDataFrame"] [role="gridcell"],
    .stApp tbody td {{
        font-family: 'IBM Plex Mono', monospace !important;
        font-variant-numeric: tabular-nums;
    }}

    /* --- Alert semantici con barra sinistra coerente alla palette --- */
    div[data-testid="stAlert"] {{
        background-color: {BG_SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-left: 3px solid {ACCENT} !important;
        border-radius: 8px !important;
    }}

    /* --- Caption Streamlit: corsivo serif discreto --- */
    div[data-testid="stCaptionContainer"], .stCaption {{
        font-family: 'Spectral', Georgia, serif !important;
        font-style: italic !important;
        color: {TEXT_MUTED} !important;
    }}

    /* --- Sidebar: intestazioni di sezione raffinate --- */
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 1.2rem !important;
    }}

    /* --- Code/tag inline: pillola carta con bordo --- */
    .stApp code {{
        background-color: {CODE_BG} !important;
        color: {CODE_COLOR} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 5px !important;
        padding: 1px 6px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.85em !important;
    }}

    /* --- Scrollbar discreta in tinta carta/ottone --- */
    ::-webkit-scrollbar {{ width: 11px; height: 11px; }}
    ::-webkit-scrollbar-track {{ background: {BG_APP}; }}
    ::-webkit-scrollbar-thumb {{
        background: {BORDER};
        border-radius: 6px;
        border: 2px solid {BG_APP};
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: {ACCENT}; }}

    /* --- Link in tinta ottone, sottolineatura discreta --- */
    .stApp a {{
        color: {ACCENT} !important;
        text-decoration-color: {BORDER} !important;
        text-underline-offset: 2px;
    }}
    .stApp a:hover {{ text-decoration-color: {ACCENT} !important; }}

    /* --- Expander summary: titolo serif --- */
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary span {{
        font-family: 'Spectral', Georgia, serif !important;
        font-weight: 600 !important;
        font-size: 1.02rem !important;
    }}

    /* --- Selezione testo in tinta ottone tenue --- */
    ::selection {{ background: rgba(154,123,60,0.22); }}

    /* =====================================================================
       FIX LEGGIBILITA' MENU A TENDINA (selectbox / multiselect / dropdown)
       BaseWeb monta il popover in un portal a livello <body>, fuori da
       .stApp: il tema scuro lasciava testo scuro su fondo scuro -> parole
       invisibili. Forziamo colori theme-aware su popover, listbox e opzioni.
       ===================================================================== */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    ul[role="listbox"],
    div[data-baseweb="popover"] ul {{
        background-color: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 8px !important;
    }}
    li[role="option"],
    ul[role="listbox"] li,
    div[data-baseweb="menu"] li,
    div[data-baseweb="popover"] li {{
        background-color: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
    }}
    /* Testo annidato dentro l'opzione (BaseWeb avvolge in <div>/<span>) */
    li[role="option"] *,
    ul[role="listbox"] li *,
    div[data-baseweb="menu"] li * {{
        color: {TEXT_PRIMARY} !important;
    }}
    /* Hover / opzione evidenziata */
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    ul[role="listbox"] li:hover {{
        background-color: {BG_SURFACE_2} !important;
        color: {TEXT_PRIMARY} !important;
    }}
    li[role="option"][aria-selected="true"] {{
        box-shadow: inset 3px 0 0 {ACCENT} !important;
    }}
    /* Valore selezionato mostrato nel box select (single + multi) */
    div[data-baseweb="select"] div[data-baseweb="select"],
    div[data-baseweb="select"] [class*="ValueContainer"],
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {{
        color: {TEXT_PRIMARY} !important;
        -webkit-text-fill-color: {TEXT_PRIMARY} !important;
    }}
    /* Tag del multiselect: pillola carta leggibile */
    div[data-baseweb="select"] span[data-baseweb="tag"],
    span[data-baseweb="tag"] {{
        background-color: {SECTION_PILL_BG} !important;
        color: {SECTION_PILL_COLOR} !important;
        border-radius: 6px !important;
    }}
    span[data-baseweb="tag"] span, span[data-baseweb="tag"] svg {{
        color: {SECTION_PILL_COLOR} !important;
        fill: {SECTION_PILL_COLOR} !important;
    }}
    /* Placeholder e testo di input dei widget (dark: spesso troppo scuro) */
    div[data-baseweb="input"] input,
    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="select"] input::placeholder {{
        color: {TEXT_PRIMARY} !important;
        -webkit-text-fill-color: {TEXT_PRIMARY} !important;
        opacity: 0.9;
    }}
    div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="select"] input::placeholder {{
        color: {TEXT_MUTED} !important;
        -webkit-text-fill-color: {TEXT_MUTED} !important;
        opacity: 1;
    }}

    /* =====================================================================
       FIX CONTRASTO GLOBALE TEMA SCURO
       Quando l'utente passa a "Dark" cambiano solo le NOSTRE variabili CSS,
       ma il tema NATIVO di Streamlit resta chiaro: molti widget mantengono
       testo scuro -> invisibile sul nostro fondo scuro. Forziamo i colori
       testo theme-aware su TUTTI i widget dell'area principale. Token gia'
       theme-aware -> sicuro anche in light.
       ===================================================================== */
    /* NB: scoped a markdown/testo dei widget — NON un generico `.stApp span`
       (romperebbe i colori inline di hero/pill/banner). */
    .stApp,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span:not([style*="color"]),
    [data-testid="stText"] {{
        color: {TEXT_PRIMARY};
    }}
    /* LAST-WORD FIX: la hero e' HTML dentro stMarkdownContainer; alcuni
       override globali Streamlit/Markdown arrivano dopo il primo render e
       possono far diventare scuri eyebrow, titolo e tagline in Light mode. */
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header,
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header .eyebrow,
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header h1,
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header .tagline,
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header .tagline * {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
        visibility: visible !important;
    }}
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header {{
        background: {HERO_BG} !important;
    }}
    .stApp [data-testid="stMarkdownContainer"] .methaniq-header h1 span {{
        color: {HERO_DOT} !important;
        -webkit-text-fill-color: {HERO_DOT} !important;
    }}
    /* Etichette widget (label sopra input/select/slider/radio/checkbox...) */
    .stApp label,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    .stApp .stRadio label, .stApp .stCheckbox label,
    .stApp .stSelectbox label, .stApp .stMultiSelect label,
    .stApp .stNumberInput label, .stApp .stTextInput label,
    .stApp .stTextArea label, .stApp .stSlider label,
    .stApp .stDateInput label, .stApp .stTimeInput label {{
        color: {TEXT_SECOND} !important;
    }}
    /* Testo digitato negli input numerici/testo/area + date/time */
    .stApp .stNumberInput input, .stApp .stTextInput input,
    .stApp .stTextArea textarea, .stApp .stDateInput input,
    .stApp .stTimeInput input {{
        color: {TEXT_PRIMARY} !important;
        -webkit-text-fill-color: {TEXT_PRIMARY} !important;
    }}
    /* Opzioni radio/checkbox: testo accanto al pallino/quadratino */
    .stApp .stRadio div[role="radiogroup"] label p,
    .stApp .stCheckbox label p,
    .stApp .stRadio label span, .stApp .stCheckbox label span {{
        color: {TEXT_PRIMARY} !important;
    }}
    /* Slider: valore sopra il thumb + estremi della barra */
    [data-testid="stThumbValue"],
    [data-testid="stTickBarMin"], [data-testid="stTickBarMax"],
    .stApp .stSlider [data-baseweb] div {{
        color: {TEXT_PRIMARY} !important;
    }}
    /* Radio/checkbox/expander: testo help e contenuto */
    div[data-testid="stExpander"] [data-testid="stMarkdownContainer"],
    div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] * {{
        color: {TEXT_PRIMARY};
    }}
    /* st.dataframe / st.table corpo: testo theme-aware (header resta navy) */
    [data-testid="stTable"] tbody td,
    [data-testid="stDataFrame"] [role="gridcell"] {{
        color: {TEXT_PRIMARY} !important;
    }}
    /* st.code / blocchi pre in area principale */
    .stApp pre, .stApp pre code {{
        color: {TEXT_PRIMARY} !important;
        background-color: {CODE_BG} !important;
    }}
    /* Toggle (st.toggle) e relative etichette */
    .stApp [data-testid="stWidgetLabel"] p {{ color: {TEXT_SECOND} !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# === Override estetico editoriale — iniettato DOPO il design system ===
# Vince per ordine di iniezione + !important. Solo aspetto, nessuna logica.
from theme_editorial import inject_editorial_theme
inject_editorial_theme(is_dark=IS_DARK)

# Solver description banner
st.markdown(
    f"<div style='background:{BG_SURFACE}; padding:14px 18px; border-radius:16px; "
    f"border:1px solid {BORDER}; margin-bottom:18px; "
    f"box-shadow: {SHADOW_CARD};'>"
    f"<span style='font-size:0.72rem; font-weight:700; letter-spacing:1px; "
    f"text-transform:uppercase; color:{SECTION_PILL_COLOR}; background:{SECTION_PILL_BG}; "
    f"padding:3px 10px; border-radius:6px; margin-right:10px;'>SOLVER</span>"
    f"<span style='color:{TEXT_SECOND}; font-size:0.95rem;'>"
    f"{_t('Pianificazione mensile biomasse — solver <b>dual-constraint</b> ')}"
    f"{_t('(saving GHG + produzione target) con configurazione impianto')} <code style='background:{CODE_BG}; "
    f"padding:2px 6px; border-radius:4px; font-size:0.85em; color:{CODE_COLOR};'>ep</code> {_t('ex RED III.')}"
    f"</span></div>",
    unsafe_allow_html=True,
)

# Brand badge + lang selector ora sono in cima alla sidebar (vedi spostamento
# subito prima del blocco 'Settings / Opzioni' a riga ~1372). Qui resta solo
# la sezione successiva ('Taglia Impianto').
_mode_label = _MODE["badge"]

with st.sidebar:
    st.markdown("---")
    st.markdown("### " + _t("🎯 Taglia Impianto"))

    # ── Modalità unità di misura: Netti o Lordi ──────────────────────────
    _unit_key = "plant_input_unit"
    if _unit_key not in st.session_state:
        st.session_state[_unit_key] = "netti"

    _unit_opts = [_t("Sm³/h NETTI"), _t("Sm³/h LORDI")]
    _unit_idx  = 0 if st.session_state[_unit_key] == "netti" else 1
    _unit_sel  = st.radio(
        _t("📐 Inserisci taglia come"),
        options=_unit_opts,
        index=_unit_idx,
        horizontal=True,
        help=_t(
            "• **Netti**: Sm³/h di biometano a valle dell'upgrading, pronti per l'iniezione o l'utilizzo (valore del Decreto e del contatore di rete).\n"
            "• **Lordi**: Sm³/h di biogas grezzo in ingresso all'upgrading, prima della rimozione di CO₂ e delle perdite di processo."
        ),
        key="plant_unit_radio",
    )
    st.session_state[_unit_key] = "netti" if _unit_sel == _unit_opts[0] else "lordi"

    # Fattore globale lordi->netti: legge aux_factor da Config. Tecnica
    # (include upgrading slip + caldaia + margini)
    # Default = DEFAULT_AUX_FACTOR = 1.29 (calcolato JRC-CONCAWE)
    _aux_base = st.session_state.get("aux_factor", DEFAULT_AUX_FACTOR)

    # Toggle per sincronizzazione automatica o override manuale del lordo
    if "override_gross_manual" not in st.session_state:
        st.session_state.override_gross_manual = False

    _sync = st.toggle(
        _t("Sincronizza Lordo con Config. Tecnica"),
        value=not st.session_state.override_gross_manual,
        help=_t("Se attivo, il Lordo è calcolato automaticamente come Netto × aux_factor (da Config. Tecnica). Se disattivato, puoi inserire il Lordo manualmente.")
    )
    st.session_state.override_gross_manual = not _sync

    if st.session_state[_unit_key] == "netti":
        _plant_input_net = st.number_input(
            "🎯 " + _t("Netto autorizzato [Sm³/h netti]"),
            min_value=10.0, max_value=2000.0,
            value=float(st.session_state.get("plant_net_smch_saved", DEFAULT_PLANT_NET_SMCH)),
            step=5.0,
            help=_t("Portata di biometano **netto** a valle upgrading. Valore contatore rete / decreto."),
            key="input_smch_netti",
        )
        plant_net_smch = _plant_input_net

        # Calcolo lordo base
        _gross_suggested = plant_net_smch * _aux_base

        if st.session_state.override_gross_manual:
            # Inserimento manuale del lordo
            plant_gross_smch = st.number_input(
                "📥 " + _t("Lordo manuale [Sm³/h lordi]"),
                min_value=plant_net_smch, max_value=10000.0,
                value=float(st.session_state.get("plant_gross_smch_saved", _gross_suggested)),
                step=5.0,
                help=_t("Inserisci manualmente la portata di biogas lordo. Questo sovrascrive il fattore aux calcolato."),
                key="input_smch_lordi_manual",
            )
            # Aggiorno aux_factor in session_state per coerenza globale
            if plant_net_smch > 0:
                st.session_state["aux_factor"] = plant_gross_smch / plant_net_smch
        else:
            plant_gross_smch = _gross_suggested
            st.caption(f"💡 {_t('Lordo calcolato')}: **{fmt_it(plant_gross_smch, 1)} Sm³/h** (aux {fmt_it(_aux_base, 3)})")
    else:
        # Modalità inserimento LORDI
        _plant_input_gross = st.number_input(
            "🎯 " + _t("Portata biogas grezzo [Sm³/h lordi]"),
            min_value=10.0, max_value=10000.0,
            value=float(st.session_state.get("plant_gross_smch_saved", DEFAULT_PLANT_NET_SMCH * _aux_base)),
            step=5.0,
            help=_t("Portata di biogas **lordo** in ingresso all'upgrading."),
            key="input_smch_lordi",
        )
        plant_gross_smch = _plant_input_gross

        if st.session_state.override_gross_manual:
            plant_net_smch = st.number_input(
                "📤 " + _t("Netto manuale [Sm³/h netti]"),
                min_value=10.0, max_value=plant_gross_smch,
                value=float(st.session_state.get("plant_net_smch_saved", plant_gross_smch / _aux_base)),
                step=5.0,
                key="input_smch_netti_manual",
            )
            if plant_net_smch > 0:
                st.session_state["aux_factor"] = plant_gross_smch / plant_net_smch
        else:
            plant_net_smch = plant_gross_smch / _aux_base
            st.caption(f"💡 {_t('Netto calcolato')}: **{fmt_it(plant_net_smch, 1)} Sm³/h** (aux {fmt_it(_aux_base, 3)})")

    # Salvo i valori in session_state per ricordarli al prossimo switch
    st.session_state["plant_net_smch_saved"]   = plant_net_smch
    st.session_state["plant_gross_smch_saved"] = plant_gross_smch

    # Riepilogo visivo lordi ↔ netti
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("📥 " + _t("Lordi"), fmt_it(plant_gross_smch, 0, " Sm³/h"))
    _c2.metric("📤 " + _t("Netti"), fmt_it(plant_net_smch, 0, " Sm³/h"))
    _c3.metric("⚙️ " + _t("aux"), fmt_it(st.session_state.get("aux_factor", _aux_base), 3))

    # Breakdown autoconsumi se disponibile (solo se non manuale o se vogliamo mostrare comunque i teorici)
    _detail = st.session_state.get("aux_factor_detail", {})
    if _detail and not st.session_state.override_gross_manual:
        _f_heat = _detail.get("f_heat", 0)
        _f_elec = _detail.get("f_elec", 0)
        _f_slip = _detail.get("f_slip", 0)
        _f_marg = _detail.get("f_margin", 0)
        st.caption(
            f"📊 **{_t('Breakdown autoconsumo')}** ({_t('% del lordo')}): "
            f"🔥 {_t('Caldaia')} {fmt_it(_f_heat*100, 1, '%')} · "
            f"⚡ {_t('Elettrico')} {fmt_it(_f_elec*100, 1, '%')} · "
            f"💨 Slip {fmt_it(_f_slip*100, 1, '%')} · "
            f"🔧 {_t('Margine')} {fmt_it(_f_marg*100, 1, '%')} "
            f"→ {_t('Totale')} {fmt_it((_f_heat+_f_elec+_f_slip+_f_marg)*100, 1, '%')} ≡ aux {fmt_it(_aux_base, 3)}"
        )
    else:
        _up_eff_base = 1.0 / _aux_base if _aux_base > 0 else 0.8
        st.caption(
            _t("ℹ️ Vai in **Config. Tecnica** per calcolare il fattore lordi/netti reale "
               "(include upgrading e caldaia). Ora uso default: "
               f"aux = {fmt_it(_aux_base, 3)} ({fmt_it((1-_up_eff_base)*100, 0, '%')} autoconsumo totale).")
        )

    st.markdown("---")
    with st.sidebar.expander("⚙️ " + _t("Config. Tecnica & GHG"), expanded=False):
        # Configuratore ep
        digestate_opt = st.selectbox(
            _t("Stoccaggio digestato"),
            list(EP_DIGESTATE.keys()), index=1,
            help=_t("RED III All.V Parte C: APERTO o CHIUSO con recupero gas."),
        )

        upgrading_opt = st.selectbox(
            _t("Tecnologia upgrading"),
            list(EP_UPGRADING.keys()), index=1,
            help=_t("Seleziona la tecnologia di upgrading (separazione CO2). Ognuna ha consumi e perdite (slip) differenti.")
        )
        offgas_opt = st.selectbox(
            _t("Combustione off-gas"),
            list(EP_OFFGAS.keys()), index=0,
            help=_t("Gestione delle emissioni fuggitive di metano nell'off-gas dell'upgrading. Un ossidatore termico (RTO) le azzera.")
        )
        ep_upgrading = EP_UPGRADING[upgrading_opt]
        ep_offgas = EP_OFFGAS[offgas_opt]
        injection_opt = st.selectbox(
            _t("Iniezione in rete"),
            list(INJECTION_PRESSURE.keys()), index=1,
            help=_t("Pressione della condotta per immissione in rete Snam/distributore. Incide sui consumi elettrici del booster.")
        )

        heat_opt = st.selectbox(
            _t("Fonte calore"),
            list(EP_HEAT.keys()), index=0,
            help=_t("Origine dell'energia termica per riscaldamento digestore. L'autoconsumo di biogas è neutrale ma consuma gas.")
        )
        elec_opt = st.selectbox(
            _t("Elettricità ausiliari"),
            list(EP_ELEC.keys()), index=1,
            help=_t("Origine dell'energia elettrica per ausiliari e agitatori. L'autoproduzione cogenerativa/FV riduce le emissioni rispetto alla rete.")
        )

        ep_digestate = EP_DIGESTATE[digestate_opt]
        ep_heat = EP_HEAT[heat_opt]
        ep_elec = EP_ELEC[elec_opt]
        _ep_raw = ep_digestate + ep_upgrading + ep_offgas + ep_heat + ep_elec
        # RED III All. V Parte C: ep = emissioni da LAVORAZIONE, sempre >= 0.
        # Le mitigazioni (es. RTO off-gas che riduce il metano slip) possono
        # AZZERARE il contributo ma NON renderlo un credito negativo: un ep<0
        # gonfierebbe il saving in modo non difendibile in audit OdC. Floor a 0.
        ep_total = max(0.0, _ep_raw)
        _ep_floored = _ep_raw < 0.0

        if _ep_floored:
            st.markdown(
                f"**ep totale: +0,0 gCO₂/MJ** "
                f"<span style='color:#9A7B3C;'>(grezzo {fmt_it(_ep_raw, 1, signed=True)} "
                f"→ vincolato a 0: RED III non ammette ep negativo)</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"**ep totale: {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ**")

        # aux_factor
        st.markdown("---")
        margin_pct = st.slider(_t("Margine/Downtime [%]"), 0.0, 10.0, 3.0, 0.5)

        cogen_frac = 0.6
        recover_chp_heat = True
        if elec_opt == ELEC_IS_INTERNAL:
            c1, c2 = st.columns(2)
            cogen_frac = c1.number_input("% Cogen", 0.0, 100.0, 60.0) / 100.0
            recover_chp_heat = c2.checkbox("Recupero Q", True)

        aux_auto_data = compute_aux_factor(
            upgrading_opt=upgrading_opt, heat_opt=heat_opt, elec_opt=elec_opt,
            injection_opt=injection_opt, margin=margin_pct/100.0,
            cogen_fraction=cogen_frac, recover_chp_heat=recover_chp_heat
        )
        aux_auto = aux_auto_data["aux_factor"]

        manual_aux_on = st.checkbox(_t("Override aux manuale"), False)
        if manual_aux_on:
            aux_factor = st.number_input("aux manuale", 1.0, 2.0, round(aux_auto, 3), 0.005)
        else:
            aux_factor = aux_auto

        st.session_state["aux_factor"] = aux_factor
        st.session_state["aux_factor_detail"] = aux_auto_data

    st.markdown("---")
    st.markdown("### " + _t("🌾 Biomasse attive"))

    # Origine del fattore emissivo eec (per tag inline ⓘ e cerchietto ?).
    def _eec_origin(_name):
        _src = (FEEDSTOCK_DB.get(_name, {}) or {}).get("src", "") or ""
        _s = _src.lower()
        if _src.startswith("UNI-TS"):
            return "UNI/TS A.5"
        if "manure credit red iii" in _s:
            return "RED III"
        if "jec" in _s or "ktbl" in _s:
            return "JEC/KTBL"
        if "gse" in _s:
            return "GSE"
        if "ipcc" in _s:
            return "IPCC"
        return _t("altro")

    def _fmt_feed(_x):
        _d = FEEDSTOCK_DB[_x]
        _adv = ('🌽 cap30%' if _d.get('annex_ix') is None
                else f"IX-{_d.get('annex_ix')} ✓avanzato")
        return (f"{_t(_x)} · eec={fmt_it(_d['eec'], 1, signed=True)} · "
                f"{_adv} · ⓘ {_eec_origin(_x)}")

    # 🔍 Lente di ricerca rapida (filtra i blocchi per nome IT/EN).
    _feed_query = st.text_input(
        "🔍 " + _t("Cerca biomassa"),
        value="",
        placeholder=_t("Digita per filtrare (mais, sorgo, pollina, sansa…)"),
        help=_t(
            "Filtra le biomasse per nome; lascia vuoto per vedere tutti i blocchi. "
            "Il tag ⓘ accanto a ogni voce indica l'origine del fattore emissivo eec: "
            "UNI/TS A.5 = valore tabellato nella norma · JEC/KTBL = banca dati LCA europea · "
            "RED III = credito effluenti (manure credit) · GSE/IPCC = altre fonti."
        ),
        key="feed_search_query",
    )
    _q = (_feed_query or "").strip().lower()

    # Blocchi per categoria, in ordine fisso (colture con mais/sorgo/erbaio in cima).
    _CAT_ORDER = [
        "Colture dedicate", "Effluenti zootecnici",
        "Sottoprodotti agroindustriali", "FORSU / Rifiuti",
    ]
    _ordered_cats = [c for c in _CAT_ORDER if c in FEEDSTOCK_CATEGORIES]
    _ordered_cats += [c for c in FEEDSTOCK_CATEGORIES if c not in _ordered_cats]

    _prev_sel = [f for f in st.session_state.get('active_feeds', DEFAULT_ACTIVE_FEEDS)
                 if f in FEED_NAMES]

    for _cat in _ordered_cats:
        _kb = f"feeds_block_{_cat}"
        if _kb not in st.session_state:
            st.session_state[_kb] = [n for n in FEEDSTOCK_CATEGORIES[_cat] if n in _prev_sel]
        _all_names = FEEDSTOCK_CATEGORIES[_cat]
        _cur = st.session_state.get(_kb, [])
        if _q:
            _visible = [n for n in _all_names if _q in n.lower() or _q in _t(n).lower()]
            # Mantieni le voci gia' selezionate tra le opzioni: evita crash di stato.
            _opts = [n for n in _all_names if n in _visible or n in _cur]
        else:
            _opts = _all_names
        if not _opts:
            continue
        st.multiselect(
            f"**{_t(_cat)}**",
            options=_opts,
            format_func=_fmt_feed,
            key=_kb,
            help=_t(
                "ⓘ origine eec: UNI/TS A.5 = valore di norma · JEC/KTBL = banca dati LCA · "
                "RED III = credito effluenti. '🌽 cap30%' = food/feed (single counting CIC); "
                "IX-A/IX-B = Annex IX avanzato (double counting CIC)."
            ),
        )

    # Ricompone active_feeds dai blocchi, preservando l'ordine del DB.
    active_feeds_sel = []
    for _cat in _ordered_cats:
        _sel_cat = st.session_state.get(f"feeds_block_{_cat}", [])
        active_feeds_sel += [n for n in FEEDSTOCK_CATEGORIES[_cat] if n in _sel_cat]

    st.session_state.active_feeds = active_feeds_sel
    active_feeds = st.session_state.active_feeds
    if not active_feeds:
        st.warning(_t("⚠️ Seleziona almeno 1 biomassa per procedere."))
        st.stop()

    # ── Trasparenza audit OdC: fonti normative dei valori eec mostrati ──
    with st.expander(_t("📚 Fonti normative biomasse attive (audit OdC)"), expanded=False):
        import pandas as _pd
        # Manure credit (eec<0 effluenti): ATTIVO di default (prassi GSE/RED III).
        st.checkbox(
            _t("Applica il manure credit agli effluenti zootecnici "
               "(RED III All. VI — attivo di default)"),
            value=True,
            key="manure_credit_declared",
            help=_t("ATTIVO (default): il credito da stoccaggio anaerobico evitato "
                    "(eec negativo) viene applicato ai reflui, come da prassi "
                    "GSE/RED III. Ricorda di conservare la dichiarazione baseline di "
                    "stoccaggio del fornitore per l'audit OdC. Disattivalo solo per "
                    "uno scenario ultra-conservativo (azzera il credito → saving più "
                    "basso)."),
        )

        def _eff_eec(_n):
            return _emission_factors_of(_n).get("eec", FEEDSTOCK_DB[_n]["eec"])

        def _eff_tier(_n):
            _m = dict(FEEDSTOCK_DB[_n])
            _m["eec"] = _eff_eec(_n)
            return eec_tier(_m)["code"]

        _rows_src = [
            {
                _t("Biomassa"): _t(_n),
                "eec [gCO₂eq/MJ]": fmt_it(_eff_eec(_n), 1, signed=True),
                "Tier": _eff_tier(_n),
                _t("Categoria"): FEEDSTOCK_DB[_n].get("cat", "—"),
                "Annex IX": FEEDSTOCK_DB[_n].get("annex_ix") or "—",
                _t("Fonte"): FEEDSTOCK_DB[_n].get("src", "—"),
            }
            for _n in active_feeds
        ]
        st.dataframe(_pd.DataFrame(_rows_src), use_container_width=True, hide_index=True)
        st.caption(_t(
            "Tier difendibilità eec: A = default normativo (UNI/TS A.5 / RED III) · "
            "B = zero da regola (residuo/rifiuto Annex IX) · C = stima conservativa "
            "(letteratura JEC/KTBL, a sfavore dell'operatore) · D = credito da "
            "dichiarazione fornitore (manure credit RED III All. VI). Solo il tier D "
            "richiede un documento esterno; A/B/C sono difendibili per costruzione."
        ))
        _n_tier_d = sum(1 for _n in active_feeds if _eff_tier(_n) == "D")
        _n_gated = sum(1 for _n in active_feeds
                       if _emission_factors_of(_n).get("manure_credit_gated"))
        if _n_gated:
            st.warning(_t(
                "⚠️ Manure credit DISATTIVATO: {n} crediti effluenti azzerati "
                "(scenario ultra-conservativo). Il saving risulta più basso del "
                "reale. Riattiva la spunta sopra per il calcolo standard GSE/RED III."
            ).format(n=_n_gated))
        if _n_tier_d:
            st.caption("ℹ️ " + _t(
                "Sono attive {n} biomasse con manure credit (tier D): per l'audit OdC "
                "conserva la dichiarazione baseline di stoccaggio del fornitore."
            ).format(n=_n_tier_d))
        st.caption(_t(
            "Annex IX = RED III Allegato IX: A (sottoprodotti/effluenti, avanzato) o "
            "B (oli/grassi, avanzato). '—' = food/feed crop (cap colture dedicate, "
            "no double counting CIC, no premio avanzato DM 15/9/2022)."
        ))
        # Dossier di conformità OdC (PDF) — catalogo completo eec/tier/fonti.
        try:
            from datetime import date as _date
            from dossier_conformita import build_conformity_dossier as _bcd
            _dossier_bytes = _bcd(
                FEEDSTOCK_DB, lang=_LANG,
                company=COMPANY_NAME, plant=PLANT_NAME, cui=PLANT_CUI,
                manure_credit_declared=bool(
                    st.session_state.get("manure_credit_declared", True)),
            )
            st.download_button(
                "📋 " + _t("Scarica dossier di conformità (OdC)"),
                data=_dossier_bytes,
                file_name=f"dossier_conformita_metaniq_{_date.today().isoformat()}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_dossier_conformita",
            )
            st.caption(_t(
                "Documento completo (33 biomasse) con eec, tier difendibilità, "
                "resa, Annex IX e fonte normativa per ogni voce: da consegnare "
                "all'Organismo di Certificazione."
            ))
        except Exception as _e_dossier:  # noqa: BLE001
            st.caption("⚠️ " + _t("Dossier non generabile") + f": {_e_dossier}")
# ============================================================
# DEFAULT GLOBALI per tab-globals (audit robustezza #1)
# ------------------------------------------------------------
# prima di definirle (es. pie chart con sum=0, audit #2), gli export
# crashano con NameError. Inizializzazione difensiva qui = zero crash.
# ============================================================
annex_mass_share         = 0.0
is_advanced              = False
cic_double               = False
cic_active               = False
pdf_revenue_rows         = []
tot_n_cic                = 0.0
tot_revenue              = 0.0
tot_revenue_base_mwh     = 0.0
tariffa_media_ponderata  = 0.0
tot_mwh                  = 0.0

# ============================================================
# AGGREGAZIONE DATI DAL DATABASE (Sostituisce il Solver)
# ------------------------------------------------------------
# Invece di usare il solver per stimare i mesi, leggiamo i dati
# REALI salvati nel database per l'anno corrente.
# ============================================================
try:
    from core.persistence import init_db as _init_db_main, load_month as _load_month_main
    from core.daily_model import compute_daily as _compute_daily_main
    from core.monthly_aggregate import aggregate_month as _aggregate_month_main
    
    _init_db_main()
    
    _current_year = int(st.session_state.get("do_year", 2024))
    _plant_id = st.session_state.get("do_plant", "default_plant")
    
    # Contesto per il calcolo (ricalcolo dinamico in base alla sidebar)
    _ctx = {
        "aux_factor": aux_factor,
        "ep": ep_total,
        "fossil_comparator": FOSSIL_COMPARATOR,
        "plant_net_smch": plant_net_smch,
    }

    _all_months_data = []
    for m_idx in range(1, 13):
        _month_entries = _load_month_main(_current_year, m_idx, plant_id=_plant_id)
        if _month_entries:
            # Calcola i dati giornalieri (DailyEntry -> DailyComputed)
            _computed_days = [_compute_daily_main(e, ctx=_ctx) for e in _month_entries]
            # Aggrega il mese (list[DailyComputed] -> MonthlyAggregate)
            _agg_obj = _aggregate_month_main(_computed_days, ctx=_ctx, year=_current_year, month=m_idx)
            # Converte in dict per il DataFrame (compatibile con df_res)
            _all_months_data.append(_agg_obj.to_dict())
        else:
            _all_months_data.append({
                "Mese": MONTHS[m_idx-1],
                "Ore": 0.0, "Sm³ lordi": 0.0, "Sm³ netti": 0.0, "MWh netti": 0.0,
                "e_w": 0.0, "Saving %": 0.0, "Validità": "❌ " + _t("Nessun dato"),
                "Totale biomasse (t)": 0.0,
                **{f: 0.0 for f in FEED_NAMES}
            })
    df_res = pd.DataFrame(_all_months_data)

    # --- KPI ANNUALI ---
    annual_t = {n: float(max(df_res[n].sum(), 0.0)) for n in active_feeds}
    annual_mwh = {n: float(max(df_res[n].sum(), 0.0)) * _yield_of(n) / aux_factor * NM3_TO_MWH for n in active_feeds}
    _tot_t = sum(annual_t.values())
    annex_mass_share = (sum(t for n, t in annual_t.items() if FEEDSTOCK_DB[n].get("annex_ix") in ("A", "B")) / _tot_t) if _tot_t > 0 else 0.0

    _tar_key = f"tariffs_eur_mwh_{APP_MODE}"
    _tar_default = 120.0  # €/MWh biometano rete (DM 15/9/2022, baseline editabile)
    if _tar_key not in st.session_state:
        st.session_state[_tar_key] = {n: _tar_default for n in active_feeds}
    for n in active_feeds:
        if n not in st.session_state[_tar_key]:
            st.session_state[_tar_key][n] = _tar_default

    pdf_revenue_rows = []
    tot_n_cic = 0.0
    for n in active_feeds:
        t, mwh_netti = annual_t[n], annual_mwh[n]
        mwh_rev = mwh_netti
        tariffa = st.session_state[_tar_key][n]
        ricavi = mwh_rev * tariffa
        n_cic = 0.0
        _tot_mwh_b = sum(annual_mwh.values())
        pdf_revenue_rows.append((n, {"t_anno": t, "yield": _yield_of(n), "mwh_netti": mwh_netti, "mwh_basis": mwh_rev, "tariffa": tariffa, "ricavi": ricavi, "quota": (mwh_netti / _tot_mwh_b * 100) if _tot_mwh_b > 0 else 0, "annex_ix": FEEDSTOCK_DB[n].get("annex_ix"), "n_cic": n_cic}))

    tot_mwh = sum(annual_mwh.values())
    tot_revenue_base_mwh = tot_mwh
    tot_revenue = sum(annual_mwh[n] * st.session_state[_tar_key][n] for n in active_feeds)
    tariffa_media_ponderata = (tot_revenue / tot_revenue_base_mwh) if tot_revenue_base_mwh > 0 else 0.0

except Exception as _agg_exc:
    st.error(f"Errore aggregazione DB: {_agg_exc}")
    df_res = pd.DataFrame()
    annual_t = {n: 0.0 for n in active_feeds}
    annual_mwh = {n: 0.0 for n in active_feeds}
    tot_mwh = 0.0
    tot_revenue = 0.0
    tot_revenue_base_mwh = 0.0
    tariffa_media_ponderata = 0.0
    pdf_revenue_rows = []
    tot_n_cic = 0.0

# GESTIONE GIORNALIERA + VERIFICA SOSTENIBILITA' MENSILE
# ------------------------------------------------------------
# Sezione operativa "giorno per giorno" con verifica di sostenibilita'
# applicata sull'AGGREGATO MENSILE (regola di compliance).
# Tutta la logica risiede nei moduli core/output/export — qui solo UI.
# ============================================================
try:
    import datetime as _dt
    import pandas as _pd_daily
    from core.calendar import generate_month_days as _gen_days, month_label as _mlabel
    from core.daily_model import DailyEntry as _DEntry, compute_daily as _compute_daily
    from core.monthly_aggregate import (
        aggregate_month as _agg_month,
        progressive_to_date as _prog_to_date,
    )
    from core.sustainability import (
        evaluate_monthly_sustainability as _eval_sust,
    )
    from core.persistence import (
        init_db as _init_db,
        save_month as _save_month,
        load_month as _load_month,
        list_saved_months as _list_months,
    )
    from core.validators import validate_daily_entry as _validate_daily
    from output.daily_table_view import (
        build_daily_dataframe as _build_daily_df,
        style_daily_dataframe as _style_daily_df,
    )
    # Import resiliente: append_monthly_total_row aggiunto in commit 7b00a71.
    # Se Streamlit Cloud sta servendo una versione cached di daily_table_view,
    # fallback a no-op così la UI non crasha (la riga TOTALE MESE non appare,
    # ma i KPI mensili sotto la tabella restano comunque visibili).
    try:
        from output.daily_table_view import append_monthly_total_row as _append_total_row
    except ImportError:
        def _append_total_row(df, feed_columns=None):  # type: ignore[no-redef]
            return df
    from output.monthly_kpis import build_monthly_kpis as _build_kpis
    from output.guidance import compute_end_of_month_guidance as _build_guidance
    from export.daily_csv import build_daily_csv as _build_daily_csv
    from export.daily_excel import build_daily_excel as _build_daily_xlsx
    from export.daily_pdf import build_daily_pdf as _build_daily_pdf
    _DAILY_OPS_AVAILABLE = True
except Exception as _daily_imp_exc:  # noqa: BLE001
    _DAILY_OPS_AVAILABLE = False
    _DAILY_IMP_ERR = str(_daily_imp_exc)

def _render_daily_ops_panel(_key_prefix: str = ""):
    """Render del pannello Operatività Giornaliera (selettore, tabella,
    KPI, banner, export). _key_prefix evita collisioni di widget keys
    quando il pannello è renderizzato in più tab."""
    _DOG_KEY = f"{_key_prefix}do_editor_gen"
    if _DAILY_OPS_AVAILABLE:


        # =================================================================
        # HEADER + selettore periodo
        # =================================================================
        # Badge anagrafica (solo se compilata). XSS hardening: ogni stringa
        # proveniente da input utente passa per html.escape() prima di entrare
        # in markdown con unsafe_allow_html=True.
        _anag_badge = ""
        if COMPANY_NAME or PLANT_NAME:
            _badge_parts = []
            if COMPANY_NAME:
                _badge_parts.append(f"🏢 <b>{_html.escape(str(COMPANY_NAME))}</b>")
            if PLANT_NAME:
                _badge_parts.append(f"🏭 {_html.escape(str(PLANT_NAME))}")
            _anag_badge = (
                f"<div style='display:inline-block;background:{AMBER}15;"
                f"color:{NAVY};padding:4px 10px;border-radius:6px;"
                f"font-size:0.78rem;margin-bottom:8px;border:1px solid {AMBER}30;'>"
                + " &nbsp;·&nbsp; ".join(_badge_parts)
                + "</div>"
            )

        st.markdown(
            f"<h2 style='margin-bottom:4px;color:{NAVY};'>📅 "
            f"{_t('Operatività Giornaliera')}</h2>"
            + _anag_badge
            + f"<div style='color:#64748B;font-size:0.85rem;margin-bottom:14px;'>"
            + _t("Sostenibilità calcolata su base mensile (mass balance RED III · "
                 "Regole Applicative GSE 2025). I valori giornalieri sono solo "
                 "monitoraggio: conta il totale a fine mese.")
            + "</div>",
            unsafe_allow_html=True,
        )

        _today = _dt.date.today()
        _csel1, _csel2, _csel3 = st.columns([1, 2, 2])
        with _csel1:
            _do_year = st.number_input(
                _t("Anno"), min_value=2020, max_value=2100,
                value=int(_today.year), step=1, key=f"{_key_prefix}do_year",
                help=_t("Seleziona l'anno solare per la rendicontazione giornaliera dei dati.")
            )
        with _csel2:
            _do_month = st.selectbox(
                _t("Periodo di rendicontazione"), list(range(1, 13)),
                index=_today.month - 1,
                format_func=lambda m: _mlabel(int(_do_year), int(m), _LANG),
                key=f"{_key_prefix}do_month",
                help=_t("Seleziona il mese di riferimento per registrare le letture giornaliere.")
            )
        with _csel3:
            # ID impianto: se l'utente ha compilato "Nome impianto" in sidebar
            # (Anagrafica simulazione) lo usiamo come default. Altrimenti "default".
            _plant_id_default = (
                PLANT_NAME.strip() if PLANT_NAME and PLANT_NAME.strip()
                else st.session_state.get("do_plant_id", "default")
            )
            _do_plant = st.text_input(
                _t("Impianto"),
                value=_plant_id_default,
                key=f"{_key_prefix}do_plant_id",
                help=_t("ID per separare i dati nel database. Auto-compilato "
                        "dal Nome impianto in Anagrafica simulazione (sidebar)."),
            )

        # =================================================================
        # CARICAMENTO STATO (DB → session_state)
        # ------------------------------------------------------------
        # Audit robustezza #7: separator "||" improbabile in plant_id reale
        # (al posto di "_") evita collisioni del tipo "Impianto_2024_01"
        # year=2024 month=1 vs "Impianto" year=2024 month=01.
        # Audit robustezza #8: sanitize plant_id (no vuoti, no whitespace).
        # =================================================================
        _do_plant_safe = (_do_plant or "").strip() or "default"
        # ISOLAMENTO MODALITA' (Standard vs Analisi): quando il pannello e' chiamato
        # con un _key_prefix (es. "tech_" dal tab Analisi), aggiungiamo un suffix
        # al plant_id effettivo cosi' che session_state e DB siano completamente
        # separati. L'utente compila la tabella Analisi solo quando ha i certificati
        # (BMT lab o EF su misura), senza interferire coi dati Standard.
        if _key_prefix:
            _do_plant_safe = f"{_do_plant_safe}__{_key_prefix.rstrip('_')}"
        _do_key = f"do_data||{_do_plant_safe}||{int(_do_year)}||{int(_do_month)}"
        _hours_key = _do_key + "::hours"
        if _do_key not in st.session_state:
            try:
                _init_db()
                _loaded = _load_month(int(_do_year), int(_do_month), plant_id=_do_plant_safe)
            except Exception as _load_exc:  # noqa: BLE001
                _LOG.exception("Daily DB load failed for %s/%s/%s",
                               _do_plant_safe, _do_year, _do_month)
                st.warning(_t("Impossibile caricare il mese salvato:") + f" {_load_exc}")
                _loaded = []
            _all_days = _gen_days(int(_do_year), int(_do_month))
            _data_map: dict = {d: {} for d in _all_days}
            # Default 0 ore: impianto spento finché non si carica biomassa.
            # Quando l'utente inserisce biomassa > 0 in un giorno, le ore
            # vengono auto-settate a 24 (default produzione continua, post-edit).
            _hours_init: dict = {d: 0.0 for d in _all_days}
            _remi_init: dict = {d: {"vb": 0.0, "e": 0.0, "qb_max": 0.0, "pci": 0.0, "rho": 0.0} for d in _all_days}
            for _e in _loaded:
                if _e.date in _data_map:
                    _data_map[_e.date] = dict(_e.feedstocks)
                    _hours_init[_e.date] = float(_e.hours_per_day)
                    _remi_init[_e.date] = {
                        "vb": float(_e.remi_vb),
                        "e": float(_e.remi_e),
                        "qb_max": float(_e.remi_qb_max),
                        "pci": float(_e.remi_pci),
                        "rho": float(_e.remi_rho),
                    }
            st.session_state[_do_key] = _data_map
            st.session_state[_hours_key] = _hours_init
            st.session_state[_do_key + "::remi"] = _remi_init

        # Audit robustezza #11: safety net "altri plant_id con dati salvati".
        # Quando l'utente rinomina l'impianto (es. "Cascina A" → "Cascina A srl")
        # i mesi salvati col vecchio nome diventano invisibili. Mostriamo qui
        # un caption con la lista degli altri plant_id per cui esistono dati,
        # così l'utente può rinominare di nuovo o copiare i dati.
        try:
            _all_saved = _list_months()
            _other_plants = sorted({
                m.get("plant_id", "") for m in _all_saved
                if m.get("plant_id") and m.get("plant_id") != _do_plant_safe
            })
            if _other_plants:
                st.caption(
                    "📂 " + _t("Mesi salvati anche con altri ID impianto:")
                    + " " + ", ".join(f"`{p}`" for p in _other_plants[:8])
                    + (f" (+{len(_other_plants)-8})" if len(_other_plants) > 8 else "")
                )
        except Exception:  # noqa: BLE001
            pass  # safety net non critica

        with st.expander("⚙️ " + _t("Operazioni mese"), expanded=False):
            _bcol1, _bcol2 = st.columns(2)
            with _bcol1:
                if st.button("🔄 " + _t("Ricarica da DB"),
                             key=f"{_key_prefix}do_btn_reload", use_container_width=True):
                    try:
                        _init_db()
                        _loaded = _load_month(int(_do_year), int(_do_month),
                                               plant_id=_do_plant_safe)
                        _all_days = _gen_days(int(_do_year), int(_do_month))
                        _data_map = {d: {} for d in _all_days}
                        # Default 0h: impianto spento per giorni senza dati DB.
                        _hours_reload: dict = {d: 0.0 for d in _all_days}
                        _remi_reload: dict = {d: {"vb": 0.0, "e": 0.0, "qb_max": 0.0,
                                                   "pci": 0.0, "rho": 0.0} for d in _all_days}
                        for _e in _loaded:
                            if _e.date in _data_map:
                                _data_map[_e.date] = dict(_e.feedstocks)
                                _hours_reload[_e.date] = float(_e.hours_per_day)
                                _remi_reload[_e.date] = {
                                    "vb": float(_e.remi_vb),
                                    "e": float(_e.remi_e),
                                    "qb_max": float(_e.remi_qb_max),
                                    "pci": float(_e.remi_pci),
                                    "rho": float(_e.remi_rho),
                                }
                        st.session_state[_do_key] = _data_map
                        st.session_state[_hours_key] = _hours_reload
                        st.session_state[_do_key + "::remi"] = _remi_reload
                        st.success(_t("Mese ricaricato dal database."))
                    except Exception as _exc:  # noqa: BLE001
                        _LOG.exception("Daily reload failed for %s",
                                       _do_plant_safe)
                        st.warning(_t("Errore ricarica:") + f" {_exc}")
            with _bcol2:
                if st.button("🆕 " + _t("Azzera mese"),
                             key=f"{_key_prefix}do_btn_new", use_container_width=True):
                    _all_days = _gen_days(int(_do_year), int(_do_month))
                    st.session_state[_do_key] = {d: {} for d in _all_days}
                    # Default 0h dopo azzeramento: impianto spento.
                    st.session_state[_hours_key] = {d: 0.0 for d in _all_days}
                    st.session_state[_do_key + "::remi"] = {d: {"vb": 0.0, "e": 0.0, "qb_max": 0.0, "pci": 0.0, "rho": 0.0} for d in _all_days}
                    st.success(_t("Mese azzerato. Inserisci nuovi dati nella tabella."))

        _do_active_feeds = list(active_feeds) if active_feeds else list(FEED_NAMES)[:6]
        _data_map = st.session_state[_do_key]
        _all_days = sorted(_data_map.keys())

        # Contesto di calcolo riusato per pre-editor + post-edit
        _ctx = {
            "aux_factor": float(aux_factor),
            "ep": float(ep_total),
            "fossil_comparator": float(FOSSIL_COMPARATOR),
            "plant_net_smch": float(plant_net_smch),
            "hours_per_day": 24.0,
        }
        _cap_smch = float(plant_net_smch) if plant_net_smch else 0.0

        # =================================================================
        # PRE-CALCOLO per visualizzazione editor (frame N-1: stato salvato)
        # ------------------------------------------------------------
        # Audit robustezza #4: distinguiamo errori "biomassa sconosciuta in
        # FEEDSTOCK_DB" (config error grave, da segnalare) da errori più
        # benigni (dati incompleti per quel giorno → silenzio OK).
        # I problemi di config vengono raccolti in un set e mostrati 1 volta.
        # =================================================================
        _compute_config_errors: set = set()

        def _compute_safely(_date, _feedstocks, _hours_run=24.0, _remi_data=None):
            """Calcola DailyComputed, accettando ore di funzionamento per riga.

            Le ore di funzionamento finiscono nel ctx come `hours_per_day`
            override → `compute_daily` calcola correttamente Sm³/giorno e
            il check del cap autorizzativo orario.
            """
            _ctx_local = dict(_ctx)
            _ctx_local["hours_per_day"] = float(_hours_run) if _hours_run else 24.0
            try:
                _entry = _DEntry(date=_date, feedstocks=_feedstocks)
                if _remi_data:
                    _entry.remi_vb = float(_remi_data.get("vb", 0.0))
                    _entry.remi_e = float(_remi_data.get("e", 0.0))
                    _entry.remi_qb_max = float(_remi_data.get("qb_max", 0.0))
                    _entry.remi_pci = float(_remi_data.get("pci", 0.0))
                    _entry.remi_rho = float(_remi_data.get("rho", 0.0))

                return _compute_daily(
                    _entry,
                    ctx=_ctx_local,
                )
            except KeyError as _kexc:  # biomassa non in FEEDSTOCK_DB
                _missing = str(_kexc).strip("'\"")
                _compute_config_errors.add(_missing)
                _LOG.warning("Daily compute: feedstock not in DB: %s", _missing)
                return None
            except Exception as _exc:  # noqa: BLE001
                _LOG.exception("Daily compute failed for %s: %s", _date, _exc)
                return None

        # _hours_key è già definito sopra (stesso scope) — safety net per
        # session reinizializzazioni parziali. Default 0h (impianto spento).
        _remi_key = _do_key + "::remi"
        if _hours_key not in st.session_state:
            st.session_state[_hours_key] = {_d: 0.0 for _d in _all_days}
        if _remi_key not in st.session_state:
            st.session_state[_remi_key] = {_d: {"vb": 0.0, "e": 0.0, "qb_max": 0.0, "pci": 0.0, "rho": 0.0} for _d in _all_days}

        _hours_map = st.session_state[_hours_key]
        _remi_map = st.session_state[_remi_key]
        # Garantisce che ci sia una entry per ogni giorno (aggiunge giorni nuovi)
        for _d in _all_days:
            _hours_map.setdefault(_d, 0.0)
            _remi_map.setdefault(_d, {"vb": 0.0, "e": 0.0, "qb_max": 0.0, "pci": 0.0, "rho": 0.0})

        # =================================================================
        # FIX BUG SM³/h NON CALCOLATI: applicazione PRE-RENDER degli edits
        # ------------------------------------------------------------
        # Il vero motivo per cui le colonne computed non si aggiornavano:
        # `_pre_computed` veniva calcolato PRIMA che gli edits dell'utente
        # fossero applicati a `_data_map`. Risultato: editor mostra "30 t"
        # nella biomassa MA Sm³/h calcolato sul vecchio _data_map vuoto.
        # ------------------------------------------------------------
        # SOLUZIONE: Streamlit salva gli edits del data_editor in
        # `session_state[editor_key]` come dict {edited_rows, added_rows,
        # deleted_rows}. Lo leggiamo QUI, prima del calcolo, e applichiamo
        # gli edits a _data_map e _hours_map. Quando poi calcoliamo
        # _pre_computed, i dati sono già allineati alla UI.
        # =================================================================
        _HOURS_COL = "Ore funz."
        if _DOG_KEY not in st.session_state:
            st.session_state[_DOG_KEY] = 0
        _editor_key = f"{_key_prefix}do_editor_{_do_key}_g{st.session_state[_DOG_KEY]}"

        _editor_state = st.session_state.get(_editor_key, {})
        _pending_edits = _editor_state.get("edited_rows", {}) if isinstance(_editor_state, dict) else {}

        if _pending_edits:
            for _row_idx_str, _changes in _pending_edits.items():
                try:
                    _row_idx = int(_row_idx_str)
                    if not (0 <= _row_idx < len(_all_days)):
                        continue
                    _d_edit = _all_days[_row_idx]
                    for _col, _val in (_changes or {}).items():
                        if _col == _HOURS_COL:
                            try:
                                # Se l'utente cancella la cella ore, default 0
                                # (impianto spento). L'auto-popolamento a 24h
                                # avviene piu' sotto solo se c'e' biomassa > 0.
                                _hours_map[_d_edit] = max(0.0, min(24.0, float(_val or 0.0)))
                            except (TypeError, ValueError):
                                _hours_map[_d_edit] = 0.0
                        elif _col == "Sm³ reali giorno":
                            _remi_map[_d_edit]["vb"] = float(_val or 0.0)
                        elif _col == "E (kWh)":
                            _remi_map[_d_edit]["e"] = float(_val or 0.0)
                        elif _col == "Qb max (Smc/h)":
                            _remi_map[_d_edit]["qb_max"] = float(_val or 0.0)
                        elif _col == "PCI (kWh/mc)":
                            _remi_map[_d_edit]["pci"] = float(_val or 0.0)
                        elif _col == "Rho (kg/mc)":
                            _remi_map[_d_edit]["rho"] = float(_val or 0.0)
                        elif _col in _do_active_feeds:
                            try:
                                _v = float(_val or 0.0)
                            except (TypeError, ValueError):
                                _v = 0.0
                            if _v > 0:
                                _data_map.setdefault(_d_edit, {})[_col] = _v
                            else:
                                if _d_edit in _data_map:
                                    _data_map[_d_edit].pop(_col, None)
                                    if not _data_map[_d_edit]:
                                        _data_map.pop(_d_edit, None)
                except (ValueError, KeyError, IndexError):
                    continue
            # Auto-popolamento ore: per ogni giorno con biomassa > 0 ma ore == 0
            # (utente ha caricato biomassa senza specificare le ore) default 24h
            # (produzione continua). Per giorni senza biomassa lasciamo 0h
            # (impianto spento).
            for _d_auto in _all_days:
                _bio_day = sum(float(v) for v in (_data_map.get(_d_auto) or {}).values())
                if _bio_day > 0 and abs(float(_hours_map.get(_d_auto, 0.0))) < 1e-9:
                    _hours_map[_d_auto] = 24.0
                elif _bio_day == 0 and abs(float(_hours_map.get(_d_auto, 0.0))) > 1e-9:
                    # Caso opposto: biomassa rimossa ma ore restate. Le azzero
                    # per coerenza (impianto senza alimentazione = spento).
                    _hours_map[_d_auto] = 0.0
            # Persisti subito gli edits in session_state
            st.session_state[_do_key] = _data_map
            st.session_state[_hours_key] = _hours_map

        _entries_list = [
            _DEntry(date=_d, feedstocks=dict(_data_map.get(_d) or {}),
                    hours_per_day=float(_hours_map.get(_d, 0.0)),
                    remi_vb=float(_remi_map[_d]["vb"]),
                    remi_e=float(_remi_map[_d]["e"]),
                    remi_qb_max=float(_remi_map[_d]["qb_max"]),
                    remi_pci=float(_remi_map[_d]["pci"]),
                    remi_rho=float(_remi_map[_d]["rho"]))
            for _d in _all_days
        ]
        _pre_computed = [
            _compute_safely(
                _e.date, _e.feedstocks,
                _hours_run=float(_hours_map.get(_e.date, 24.0)),
                _remi_data=_remi_map.get(_e.date),
            )
            for _e in _entries_list
        ]
        _computed_list = [_c for _c in _pre_computed if _c is not None]

        _regime_lbl = "DM 2022 (RED III)"
        _agg = _agg_month(_computed_list, ctx=_ctx,
                           year=int(_do_year), month=int(_do_month))
        _sust = _eval_sust(
            _agg, regime=_regime_lbl,
            threshold=float(ghg_threshold),
            regime_constraints={"max_sm3h_authorized": _cap_smch or None},
        )
        _kpis = _build_kpis(_agg, _sust)
        _thr_pct = float(_kpis["threshold"])


        # =================================================================
        # COMPUTE KPI STANDARD (senza override BMT / emission factor).
        # Hack pragmatico: swap temporaneo dei dict globali, try/finally.
        # =================================================================
        def _compute_kpis_standard(_entries, _ctx_local, _y, _mo, _reg, _thr, _cap):
            import sys as _sys
            _gmod = _sys.modules[__name__]
            _saved_yields = dict(_gmod._EFFECTIVE_YIELDS)
            _saved_emiss = dict(_gmod._EMISSION_OVERRIDES)
            try:
                _gmod._EFFECTIVE_YIELDS.clear()
                _gmod._EMISSION_OVERRIDES.clear()
                _std_c = []
                for _e in _entries:
                    try:
                        _cc = _compute_daily(_e, ctx=_ctx_local)
                        if _cc is not None:
                            _std_c.append(_cc)
                    except Exception:
                        continue
                _std_a = _agg_month(_std_c, ctx=_ctx_local, year=_y, month=_mo)
                _std_s = _eval_sust(
                    _std_a, regime=_reg, threshold=_thr,
                    regime_constraints={"max_sm3h_authorized": _cap or None},
                )
                return _build_kpis(_std_a, _std_s)
            finally:
                _gmod._EFFECTIVE_YIELDS.clear()
                _gmod._EFFECTIVE_YIELDS.update(_saved_yields)
                _gmod._EMISSION_OVERRIDES.clear()
                _gmod._EMISSION_OVERRIDES.update(_saved_emiss)

        _has_yield_overrides = bool(_EFFECTIVE_YIELDS)
        _has_emiss_overrides = bool(_EMISSION_OVERRIDES)
        _has_any_override = _has_yield_overrides or _has_emiss_overrides

        if _has_any_override:
            _kpis_standard = _compute_kpis_standard(
                _entries_list, _ctx, int(_do_year), int(_do_month),
                _regime_lbl, float(ghg_threshold), _cap_smch,
            )
        else:
            _kpis_standard = _kpis

        # =================================================================
        # TABELLA UNICA — input editabili + colonne calcolate (disabled)
        # Gli edits sono GIÀ stati applicati a _data_map / _hours_map sopra
        # (lettura di session_state[editor_key].edited_rows pre-render),
        # quindi _pre_computed è già fresh e le colonne calcolate sono OK.
        # =================================================================
        _SMH_GROSS_COL = "Sm³/h lordi"
        _SMH_COL = "Sm³/h netti"
        _SAV_COL = "Saving GHG (%)"
        _OK_COL = "Esito"
        _BIO_TOT_COL = "Totale Biomasse (t)"

        _thr_pct_pre = float(ghg_threshold) * 100.0 if ghg_threshold else 80.0

        def _row_outcome(c, biomass_t, hours_run):
            """✅ giorno OK · ❌ violazione · — nessun dato/fermo."""
            if c is None or biomass_t <= 0 or hours_run <= 0:
                return "—"
            sm3h = float(c.sm3_netti_ora)
            cap_ok = (_cap_smch <= 0) or (sm3h <= _cap_smch)
            sav_ok = c.daily_saving_estimate >= _thr_pct_pre
            return "✅" if (cap_ok and sav_ok) else "❌"

        def _row_note(c, biomass_t, hours_run):
            if c is None or biomass_t <= 0 or hours_run <= 0:
                return "—"
            sm3h = float(c.sm3_netti_ora)
            cap_ok = (_cap_smch <= 0) or (sm3h <= _cap_smch)
            sav_ok = c.daily_saving_estimate >= _thr_pct_pre

            notes = []
            if not cap_ok:
                notes.append(_t("Violazione cap"))
            if not sav_ok:
                notes.append(_t("Saving < soglia"))

            if not notes:
                return _t("OK")
            return " + ".join(notes)

        st.markdown(f"### 🌾 {_t('Tabella giornaliera')}")
        st.caption(
            _t("Inserisci **ore di funzionamento** (formato decimale: 16.50 = 16h 30min) "
               "e **biomasse t/giorno**. Sm³/h lordi, Sm³/h netti, Saving GHG e Esito "
               "si aggiornano automaticamente.")
        )

        _REMI_VB_COL = "Sm³ reali giorno"
        _REMI_E_COL = "E (kWh)"
        _REMI_QBMAX_COL = "Qb max (Smc/h)"
        _REMI_PCI_COL = "PCI (kWh/mc)"
        _REMI_RHO_COL = "Rho (kg/mc)"
        _REMI_FLOW_COL = "Portata REMI (Smc/h)"
        _REMI_POW_COL = "Potenza REMI (MW)"
        _REMI_SPEC_COL = "Energia Spec. (kWh/Smc)"

        _edit_rows = []
        for _i, _d in enumerate(_all_days):
            _h = float(_hours_map.get(_d, 0.0))
            _bio_row = 0.0
            _row = {"Data": fmt_date(_d), _HOURS_COL: _h}
            for _f in _do_active_feeds:
                _v = float((_data_map.get(_d) or {}).get(_f, 0.0))
                _row[_f] = _v
                _bio_row += _v
            _row[_BIO_TOT_COL] = _bio_row

            _rm = _remi_map.get(_d, {})
            _row.update({
                _REMI_VB_COL: _rm.get("vb", 0.0),
            })

            _c = _pre_computed[_i]
            if _c is not None:
                _row[_SMH_GROSS_COL] = float(_c.sm3_gross_ora)
                _row[_SMH_COL]       = float(_c.sm3_netti_ora)
                _row[_SAV_COL]       = float(_c.daily_saving_estimate)
                _row[_REMI_FLOW_COL] = _c.remi_portata_media_smch
            else:
                _row[_SMH_GROSS_COL] = 0.0
                _row[_SMH_COL]       = 0.0
                _row[_SAV_COL]       = 0.0
                _row[_REMI_FLOW_COL] = 0.0

            _row[_OK_COL]        = _row_outcome(_c, _bio_row, _h)
            _row["Note"]         = _row_note(_c, _bio_row, _h)
            _edit_rows.append(_row)

        _is_sust_mtd = _kpis.get('compliant', False)
        _sust_icon = "✅ SOSTENIBILE" if _is_sust_mtd else "❌ NON SOSTENIBILE"
        _totals_row = {
            "Data": "TOTALE MESE",
            _HOURS_COL: sum(float(_hours_map.get(_d, 0.0)) for _d in _all_days)
        }
        for _f in _do_active_feeds:
            _totals_row[_f] = sum(float((_data_map.get(_d) or {}).get(_f, 0.0)) for _d in _all_days)

        _totals_row[_BIO_TOT_COL] = _kpis.get('biomass_total_t', 0.0)
        _totals_row[_REMI_VB_COL] = _kpis.get('remi_vb_total', 0.0)
        _compiled_hours = sum(_r.get(_HOURS_COL, 24.0) for _r in _edit_rows if _r.get(_BIO_TOT_COL, 0) > 0 or _r.get(_REMI_VB_COL, 0) > 0 or _r.get(_SMH_GROSS_COL, 0) > 0)
        _totals_row[_SMH_GROSS_COL] = _kpis.get('sm3_gross', 0.0) / _compiled_hours if _compiled_hours > 0 else 0.0
        _totals_row[_SMH_COL] = _kpis.get('sm3_netti', 0.0) / _compiled_hours if _compiled_hours > 0 else 0.0
        _totals_row[_SAV_COL] = _kpis.get('saving_pct', 0.0)
        _totals_row[_REMI_FLOW_COL] = _kpis.get('remi_vb_total', 0.0) / _compiled_hours if _compiled_hours > 0 else 0.0
        _totals_row[_OK_COL] = _sust_icon
        _saving_pct = _kpis.get('saving_pct_net', 0.0)
        _thr = _kpis.get('threshold', 0.0)
        if _is_sust_mtd:
            _totals_row["Note"] = f"OK — Saving {_saving_pct:.1f}% (≥ {_thr:.0f}%) e limiti rispettati"
        else:
            if _saving_pct < _thr:
                _totals_row["Note"] = f"KO — Saving {_saving_pct:.1f}% (soglia {_thr:.0f}%)"
            else:
                _failed_c = [c.get("name", "") for c in _kpis.get('constraints_status', []) if not c.get("ok", True)]
                _totals_row["Note"] = "KO — Vincoli violati: " + " | ".join(_failed_c)

        _edit_rows.append(_totals_row)
        _edit_df = _pd_daily.DataFrame(_edit_rows)

        # =================================================================
        # CSS iniettato: evidenzia l'ultima riga (TOTALE MESE) del data_editor
        # — react-data-grid usa aria-rowindex 1-based dove header=1 e
        # l'ultima riga del data ha indice = 1 + N_data_rows.
        # =================================================================
        _total_aria_idx = 1 + len(_edit_rows)  # 1 header + N righe (totale = ultima)
        st.markdown(
            f"""
            <style>
            div[data-testid="stDataFrame"] div[role="row"][aria-rowindex="{_total_aria_idx}"],
            div[data-testid="stDataEditor"] div[role="row"][aria-rowindex="{_total_aria_idx}"] {{
                background: linear-gradient(90deg,
                    rgba(154,123,60,0.20) 0%,
                    rgba(239,231,212,0.55) 50%,
                    rgba(154,123,60,0.20) 100%) !important;
                box-shadow: inset 0 2px 0 #9A7B3C, inset 0 -2px 0 #9A7B3C !important;
            }}
            div[data-testid="stDataFrame"] div[role="row"][aria-rowindex="{_total_aria_idx}"] [role="gridcell"],
            div[data-testid="stDataEditor"] div[role="row"][aria-rowindex="{_total_aria_idx}"] [role="gridcell"] {{
                font-weight: 700 !important;
                font-size: 1.02rem !important;
                color: #15242E !important;
                background-color: transparent !important;
                border-color: #9A7B3C !important;
            }}
            /* Prima cella (Data = "TOTALE MESE") extra-evidente */
            div[data-testid="stDataFrame"] div[role="row"][aria-rowindex="{_total_aria_idx}"] [role="gridcell"]:first-of-type,
            div[data-testid="stDataEditor"] div[role="row"][aria-rowindex="{_total_aria_idx}"] [role="gridcell"]:first-of-type {{
                color: #7A6230 !important;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        # _editor_key è stato definito sopra (g{counter}). Cambia solo se
        # bumpiamo do_editor_gen (es. dopo cambio mese / nuovo / ricarica DB).
        _edited = st.data_editor(
            _edit_df,
            key=_editor_key,
            num_rows="fixed",
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn(
                    "Data", disabled=True,
                    help=_t("Giorno del mese di rendicontazione."),
                ),
                _HOURS_COL: st.column_config.NumberColumn(
                    _HOURS_COL, min_value=0.0, max_value=24.0,
                    step=0.25, format="%.2f",
                    help=_t("Ore di funzionamento dell'impianto. Formato decimale: "
                            "16.50 = 16h 30min, 16.25 = 16h 15min, 16.75 = 16h 45min. "
                            "Default 24.00 (impianto sempre attivo)."),
                ),
                **{
                    _f: st.column_config.NumberColumn(
                        _f, min_value=0.0, step=0.1, format="%.2f",
                        help=_t("Biomassa giornaliera (t)"),
                    )
                    for _f in _do_active_feeds
                },
                _BIO_TOT_COL: st.column_config.NumberColumn(
                    _BIO_TOT_COL, disabled=True, format="%.2f",
                    help=_t("Somma totale delle biomasse inserite nel giorno (t)"),
                ),
                _SMH_GROSS_COL: st.column_config.NumberColumn(
                    _SMH_GROSS_COL, disabled=True, format="%.1f",
                    help=_t("Biogas LORDO prodotto in 1 ora. "
                            "Calcolato = Resa teorica biomasse / ore di funzionamento."),
                ),
                _SMH_COL: st.column_config.NumberColumn(
                    _SMH_COL, disabled=True, format="%.1f",
                    help=_t("Biometano NETTO immesso in rete in 1 ora. "
                            "Calcolato = Sm³ reali giorno / ore di funzionamento. "
                            "Cap autorizzato:") + f" {_cap_smch:,.0f}",
                ),
                _SAV_COL: st.column_config.NumberColumn(
                    _SAV_COL, disabled=True, format="%.2f",
                    help=_t("Saving GHG giornaliero (informativo). La compliance è mensile."),
                ),
                _OK_COL: st.column_config.TextColumn(
                    _OK_COL, disabled=True, width="small",
                    help=_t("✅ giorno OK (entro cap e sopra soglia GHG) · "
                            "❌ violazione cap o saving sotto soglia · "
                            "— nessun dato. NB: la conformità ufficiale resta mensile."),
                ),
                "Note": st.column_config.TextColumn(
                    "Note", disabled=True, width="medium",
                    help=_t("Dettaglio dell'esito (es. OK, Violazione cap, Saving sotto soglia)."),
                ),
                _REMI_VB_COL: st.column_config.NumberColumn(
                    _REMI_VB_COL, min_value=0.0, format="%.0f",
                    help=_t("Volume biometano reale misurato al REMI (Sm³) in questo giorno. "
                            "Questo valore viene diviso per le Ore per determinare gli Sm³/h netti."),
                ),
                _REMI_FLOW_COL: st.column_config.NumberColumn(
                    _REMI_FLOW_COL, disabled=True, format="%.1f",
                    help=_t("Portata media reale misurata al REMI = Sm³ reali / ore di funzionamento."),
                ),
            },
            use_container_width=True,
        )

        # NB: _data_map e _hours_map sono GIÀ aggiornati dal blocco
        # "applicazione PRE-RENDER degli edits" sopra. Non serve un secondo
        # update post-render né st.rerun() forzato: lo state è già coerente.
        # _edited è ignorato qui (lo usiamo solo come trigger del rerun
        # automatico di Streamlit dopo l'edit utente).

        # =================================================================
        # CALCOLO POST-EDIT (sorgente unica per tabella OUTPUT + KPI + banner)
        # ------------------------------------------------------------
        # Usa _hours_map aggiornato ad ogni giorno → Sm³/h riflettono
        # le ore reali di funzionamento.
        # =================================================================
        # I KPI sono già stati calcolati in fase di pre-render (sopra l'editor)

        def _it_num(value, decimals):
            # Locale-aware: usa get_lang() per scegliere stile IT vs EN.
            try:
                from i18n_runtime import get_lang as _gl
                _lang_local = _gl()
            except Exception:
                _lang_local = "it"
            s = f"{float(value):,.{decimals}f}"
            if _lang_local == "en":
                return s
            return s.replace(",", "X").replace(".", ",").replace("X", ".")

        # =================================================================
        # RIGA TOTALE MESE — tabella HTML completa con TUTTE le colonne
        # dell'editor, formattata in modo da spiccare immediatamente sotto
        # la tabella giornaliera.
        # =================================================================
        _is_sust_mtd = _kpis.get('compliant', False)
        _sust_color = "#059669" if _is_sust_mtd else "#DC2626"
        _sust_bg = ("linear-gradient(135deg,#059669 0%,#047857 100%)"
                    if _is_sust_mtd else
                    "linear-gradient(135deg,#DC2626 0%,#991B1B 100%)")
        _sust_icon_full = "✅ OK" if _is_sust_mtd else "❌ KO"
        # Note sintetiche compatte. Usa il MSG esatto dei constraint (es. "3
        # giorno/i sopra cap autorizzativo") invece del solo nome: il valore
        # medio mensile può essere sotto soglia ma giorni singoli sopra → spiega.
        _saving_pct_net = _kpis.get('saving_pct_net', 0.0)
        _failed_msgs = [
            (c.get("msg") or c.get("name") or "")
            for c in _kpis.get('constraints_status', [])
            if not c.get("ok", True)
        ]
        if _is_sust_mtd:
            _note_mtd = f"Saving {_saving_pct_net:.1f}% ≥ {_thr_pct:.0f}%"
        elif _saving_pct_net < _thr_pct:
            _note_mtd = f"Saving {_saving_pct_net:.1f}% < {_thr_pct:.0f}%"
        elif _failed_msgs:
            _note_mtd = "KO: " + " · ".join(_failed_msgs)
        else:
            _note_mtd = "KO"

        # Costruisco header + valori della riga totale per OGNI colonna.
        # Usiamo _compiled_hours (calcolato sopra a riga ~2636 PRIMA che la
        # totals_row venga aggiunta a _edit_rows). Se calcolassimo ora su
        # _edit_rows includeremmo la totals_row stessa (HOURS=744 + BIO=80)
        # gonfiando il divisore → Sm³/h medi sbagliati (es. 6,5 invece di 208).
        _tot_hours = sum(float(_hours_map.get(_d, 0.0)) for _d in _all_days)
        _tot_smh_gross = (_kpis.get('sm3_gross', 0.0) / _compiled_hours) if _compiled_hours > 0 else 0.0
        _tot_smh_net = (_kpis.get('sm3_netti', 0.0) / _compiled_hours) if _compiled_hours > 0 else 0.0
        _tot_remi_flow = (_kpis.get('remi_vb_total', 0.0) / _compiled_hours) if _compiled_hours > 0 else 0.0

        # Abbrevia i nomi biomassa per la riga compatta (massimo 8 char)
        def _abbr(name: str, n: int = 8) -> str:
            name = str(name).strip()
            return name if len(name) <= n else (name[:n - 1] + "…")

        # Costruzione celle compatte — solo dati ESSENZIALI (no Sm³/h lordi,
        # no Portata REMI, no Note — ridondanti con Esito/Sm³ netti).
        # Header breve + full name in `title` (tooltip al hover).
        _cells: list = []  # list of (short_hdr, full_hdr, value, align)
        _cells.append(("TOTALE",  "TOTALE MESE",                "📊 TOTALE MESE",                                            "left"))
        _cells.append(("Ore",     _HOURS_COL,                    f"{_it_num(_tot_hours, 0)}h",                                "right"))
        for _f in _do_active_feeds:
            _qty = sum(float((_data_map.get(_d) or {}).get(_f, 0.0)) for _d in _all_days)
            _cells.append((_abbr(_f), str(_f), f"{_it_num(_qty, 1)}t", "right"))
        _cells.append(("Tot t",   _BIO_TOT_COL,                  f"{_it_num(_kpis.get('biomass_total_t', 0.0), 1)}t",         "right"))
        _cells.append(("Sm³ tot", _REMI_VB_COL,                  f"{_it_num(_kpis.get('remi_vb_total', 0.0), 0)}",            "right"))
        _cells.append(("Sm³/h",   _SMH_COL,                      f"{_it_num(_tot_smh_net, 1)}",                                "right"))
        _cells.append(("Saving",  _SAV_COL,                      f"{_kpis.get('saving_pct', 0.0):.2f}%",                       "right"))
        _cells.append(("Esito",   _OK_COL,                       _sust_icon_full,                                              "center"))

        # Genero HTML thead + tbody (1 sola riga totale) — ultra compatto
        _hdr_html = "".join(
            f"<th title='{full}' style='padding:3px 5px;font-size:0.58rem;"
            f"font-weight:700;text-transform:uppercase;letter-spacing:0.2px;"
            f"color:#B59450;text-align:{align};border-bottom:1px solid #9A7B3C;"
            f"white-space:nowrap;line-height:1;'>{short}</th>"
            for short, full, _val, align in _cells
        )
        _val_cells_html = []
        for short, full, val, align in _cells:
            if short == "Esito":
                cell = (
                    f"<td title='{full}' style='padding:4px 5px;text-align:{align};"
                    f"vertical-align:middle;'>"
                    f"<span style='background:{_sust_bg};color:#FFFFFF;"
                    f"padding:2px 6px;border-radius:3px;font-weight:800;"
                    f"font-size:0.72rem;white-space:nowrap;'>{val}</span></td>"
                )
            elif short == "Saving":
                cell = (
                    f"<td title='{full}' style='padding:4px 5px;text-align:{align};"
                    f"font-weight:800;font-size:0.82rem;color:{_sust_color};"
                    f"vertical-align:middle;white-space:nowrap;'>{val}</td>"
                )
            elif short == "TOTALE":
                cell = (
                    f"<td title='{full}' style='padding:4px 6px;text-align:{align};"
                    f"font-weight:800;font-size:0.78rem;color:#B59450;"
                    f"vertical-align:middle;white-space:nowrap;'>{val}</td>"
                )
            else:
                cell = (
                    f"<td title='{full}' style='padding:4px 5px;text-align:{align};"
                    f"font-weight:700;font-size:0.76rem;color:#F8FAFC;"
                    f"vertical-align:middle;white-space:nowrap;'>{val}</td>"
                )
            _val_cells_html.append(cell)
        _row_html = "".join(_val_cells_html)

        st.markdown(
            f"""
            <div style='margin-top:-0.5rem;margin-bottom:0.6rem;
                background:#15242E;
                border-top:2px solid #9A7B3C;
                border-radius:0 0 6px 6px;
                box-shadow:none;'>
              <table style='width:100%;border-collapse:collapse;table-layout:auto;'>
                <thead><tr>{_hdr_html}</tr></thead>
                <tbody><tr>{_row_html}</tr></tbody>
              </table>
            </div>
            """, unsafe_allow_html=True
        )

        # Conteggi anomalie giornaliere (post-edit, sempre fresh)
        _n_days_data = sum(1 for _c in _computed_list if _c.biomass_total_t > 0)
        _n_cap_viol = sum(
            1 for _c in _computed_list
            if _cap_smch > 0 and _c.sm3_netti_ora > _cap_smch
        )
        # Audit robustezza #19: il filtro `0 < saving` mascherava i giorni
        # patologici con saving NEGATIVO (e_total > comparator → impianto
        # peggio del fossile). Solo giorni SENZA dati biomasse vanno esclusi
        # dal conteggio: usiamo `biomass_total_t > 0` come gate.
        _n_save_viol = sum(
            1 for _c in _computed_list
            if _c.biomass_total_t > 0 and _c.daily_saving_estimate < _thr_pct
        )
        _n_ok = max(0, _n_days_data - _n_cap_viol - _n_save_viol)
        # Nota: i giorni di picco oltre cap non bloccano la conformità (la
        # verifica DM 2022 è MENSILE sulla portata media). Mostriamo info
        # se ci sono picchi ma il mese è OK: utile per audit, non per blocco.
        if _n_cap_viol > 0 and _cap_smch > 0:
            _avg_smh_net_mese = (_kpis.get('sm3_netti', 0.0) / _compiled_hours) if _compiled_hours > 0 else 0.0
            if _avg_smh_net_mese <= _cap_smch:
                st.info(
                    f"ℹ️ {_n_cap_viol} {_t('giorno/i di picco sopra cap')} "
                    f"({_cap_smch:,.0f} Sm³/h), {_t('ma la portata media mensile')} "
                    f"({_avg_smh_net_mese:,.1f} Sm³/h) {_t('è sotto soglia')} — "
                    f"{_t('conformità DM 2022 verificata sul totale mensile, mese OK.')}"
                )
        st.caption(
            f"✅ **{_n_ok}** {_t('giorni OK')} · "
            f"❌ **{_n_cap_viol + _n_save_viol}** {_t('giorni con violazioni')} "
            f"({_n_cap_viol} {_t('cap')} / {_n_save_viol} {_t('saving')}) · "
            f"— **{len(_all_days) - _n_days_data}** {_t('giorni senza dati')} · "
            f"{_t('cap')} {_cap_smch:,.0f} Sm³/h · {_t('soglia')} {_thr_pct:.1f}% — "
            f"{_t('la conformità ufficiale resta mensile')}"
        )

        # =================================================================
        # MINI BARCHART biomasse totali per giorno
        # =================================================================
        if _n_days_data > 0:
            _chart_df = _pd_daily.DataFrame({
                "data": [_c.date.strftime("%d/%m") for _c in _computed_list],
                "biomassa (t)": [_c.biomass_total_t for _c in _computed_list],
            }).set_index("data")
            try:
                st.bar_chart(_chart_df, height=160, color=AMBER)
            except Exception:  # vecchie versioni Streamlit ignorano color
                st.bar_chart(_chart_df, height=160)

        # =================================================================
        # BANNER ESITO MENSILE — HTML custom con gradient e palette brand
        # =================================================================
        # Audit robustezza #20: mese vuoto NON deve mostrare "MESE SOSTENIBILE
        # 100%". Quando non ci sono dati, mostriamo banner neutro "in attesa".
        if _n_days_data == 0:
            st.markdown(
                f"""
                <div style='background:linear-gradient(135deg,#64748B 0%,#475569 100%);
                     color:#FFFFFF;padding:18px 22px;border-radius:14px;
                     margin:10px 0 16px 0;
                     box-shadow:0 4px 12px rgba(15,23,42,0.18);'>
                    <div style='font-size:0.7rem;font-weight:700;letter-spacing:1.5px;
                         text-transform:uppercase;opacity:0.85;margin-bottom:4px;'>
                        {_t('Esito ufficiale')} — {_regime_lbl}
                    </div>
                    <div style='display:flex;align-items:center;gap:14px;'>
                        <div style='font-size:2.2rem;line-height:1;'>⏳</div>
                        <div>
                            <div style='font-size:1.6rem;font-weight:700;line-height:1.1;'>
                                {_t('IN ATTESA DI DATI')}
                            </div>
                            <div style='font-size:0.95rem;opacity:0.95;margin-top:4px;'>
                                {_t('Inserisci almeno un giorno con biomassa &gt; 0 '
                                    'per calcolare il saving GHG mensile.')}
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            if _kpis["compliant"]:
                _bg = f"linear-gradient(135deg, {SUCCESS} 0%, #047857 100%)"
                _icon = "✅"
                _label = _t("MESE SOSTENIBILE")
                _detail = (f"{_t('saving')} <b>{_kpis['saving_pct']:.2f}%</b> ≥ "
                           f"{_t('soglia')} {_thr_pct:.2f}% "
                           f"(+{_kpis['margin']:.2f} pt {_t('di margine')})")
            else:
                _bg = "linear-gradient(135deg, #DC2626 0%, #991B1B 100%)"
                _icon = "❌"
                _label = _t("MESE NON SOSTENIBILE")
                if _kpis['saving_pct'] >= _thr_pct:
                    _detail = (f"{_t('saving')} <b>{_kpis['saving_pct']:.2f}%</b> ≥ "
                               f"{_t('soglia')} {_thr_pct:.2f}%. "
                               f"<b>{_t('Tuttavia, ci sono vincoli di regime violati')}</b> ({_t('vedi Dettagli')}).")
                else:
                    _detail = (f"{_t('saving')} <b>{_kpis['saving_pct']:.2f}%</b> &lt; "
                               f"{_t('soglia')} {_thr_pct:.2f}% "
                               f"({abs(_kpis['margin']):.2f} pt {_t('sotto soglia')})")
            st.markdown(
                f"""
                <div style='background:{_bg};color:#FFFFFF;padding:18px 22px;
                     border-radius:14px;margin:10px 0 16px 0;
                     box-shadow:0 4px 12px rgba(15,23,42,0.18);'>
                    <div style='font-size:0.7rem;font-weight:700;letter-spacing:1.5px;
                         text-transform:uppercase;opacity:0.85;margin-bottom:4px;'>
                        {_t('Esito ufficiale')} — {_regime_lbl}
                    </div>
                    <div style='display:flex;align-items:center;gap:14px;'>
                        <div style='font-size:2.2rem;line-height:1;'>{_icon}</div>
                        <div>
                            <div style='font-size:1.6rem;font-weight:700;line-height:1.1;'>
                                {_label}
                            </div>
                            <div style='font-size:0.95rem;opacity:0.95;margin-top:4px;'>
                                {_detail}
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # =================================================================
        # CONFRONTO STANDARD vs ANALISI (BMT + Relazione tecnica)
        # =================================================================
        st.markdown("---")
        st.markdown(f"### 📊 {_t('Confronto Standard vs Analisi')}")

        if not _has_any_override:
            st.info(_t(
                "ℹ️ Attiva un override BMT (laboratorio) o un override "
                "Fattori Emissivi (relazione tecnica) in sidebar per "
                "vedere le differenze tra dato Standard "
                "(UNI-TS/RED III tabellare) e dato di Analisi (reale impianto)."
            ))
        else:
            _badges = []
            if _has_yield_overrides:
                _badges.append(f"🧪 {len(_EFFECTIVE_YIELDS)} BMT override")
            if _has_emiss_overrides:
                _badges.append(f"🧬 {len(_EMISSION_OVERRIDES)} EF override")
            st.caption(f"Override attivi: {' · '.join(_badges)}")

            def _delta_pct(_a, _s):
                return ((_a - _s) / _s * 100.0) if _s else 0.0

            _cmp_rows = [
                {
                    "KPI": "Biomasse (t/mese)",
                    "Standard": _it_num(_kpis_standard.get("biomass_total_t", 0.0), 1),
                    "Analisi":  _it_num(_kpis.get("biomass_total_t", 0.0), 1),
                    "Δ %":      f"{_delta_pct(_kpis.get('biomass_total_t', 0), _kpis_standard.get('biomass_total_t', 0)):+.2f}%",
                },
                {
                    "KPI": "Sm³ netti (mese)",
                    "Standard": _it_num(_kpis_standard.get("sm3_netti", 0.0), 0),
                    "Analisi":  _it_num(_kpis.get("sm3_netti", 0.0), 0),
                    "Δ %":      f"{_delta_pct(_kpis.get('sm3_netti', 0), _kpis_standard.get('sm3_netti', 0)):+.2f}%",
                },
                {
                    "KPI": "MWh netti (mese)",
                    "Standard": _it_num(_kpis_standard.get("mwh", 0.0), 1),
                    "Analisi":  _it_num(_kpis.get("mwh", 0.0), 1),
                    "Δ %":      f"{_delta_pct(_kpis.get('mwh', 0), _kpis_standard.get('mwh', 0)):+.2f}%",
                },
                {
                    "KPI": "Saving GHG (%)",
                    "Standard": f"{_kpis_standard.get('saving_pct', 0.0):.2f}",
                    "Analisi":  f"{_kpis.get('saving_pct', 0.0):.2f}",
                    "Δ %":      f"{(_kpis.get('saving_pct', 0) - _kpis_standard.get('saving_pct', 0)):+.2f} pt",
                },
            ]
            import pandas as _pd_cmp
            st.dataframe(
                _pd_cmp.DataFrame(_cmp_rows),
                hide_index=True,
                use_container_width=True,
            )

            _std_compliant = _kpis_standard.get("compliant", False)
            _an_compliant = _kpis.get("compliant", False)
            if _std_compliant != _an_compliant:
                if _an_compliant and not _std_compliant:
                    st.success(_t(
                        "✅ Gli override (BMT/Relazione) rendono il mese "
                        "SOSTENIBILE. Con i soli valori Standard NON saresti "
                        "conforme."
                    ))
                else:
                    st.error(_t(
                        "❌ Con i valori Standard il mese sarebbe SOSTENIBILE, "
                        "ma gli override applicati abbassano la performance "
                        "sotto soglia. Verifica i certificati."
                    ))

        # 3 KPI laterali (saving NON ripetuto: già nel banner)

        _k1, _k2, _k3 = st.columns(3)
        _k1.metric("🌾 " + _t("Biomassa mese"), f"{_it_num(_kpis['biomass_total_t'], 1)} t")
        _k2.metric("⚡ " + _t("MWh netti mese"), _it_num(_kpis['mwh'], 1))
        _k3.metric(
            "📅 " + _t("Giorni con dati"),
            f"{_kpis['n_days_with_data']} / {len(_all_days)}",
        )

        # KPI REMI consolidati (se presenti dati)
        if _kpis.get("remi_vb_total", 0) > 0:
            st.markdown(f"#### 📊 {_t('Consolidato REMI mese (dati dal contatore fiscale)')}")

            # Formattazione compatta: numeri grandi -> K (×10³) / M (×10⁶)
            # con 1 decimale, separatore italiano.
            def _fmt_compact(value: float, unit: str, decimals_small: int = 0) -> str:
                v = float(value or 0.0)
                if abs(v) >= 1_000_000:
                    s = f"{v/1_000_000:.2f}".replace(".", ",")
                    return f"{s} M{unit}"
                if abs(v) >= 10_000:
                    s = f"{v/1_000:.1f}".replace(".", ",")
                    return f"{s} k{unit}"
                return f"{_it_num(v, decimals_small)} {unit}"

            _e_estimated = bool(_kpis.get("remi_e_estimated", False))
            _e_marker = " *" if _e_estimated else ""

            # Colonne con larghezza pesata: dai più spazio a Vb (numero lungo)
            # e a PCI (unità lunga "kWh/Sm³"). Le altre più strette.
            _r1, _r2, _r3, _r4, _r5 = st.columns([1.15, 1.15, 1.05, 0.95, 1.20])
            _r1.metric(
                "📉 " + _t("Volume biometano (Vb)"),
                _fmt_compact(_kpis["remi_vb_total"], "Sm³"),
                help=_t(
                    "Vb = Volume di biometano immesso in rete nel mese, "
                    "letto dal contatore REMI (Sm³ standard a 15°C, 1.01325 bar). "
                    "È il totale di tutte le letture giornaliere 'Sm³ reali giorno' "
                    "compilate nella tabella."
                ),
            )
            _r2.metric(
                "🔋 " + _t("Energia immessa (E)") + _e_marker,
                _fmt_compact(_kpis["remi_e_total"], "Wh"),
                help=_t(
                    "E = Energia termica totale immessa in rete (kWh). "
                    "Se non compili la colonna 'E (kWh)' giornaliera, viene "
                    "stimata come Vb × PCI (PCI medio compilato, oppure "
                    "9.79 kWh/Sm³ standard biometano UNI EN 16723-1)."
                ),
            )
            _r3.metric(
                "🌀 " + _t("Portata media"),
                _fmt_compact(_kpis["remi_portata_media_smch"], "Sm³/h", decimals_small=1),
                help=_t(
                    "Portata oraria media del biometano (Vb totale / ore di "
                    "funzionamento effettive). Da confrontare col cap "
                    "autorizzativo dell'impianto."
                ),
            )
            _r4.metric(
                "⚡ " + _t("Potenza media"),
                f"{_it_num(_kpis['remi_potenza_media_mw'], 3)} MW",
                help=_t(
                    "Potenza termica media (E totale / ore / 1000). "
                    "Indica la capacità effettiva di immissione."
                ),
            )
            _r5.metric(
                "🎯 " + _t("PCI medio"),
                f"{_it_num(_kpis['remi_energia_specifica_kwh_smc'], 2)} kWh/Sm³",
                help=_t(
                    "Energia specifica = E / Vb. Per il biometano puro UNI EN "
                    "16723-1 è ~9.79 kWh/Sm³. Valori molto diversi indicano "
                    "biometano fuori specifica o errore di lettura."
                ),
            )
            if _e_estimated:
                _pci_use = _kpis.get("remi_pci_avg") or 9.79
                st.caption(
                    "ℹ️ *E totale stimato come **Vb × PCI** "
                    f"({_it_num(_pci_use, 2)} kWh/Smc, "
                    + (_t("media compilata") if _kpis.get("remi_pci_avg") else _t("PCI standard biometano UNI EN 16723-1"))
                    + "). " + _t(
                        "Compila la colonna **E (kWh)** giornaliera per usare la "
                        "lettura reale del contatore REMI."
                    )
                )

        # =================================================================
        # DETTAGLI & AUDIT — un solo expander con vincoli + indicazioni + audit
        # =================================================================
        _guidance = _build_guidance(_agg, _sust, regime=_regime_lbl)
        _audit = {
            # === Anagrafica simulazione (sidebar) ===
            _t("Nome azienda"):                     COMPANY_NAME or "—",
            _t("Sede legale"):                      COMPANY_LEGAL_ADDRESS or "—",
            _t("Nome impianto"):                    PLANT_NAME or "—",
            _t("Sede operativa"):                   PLANT_OPERATIONAL_ADDRESS or "—",
            # === Parametri di calcolo ===
            _t("Regime applicato"):                 _regime_lbl,
            _t("Soglia normativa (%)"):             f"{_thr_pct:.2f}",
            _t("Comparatore fossile (gCO2eq/MJ)"):  f"{FOSSIL_COMPARATOR:.2f}",
            _t("Aux factor (lordo/netto)"):         f"{aux_factor:.4f}",
            _t("EP totale (gCO2eq/MJ)"):            f"{ep_total:.3f}",
            _t("Plant net (Sm³/h)"):                f"{plant_net_smch:.2f}",
            _t("Origine rese"):                     _t("BMT override se attivo, altrimenti tabella standard"),
            _t("Origine fattori emissivi"):         _t("Override Relazione tecnica se attivo, altrimenti UNI-TS 11567:2024"),
            _t("Formula"):                          _t("Sostenibile = saving_mese ≥ soglia AND vincoli regime OK"),
            _t("Giorni con dati"):                  f"{_kpis['n_days_with_data']}",
            _t("Giorni cap autorizzativo violato"): f"{len(_kpis.get('cap_violation_days', []))}",
        }
        with st.expander("🔍 " + _t("Dettagli, vincoli e audit"), expanded=False):
            if _kpis.get("constraints_status"):
                st.markdown("**" + _t("Stato vincoli regime") + "**")
                for _c in _kpis["constraints_status"]:
                    _ic = "✅" if _c.get("ok") else "❌"
                    st.write(f"{_ic} **{_c.get('name','?')}** — {_c.get('msg','')}")
                st.write("")
            if _guidance:
                st.markdown("**🎯 " + _t("Indicazioni operative") + "**")
                for _g in _guidance:
                    st.write(f"- {_g}")
                st.write("")
            st.markdown("**🧾 " + _t("Audit Trail mese") + "**")
            for _k, _v in _audit.items():
                st.write(f"- **{_k}**: {_v}")

        # =================================================================
        # AUTO-SAVE silenzioso (sostituisce ex bottone "Salva mese su DB").
        # Idempotente: save_month usa INSERT OR REPLACE; eseguiamo solo se
        # i dati sono cambiati dall'ultimo save (hash su session_state).
        # Skip silenzioso se ci sono errori di validazione o 0 giorni.
        # =================================================================
        st.markdown("---")
        if _n_days_data > 0:
            try:
                import hashlib as _hashlib
                _payload = repr([
                    (str(_e.date), float(getattr(_e, "hours_per_day", 24.0)),
                     sorted((str(k), float(v)) for k, v in (_e.feedstocks or {}).items()),
                     float(getattr(_e, "remi_vb", 0.0)),
                     float(getattr(_e, "remi_e", 0.0)),
                     float(getattr(_e, "remi_qb_max", 0.0)),
                     float(getattr(_e, "remi_pci", 0.0)),
                     float(getattr(_e, "remi_rho", 0.0)))
                    for _e in _entries_list
                ]) + f"|{_regime_lbl}|{float(ghg_threshold):.4f}|{_do_plant_safe}"
                _payload_hash = _hashlib.md5(_payload.encode("utf-8")).hexdigest()
                _hash_key = f"_autosave_hash_{_do_plant_safe}_{int(_do_year)}_{int(_do_month)}"
                if st.session_state.get(_hash_key) != _payload_hash:
                    # Validazione silenziosa: salviamo solo se 0 errori
                    _has_validation_errs = False
                    for _e in _entries_list:
                        _ok, _, _ = _validate_daily(
                            _e.date, _e.feedstocks, allowed_feeds=list(FEED_NAMES))
                        if not _ok:
                            _has_validation_errs = True
                            break
                    if not _has_validation_errs:
                        _init_db()
                        _save_month(
                            int(_do_year), int(_do_month), _entries_list,
                            plant_id=_do_plant_safe, regime=_regime_lbl,
                            threshold=float(ghg_threshold),
                        )
                        st.session_state[_hash_key] = _payload_hash
                        from datetime import datetime as _dt_now
                        st.session_state[f"{_hash_key}_ts"] = _dt_now.now().strftime("%H:%M:%S")
                # Indicatore discreto
                _ts = st.session_state.get(f"{_hash_key}_ts")
                if _ts:
                    st.caption(f"💾 {_t('Auto-salvato')} {_ts}")
            except Exception as _exc:  # noqa: BLE001
                _LOG.exception("Auto-save daily failed")
                st.caption(f"⚠️ {_t('Auto-save non riuscito')}: {_exc}")

        # =================================================================
        # ESPORTA REPORT — sezione sempre visibile (bottoni disabilitati se
        # non ci sono giorni con dati > 0, così l'utente vede dove cliccare)
        # =================================================================
        st.markdown("**📥 " + _t("Esporta report") + "**")
        _disabled = (_n_days_data == 0)
        if _disabled:
            st.caption("ℹ️ " + _t("I bottoni si attivano dopo aver inserito almeno un giorno con biomassa > 0."))
        _daily_df_full = (
            _build_daily_df(_entries_list, _computed_list, feed_columns=_do_active_feeds)
            if not _disabled else pd.DataFrame()
        )
        _scol1, _scol2, _scol3 = st.columns(3)
        _fname_base = f"metaniq_{int(_do_year)}_{int(_do_month):02d}"
        with _scol1:
            try:
                st.download_button(
                    "⬇️ CSV",
                    _build_daily_csv(_daily_df_full) if not _disabled else b"",
                    file_name=f"{_fname_base}.csv",
                    mime="text/csv", key=f"{_key_prefix}do_btn_csv",
                    use_container_width=True, disabled=_disabled,
                )
            except Exception as _exc:  # noqa: BLE001
                _LOG.exception("Daily CSV export failed")
                st.warning(f"CSV: {_exc}")
        with _scol2:
            try:
                _xlsx_overrides = {
                    "bmt": dict(_EFFECTIVE_YIELDS),
                    "ef": dict(_EMISSION_OVERRIDES),
                }
                _xlsx_plant = {
                    "year": int(_do_year),
                    "month": int(_do_month),
                    "regime": _regime_lbl,
                    "threshold_pct": float(ghg_threshold),
                    "company": COMPANY_NAME or "—",
                    "plant_name": PLANT_NAME or "—",
                    "max_sm3h": _cap_smch,
                }
                st.download_button(
                    "⬇️ Excel",
                    _build_daily_xlsx(
                        _daily_df_full, _kpis, _audit,
                        kpis_standard=_kpis_standard if _has_any_override else None,
                        overrides_info=_xlsx_overrides,
                        plant_info=_xlsx_plant,
                    ) if not _disabled else b"",
                    file_name=f"{_fname_base}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"{_key_prefix}do_btn_xlsx",
                    use_container_width=True, disabled=_disabled,
                )
            except Exception as _exc:  # noqa: BLE001
                _LOG.exception("Daily XLSX export failed")
                st.warning(f"Excel: {_exc}")
        with _scol3:
            try:
                # Tentativo con lang= (versione i18n-aware). Fallback alla
                # firma vecchia se il modulo in cache non ha ancora il param
                # (Streamlit Cloud potrebbe servire una vecchia versione
                # mentre il deploy nuovo è in propagazione).
                if not _disabled:
                    try:
                        _pdf_bytes = _build_daily_pdf(
                            _daily_df_full, _kpis, _audit, _guidance,
                            lang=get_lang(),
                        )
                    except TypeError:
                        _pdf_bytes = _build_daily_pdf(
                            _daily_df_full, _kpis, _audit, _guidance,
                        )
                else:
                    _pdf_bytes = b""
                st.download_button(
                    "⬇️ PDF",
                    _pdf_bytes,
                    file_name=f"{_fname_base}.pdf",
                    mime="application/pdf", key=f"{_key_prefix}do_btn_pdf",
                    use_container_width=True, disabled=_disabled,
                )
            except Exception as _exc:  # noqa: BLE001
                _LOG.exception("Daily PDF export failed")
                st.warning(f"PDF: {_exc}")
    else:
        st.markdown("---")
        st.warning(
            _t("📅 Gestione Giornaliera non disponibile in questa build ") +
            f"({_DAILY_IMP_ERR if '_DAILY_IMP_ERR' in dir() else _t('moduli mancanti')})."
        )


tab_daily, tab_tech, tab_business = st.tabs([
    "📆 " + _t("Conduzione Giornaliera — Standard (UNI-TS / RED III)"),
    "🧪 " + _t("Conduzione Giornaliera — Analisi (BMT & Fattori Emissivi su misura)"),
    "📊 " + _t("Risultati, Incentivi & Business Plan"),
])

with tab_tech:
    # ============================================================
    # BMT OVERRIDE — Resa certificata laboratorio (per biomassa)
    # ============================================================
    # Per ogni biomassa attiva, l'utente puo' attivare un override
    # della resa standard tabellare con una resa BMT certificata
    # da laboratorio. Vincoli:
    #   - certificato OBBLIGATORIO (PDF/JPG/PNG/XLSX/CSV)
    #   - valore BMT > 0
    #   - laboratorio, data, riferimento campione obbligatori
    #   - warning se scostamento dal valore standard > +/-30%
    # La tabella standard NON viene mai modificata: l'override
    # e' tracciato solo per la singola biomassa.
    if "bmt_overrides" not in st.session_state:
        st.session_state["bmt_overrides"] = {}

    with st.expander(
        _t("🧪 Override resa BMT certificata (opzionale, per biomassa)"),
        expanded=False,
    ):
        st.caption(_t(
            "Per ciascuna biomassa attiva puoi sostituire la resa standard "
            "(tabella interna UNI-TS / JEC v5) con una resa BMT certificata "
            "da laboratorio. Il certificato e' OBBLIGATORIO: senza file "
            "caricato l'override non viene applicato e viene mostrato un "
            "errore. La resa BMT vale SOLO per la biomassa selezionata; "
            "le altre continuano a usare la tabella standard. Lo scostamento "
            f"oltre il +/-{int(BMT_DEVIATION_WARN_THRESHOLD*100)}% rispetto "
            "alla tabella standard genera un warning di verifica."
        ))

        # Cleanup: rimuovi override per biomasse non piu' attive
        for _stale in list(st.session_state["bmt_overrides"].keys()):
            if _stale not in active_feeds:
                st.session_state["bmt_overrides"].pop(_stale, None)

        for _bmt_name in active_feeds:
            _std_y = float(FEEDSTOCK_DB[_bmt_name]["yield"])
            _key_active = f"bmt_active__{_bmt_name}"
            _key_value  = f"bmt_value__{_bmt_name}"
            _key_lab    = f"bmt_lab__{_bmt_name}"
            _key_date   = f"bmt_date__{_bmt_name}"
            _key_sample = f"bmt_sample__{_bmt_name}"
            _key_cert   = f"bmt_cert__{_bmt_name}"

            _bmt_active = st.checkbox(
                f"🧪 {_bmt_name}  ·  {_t('attiva BMT certificato')} "
                f"({_t('standard')} {fmt_it(_std_y, 0)} Nm³/t)",
                key=_key_active,
                value=st.session_state.get(_key_active, False),
                help=_t("Se attivata, la resa standard") + f" {fmt_it(_std_y, 0)} Nm³/t " + _t("verra' sostituita dal valore BMT certificato per") + f" **{_bmt_name}**. " + _t("Il certificato e' obbligatorio."),
            )

            if not _bmt_active:
                # Rimuovi eventuale override precedente
                st.session_state["bmt_overrides"].pop(_bmt_name, None)
                continue

            with st.container():
                _bmt_col1, _bmt_col2 = st.columns([1, 1])
                with _bmt_col1:
                    _bmt_value = st.number_input(
                        f"{_t('Resa BMT')} [{BMT_YIELD_UNIT}]",
                        min_value=0.0, max_value=2000.0,
                        value=float(st.session_state.get(
                            _key_value, _std_y)),
                        step=1.0, key=_key_value,
                        help=_t("Resa misurata da test BMT in laboratorio (unita': ") + f"{BMT_YIELD_UNIT}" + _t("). Deve essere > 0."),
                    )
                    _bmt_lab = st.text_input(
                        _t("Laboratorio"),
                        value=st.session_state.get(_key_lab, ""),
                        key=_key_lab,
                        help=_t("Nome/ragione sociale del laboratorio emittente."),
                    )
                with _bmt_col2:
                    _bmt_date = st.text_input(
                        _t("Data certificato (YYYY-MM-DD)"),
                        value=st.session_state.get(_key_date, ""),
                        key=_key_date,
                        help=_t("Data di emissione del rapporto di prova."),
                    )
                    _bmt_sample = st.text_input(
                        _t("Riferimento campione"),
                        value=st.session_state.get(_key_sample, ""),
                        key=_key_sample,
                        help=_t("Numero rapporto di prova / ID campione."),
                    )

                _cert_uploaded = True
                _cert_name = ""
                _cert_size = 0

                _bmt_valid, _bmt_errs, _bmt_warns = validate_bmt_override(
                    bmt_value=_bmt_value,
                    standard_yield=_std_y,
                    certificate_uploaded=_cert_uploaded,
                    lab_name=_bmt_lab,
                    cert_date=_bmt_date,
                    sample_ref=_bmt_sample,
                    cert_filename=_cert_name,
                )

                for _e in _bmt_errs:
                    st.error(f"❌ {_e}")
                for _w in _bmt_warns:
                    st.warning(f"⚠️ {_w}")

                if _bmt_valid:
                    _cert_obj = BMTCertificate(
                        biomass_name=_bmt_name,
                        bmt_value=float(_bmt_value),
                        lab_name=_bmt_lab.strip(),
                        cert_date=_bmt_date.strip(),
                        sample_ref=_bmt_sample.strip(),
                        cert_filename=_cert_name,
                        cert_size_bytes=int(_cert_size),
                    )
                    st.session_state["bmt_overrides"][_bmt_name] = {
                        "active": True,
                        "certificate": _cert_obj,
                    }
                    st.success(
                        f"✅ Override BMT attivo per **{_bmt_name}**: "
                        f"{fmt_it(_bmt_value, 1)} {BMT_YIELD_UNIT} "
                        f"(Lab: {_bmt_lab} · Cert: {_cert_name})"
                    )
                else:
                    # Rimuovi qualsiasi override precedente per coerenza
                    st.session_state["bmt_overrides"].pop(_bmt_name, None)
                    st.error(
                        f"⛔ Override BMT NON applicato per **{_bmt_name}**: "
                        f"resa standard {fmt_it(_std_y, 0)} Nm³/t in uso."
                    )

                st.markdown("---")

    if "dry_matter_overrides" not in st.session_state:
        st.session_state["dry_matter_overrides"] = {}

    with st.expander(
        "🌾 " + _t("Ponderazione Umidità / Sostanza Secca (UNI/TS 11567:2024)"),
        expanded=False,
    ):
        st.caption(_t(
            "La specifica tecnica UNI/TS 11567:2024 richiede di normalizzare il peso delle "
            "biomasse in ingresso in base alla sostanza secca reale rispetto al valore standard "
            "(Prospetto A.1). Abilita questa opzione se disponi di misure di laboratorio reali "
            "per calcolare correttamente il coefficiente Wn per la codigestione."
        ))

        # Cleanup: rimuovi override per biomasse non piu' attive
        for _stale in list(st.session_state["dry_matter_overrides"].keys()):
            if _stale not in active_feeds:
                st.session_state["dry_matter_overrides"].pop(_stale, None)

        for _dm_name in active_feeds:
            _std_dm = float(FEEDSTOCK_DB[_dm_name].get("dry_matter_std", 1.0))
            _key_dm_active = f"dm_active__{_dm_name}"
            _key_dm_value  = f"dm_value__{_dm_name}"

            _dm_active = st.checkbox(
                f"🌾 {_dm_name}  ·  {_t('inserisci sostanza secca reale')} "
                f"({_t('standard')} {fmt_it(_std_dm * 100, 1)}% ST)",
                key=_key_dm_active,
                value=st.session_state.get(_key_dm_active, False),
                help=_t("Se attiva, normalizza la biomassa immessa usando il rapporto tra sostanza secca reale e standard."),
            )

            if _dm_active:
                _dm_val = st.number_input(
                    f"{_t('Sostanza Secca Reale (ST %)')} - {_dm_name}",
                    min_value=1.0, max_value=100.0,
                    value=float(st.session_state.get(_key_dm_value, _std_dm * 100.0)),
                    step=0.5, key=_key_dm_value,
                    help=_t("Inserisci la percentuale di sostanza secca reale. La resa verrà moltiplicata per ST_reale / ST_standard."),
                )
                st.session_state["dry_matter_overrides"][_dm_name] = _dm_val / 100.0
            else:
                st.session_state["dry_matter_overrides"].pop(_dm_name, None)

            st.markdown("---")

    # ============================================================
    # Popola _EFFECTIVE_YIELDS in base agli override validati
    # ============================================================
    _EFFECTIVE_YIELDS.clear()
    _yield_audit_rows: list[dict] = []
    for _bn in active_feeds:
        _resolved = resolve_biomass_yield(
            _bn,
            float(FEEDSTOCK_DB[_bn]["yield"]),
            st.session_state["bmt_overrides"],
        )
        if _resolved["override_active"]:
            _EFFECTIVE_YIELDS[_bn] = float(_resolved["yield_used"])
        _yield_audit_rows.append(build_yield_audit_row(_resolved))

    # ============================================================
    # Popola _EFFECTIVE_DRY_MATTERS in base alla sostanza secca reale
    # ============================================================
    _EFFECTIVE_DRY_MATTERS.clear()
    for _bn in active_feeds:
        if st.session_state.get(f"dm_active__{_bn}", False):
            _val = st.session_state.get(f"dm_value__{_bn}")
            if _val is not None:
                _EFFECTIVE_DRY_MATTERS[_bn] = float(_val) / 100.0

    # Mini-banner riepilogo override attivi
    _n_active = sum(1 for r in _yield_audit_rows if r["Origine resa"] == SOURCE_BMT)
    if _n_active > 0:
        st.info(
            f"🧪 **{_n_active}** override BMT attivi su **{len(active_feeds)}** "
            f"biomasse. Le rese effettive sono usate in tutti i calcoli, "
            f"tabelle e export (CSV / Excel / PDF) con tracciabilita' "
            f"completa di laboratorio, certificato, data e campione."
        )

    # ============================================================
    # FATTORI EMISSIVI REALI — Override da relazione tecnica
    # ============================================================
    # Per ogni biomassa l'utente puo' attivare un override dei fattori
    # emissivi standard (eec, esca, etd, ep + crediti extra) usando i
    # valori dichiarati in una RELAZIONE TECNICA dell'impianto. Vincoli:
    #   - relazione tecnica OBBLIGATORIA (PDF/DOCX/XLSX/CSV/JPG/PNG)
    #   - tutti i fattori numerici, finiti, segno corretto
    #   - metadati relazione obbligatori (titolo, autore, societa',
    #     data, impianto, riferimento campione)
    #   - warning se uno qualsiasi dei fattori scosta >+/-30%
    # La tabella standard NON viene mai modificata. L'override e'
    # tracciato solo per la singola biomassa.
    if "emission_factor_overrides" not in st.session_state:
        st.session_state["emission_factor_overrides"] = {}

    with st.expander(
        _t("🧬 Fattori emissivi reali da relazione tecnica (opzionale)"),
        expanded=False,
    ):
        st.caption(
            "Per ciascuna biomassa attiva puoi sostituire i fattori emissivi "
            "standard tabellari (eec / esca / etd / ep) con i valori REALI "
            "dichiarati nella relazione tecnica dell'impianto. La relazione "
            "e' OBBLIGATORIA: senza file caricato l'override non viene "
            "applicato e viene mostrato un errore. I valori reali si "
            "applicano SOLO alla biomassa selezionata. Soglia warning di "
            f"scostamento: +/-{int(EMISSION_DEVIATION_WARN_THRESHOLD*100)}%. "
            f"Formula coerente: e_total = eec + etd + ep - esca - crediti_extra."
        )

        # Cleanup: rimuovi override per biomasse non piu' attive
        for _stale in list(st.session_state["emission_factor_overrides"].keys()):
            if _stale not in active_feeds:
                st.session_state["emission_factor_overrides"].pop(_stale, None)

        for _ef_name in active_feeds:
            _d_std = FEEDSTOCK_DB[_ef_name]
            _eec_std = float(_d_std["eec"])
            _esca_std = float(_d_std["esca"])
            _etd_std = float(_d_std["etd"])

            _key_active  = f"ef_active__{_ef_name}"
            _key_eec     = f"ef_eec__{_ef_name}"
            _key_esca    = f"ef_esca__{_ef_name}"
            _key_etd     = f"ef_etd__{_ef_name}"
            _key_ep      = f"ef_ep__{_ef_name}"
            _key_extra   = f"ef_extra__{_ef_name}"
            _key_title   = f"ef_title__{_ef_name}"
            _key_author  = f"ef_author__{_ef_name}"
            _key_company = f"ef_company__{_ef_name}"
            _key_date    = f"ef_date__{_ef_name}"
            _key_plant   = f"ef_plant__{_ef_name}"
            _key_sample  = f"ef_sample__{_ef_name}"
            _key_notes   = f"ef_notes__{_ef_name}"
            _key_report  = f"ef_report__{_ef_name}"

            _ef_active = st.checkbox(
                f"🧬 {_ef_name}  ·  {_t('usa fattori emissivi reali da relazione')} "
                f"(std: eec={fmt_it(_eec_std, 1, signed=True)}, "
                f"esca={fmt_it(_esca_std, 1)}, etd={fmt_it(_etd_std, 1)} {EMISSION_UNIT})",
                key=_key_active,
                value=st.session_state.get(_key_active, False),
                help=_t("Se attivata, i fattori emissivi standard di ") + f"**{_ef_name}**" + _t(" saranno sostituiti dai valori dichiarati nella relazione tecnica dell'impianto. La relazione tecnica e' obbligatoria."),
            )

            if not _ef_active:
                st.session_state["emission_factor_overrides"].pop(_ef_name, None)
                continue

            with st.container():
                _ef_c1, _ef_c2 = st.columns([1, 1])
                with _ef_c1:
                    _ef_eec = st.number_input(
                        f"{_t('eec reale')} [{EMISSION_UNIT}]",
                        min_value=-200.0, max_value=300.0,
                        value=float(st.session_state.get(_key_eec, _eec_std)),
                        step=0.1, format="%.2f", key=_key_eec,
                        help=_t("Emissioni eec dichiarate nella relazione tecnica. Puo' essere negativo (manure credit gia' incorporato)."),
                    )
                    _ef_esca = st.number_input(
                        f"{_t('esca reale')} [{EMISSION_UNIT}] {_t('(credito, positivo)')}",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_esca, _esca_std)),
                        step=0.1, format="%.2f", key=_key_esca,
                        help=_t("Credito esca: dichiarato come valore positivo, sottratto da e_total."),
                    )
                    _ef_etd = st.number_input(
                        f"{_t('etd reale')} [{EMISSION_UNIT}]",
                        min_value=0.0, max_value=50.0,
                        value=float(st.session_state.get(_key_etd, _etd_std)),
                        step=0.1, format="%.2f", key=_key_etd,
                    )
                with _ef_c2:
                    _ef_ep = st.number_input(
                        f"{_t('ep reale')} [{EMISSION_UNIT}] {_t('(per-biomassa)')}",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_ep, 0.0)),
                        step=0.1, format="%.2f", key=_key_ep,
                        help=_t("Emissioni di processo dichiarate nella relazione (sostituisce l'ep impianto-wide per questa biomassa)."),
                    )
                    _ef_extra = st.number_input(
                        f"{_t('Crediti emissivi extra')} [{EMISSION_UNIT}]",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_extra, 0.0)),
                        step=0.1, format="%.2f", key=_key_extra,
                        help=_t("Crediti AGGIUNTIVI dichiarati nella relazione (NON gia' inclusi in esca). Default 0. NON sottrarre due volte la stessa voce."),
                    )

                _ef_t1, _ef_t2 = st.columns([1, 1])
                with _ef_t1:
                    _ef_title = st.text_input(
                        _t("Titolo relazione"),
                        value=st.session_state.get(_key_title, ""),
                        key=_key_title,
                    )
                    _ef_author = st.text_input(
                        _t("Autore / tecnico redattore"),
                        value=st.session_state.get(_key_author, ""),
                        key=_key_author,
                    )
                    _ef_company = st.text_input(
                        _t("Societa' / studio tecnico"),
                        value=st.session_state.get(_key_company, ""),
                        key=_key_company,
                    )
                    _ef_date = st.text_input(
                        _t("Data relazione (YYYY-MM-DD)"),
                        value=st.session_state.get(_key_date, ""),
                        key=_key_date,
                    )
                with _ef_t2:
                    _ef_plant = st.text_input(
                        _t("Impianto di riferimento"),
                        value=st.session_state.get(_key_plant, ""),
                        key=_key_plant,
                    )
                    _ef_sample = st.text_input(
                        _t("Riferimento campione / lotto"),
                        value=st.session_state.get(_key_sample, ""),
                        key=_key_sample,
                    )
                    _ef_notes = st.text_area(
                        _t("Note metodologiche (opzionale)"),
                        value=st.session_state.get(_key_notes, ""),
                        key=_key_notes, height=68,
                        help="Metodo dichiarato nella relazione: es. RED III All. V Parte C, JEC v5, ISCC, REDcert, ecc.",
                    )

                _r_uploaded = True
                _r_name = ""
                _r_size = 0

                # NB: standard_factors NON include 'ep' perche' ep_total
                # impianto-wide non e' ancora computato in sidebar; il
                # warning di scostamento per ep verrebbe spurio. Il check
                # del range plausibilita' su ep_real resta attivo.
                _ef_valid, _ef_errs, _ef_warns = validate_real_emission_factor_override(
                    biomass_name=_ef_name,
                    eec_real=_ef_eec, esca_real=_ef_esca,
                    etd_real=_ef_etd, ep_real=_ef_ep,
                    extra_credits_real=_ef_extra,
                    standard_factors={"eec": _eec_std, "esca": _esca_std,
                                       "etd": _etd_std},
                    report_uploaded=_r_uploaded,
                    report_filename=_r_name,
                    report_title=_ef_title,
                    author_name=_ef_author,
                    company_name=_ef_company,
                    report_date=_ef_date,
                    plant_reference=_ef_plant,
                    sample_lot_ref=_ef_sample,
                    methodology_notes=_ef_notes,
                )

                for _e in _ef_errs:
                    st.error(f"❌ {_e}")
                for _w in _ef_warns:
                    st.warning(f"⚠️ {_w}")

                if _ef_valid:
                    _ef_report_obj = EmissionFactorReport(
                        biomass_name=_ef_name,
                        eec_real=float(_ef_eec),
                        esca_real=float(_ef_esca),
                        etd_real=float(_ef_etd),
                        ep_real=float(_ef_ep),
                        extra_credits_real=float(_ef_extra),
                        report_title=_ef_title.strip(),
                        author_name=_ef_author.strip(),
                        company_name=_ef_company.strip(),
                        report_date=_ef_date.strip(),
                        plant_reference=_ef_plant.strip(),
                        sample_lot_ref=_ef_sample.strip(),
                        methodology_notes=_ef_notes.strip(),
                        report_filename=_r_name,
                        report_size_bytes=int(_r_size),
                        unit=EMISSION_UNIT,
                    )
                    st.session_state["emission_factor_overrides"][_ef_name] = {
                        "active": True, "report": _ef_report_obj,
                    }
                    _e_t = calculate_emission_total(
                        _ef_eec, _ef_esca, _ef_etd, _ef_ep, _ef_extra)
                    st.success(
                        f"✅ Override fattori reali ATTIVO per **{_ef_name}** "
                        f"·  e_total = {fmt_it(_e_t, 2)} {EMISSION_UNIT} "
                        f"·  Relazione: {_r_name} ({_ef_company} / {_ef_date})"
                    )
                else:
                    st.session_state["emission_factor_overrides"].pop(_ef_name, None)
                    st.error(
                        f"⛔ Override fattori reali NON applicato per **{_ef_name}**: "
                        f"valori standard restano in uso "
                        f"(eec={fmt_it(_eec_std, 1, signed=True)} {EMISSION_UNIT})."
                    )
                st.markdown("---")

    # ============================================================
    # Popola _EMISSION_OVERRIDES da session_state per i calcoli
    # ============================================================
    _EMISSION_OVERRIDES.clear()
    _emission_audit_rows: list[dict] = []
    for _ef_n in active_feeds:
        _std_d = FEEDSTOCK_DB[_ef_n]
        _std_factors = {
            "eec":  float(_std_d["eec"]),
            "esca": float(_std_d["esca"]),
            "etd":  float(_std_d["etd"]),
            "ep":   0.0,  # ep impianto-wide aggiunto in fase di audit display
        }
        _resolved = resolve_emission_factors(
            _ef_n, _std_factors, ep_default=0.0,
            overrides=st.session_state["emission_factor_overrides"],
        )
        if _resolved["override_active"]:
            _EMISSION_OVERRIDES[_ef_n] = {
                "eec":   _resolved["eec_used"],
                "esca":  _resolved["esca_used"],
                "etd":   _resolved["etd_used"],
                "ep":    _resolved["ep_used"],
                "extra": _resolved["extra_credits_used"],
                "source": _resolved["source"],
            }
        _emission_audit_rows.append(
            build_emission_factor_audit_row(_resolved)
        )

    _ef_n_active = sum(
        1 for r in _emission_audit_rows
        if r["Origine fattori"] == EF_SOURCE_REAL
    )
    if _ef_n_active > 0:
        st.info(
            f"🧬 **{_ef_n_active}** override fattori emissivi reali attivi su "
            f"**{len(active_feeds)}** biomasse. I fattori reali sostituiscono "
            f"quelli standard SOLO per le biomasse indicate; tutti i calcoli "
            f"(saving GHG, e_total, validita') e tutti gli export (CSV / "
            f"Excel / PDF) usano i valori reali con tracciabilita' completa "
            f"(titolo relazione, autore, societa', data, impianto, campione)."
        )

    st.divider()
    st.header(_t("🏭 Configurazione impianto (ep)"))
    st.caption(_t("I parametri impiantistici concorrono a `ep` (processing), che incide direttamente sul saving GHG ex RED III."))

    # Destinazione d'uso -> soglia GHG saving (DM 15/9/2022 / RED III)
    end_use = st.selectbox(
        "🎯 " + _t("Destinazione biometano (→ soglia saving + comparator)"),
        list(END_USE_THRESHOLDS.keys()),
        index=0,
        help=_t("RED III + D.Lgs. 5/2026: 80% per elettricita'/calore (impianto nuovo ≥20/11/2023), 70% per esistenti <10 MW primi 15 anni, 65% per trasporti. Il comparator fossile (80 per rete/calore, 94 per trasporti) viene aggiornato di conseguenza."),
    )
    ghg_threshold = END_USE_THRESHOLDS[end_use]
    FOSSIL_COMPARATOR = COMPARATOR_BY_END_USE[end_use]
    st.caption(
        f"📐 Comparator fossile RED III: **{fmt_it(FOSSIL_COMPARATOR, 0)} "
        f"gCO₂/MJ** "
        + ("(gas naturale sostituito)" if FOSSIL_COMPARATOR == 80.0
           else "(diesel sostituito)")
    )
    target_saving = ghg_threshold + 0.01  # +1 pp margine sicurezza
    target_e_max = FOSSIL_COMPARATOR * (1 - target_saving)
    max_allowed_e = FOSSIL_COMPARATOR * (1 - ghg_threshold)
    st.metric(
        _t("Soglia saving obbligatoria"),
        fmt_it(ghg_threshold * 100, 0, "%"),
        delta=f"{_t('target solver')} {fmt_it(target_saving * 100, 0, '%')}",
        help=_t("Soglia minima di riduzione delle emissioni GHG rispetto al comparatore fossile (RED III). Il target solver include un margine di sicurezza di +1% per evitare oscillazioni."),
    )

    # =================================================================
    # TABELLA GIORNALIERA — modalità ANALISI.
    # SEMPRE VISIBILE (anche senza override) ma con dati INDIPENDENTI dal tab
    # Standard (session_state e DB isolati tramite plant_id suffix "__tech",
    # vedi _render_daily_ops_panel a riga 2292). L'utente la compila quando
    # ha i certificati (BMT lab e/o EF su misura).
    # =================================================================
    _tech_has_bmt = bool(_EFFECTIVE_YIELDS)
    _tech_has_ef = bool(_EMISSION_OVERRIDES)
    _tech_has_any = _tech_has_bmt or _tech_has_ef

    st.markdown("---")
    if _tech_has_any:
        _tech_badges = []
        if _tech_has_bmt:
            _tech_badges.append(f"🧪 {len(_EFFECTIVE_YIELDS)} BMT lab")
        if _tech_has_ef:
            _tech_badges.append(f"🧬 {len(_EMISSION_OVERRIDES)} EF su misura")
        st.success(
            "✅ " + _t("Modalità Analisi attiva") + " · " + " · ".join(_tech_badges)
            + " — " + _t("override applicati sopra i valori tabellari standard.")
        )
    else:
        st.info(
            "ℹ️ " + _t(
                "Nessun override caricato: la tabella sotto calcola comunque "
                "usando i valori **STANDARD tabellari** (UNI-TS / RED III). "
                "Quando carichi BMT lab o Fattori Emissivi su misura nelle "
                "sezioni qui sopra, quei valori sostituiscono i tabellari "
                "biomassa per biomassa."
            )
        )
    st.caption(_t(
        "📋 Dati giornalieri (biomasse, ore, REMI) indipendenti dal tab Standard. "
        "Conformità DM 2022 verificata sul totale mensile."
    ))
    _render_daily_ops_panel(_key_prefix="tech_")

with tab_business:
    # ============================================================
    # PRO FORMA / BUSINESS PLAN — DM 2022
    # ============================================================
    # Defaults derivati da benchmark impianto medio biometano agricolo
    # (250 Smc/h, costi medi settore 2024), ricalibrati al 2026 con
    # inflazione ISTAT cumulata e tassi BCE.
    # ============================================================
    st.divider()
    st.header(_t("🧬 DM 2022 — Configurazione Impianto & Incentivi"))

    # ── 1. TIPOLOGIA IMPIANTO ──────────────────────────────────────────
    st.subheader("🏭 " + _t("Tipologia impianto"))
    st.caption(_t(
        "La tipologia determina la **tariffa di riferimento** base a cui si partecipa all'asta GSE. "
        "Nuova costruzione e ampliamento hanno la tariffa più alta; "
        "riconversione parziale la più bassa (impianto CHP esistente che dedica parte del biogas a biometano)."
    ))

    bp_plant_type = st.selectbox(
        _t("Tipo di intervento"),
        options=list(BP_PLANT_TYPES.keys()),
        index=list(BP_PLANT_TYPES.keys()).index(BP_PLANT_TYPE_DEFAULT),
        format_func=lambda x: BP_PLANT_TYPES[x]["label"],
        help=_t(
            "• **Nuova costruzione**: impianto ex-novo\n"
            "• **Riconversione totale**: ex-biogas CHP convertito interamente a biometano\n"
            "• **Riconversione parziale**: parte del biogas resta al CHP, parte va all'upgrading\n"
            "• **Ampliamento**: incremento capacità su impianto esistente"
        ),
        key="bp_plant_type",
    )

    # ── 2. DESTINAZIONE D'USO ─────────────────────────────────────────
    st.subheader("🎯 " + _t("Destinazione d'uso biometano"))
    st.caption(_t(
        "La destinazione d'uso determina la **soglia GHG saving** richiesta (RED III) "
        "e il comparator fossile. Non cambia la tariffa base ma può aprire accesso a mercati diversi."
    ))

    bp_dest_use = st.selectbox(
        _t("Destinazione finale"),
        options=list(BP_DEST_USE.keys()),
        index=0,
        help=_t(
            "• **Rete gas / industria / calore**: saving ≥ 80%, comparator 80 gCO₂/MJ\n"
            "• **Trasporti (Bio-CNG/Bio-GNL)**: saving ≥ 65%, comparator 94 gCO₂/MJ — mercato premium\n"
            "• **Uso termico residenziale/terziario**: saving ≥ 80%, comparator 80 gCO₂/MJ"
        ),
        key="bp_dest_use",
    )
    _dest_info = BP_DEST_USE[bp_dest_use]
    st.info(
        f"📋 **Soglia GHG saving RED III**: ≥ {fmt_it(_dest_info['ghg_thr']*100, 0, '%')} · "
        f"**Comparator fossile**: {fmt_it(_dest_info['cmp'], 0)} gCO₂/MJ"
    )

    # ── 3. FASCIA PRODUTTIVA & MECCANISMO TARIFFA ─────────────────────
    st.subheader("⚡ " + _t("Fascia produttiva & meccanismo tariffa"))

    _fascia = "fascia_a" if plant_net_smch <= BP_SOGLIA_FASCIA_SMCH else "fascia_b"
    _fascia_label = (
        f"🅰 Fascia A (≤ {fmt_it(BP_SOGLIA_FASCIA_SMCH, 0)} Smc/h)"
        if _fascia == "fascia_a"
        else f"🅱 Fascia B (> {fmt_it(BP_SOGLIA_FASCIA_SMCH, 0)} Smc/h)"
    )
    st.markdown(
        f"**Taglia impianto**: {fmt_it(plant_net_smch, 0)} Smc/h → "
        f"**{_fascia_label}**"
    )

    # Meccanismo tariffa (TO obbligatorio solo ≤250 con rete obbligo terzi)
    if _fascia == "fascia_a":
        _mecca_opts = [BP_MECCA_TO, BP_MECCA_TP]
        _mecca_default = 0
    else:
        _mecca_opts = [BP_MECCA_TP]
        _mecca_default = 0

    bp_mecca = st.radio(
        _t("Meccanismo tariffa"),
        options=_mecca_opts,
        index=_mecca_default,
        horizontal=True,
        help=_t(
            "• **TO (Omnicomprensiva)**: GSE ritira il biometano e le GO — disponibile solo ≤ 250 Smc/h in rete con obbligo di connessione terzi. Incasso garantito.\n"
            "• **TP (Premio)**: il produttore vende il gas sul mercato autonomamente; l'incentivo = TR_aggiudicata − (prezzo_gas_PSV + valore_GO). Più flessibile ma esposto al mercato."
        ),
        key="bp_mecca",
    )

    if bp_mecca == BP_MECCA_TP:
        _col_g, _col_go = st.columns(2)
        with _col_g:
            bp_prezzo_gas = st.number_input(
                _t("Prezzo gas PSV [€/MWh]"),
                min_value=0.0, max_value=200.0,
                value=BP_PREZZO_GAS_DEFAULT, step=1.0,
                help=_t("Prezzo medio mensile gas naturale sul PSV (mercato italiano). Usato per calcolo Tariffa Premio netta."),
                key="bp_prezzo_gas",
            )
        with _col_go:
            bp_prezzo_go = st.number_input(
                _t("Valore GO biometano [€/MWh]"),
                min_value=0.0, max_value=30.0,
                value=BP_PREZZO_GO_DEFAULT, step=0.5,
                help=_t("Valore medio Garanzie di Origine biometano sul mercato. Incluso nella TR netta per la Tariffa Premio."),
                key="bp_prezzo_go",
            )
    else:
        bp_prezzo_gas = BP_PREZZO_GAS_DEFAULT
        bp_prezzo_go  = BP_PREZZO_GO_DEFAULT

    # ── 4. TARIFFA BASE + RIBASSO ──────────────────────────────────────
    st.subheader("💰 " + _t("Tariffa di riferimento & ribasso d'asta"))

    _tr_auto = BP_TARIFFE_REF[bp_plant_type][_fascia]
    st.caption(
        f"📐 **TR normativa** ({BP_PLANT_TYPES[bp_plant_type]['label']} · {_fascia_label}): "
        f"**{fmt_it(_tr_auto, 1)} €/MWh** "
        f"(fonte: DM 15/9/2022 + adeguamento ISTAT 4° bando PNRR)"
    )

    bp_tariffa_eur_mwh = st.number_input(
        _t("Tariffa di riferimento [€/MWh] — modificabile"),
        min_value=50.0, max_value=300.0,
        value=float(_tr_auto), step=0.5,
        help=_t(
            "Valore normativo pre-calcolato in base alla tipologia e alla fascia produttiva. "
            "Modificalo se hai ricevuto una TR diversa dal GSE o per scenari what-if."
        ),
        key="bp_tariffa_base_input",
    )
    bp_ribasso_pct = st.slider(
        _t("Ribasso d'asta [%]"),
        min_value=0.0, max_value=30.0,
        value=BP_RIBASSO_DEFAULT_PCT, step=0.5,
        help=_t("Ribasso offerto in fase di asta GSE. Tariffa aggiudicata = TR × (1 − ribasso/100)."),
        key="bp_ribasso",
    )
    _tr_aggiudicata = bp_tariffa_eur_mwh * (1.0 - bp_ribasso_pct / 100.0)

    # ── 5. PREMI CUMULABILI ────────────────────────────────────────────
    st.subheader("🏆 " + _t("Premi cumulabili"))
    st.caption(_t(
        "⚠️ **Importante**: i valori €/MWh qui sotto NON sono quote fisse "
        "previste dal DM 15/9/2022, ma **stime indicative** del beneficio "
        "economico aggiuntivo ottenibile per due categorie di impianto: "
        "(1) biometano **avanzato** (matrici Allegato IX RED III) con accesso "
        "al mercato CIC, (2) upgrading con tecnologie qualificate "
        "(maggior saving GHG → premi indiretti). "
        "Personalizza i valori in base al tuo contratto specifico, all'andamento "
        "del mercato CIC e ai requisiti del bando GSE di riferimento."
    ))

    _col_pm, _col_pu = st.columns(2)
    with _col_pm:
        bp_premio_matrice_on = st.checkbox(
            f"🌿 {_t('Premio matrice avanzata')} (+{fmt_it(BP_PREMIO_MATRICE_DEFAULT, 0)} €/MWh)",
            value=True,
            help=_t(
                "Stima del beneficio economico aggiuntivo per impianti che operano "
                "in modalità **biometano avanzato** (> 70% in massa di feedstock "
                "Annex IX RED III: sottoprodotti agricoli, effluenti zootecnici, "
                "FORSU, ecc.). Il beneficio reale dipende dal contratto specifico "
                "e dal valore di mercato dei CIC (Certificati di Immissione in "
                "Consumo) per il settore trasporti — variabile tipicamente "
                "60-120 €/CIC. NON è una quota fissa garantita dal DM 2022. "
                "La quota Annex IX viene verificata nel tab «🥧 Mix annuale»."
            ),
            key="bp_pm_on",
        )
        bp_premio_matrice_eur = st.number_input(
            _t("Valore premio matrice [€/MWh]"),
            min_value=0.0, max_value=30.0,
            value=BP_PREMIO_MATRICE_DEFAULT, step=0.5,
            key="bp_pm_val",
            disabled=not bp_premio_matrice_on,
            help=_t("Inserisci il valore stimato del premio matrice avanzata (€/MWh). Questo valore si somma alla tariffa di riferimento.")
        )

    with _col_pu:
        # Premio upgrading: attivo se tecnologia è membrane o amminico
        _upg_opt = st.session_state.get("upgrading_opt_saved", "")
        _upg_premio_auto = any(t in _upg_opt for t in BP_PREMIO_UPGRADING_TECNO)
        bp_premio_upg_on = st.checkbox(
            f"⚙️ {_t('Premio upgrading qualificato')} (+{fmt_it(BP_PREMIO_UPGRADING_DEFAULT, 0)} €/MWh)",
            value=_upg_premio_auto,
            help=_t(
                "Stima del beneficio economico INDIRETTO per impianti con "
                "tecnologie upgrading qualificate (membrane o amminico chimico, "
                "slip CH₄ < 1%, EP_upgrading ≤ 5 gCO₂/MJ). Il valore non è "
                "una quota normativa del DM 2022 ma una stima del maggior "
                "saving GHG → maggior valore del biometano sul mercato "
                "trasporti (CIC) → premio implicito nel prezzo medio di "
                "vendita. Rilevato automaticamente dalla configurazione "
                "upgrading in Config. Tecnica."
            ) + (f" [{'✅ auto' if _upg_premio_auto else '⚠️ verifica in Config. Tecnica'}]",)[0],
            key="bp_pu_on",
        )
        bp_premio_upg_eur = st.number_input(
            _t("Valore premio upgrading [€/MWh]"),
            min_value=0.0, max_value=20.0,
            value=BP_PREMIO_UPGRADING_DEFAULT, step=0.5,
            key="bp_pu_val",
            disabled=not bp_premio_upg_on,
            help=_t("Inserisci il valore stimato del premio upgrading qualificato (€/MWh). Questo valore si somma alla tariffa di riferimento.")
        )

    # Premio PNRR conto capitale
    st.markdown("---")
    bp_pnrr_pct = st.number_input(
        "🇪🇺 " + _t("Contributo PNRR conto capitale [%]"),
        min_value=0.0, max_value=65.0,
        value=BP_PNRR_QUOTA_PCT_DEFAULT, step=1.0,
        help=_t(
            f"Quota contributo a fondo perduto su CAPEX ammissibile (cap massimale GSE "
            f"{fmt_it(BP_MASSIMALE_SPESA_EUR_PER_SMCH, 0)} €/Smc/h). "
            "Default 40% (M2C2 PNRR). Aumenta a 50-60% per aree del Sud (ZES/deroghe regionali)."
        ),
        key="bp_pnrr",
    )

    # ── RIEPILOGO TARIFFA ──────────────────────────────────────────────
    _tot_premi = (
        (bp_premio_matrice_eur if bp_premio_matrice_on else 0.0)
        + (bp_premio_upg_eur   if bp_premio_upg_on   else 0.0)
    )
    _tariffa_lorda = _tr_aggiudicata + _tot_premi

    if bp_mecca == BP_MECCA_TP:
        _tariffa_netta_tp = _tariffa_lorda - bp_prezzo_gas - bp_prezzo_go
        _recap_line = (
            f"**TR aggiudicata** {fmt_it(_tr_aggiudicata, 1)} + "
            f"**Premi** {fmt_it(_tot_premi, 1)} = "
            f"**{fmt_it(_tariffa_lorda, 1)} €/MWh lorda** → "
            f"TP netta = {fmt_it(_tariffa_lorda, 1)} − {fmt_it(bp_prezzo_gas, 1)} (gas) − "
            f"{fmt_it(bp_prezzo_go, 1)} (GO) = "
            f"**{fmt_it(_tariffa_netta_tp, 1)} €/MWh netta incentivo**"
        )
        bp_tariffa_eff = _tariffa_lorda   # per BP: usiamo lorda (gas venduto separatamente)
    else:
        _recap_line = (
            f"**TR aggiudicata** {fmt_it(_tr_aggiudicata, 1)} + "
            f"**Premi** {fmt_it(_tot_premi, 1)} = "
            f"**{fmt_it(_tariffa_lorda, 1)} €/MWh** (TO — tutto incluso, GSE ritira gas + GO)"
        )
        bp_tariffa_eff = _tariffa_lorda

    st.success(f"📐 **Riepilogo tariffa**: " + _recap_line + f" · Durata: **{BP_DURATA_TARIFFA_ANNI} anni**")


    bp_result = compute_revenues(plant_smch=plant_net_smch, tariffa_eur_mwh=bp_tariffa_eff)
    # Riutilizzo delle variabili calcolate nella sidebar
    # (ep_total, aux_factor, etc. sono già definiti globalmente)

    # =================================================================
    # 🎯 HERO ECONOMICO — KPI principali sempre visibili in cima alla
    # sezione Business Plan. Calcolati dal Business Plan engine
    # `core.business_plan.build_business_plan()`.
    # =================================================================
    try:
        from core.business_plan import build_business_plan as _build_bp_engine
        from core.calculation_engine import (
            BP_CAPEX_DEFAULTS_PER_SMCH as _BP_CAPEX,
            BP_OPEX_DEFAULTS_PER_SMCH_YEAR as _BP_OPEX,
        )
        _capex_unit = float(_BP_CAPEX.get(bp_plant_type, _BP_CAPEX.get("nuova_costruzione", 38_000)))
        _opex_unit = float(sum(_BP_OPEX.values()) if _BP_OPEX else 5_350)
        # Stato pre-form: si usano default; user può modificare nel sub-tab BP sotto.
        _bp_hero_state_key = "_bp_hero_overrides"
        _overrides = st.session_state.get(_bp_hero_state_key, {})
        _capex_unit = float(_overrides.get("capex_unit", _capex_unit))
        _opex_unit = float(_overrides.get("opex_unit", _opex_unit))
        _pnrr_pct = float(_overrides.get("pnrr_pct", 0.0))
        _bp_hero = _build_bp_engine(
            plant_smch=plant_net_smch,
            tariffa_eur_mwh=bp_tariffa_eff,
            capex_eur_per_smch=_capex_unit,
            opex_eur_per_smch_year=_opex_unit,
            pnrr_quota_pct=_pnrr_pct,
        )
        _hero_cols = st.columns(5)
        _hero_cols[0].metric(
            _t("Ricavo annuo"),
            f"{fmt_it(_bp_hero.rows[1].ricavi / 1000, 0)}k €",
            help=_t("Ricavo lordo stimato per il primo anno di esercizio commerciale, comprensivo di tariffa base e premi.")
        )
        _hero_cols[1].metric(
            _t("CAPEX totale"),
            f"{fmt_it(_bp_hero.capex_total / 1_000_000, 1)}M €",
            help=_t("Investimento totale stimato per la realizzazione dell'impianto chiavi in mano, comprensivo di costi forfait e PNRR.")
        )
        _hero_cols[2].metric(
            "IRR Equity",
            f"{_bp_hero.irr_equity * 100:.1f}%" if -1 < _bp_hero.irr_equity < 10 else "—",
            help=_t("Tasso Interno di Rendimento calcolato sui flussi di cassa del capitale proprio (Equity IRR).")
        )
        _hero_cols[3].metric(
            "NPV @ 6%",
            f"{fmt_it(_bp_hero.npv_project / 1_000_000, 1)}M €",
            help=_t("Valore Attuale Netto (NPV) del progetto calcolato su base 15 anni attualizzato al tasso del 6.0%.")
        )
        _hero_cols[4].metric(
            _t("Payback"),
            f"{_bp_hero.payback_years:.1f} {_t('anni')}" if _bp_hero.payback_years else "—",
            help=_t("Tempo di recupero (in anni) del capitale proprio investito, al netto del finanziamento e del PNRR.")
        )
        st.caption("ℹ️ " + _t(
            "KPI economici calcolati con CAPEX/OPEX di default. "
            "Personalizza nella sezione **💼 Business Plan completo** in fondo al tab."
        ))
    except Exception as _bp_exc:  # noqa: BLE001
        _LOG.warning("Business Plan hero KPI failed: %s", _bp_exc)

    st.info(_t("⚙️ La configurazione tecnica e i parametri GHG sono ora gestiti nel **pannello laterale (sidebar)** per un'esperienza più intuitiva."))
    
    # Breakdown ep (mode-aware) - visualizzato qui come risultato
    st.subheader(_t("🌿 Risultati Sostenibilità (ep)"))
    with st.expander(
        f"📊 Breakdown ep = {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ",
        expanded=True,
    ):
        _ep_lines = [
            f"- Digestato: **{fmt_it(ep_digestate, 1, signed=True)}**",
            f"- Upgrading: **{fmt_it(ep_upgrading, 1, signed=True)}**",
            f"- Off-gas: **{fmt_it(ep_offgas, 1, signed=True)}**",
            f"- Calore: **{fmt_it(ep_heat, 1, signed=True)}**",
            f"- Elettricità: **{fmt_it(ep_elec, 1, signed=True)}**",
        ]
        if globals().get("_ep_floored") or (ep_digestate+ep_upgrading+ep_offgas+ep_heat+ep_elec) < 0:
            _ep_lines.append(
                f"- _Somma grezza: {fmt_it(ep_digestate+ep_upgrading+ep_offgas+ep_heat+ep_elec, 1, signed=True)} "
                f"→ vincolata a 0 (RED III: ep ≥ 0)_"
            )
        _ep_lines.append(f"- **Totale ep: {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ**")
        st.markdown("\n".join(_ep_lines))

    st.divider()

    # Breakdown aux_factor
    st.subheader(_t("⚡ Bilancio Energetico (aux_factor)"))
    with st.expander(
        f"🔬 Dettaglio calcolo aux_factor = {fmt_it(aux_factor, 3)}",
        expanded=True,
    ):
        if aux_auto_data:
            st.markdown(
                f"**Formula**: aux = 1 / (1 − f_calore − f_elettr − f_slip − f_margine)\n\n"
                f"### 🔥 BILANCIO TERMICO\n"
                f"Fabbisogno termico lordo = **{fmt_it(aux_auto_data['heat_need_gross'], 3)} kWh_t/Sm³**\n"
                f"- Riscaldamento digestori (mesofilo): {fmt_it(HEAT_DIGESTORE, 3)}\n"
                f"- Calore upgrading: {fmt_it(HEAT_DEMAND_UPGRADING.get(upgrading_opt, 0), 3)}\n\n"
                f"→ **f_calore = {fmt_it(aux_auto_data['f_heat']*100, 2, '%')}**\n\n"
                f"### ⚡ BILANCIO ELETTRICO\n"
                f"Fabbisogno elettrico totale = **{fmt_it(aux_auto_data['elec_need'], 3)} kWh_e/Sm³**\n"
                f"→ **f_elettr = {fmt_it(aux_auto_data['f_elec']*100, 2, '%')}**\n\n"
                f"### ∑ TOTALE AUTOCONSUMO: **{fmt_it(aux_auto_data['f_tot']*100, 2, '%')}**"
            )

    st.metric(
        "Produzione lorda richiesta",
        fmt_it(plant_net_smch * aux_factor, 1, " Sm³/h"),
        help=_t("Produzione oraria lorda di biogas necessaria per garantire la produzione netta immessa in rete, tenuto conto dell'aux_factor.")
    )

    # ============================================================
    # EXPORT & REPORTING (sezione accorpata nel tab Risultati, Incentivi & BP)
    # ============================================================
    st.divider()
    st.header("📊 " + _t("Risultati, Reporting & Export Annuali"))
    st.caption(_t("Sezione DB (in alto): dati REALI consolidati da Gestione Giornaliera. "
                  "Sezione Simulatore (in basso): analisi what-if pre-popolata dai dati DB."))

    # Snapshot del df_res da DB PRIMA che la sezione simulatore lo sovrascriva
    # (a riga ~4205 df_res viene reassegnato con i risultati del solver/manuale).
    df_res_db = df_res.copy() if not df_res.empty else pd.DataFrame()

    if df_res.empty or df_res["Sm³ netti"].sum() == 0:
        st.info(_t("ℹ️ Nessun dato annuale disponibile. Inserisci e salva i dati nella «Gestione Giornaliera» per generare i report."))
    else:
        # Tabella riepilogativa annuale
        st.subheader(_t("📈 Piano Mensile Consolidato (da DB)"))
        st.dataframe(df_res.style.format({
            "Ore": "{:.0f}", "Sm³ lordi": "{:,.0f}", "Sm³ netti": "{:,.0f}",
            "MWh netti": "{:,.1f}", "e_w": "{:.2f}", "Saving %": "{:.1f}%",
            "Totale biomasse (t)": "{:,.0f}"
        }), use_container_width=True, hide_index=True)

        # --- SEZIONE REMI ---
        if "remi_vb" in df_res.columns and df_res["remi_vb"].sum() > 0:
            st.divider()
            st.subheader(_t("📉 Consolidato REMI (Real-Time)"))
            _remi_cols = [
                "Mese", "remi_vb", "remi_e", "remi_qb_max", 
                "remi_pci", "remi_rho", "remi_portata_media", 
                "remi_potenza_media", "remi_energia_specifica"
            ]
            st.dataframe(df_res[_remi_cols], column_config={
                "Mese": st.column_config.TextColumn("Mese"),
                "remi_vb": st.column_config.NumberColumn("Vb (Sm³)", format="%d"),
                "remi_e": st.column_config.NumberColumn("E (kWh)", format="%d"),
                "remi_qb_max": st.column_config.NumberColumn("Qb max (Sm³/h)", format="%.1f"),
                "remi_pci": st.column_config.NumberColumn("PCI (kWh/Sm³)", format="%.4f"),
                "remi_rho": st.column_config.NumberColumn("Rho (kg/Sm³)", format="%.4f"),
                "remi_portata_media": st.column_config.NumberColumn("Portata Media (Sm³/h)", format="%.1f"),
                "remi_potenza_media": st.column_config.NumberColumn("Potenza Media (MW)", format="%.3f"),
                "remi_energia_specifica": st.column_config.NumberColumn("Energia Specif. (kWh/Sm³)", format="%.3f"),
            }, use_container_width=True, hide_index=True)

        # Logica Export (estratta dal Solver)
        try:
            # Output model context per export
            _om_ctx = {
                "APP_MODE": APP_MODE, "APP_MODE_LABEL": _MODE["label"], "lang": _LANG,
                "plant_net_smch": plant_net_smch,
                "aux_factor": aux_factor, "ep_total": ep_total, "end_use": end_use,
                "ghg_threshold": ghg_threshold, "fossil_comparator": FOSSIL_COMPARATOR,
                "active_feeds": active_feeds, "FEEDSTOCK_DB": FEEDSTOCK_DB,
                "df_res": df_res, "tot_biomasse_t": float(df_res["Totale biomasse (t)"].sum()),
                "tot_sm3_netti": float(df_res["Sm³ netti"].sum()), "tot_mwh_netti": float(df_res["MWh netti"].sum()),
                "saving_avg": saving_annuale_pesato(df_res, comparator=FOSSIL_COMPARATOR), "valid_months": int(df_res["Validità"].str.startswith("✅").sum()),
                "tot_revenue": float(tot_revenue), "tariffa_media_ponderata": float(tariffa_media_ponderata),
                "revenue_rows": pdf_revenue_rows,
                "actual_yields": {_f: _yield_of(_f) for _f in active_feeds},
                "actual_emissions": {_f: _emission_factors_of(_f) for _f in active_feeds},
                "yield_audit_rows": list(_yield_audit_rows),
                "emission_audit_rows": list(_emission_audit_rows),
            }
            
            # --- EXPORT BUTTONS ---
            st.divider()
            _dl_col1, _dl_col2, _dl_col_pptx, _dl_col3, _dl_col4 = st.columns([1.2, 1.0, 1.0, 0.8, 0.8])
            
            # Context for XLSX
            _xlsx_ctx = {
                "active_feeds": active_feeds, "FEEDSTOCK_DB": FEEDSTOCK_DB,
                "aux_factor": aux_factor, "ep_total": ep_total,
                "fossil_comparator": FOSSIL_COMPARATOR, "ghg_threshold": ghg_threshold,
                "plant_net_smch": plant_net_smch, "NM3_TO_MWH": NM3_TO_MWH,
                "MONTHS": MONTHS, "MONTH_HOURS": MONTH_HOURS,
                "initial_data": {row["Mese"]: {"Ore": int(row["Ore"]), **{f: row[f] for f in active_feeds if f in row}} for _, row in df_res.iterrows()},
                "APP_MODE_LABEL": _MODE["label"], "end_use": end_use,
                "bp_tariffa_eff_mwh": float(tariffa_media_ponderata), "bp_ore_anno": 8500.0,
                "bp_durata_tariffa": BP_DURATA_TARIFFA_ANNI,
                "bp_pnrr_pct": st.session_state.get("bp_pnrr_pct", 40.0),
                "bp_tax_rate_pct": BP_TAX_RATE_PCT, "bp_ammort_anni": BP_AMMORTAMENTO_ANNI,
                "bp_npv_disc_rate_pct": 6.0, "bp_massimale_eur_per_smch": BP_MASSIMALE_SPESA_EUR_PER_SMCH,
                "NM3_TO_MWH": NM3_TO_MWH, "lang": _LANG,
                "yield_audit_rows": list(_yield_audit_rows), "effective_yields": dict(_EFFECTIVE_YIELDS),
                "emission_audit_rows": list(_emission_audit_rows), "emission_overrides": dict(_EMISSION_OVERRIDES),
                "actual_yields": {_f: _yield_of(_f) for _f in active_feeds},
                "actual_emissions": {_f: _emission_factors_of(_f) for _f in active_feeds},
            }

            with _dl_col1:
                try:
                    from excel_export import build_metaniq_xlsx
                    _xlsx_buf = build_metaniq_xlsx(_xlsx_ctx)
                    st.download_button(_t("📊 Scarica Excel"), data=_xlsx_buf.getvalue(), file_name=f"metaniq_{APP_MODE}_consolidato.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
                except Exception as _e: st.error(f"XLSX Error: {_e}")

            with _dl_col2:
                try:
                    from pdf_export import build_metaniq_pdf
                    # Re-use _xlsx_ctx or build specific one
                    _pdf_buf = build_metaniq_pdf(_xlsx_ctx)
                    st.download_button(_t("📄 Scarica PDF"), data=_pdf_buf.getvalue(), file_name=f"metaniq_{APP_MODE}_report.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except Exception as _e: st.error(f"PDF Error: {_e}")

            with _dl_col_pptx:
                try:
                    from export.pptx_export import build_metaniq_pptx
                    _pptx_buf = build_metaniq_pptx(_xlsx_ctx)
                    st.download_button(_t("📊 Presentazione"), data=_pptx_buf.getvalue(), file_name=f"metaniq_{APP_MODE}_slides.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True, type="primary")
                except Exception as _e: st.error(f"PPTX Error: {_e}")

        except Exception as _exp_ui_exc:
            st.error(f"Errore UI Export: {_exp_ui_exc}")

    # ============================================================
    # AUDIT RESE — Tracciabilita' BMT vs tabella standard
    # ============================================================
    if _yield_audit_rows:
        st.markdown("##### 🧪 Audit rese biomasse (BMT certificato vs tabella standard)")
        df_yield_audit = pd.DataFrame(_yield_audit_rows)
        # Format numerici
        df_yield_audit_disp = df_yield_audit.copy()
        df_yield_audit_disp["Resa standard"] = df_yield_audit_disp["Resa standard"].apply(
            lambda v: fmt_it(v, 1)
        )
        df_yield_audit_disp["Resa usata"] = df_yield_audit_disp["Resa usata"].apply(
            lambda v: fmt_it(v, 1)
        )
        st.dataframe(
            df_yield_audit_disp, hide_index=True, use_container_width=True,
        )
        st.caption(
            f"Origine resa = `{SOURCE_BMT}` se l'utente ha caricato un "
            f"certificato valido E ha attivato l'override per quella "
            f"biomassa; altrimenti `{BMT_SOURCE_STD}`. La tabella standard "
            f"NON viene mai modificata."
        )

    # ============================================================
    # AUDIT FATTORI EMISSIVI — Tracciabilita' override reali vs standard
    # ============================================================
    if _emission_audit_rows:
        # Allinea ep_standard nei rows con il valore impianto-wide attuale
        # (resolve_emission_factors era stata chiamata con ep_default=0
        # perche' ep_total non era ancora computato in sidebar)
        for _r in _emission_audit_rows:
            if _r["Origine fattori"] == EF_SOURCE_STD:
                _r["ep standard"] = float(ep_total)
                _r["ep usato"] = float(ep_total)
                # ricalcola e_total con ep_total aggiornato
                _r["e_total"] = calculate_emission_total(
                    _r["eec usato"], _r["esca usato"],
                    _r["etd usato"], _r["ep usato"],
                    _r.get("Crediti extra", 0.0),
                )

        st.markdown("##### 🧬 Audit fattori emissivi (relazione tecnica vs standard)")
        df_ef_audit = pd.DataFrame(_emission_audit_rows)
        # Format numeric columns
        df_ef_audit_disp = df_ef_audit.copy()
        for _c in ("eec standard", "eec usato", "esca standard", "esca usato",
                    "etd standard", "etd usato", "ep standard", "ep usato",
                    "Crediti extra", "e_total"):
            if _c in df_ef_audit_disp.columns:
                df_ef_audit_disp[_c] = df_ef_audit_disp[_c].apply(
                    lambda v: fmt_it(v, 2, signed=(_c in ("eec standard", "eec usato", "e_total")))
                )
        st.dataframe(df_ef_audit_disp, hide_index=True, use_container_width=True)
        st.caption(
            f"Origine = `{EF_SOURCE_REAL}` se l'utente ha caricato la relazione "
            f"tecnica E ha attivato l'override per quella biomassa; altrimenti "
            f"`{EF_SOURCE_STD}`. La tabella standard NON viene mai modificata. "
            f"Soglia warning scostamento: ±{int(EMISSION_DEVIATION_WARN_THRESHOLD*100)}%."
        )

    # ------------------------- MODE SELECTOR -------------------------
    st.subheader(_t("🎯 Modalità di calcolo"))

    N_active = len(active_feeds)
    MODE_DUAL = f"{N_active-2} {_t('biomasse fisse + 2 calcolate  (saving target + produzione)')}"
    MODE_SINGLE = f"{N_active-1} {_t('biomasse fisse + 1 calcolata  (solo produzione)')}"

    # --- Applica eventuali risultati ottimizzazione PRIMA di creare i widget ---
    # (Streamlit non consente di modificare session_state di una chiave-widget
    # dopo che qualunque widget e' stato renderizzato nello stesso run.)
    #
    # BUG-FIX: la state_key del renderer (line ~3170) include _active_hash
    # (per evitare contaminazioni cross-config). Qui dobbiamo usare lo
    # STESSO formato di chiave, altrimenti la "fixed-at-zero" iniettata
    # dall'optimizer viene salvata sotto una chiave che il renderer non
    # legge (e quindi sovrascritta dai default _default_mass).
    _pending_opt = st.session_state.pop("_pending_optimization", None)
    if _pending_opt is not None:
        _opt_active_hash = str(hash(tuple(sorted(active_feeds))))[:8]
        if _pending_opt.get("is_mono"):
            mono = _pending_opt["mono"]
            others = [n for n in active_feeds if n != mono]
            st.session_state["fixed_multiselect"] = others
            new_state_key = f"mens_in_1unk_{_opt_active_hash}_{'-'.join(others)}"
            rows_init = []
            for mm, hh in zip(MONTHS, MONTH_HOURS):
                r = {"Mese": mm, "Ore": hh}
                for f in others:
                    r[f] = 0.0
                rows_init.append(r)
            st.session_state[new_state_key] = pd.DataFrame(rows_init)
        else:
            st.session_state["fixed_multiselect"] = list(_pending_opt["unused"])
            new_state_key = f"mens_in_2unk_{_opt_active_hash}_{'-'.join(_pending_opt['unused'])}"
            rows_init = []
            for mm, hh in zip(MONTHS, MONTH_HOURS):
                r = {"Mese": mm, "Ore": hh}
                for f in _pending_opt["unused"]:
                    r[f] = 0.0
                rows_init.append(r)
            st.session_state[new_state_key] = pd.DataFrame(rows_init)
        
        st.session_state["_optimize_info"] = {
            "pair": _pending_opt["pair"],
            "unused": _pending_opt["unused"],
            "total_year": _pending_opt["total_year"],
            "is_mono": _pending_opt.get("is_mono", False),
            "mono": _pending_opt.get("mono"),
        }
    # -------- PULSANTE OTTIMIZZA (tutta larghezza, sempre visibile) ------------
    from math import comb as _comb
    _n_combinations = _comb(N_active, 2) if N_active >= 2 else 0
    _prod_label = f"{fmt_it(plant_net_smch, 0)} Sm³/h netti"
    st.markdown(
        f"##### ⚡ {_t('Auto-calcolo ottimale')} – {_t('enumera le')} **{_n_combinations} {_t('combinazioni')}** "
        f"{_t('possibili tra le')} {N_active} {_t('biomasse attive e minimizza la massa totale')} "
        f"({_t('saving')} ≥ {fmt_it(ghg_threshold*100, 0, '%')}, {_t('produzione')} = {_prod_label})"
    )
    optimize_clicked = st.button(
        "🚀 OTTIMIZZA  (minimizza massa totale biomasse)",
        help=f"Enumera le C({N_active},2) = {_n_combinations} coppie di biomasse attive + "
             f"{N_active} soluzioni mono, sceglie quella con massa totale minima che "
             "soddisfa entrambi i vincoli (produzione + saving GHG). "
             "Le biomasse non selezionate vengono azzerate.",
        use_container_width=True,
        type="primary",
        key="btn_optimize",
    )
    st.divider()

    # --- Gestione click OTTIMIZZA ----------------------------------------------
    # Salva solo un flag "_pending_optimization" (chiave NON-widget) e fa rerun:
    # al giro successivo il blocco sopra imposta i widget PRIMA che vengano creati.
    if optimize_clicked:
        best = find_optimal_pair(
            aux=aux_factor, plant_net=plant_net_smch,
            ep=ep_total, target_e_max=target_e_max,
            feed_list=active_feeds,
        )
        if best is None:
            _tip_impianto = (
                "stoccaggio digestato coperto, upgrading a membrane/amminico, "
                "off-gas RTO"
            )
            _unit_prod = f"{fmt_it(plant_net_smch, 0)} Sm³/h"
            st.error(
                "❌ Nessuna combinazione delle biomasse attive riesce a soddisfare "
                f"simultaneamente saving ≥ {fmt_it(ghg_threshold*100, 0, '%')} e "
                f"produzione {_unit_prod} con la configurazione "
                f"ep attuale ({fmt_it(ep_total, 1, signed=True)} gCO₂/MJ). "
                "Prova ad: aggiungere biomasse a manure credit (liquami/letami), "
                f"migliorare la configurazione impianto ({_tip_impianto}), "
                "oppure abbassare il setpoint produttivo."
            )
        else:
            pair, total_h, masses_h = best
            # Se solo una biomassa ha massa > 0 -> ottimo MONO
            active_masses = [n for n, v in masses_h.items() if v > 1e-9]
            is_mono = len(active_masses) == 1
            unused = [n for n in active_feeds if n not in pair]
            annual_hours = sum(MONTH_HOURS)
            st.session_state["_pending_optimization"] = {
                "pair": list(pair),
                "unused": unused,
                "total_year": total_h * annual_hours,
                "is_mono": is_mono,
                "mono": active_masses[0] if is_mono else None,
            }
            st.rerun()

    # -------- SMART SOLVER MENU --------------------------------------------------

    st.caption(_t("Le biomasse NON selezionate verranno calcolate automaticamente dal sistema. Lasciane 1 fuori per centrare la produzione, lasciane 2 fuori per centrare produzione e saving. Selezionale tutte per una pura simulazione."))

    default_fixed = active_feeds[:min(2, N_active)]
    prev_default = st.session_state.get("fixed_multiselect", [])
    if not all(p in active_feeds for p in prev_default):
        st.session_state["fixed_multiselect"] = default_fixed

    fixed_feeds = st.multiselect(
        _t("Biomasse manuali"),
        options=active_feeds,
        default=default_fixed if "fixed_multiselect" not in st.session_state else None,
        help=_t("Scegli le biomasse fisse."),
        key="fixed_multiselect"
    )

    unknown_feeds = [n for n in active_feeds if n not in fixed_feeds]

    if len(unknown_feeds) > 2:
        st.warning(_t("Il sistema può risolvere al massimo 2 incognite (produzione + saving). Seleziona più biomasse manuali."))
        st.stop()

    # Info Banner depending on unknowns
    if len(unknown_feeds) == 2:
        st.info(f"**{_t('Modalità dual-constraint')}**: {_t('il solver calcola')} **{unknown_feeds[0]}** e **{unknown_feeds[1]}** {_t('per ottenere saving')} **{fmt_it(target_saving*100, 0, '%')}** e {_t('produzione')} **{_prod_label}**.")
    elif len(unknown_feeds) == 1:
        st.info(f"**{_t('Modalità produzione-only')}**: {_t('il sistema calcola')} **{unknown_feeds[0]}** {_t('per chiudere la produzione')}. {_t('Il saving sarà una conseguenza.')}")
    else:
        st.info(f"**{_t('Modalità simulazione')}**: {_t('nessuna incognita. Inserisci tutte le quantità manualmente in tabella per vedere i risultati.')}")

    is_dual_mode = (len(unknown_feeds) == 2)

    # ------------------------- TABELLA UNIFICATA (input + risultati) -------------------------


    # Valori di default plausibili per biomasse comuni; fallback generico per il resto
    # (il cliente li riaggiusta a mano in tabella mensile)
    defaults_all = {
        "Trinciato di mais": 1800.0,
        "Trinciato di sorgo da foraggio": 400.0,
        "Trinciato di sorgo uso energetico (biodigestori)": 400.0,
        "Pollina ovaiole (aerobico)": 300.0,
        "Pollina broiler (lettiera)": 250.0,
        "Pollina tacchini": 200.0,
        "Liquame suino": 1500.0,
        "Liquame bovino": 1200.0,
        "Liquame bufalino": 1100.0,
        "Letame bovino palabile": 500.0,
        "Letame equino": 150.0,
        "Deiezioni conigli": 100.0,
        "Triticale insilato": 400.0,
        "Segale insilata": 300.0,
        "Orzo insilato": 300.0,
        "Loietto insilato (ryegrass)": 300.0,
        "Erba medica insilata": 250.0,
        "Doppia coltura (2° raccolto)": 500.0,
        "Erbaio misto insilato": 300.0,
        "Barbabietola da zucchero": 300.0,
        "Sansa di olive umida": 300.0,
        "Sansa vergine": 200.0,
        "Pastazzo di agrumi": 250.0,
        "Vinaccia (con raspi)": 200.0,
        "Raspi d'uva": 100.0,
        "Feccia vinicola": 150.0,
        "Siero di latte": 500.0,
        "Scotta (siero residuo)": 400.0,
        "Trebbie di birra": 250.0,
        "Lolla/pula di riso": 100.0,
        "Melasso": 150.0,
        "Scarti panificazione/pasticceria": 100.0,
        "Grassi esausti / UCO": 50.0,
        "Scarti macellazione (cat. 3)": 100.0,
        "Sottoprodotti ortofrutticoli": 300.0,
        "Scarti caseari vari": 200.0,
        "Fanghi agro-industriali": 200.0,
        "Polpe di barbabietola fresche": 400.0,
        "Polpe di barbabietola insilate": 350.0,
        "Melasso di barbabietola": 120.0,
        "FORSU selezionata": 400.0,
        "Fanghi depurazione": 150.0,
    }
    # Fallback: se una biomassa attiva non e' in defaults_all, usa 200 t/mese
    def _default_mass(feed):
        return defaults_all.get(feed, 200.0)

    def _prefill_from_db(df_db, fixed_feeds_l, months_l, month_hours_l):
        """Costruisce il DataFrame iniziale del simulatore pre-popolato con
        i dati REALI aggregati dal DB (df_res_db). Una riga per mese con
        colonne (Mese, Ore, *fixed_feeds). Mesi senza dati DB -> Ore di
        default (calendario) e biomasse a 0 (no stime arbitrarie)."""
        rows = []
        df_db_idx = (df_db.set_index("Mese")
                     if (df_db is not None and not df_db.empty)
                     else None)
        for _m, _hd in zip(months_l, month_hours_l):
            row = {"Mese": _m}
            if df_db_idx is not None and _m in df_db_idx.index:
                db_row = df_db_idx.loc[_m]
                ore_db = float(db_row.get("Ore", 0.0) or 0.0)
                row["Ore"] = int(round(ore_db)) if ore_db > 0 else _hd
                for _f in fixed_feeds_l:
                    v = float(db_row.get(_f, 0.0) or 0.0) if _f in db_row.index else 0.0
                    row[_f] = v
            else:
                row["Ore"] = _hd
                for _f in fixed_feeds_l:
                    row[_f] = _default_mass(_f)
            rows.append(row)
        return pd.DataFrame(rows)

    # --- Stato persistente: memorizzo SOLO le colonne editabili (Mese, Ore, fisse).
    # Chiave state univoca per combinazione mode+fisse+active_feeds, cosi' cambio
    # biomasse attive -> nuovo state (evita contaminazioni tra configurazioni diverse).
    _active_hash = str(hash(tuple(sorted(active_feeds))))[:8]
    # Year/plant context: se l'utente cambia anno/impianto in Gestione
    # Giornaliera, il simulatore invalida lo state e ri-popola con i nuovi
    # dati DB.
    _sim_year = int(st.session_state.get("do_year", _dt.date.today().year))
    _sim_plant = (st.session_state.get("do_plant_id") or PLANT_NAME or "default").strip() or "default"
    state_key = f"mens_in_{len(unknown_feeds)}unk_{_active_hash}_{_sim_year}_{_sim_plant}_{'-'.join(fixed_feeds)}"

    # Inizializzazione state: pre-fill intelligente da DB.
    _db_has_data = (not df_res_db.empty) and (df_res_db["Sm³ netti"].sum() > 0)
    if state_key not in st.session_state:
        if _db_has_data:
            st.session_state[state_key] = _prefill_from_db(
                df_res_db, fixed_feeds, MONTHS, MONTH_HOURS)
            st.session_state[f"{state_key}__source"] = "db"
        else:
            init_rows = []
            for m, h in zip(MONTHS, MONTH_HOURS):
                row = {"Mese": m, "Ore": h}
                for f in fixed_feeds:
                    row[f] = _default_mass(f)
                init_rows.append(row)
            st.session_state[state_key] = pd.DataFrame(init_rows)
            st.session_state[f"{state_key}__source"] = "defaults"

    # Rileva "scenario modificato": tabella corrente != pre-fill DB
    _scenario_modified = False
    if _db_has_data:
        try:
            _expected_db = _prefill_from_db(df_res_db, fixed_feeds, MONTHS, MONTH_HOURS)
            _cur_cols = ["Mese", "Ore"] + fixed_feeds
            _cur = st.session_state[state_key][_cur_cols].reset_index(drop=True)
            _exp = _expected_db[_cur_cols].reset_index(drop=True)
            _scenario_modified = not _cur.round(2).equals(_exp.round(2))
        except Exception:
            _scenario_modified = True

    # Banner di stato
    if _db_has_data and not _scenario_modified:
        st.info(
            f"🟢 **Simulatore allineato al DB** — la tabella mostra i dati reali "
            f"aggregati per anno **{_sim_year}**, impianto **{_sim_plant}**. "
            f"Modifica liberamente le celle ✏️ per simulare scenari what-if "
            f"(le modifiche **non vengono salvate nel database**)."
        )
    elif _scenario_modified:
        st.warning(
            f"🟡 **Simulazione what-if — scenario modificato** "
            f"(dati base: anno {_sim_year}, impianto {_sim_plant}). "
            f"Le modifiche sono solo in memoria, non salvate nel DB. "
            f"Usa «🔄 Ricarica dati reali dal DB» per tornare al dato reale."
        )
    else:
        st.warning(
            "🟡 **" + _t("Simulazione what-if") + "** — "
            + _t("DB vuoto per anno") + f" {_sim_year} / "
            + _t("impianto") + f" {_sim_plant}: "
            + _t("la tabella usa valori plausibili di default. ")
            + _t("Inserisci i dati reali da «Gestione Giornaliera» per attivare il pre-fill DB.")
        )

    col_tab_title, col_tab_btn_db, col_tab_btn = st.columns([3, 1.4, 1], vertical_alignment="bottom")
    with col_tab_title:
        st.subheader(_t("📆 Tabella mensile – modifica le celle ✏️, il resto si ricalcola"))
    with col_tab_btn_db:
        if st.button(
            "🔄 " + _t("Ricarica dati reali dal DB"),
            use_container_width=True,
            disabled=not _db_has_data,
            help=(
                _t("Sovrascrive la tabella con i valori reali aggregati dal "
                   "database per anno") + f" {_sim_year} / "
                + _t("impianto") + f" {_sim_plant}. "
                + _t("Le modifiche correnti vengono perse.")
                if _db_has_data else
                _t("Nessun dato nel DB per anno/impianto correnti. "
                   "Inserisci i dati da «Gestione Giornaliera».")
            ),
            key=f"btn_reload_db_{state_key}",
        ):
            st.session_state[state_key] = _prefill_from_db(
                df_res_db, fixed_feeds, MONTHS, MONTH_HOURS)
            st.session_state[f"{state_key}__source"] = "db"
            st.rerun()
    with col_tab_btn:
        if st.button("🔄 Reset", use_container_width=True,
                     help=_t("Ripristina i valori iniziali di default per questa configurazione.")):
            st.session_state.pop(state_key, None)
            st.session_state.pop(f"{state_key}__source", None)
            st.rerun()

    # Retrocompatibilita': se lo state esiste con vecchia colonna target per mese, rimuovo
    if "Target Sm³/h netti" in st.session_state[state_key].columns:
        st.session_state[state_key] = st.session_state[state_key].drop(
            columns=["Target Sm³/h netti"]
        )

    input_df = st.session_state[state_key]

    # ------------------------- CALCOLI PER MESE -------------------------
    results = []
    warnings_list = []
    for _, row in input_df.iterrows():
        fixed_map = {n: float(row[n]) for n in fixed_feeds}
        hours = float(row["Ore"])

        if len(unknown_feeds) >= 2:
            sol, feasible, msg = solve_2_unknowns_dual(
                fixed_map, unknown_feeds, hours, aux_factor, plant_net_smch,
                ep_total, target_e_max,
            )
            all_masses = {**fixed_map, **sol}
            if not feasible:
                warnings_list.append(f"**{row['Mese']}**: {msg}")
        elif len(unknown_feeds) == 1:
            computed = solve_1_unknown_production(
                fixed_map, unknown_feeds[0], hours, aux_factor, plant_net_smch
            )
            all_masses = dict(fixed_map)
            all_masses[unknown_feeds[0]] = max(computed, 0.0)
            feasible = (computed >= 0)
            if not feasible:
                warnings_list.append(
                    f"**{row['Mese']}**: {unknown_feeds[0]} = {fmt_it(computed, 1)} t (<0). "
                    f"Le biomasse fisse gia' superano il fabbisogno lordo."
                )
        else:
            # Simulazione pura: nessuna incognita
            all_masses = dict(fixed_map)
            feasible = True

        summary = ghg_summary(all_masses, aux_factor, ep_total, FOSSIL_COMPARATOR)

        # Validita' - DUE CONDIZIONI OBBLIGATORIE:
        #   (1) saving GHG >= soglia RED III (80/70/65% a seconda uso finale),
        #       calcolato su biometano LORDO (anche la quota autoconsumata dagli
        #       ausiliari CHP+caldaia deve essere rinnovabile per >=80%).
        #   (2) produzione netta <= plant_net_smch (taglia autorizzata).
        net_smch = summary["nm3_net"] / hours if hours > 0 else 0.0
        # tolleranza 1e-6 per evitare falsi negativi da arrotondamenti float
        saving_ok = summary["saving"] >= ghg_threshold * 100 - 1e-6
        prod_ok = net_smch <= plant_net_smch + 0.5   # tolleranza +0.5 Sm3/h
        target_hit = abs(net_smch - plant_net_smch) < 0.5

        if saving_ok and prod_ok:
            validita = "✅ Valido"
        else:
            motivi = []
            if not saving_ok:
                motivi.append(
                    f"saving {fmt_it(summary['saving'], 1, '%')} < "
                    f"{fmt_it(ghg_threshold*100, 0, '%')}"
                )
            if not prod_ok:
                motivi.append(
                    f"netti {fmt_it(net_smch, 1)} > "
                    f"{fmt_it(plant_net_smch, 0)} Sm³/h (over-autorizz.)"
                )
            validita = "❌ Non valido: " + "; ".join(motivi)

        if saving_ok and prod_ok and not target_hit:
            stato = (
                f"⚠️ netti {fmt_it(net_smch, 1)} < "
                f"{fmt_it(plant_net_smch, 0)} (sub-ottimale)"
            )
        elif not feasible:
            stato = "clampato"
        else:
            stato = (
                f"saving {fmt_it(summary['saving'], 1, '%')} · "
                f"netti {fmt_it(net_smch, 1)}"
            )

        res = {"Mese": row["Mese"], "Ore": int(hours)}
        for n in active_feeds:
            res[n] = all_masses.get(n, 0.0)
        res["Totale biomasse (t)"] = sum(all_masses.values())
        res["Sm³ lordi"] = summary["nm3_gross"]
        res["Sm³ netti"] = summary["nm3_net"]
        res["MWh netti"] = summary["mwh_net"]
        res["GHG (gCO₂/MJ)"] = summary["e_w"]
        res["Saving %"] = summary["saving"]
        res["Sm³/h netti"] = net_smch
        res["Validità"] = validita
        res["Note"] = stato
        results.append(res)

    df_res = pd.DataFrame(results)

    # ------------------------- TABELLA UNICA EDITABILE -------------------------
    # TUTTE le colonne sono TextColumn con numeri in formato italiano (1.234,56).
    # Le celle editabili (Ore + biomasse fisse) vengono riparseate con parse_it()
    # che accetta '1.234,56', '1234,56' o '1234.56'.
    df_disp = df_res.copy()

    # Editabili -> pre-formattate in italiano
    df_disp["Ore"] = df_disp["Ore"].apply(lambda v: fmt_it(v, 0))
    for f in fixed_feeds:
        df_disp[f] = df_disp[f].apply(lambda v: fmt_it(v, 1))

    # Read-only -> pre-formattate in italiano
    for u in unknown_feeds:
        df_disp[u] = df_disp[u].apply(lambda v: fmt_it(v, 1))
    df_disp["Totale biomasse (t)"] = df_disp["Totale biomasse (t)"].apply(lambda v: fmt_it(v, 0))
    df_disp["Sm³ lordi"]   = df_disp["Sm³ lordi"].apply(lambda v: fmt_it(v, 0))
    df_disp["Sm³ netti"]   = df_disp["Sm³ netti"].apply(lambda v: fmt_it(v, 0))
    df_disp["MWh netti"]   = df_disp["MWh netti"].apply(lambda v: fmt_it(v, 1))
    df_disp["GHG (gCO₂/MJ)"] = df_disp["GHG (gCO₂/MJ)"].apply(lambda v: fmt_it(v, 2))
    df_disp["Saving %"]    = df_disp["Saving %"].apply(lambda v: fmt_it(v, 1, "%"))
    df_disp["Sm³/h netti"] = df_disp["Sm³/h netti"].apply(lambda v: fmt_it(v, 1))

    col_cfg = {
        "Mese": st.column_config.TextColumn("Mese", disabled=True),
        "Ore": st.column_config.TextColumn(
            "Ore ✏️",
            help="Ore operative del mese (modificabile, max 744)",
        ),
    }
    for f in fixed_feeds:
        col_cfg[f] = st.column_config.TextColumn(
            f"{f} ✏️ (t)",
            help=f"INPUT – formato italiano (es. 1.800,0) – "
                 f"Resa {fmt_it(_yield_of(f), 0)} Nm³/t FM",
        )
    for u in unknown_feeds:
        col_cfg[u] = st.column_config.TextColumn(
            f"{u} 🧮 (t)",
            disabled=True,
            help=f"CALCOLATA dal solver – Resa {fmt_it(_yield_of(u), 0)} Nm³/t FM",
        )
    col_cfg["Totale biomasse (t)"] = st.column_config.TextColumn("Tot. t", disabled=True)
    "Sm³ lordi"
    "Sm³ netti"
    col_cfg["Sm³ lordi"]   = st.column_config.TextColumn(
        "Sm³ lordi", disabled=True,
        help="Sm³ biometano lordi (pre-perdite upgrading/processo)",
    )
    col_cfg["Sm³ netti"]   = st.column_config.TextColumn(
        "Sm³ netti", disabled=True,
        help="Sm³ biometano immessi in rete (post-aux_factor)",
    )
    col_cfg["MWh netti"]   = st.column_config.TextColumn(
        "MWh netti",
        disabled=True,
        help="Energia biometano netta immessa in rete",
    )
    col_cfg["GHG (gCO₂/MJ)"] = st.column_config.TextColumn(
        "e_w", disabled=True, help="Emissioni pesate gCO₂eq/MJ",
    )
    col_cfg["Saving %"] = st.column_config.TextColumn(
        "Saving %", disabled=True,
        help=f"Obbligatorio ≥ {fmt_it(ghg_threshold*100, 0, '%')} (RED III – {end_use})",
    )
    col_cfg["Sm³/h netti"] = st.column_config.TextColumn(
        "Sm³/h netti", disabled=True,
        help=f"Obbligatorio ≤ {fmt_it(plant_net_smch, 0)} (tetto autorizzativo)",
    )
    col_cfg["Validità"] = st.column_config.TextColumn("Validità", disabled=True, width="medium")
    col_cfg["Note"] = st.column_config.TextColumn("Note", disabled=True, width="medium")

    edited = st.data_editor(
        df_disp,
        column_config=col_cfg,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=470,
        key=f"editor_unified_{state_key}",
    )

    # --- Se l'utente ha modificato una cella editabile, aggiorna state e rerun
    # Le celle editabili sono TextColumn: parse_it() gestisce formato italiano.
    edit_cols = ["Mese", "Ore"] + fixed_feeds
    new_input = edited[edit_cols].reset_index(drop=True).copy()
    # Clamp: ore e masse devono essere >= 0 (niente valori negativi inseriti
    # per errore). Ore max 744 (mese piu' lungo) non applicata come hard-cap
    # per consentire future simulazioni di turni doppi/extra manutenzione.
    # Audit robustezza #15: vectorize parse_it (era .apply() in loop ×N feeds).
    # parse_it accetta sia "1.234,56" sia "1234.56" sia float; pd.to_numeric
    # gestisce direttamente float/int; per stringhe italiane fallback con map.
    def _vectorize_parse(series):
        # Tenta cast diretto (caso più comune: pandas restituisce già float)
        s_num = pd.to_numeric(series, errors="coerce")
        # Fallback per le celle stringa che non si sono convertite (es. "1.234,56")
        if s_num.isna().any():
            s_num = s_num.where(
                ~s_num.isna(),
                series.astype(str).map(parse_it),
            )
        return pd.to_numeric(s_num, errors="coerce").fillna(0).clip(lower=0)

    new_input["Ore"] = _vectorize_parse(new_input["Ore"]).astype(int)
    for f in fixed_feeds:
        new_input[f] = _vectorize_parse(new_input[f]).astype(float)

    old_input = input_df[edit_cols].reset_index(drop=True).copy()
    old_input["Ore"] = old_input["Ore"].astype(int)
    for f in fixed_feeds:
        old_input[f] = old_input[f].astype(float)

    if not new_input.equals(old_input):
        st.session_state[state_key] = new_input
        st.rerun()

    if warnings_list:
        st.warning(_t("⚠️ Mesi con problemi di fattibilità:") + "\n\n" + "\n\n".join(f"- {w}" for w in warnings_list))

    # ------------------------- SINTESI -------------------------
    st.subheader(_t("📈 Sintesi annuale (simulazione what-if)"))
    st.caption(_t(
        "🟡 KPI calcolati sui valori CORRENTEMENTE in tabella (simulazione). "
        "Non riflettono necessariamente i dati salvati nel database."
    ))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tot. biomasse (t/anno)",
              fmt_it(df_res["Totale biomasse (t)"].sum(), 0))
    c2.metric("Sm³ netti (anno)",
              fmt_it(df_res["Sm³ netti"].sum(), 0))
    c3.metric("MWh netti (anno)",
              fmt_it(df_res["MWh netti"].sum(), 0))
    c4.metric("Saving annuo (%)",
              fmt_it(saving_annuale_pesato(df_res, comparator=FOSSIL_COMPARATOR), 1),
              help=_t("Saving GHG ricalcolato sui totali annuali (RED III), "
                      "non media aritmetica dei mesi."))
    valid_months = df_res["Validità"].str.startswith("✅").sum()
    c5.metric(_t("Mesi validi"), f"{valid_months}/12",
              delta="OK" if valid_months == 12 else f"{12-valid_months}{_t(' NON validi')}",
              delta_color="normal" if valid_months == 12 else "inverse")

    # --- Sintesi reale (DB) — affiancata, solo se il DB ha dati ---
    if _db_has_data:
        st.markdown("##### 📊 " + _t("Sintesi reale (DB)") +
                    f" — _{_t('dati salvati')} {_sim_year} / {_sim_plant}_")
        st.caption(_t(
            "🟢 KPI calcolati sui dati operativi REALI aggregati dal database "
            "(Gestione Giornaliera). Non cambiano modificando la tabella sopra."
        ))
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric(_t("Tot. biomasse (t/anno)"),
                  fmt_it(df_res_db["Totale biomasse (t)"].sum(), 0))
        d2.metric(_t("Sm³ netti (anno)"),
                  fmt_it(df_res_db["Sm³ netti"].sum(), 0))
        d3.metric(_t("MWh netti (anno)"),
                  fmt_it(df_res_db["MWh netti"].sum(), 0))
        _saving_db_annuo = saving_annuale_pesato(df_res_db, comparator=FOSSIL_COMPARATOR)
        d4.metric(_t("Saving annuo (%)"),
                  fmt_it(_saving_db_annuo, 1),
                  help=_t("Saving GHG ricalcolato sui totali annuali (RED III), "
                          "non media aritmetica dei mesi."))
        _valid_db = (df_res_db["Validità"].str.startswith("✅").sum()
                     if "Validità" in df_res_db.columns else 0)
        d5.metric(_t("Mesi con dati"), f"{_valid_db}/12")

        if _scenario_modified:
            _delta_t = (df_res["Totale biomasse (t)"].sum()
                        - df_res_db["Totale biomasse (t)"].sum())
            _delta_sm3 = (df_res["Sm³ netti"].sum()
                          - df_res_db["Sm³ netti"].sum())
            _sign_t = "+" if _delta_t >= 0 else ""
            _sign_s = "+" if _delta_sm3 >= 0 else ""
            st.caption(
                f"Δ scenario vs reale: biomasse "
                f"**{_sign_t}{fmt_it(_delta_t, 0)} t** · "
                f"Sm³ netti **{_sign_s}{fmt_it(_delta_sm3, 0)}**"
            )

    # ------------------------- GRAFICI -------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        _t("🌾 Biomasse per mese"),
        _t("🌍 Sostenibilità"),
        _t("⚡ Produzione"),
        _t("🥧 Mix annuale"),
        _t("💼 Ricavi"),
    ])

    with tab1:
        df_melt = df_res.melt(
            id_vars="Mese", value_vars=active_feeds,
            var_name="Biomassa", value_name="t/mese",
        )
        fig = px.bar(
            df_melt, x="Mese", y="t/mese", color="Biomassa",
            color_discrete_map={n: FEEDSTOCK_DB[n]["color"] for n in active_feeds},
            title="Ripartizione mensile biomasse",
        )
        fig.update_layout(barmode="stack", height=450)
        apply_metaniq_theme(fig, dark=IS_DARK)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df_res["Mese"], y=df_res["Saving %"],
            marker=dict(
                color=df_res["Saving %"],
                colorscale=[[0, "#E53935"], [0.5, "#FDD835"], [1, "#43A047"]],
                cmin=70, cmax=100,
                colorbar=dict(title="Saving %"),
            ),
            text=[fmt_it(v, 1, "%") for v in df_res["Saving %"]],
            textposition="outside",
        ))
        fig2.add_hline(y=ghg_threshold*100, line_dash="dash", line_color="red",
                       annotation_text=f"Soglia RED III {fmt_it(ghg_threshold*100, 0, '%')}",
                       annotation_position="top right")
        fig2.add_hline(y=target_saving*100, line_dash="dot", line_color="green",
                       annotation_text=f"Target solver {fmt_it(target_saving*100, 0, '%')}",
                       annotation_position="bottom right")
        fig2.update_layout(title="Saving GHG mensile (%)",
                           yaxis_title="Saving (%)", height=450,
                           yaxis=dict(range=[60, 160]))
        apply_metaniq_theme(fig2, dark=IS_DARK)
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        # Etichette numeriche leggibili coerenti con la tabella (formato IT: 287.928)
        lordi_vals = df_res["Sm³ lordi"].astype(float)
        netti_vals = df_res["Sm³ netti"].astype(float)
        lordi_labels = [fmt_it(v, 0) for v in lordi_vals]
        netti_labels = [fmt_it(v, 0) for v in netti_vals]

        _lbl_lordo = (
            "Sm³ lordi (biomasse)"
        )
        _lbl_netto = (
            "Sm³ netti (immessi in rete)"
        )
        _lbl_title = "Produzione mensile Sm³"
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=df_res["Mese"], y=lordi_vals,
            name=_lbl_lordo, marker_color="#94A3B8",
            text=lordi_labels, textposition="outside",
            hovertemplate=f"<b>%{{x}}</b><br>{_lbl_lordo}: %{{text}}<extra></extra>",
        ))
        fig3.add_trace(go.Bar(
            x=df_res["Mese"], y=netti_vals,
            name=_lbl_netto, marker_color=NAVY,
            text=netti_labels, textposition="outside",
            hovertemplate=f"<b>%{{x}}</b><br>{_lbl_netto}: %{{text}}<extra></extra>",
        ))
        fig3.update_layout(
            title=f"{_lbl_title}  (aux_factor = {fmt_it(aux_factor, 2)})",
            barmode="group", height=500,
            yaxis_title="Sm³ / mese",
            yaxis=dict(tickformat=",.0f", separatethousands=True),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        apply_metaniq_theme(fig3, dark=IS_DARK)
        st.plotly_chart(fig3, use_container_width=True)

        st.caption(
            f"📐 **Dimensionamento**: Sm³ lordi = {fmt_it(plant_net_smch, 0)} × "
            f"{fmt_it(aux_factor, 2)} × ore_mese · "
            f"Sm³ netti = Sm³ lordi ÷ {fmt_it(aux_factor, 2)} = "
            f"{fmt_it(plant_net_smch, 0)} × ore_mese. "
            "Stessi numeri riportati in tabella (colonne «Sm³ lordi» e «Sm³ netti»)."
        )

    with tab4:
        # Mix in tonnellate (FM)
        annual_t = {n: max(df_res[n].sum(), 0) for n in active_feeds}
        # Mix in MWh netti: ogni biomassa contribuisce in proporzione a (massa x yield)
        # MWh_netti_n = massa_n x yield_n / aux_factor x NM3_TO_MWH
        annual_mwh = {
            n: max(df_res[n].sum(), 0) * _yield_of(n)
               / aux_factor * NM3_TO_MWH
            for n in active_feeds
        }
        color_map = {n: FEEDSTOCK_DB[n]["color"] for n in active_feeds}

        # Audit robustezza #2: protezione pie chart con sum=0 (Plotly raises)
        _has_data = sum(annual_t.values()) > 0 and sum(annual_mwh.values()) > 0
        if not _has_data:
            st.info(
                "ℹ️ " + _t("Nessun dato annuale ancora disponibile. "
                           "Inserisci almeno un valore nella tabella mensile "
                           "per vedere il mix annuale.")
            )

        colA, colB = st.columns(2)
        with colA:
            if _has_data:
                fig4a = px.pie(
                    names=list(annual_t.keys()),
                    values=list(annual_t.values()),
                    color=list(annual_t.keys()),
                    color_discrete_map=color_map,
                    title=f"Mix t/anno (totale {fmt_it(sum(annual_t.values()), 0)} t)",
                    hole=0.4,
                )
                fig4a.update_traces(textposition="inside", textinfo="percent+label")
                apply_metaniq_theme(fig4a, dark=IS_DARK)
                st.plotly_chart(fig4a, use_container_width=True)

        with colB:
            _pie_mwh_label = "MWh netti"
            _pie_total = sum(annual_mwh.values())
            _pie_values = list(annual_mwh.values())
            if _has_data and sum(_pie_values) > 0:
                fig4b = px.pie(
                    names=list(annual_mwh.keys()),
                    values=_pie_values,
                    color=list(annual_mwh.keys()),
                    color_discrete_map=color_map,
                    title=f"Mix {_pie_mwh_label}/anno "
                          f"(totale {fmt_it(_pie_total, 0)} MWh)",
                    hole=0.4,
                )
                fig4b.update_traces(textposition="inside", textinfo="percent+label")
                apply_metaniq_theme(fig4b, dark=IS_DARK)
                st.plotly_chart(fig4b, use_container_width=True)

        # ============================================================
        # CALCOLO STATUS AVANZATO IMPIANTO (solo DM 2018)
        # ============================================================
        # Quota in MASSA Annex IX vs totale -> classificazione plant-level
        _tot_t = sum(annual_t.values())
        if _tot_t > 0:
            _t_annex = sum(
                t for n, t in annual_t.items()
                if FEEDSTOCK_DB[n].get("annex_ix") in ("A", "B")
            )
            annex_mass_share = _t_annex / _tot_t
        else:
            annex_mass_share = 0.0

        # DM 2022: nessun regime CIC, niente classificazione "avanzato"
        is_advanced  = False
        cic_double   = False
        cic_active   = False

        # ============================================================
        # TARIFFA PER BIOMASSA (DM 2022 — tariffa diretta €/MWh)
        # ============================================================
        _tar_unit = "€/MWh"
        _tar_default = 120.0
        st.markdown(
            f"##### 💶 Dettaglio per tipologia di biomassa"
            f" (tariffa {_tar_unit} editabile ✏️)"
        )

        # Stato persistente: tariffe per biomassa.
        _tar_key = f"tariffs_eur_mwh_{APP_MODE}"
        if _tar_key not in st.session_state:
            st.session_state[_tar_key] = {n: _tar_default for n in active_feeds}
        # Retrocompat: se mancano chiavi per nuove biomasse
        for n in active_feeds:
            if n not in st.session_state[_tar_key]:
                st.session_state[_tar_key][n] = _tar_default

        _tot_mwh_basis_raw = sum(annual_mwh.values())  # MWh CH4 netto per biometano

        detail_rows = []
        pdf_revenue_rows = []  # raw numerics per il report PDF
        tot_n_cic = 0.0
        for n in active_feeds:
            t = annual_t[n]
            nm3_lordi = t * _yield_of(n)  # resa effettiva (BMT override se attivo)
            nm3_netti = nm3_lordi / aux_factor
            mwh_netti = nm3_netti * NM3_TO_MWH

            # DM 2022: tariffa diretta €/MWh
            mwh_revenue = mwh_netti
            tariffa = st.session_state[_tar_key][n]
            ricavi = mwh_revenue * tariffa
            n_cic = 0.0
            quota = ((mwh_netti / _tot_mwh_basis_raw * 100)
                     if _tot_mwh_basis_raw > 0 else 0)
            pdf_revenue_rows.append((n, {
                "t_anno": t,
                "yield": _yield_of(n),  # resa effettiva (BMT override se attivo)
                "mwh_netti": mwh_netti,
                "mwh_basis": mwh_revenue,  # base ricavi
                "tariffa": tariffa,
                "ricavi": ricavi,
                "quota": quota,
                "annex_ix": FEEDSTOCK_DB[n].get("annex_ix"),
                "n_cic": n_cic,
            }))
            row_detail = {
                "Biomassa": n,
                "t/anno (FM)":     fmt_it(t, 0),
                "Resa (Nm³/t)":    fmt_it(_yield_of(n), 0),  # resa effettiva
                "Sm³ netti/anno":  fmt_it(nm3_netti, 0),
                "MWh netti/anno":  fmt_it(mwh_netti, 1),
                "Quota % MWh":     fmt_it(quota, 1, "%"),
                f"Tariffa {_tar_unit}": fmt_it(tariffa, 2),
                "Ricavi €/anno":   fmt_it(ricavi, 0, " €"),
            }
            detail_rows.append(row_detail)
        df_detail = pd.DataFrame(detail_rows)

        detail_col_cfg = {
            "Biomassa":       st.column_config.TextColumn("Biomassa", disabled=True),
            "t/anno (FM)":    st.column_config.TextColumn("t/anno (FM)", disabled=True),
            "Resa (Nm³/t)":   st.column_config.TextColumn("Resa Nm³/t", disabled=True),
            "Sm³ netti/anno": st.column_config.TextColumn("Sm³ netti/anno", disabled=True),
            "MWh netti/anno": st.column_config.TextColumn("MWh netti/anno", disabled=True),
            "Quota % MWh":    st.column_config.TextColumn("Quota % MWh", disabled=True),
            "Ricavi €/anno": st.column_config.TextColumn(
                "Ricavi €/anno 🧮", disabled=True,
                help=f"MWh netti × tariffa {_tar_unit} (si ricalcola al variare dei parametri)",
            ),
            f"Tariffa {_tar_unit}": st.column_config.TextColumn(
                f"Tariffa {_tar_unit} ✏️",
                help=f"Tariffa incentivante/PPA [{_tar_unit}] in formato "
                     f"italiano (es. 1.234,56). Modificabile per simulazioni.",
            ),
        }

        edited_detail = st.data_editor(
            df_detail,
            column_config=detail_col_cfg,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key=f"editor_revenue_detail_{APP_MODE}",
        )

        # Se l'utente ha modificato una tariffa -> salva e rerun.
        # Clamp: tariffe negative non hanno senso fisico -> >=0.
        _tar_col = f"Tariffa {_tar_unit}"
        new_tariffs = {
            row["Biomassa"]: max(parse_it(row[_tar_col]), 0.0)
            for _, row in edited_detail.iterrows()
        }
        if new_tariffs != st.session_state[_tar_key]:
            st.session_state[_tar_key] = new_tariffs
            st.rerun()

        # ============================================================
        # TOTALI RICAVI (DM 2022 — tariffa diretta €/MWh)
        # ============================================================
        tot_mwh = sum(annual_mwh.values())
        tot_revenue_base_mwh = tot_mwh
        tot_revenue = sum(
            annual_mwh[n] * st.session_state[_tar_key][n]
            for n in active_feeds
        )
        tariffa_media_ponderata = (
            (tot_revenue / tot_revenue_base_mwh) if tot_revenue_base_mwh > 0 else 0.0
        )
        cA, cB, cC = st.columns(3)
        cA.metric("MWh netti totali/anno", fmt_it(tot_mwh, 0))
        cB.metric("Tariffa media ponderata",
                  fmt_it(tariffa_media_ponderata, 2, " €/MWh"))
        cC.metric("💰 Ricavi totali/anno", fmt_it(tot_revenue, 0, " €"))
        st.caption(
            f"📐 **Calcolo**: MWh netti/biomassa = t × resa_Nm³/t ÷ "
            f"{fmt_it(aux_factor, 2)} × 0,00997. "
            f"Ricavi/biomassa = MWh netti × tariffa €/MWh. "
            f"Modifica la colonna «Tariffa €/MWh» per simulare scenari diversi."
        )

    # ============================================================
    # TAB 5 — BUSINESS PLAN (DM 2022)
    # ============================================================
    if bp_result is not None:
        with tab5:
            st.markdown("<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:#726C5E; margin-bottom:8px;'>// PRO FORMA · DM 2022</div>", unsafe_allow_html=True)
            st.subheader(_t("💼 Ricavi Annui"))
            st.caption("Calcolo dei ricavi sulla base della tariffa incentivante (o premio) DM 2022 e della produzione di biometano.")

            bp_cA, bp_cB = st.columns(2)
            bp_cA.metric("Ricavi anno regime", fmt_it(bp_result["ricavo_annuo"]/1000, 0, " k€/a"), delta=f"{fmt_it(bp_result['biometano_mwh_anno'], 0)} MWh/a")
            bp_cB.metric("Tariffa applicata", fmt_it(bp_result["tariffa_eur_mwh"], 1, " €/MWh"), delta=f"Per {bp_result['durata_tariffa']} anni")

    # ============================================================
    # OUTPUT MODEL UNIFICATO (Fase 2 refactor)
    # ------------------------------------------------------------
    # Costruisce un'unica struttura `output_model` da cui leggono i nuovi
    # export modulari (CSV, e in futuro Excel/PDF). I percorsi legacy
    # restano attivi come fallback (try/except sotto).
    # ============================================================
    output_model = None
    if _HAS_OUTPUT_MODEL:
        try:
            _annual_t   = {n: float(max(df_res[n].sum(), 0.0)) for n in active_feeds}
            _annual_mwh = {
                n: float(max(df_res[n].sum(), 0.0)) * _yield_of(n) * NM3_TO_MWH / aux_factor
                for n in active_feeds
            }
            _om_ctx = {
                # Identita' / scenario
                "APP_MODE":          APP_MODE,
                "APP_MODE_LABEL":    _MODE["label"],
                "lang":              _LANG,
                # Impianto
                "plant_net_smch":    plant_net_smch,
                "aux_factor":        aux_factor,
                "ep_total":          ep_total,
                "end_use":           end_use,
                "ghg_threshold":     ghg_threshold,
                "fossil_comparator": FOSSIL_COMPARATOR,
                "upgrading_opt":     upgrading_opt,
                "offgas_opt":        offgas_opt,
                "injection_opt":     injection_opt,
                # Dati / DB
                "active_feeds":      active_feeds,
                "FEEDSTOCK_DB":      FEEDSTOCK_DB,
                # Tabella mensile e annuali
                "df_res":            df_res,
                "annual_t":          _annual_t,
                "annual_mwh":        _annual_mwh,
                "revenue_rows":      pdf_revenue_rows,
                # KPI aggregati
                "tot_biomasse_t":    float(df_res["Totale biomasse (t)"].sum()),
                "tot_sm3_netti":     float(df_res["Sm³ netti"].sum()),
                "tot_mwh_netti":     float(df_res["MWh netti"].sum()),
                "tot_mwh":           float(tot_mwh),
                "saving_avg":        saving_annuale_pesato(df_res, comparator=FOSSIL_COMPARATOR),
                "valid_months":      int(df_res["Validità"].str.startswith("✅").sum()),
                "tot_revenue":       float(tot_revenue),
                "tariffa_media_ponderata": float(tariffa_media_ponderata)
                                           if 'tariffa_media_ponderata' in dir() else 0.0,
                # Business plan DM 2022
                "bp_result":         bp_result,
                # Audit
                "yield_audit_rows":     list(_yield_audit_rows),
                "emission_audit_rows":  list(_emission_audit_rows),
                "emission_overrides":   dict(_EMISSION_OVERRIDES),
                "actual_yields": {_f: _yield_of(_f) for _f in active_feeds},
                "actual_emissions": {_f: _emission_factors_of(_f) for _f in active_feeds},
            }
            output_model = _build_output_model(_om_ctx)
        except Exception as _om_exc:  # noqa: BLE001
            output_model = None
            st.warning(
                "Output model non disponibile in questa run "
                f"(fallback al percorso legacy): {_om_exc}"
            )

    # ------------------------- EXPORT -------------------------
    st.divider()
    st.markdown(
        f"<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; "
        f"font-weight:600; letter-spacing:1.5px; text-transform:uppercase; "
        f"color:{TEXT_MUTED}; margin-bottom:10px;'>// EXPORT</div>",
        unsafe_allow_html=True,
    )
    st.caption(_t(
        "**Excel autocalcolante** ✏️: scarica il file `.xlsx`, modifica le "
        "celle gialle (Ore + Biomasse) direttamente in Excel/Numbers/LibreOffice "
        "e tutti i calcoli (produzione, saving GHG, validità) si aggiornano "
        "**istantaneamente** grazie alle formule live integrate. "
        "Niente upload, niente roundtrip — il file fa tutto da solo."
    ))

    # ===== Riga unica: 3 download (XLSX primario, PDF, CSV legacy) =====
    _dl_col1, _dl_col2, _dl_col_pptx, _dl_col3, _dl_col4 = st.columns([1.2, 1.0, 1.0, 0.8, 0.8])

    with _dl_col1:
        # XLSX autocalcolante: download primario
        try:
            # Pre-fill con lo stato corrente (input_df ha Mese, Ore, fixed_feeds;
            # le unknown sono in df_res — passiamo il merge completo).
            _initial_data = {}
            for _, row in df_res.iterrows():
                _initial_data[row["Mese"]] = {"Ore": int(row["Ore"])}
                for f in active_feeds:
                    if f in row:
                        _initial_data[row["Mese"]][f] = float(row[f])
            _xlsx_ctx = {
                "active_feeds": active_feeds,
                "FEEDSTOCK_DB": FEEDSTOCK_DB,
                "aux_factor":   aux_factor,
                "ep_total":     ep_total,
                "fossil_comparator": FOSSIL_COMPARATOR,
                "ghg_threshold":     ghg_threshold,
                "plant_net_smch":    plant_net_smch,
                "NM3_TO_MWH":        NM3_TO_MWH,
                "MONTHS":            MONTHS,
                "MONTH_HOURS":       MONTH_HOURS,
                "initial_data":      _initial_data,
                "APP_MODE_LABEL":    _MODE["label"],
                "end_use":           end_use,
            }
            # === Aggiunge contesto Business Plan ===
            # Tariffa effettiva DM 2022 (€/MWh) per la sheet "Business Plan".
            _bp_tariffa_mwh = (
                float(bp_tariffa_eff) if bp_result is not None else 131.0
            )

            # Ore anno default 8500 (puo' essere editato in Excel)
            _bp_ore_anno = 8500.0

            # CAPEX/OPEX defaults per BP: leggi dalle costanti
            _xlsx_ctx.update({
                "bp_tariffa_eff_mwh":        _bp_tariffa_mwh,
                "bp_ore_anno":               _bp_ore_anno,








                "bp_durata_tariffa":         BP_DURATA_TARIFFA_ANNI,
                "bp_pnrr_pct":               bp_pnrr_pct,


                "bp_tax_rate_pct":           BP_TAX_RATE_PCT,
                "bp_ammort_anni":            BP_AMMORTAMENTO_ANNI,
                "bp_npv_disc_rate_pct":      6.0,
                "bp_massimale_eur_per_smch": BP_MASSIMALE_SPESA_EUR_PER_SMCH,
                # CAPEX/OPEX breakdown rimosso
                "NM3_TO_MWH":                NM3_TO_MWH,
                "lang":                      _LANG,
                # === BMT override audit (resa effettiva vs standard) ===
                "yield_audit_rows":          list(_yield_audit_rows),
                "effective_yields":          dict(_EFFECTIVE_YIELDS),
                # === Audit fattori emissivi reali (relazione tecnica) ===
                "emission_audit_rows":       list(_emission_audit_rows),
                "emission_overrides":        dict(_EMISSION_OVERRIDES),
                # === Rese e fattori emissivi correnti ponderati/normalizzati ===
                "actual_yields":             {_f: _yield_of(_f) for _f in active_feeds},
                "actual_emissions":          {_f: _emission_factors_of(_f) for _f in active_feeds},
            })
            _xlsx_buf = build_metaniq_xlsx(_xlsx_ctx)
            _xlsx_data = _xlsx_buf.getvalue()
            _xlsx_ok = True
        except Exception as _xlsx_exc:  # noqa: BLE001
            _xlsx_data = None
            _xlsx_ok = False
            _xlsx_err = str(_xlsx_exc)

        if _xlsx_ok:
            st.download_button(
                _t("📊 Scarica Excel modificabile"),
                data=_xlsx_data,
                file_name=f"metaniq_{APP_MODE}_editabile.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
                help="Excel autocalcolante (.xlsx). Apri il file e modifica "
                     "DIRETTAMENTE in Excel le celle gialle (Ore + Biomasse). "
                     "Tutti gli altri valori (Sm³, MWh, e_w, saving %, "
                     "validità) si ricalcolano automaticamente in tempo "
                     "reale grazie alle formule live. 3 fogli: «Piano "
                     "mensile» (editabile), «Database feedstock» (yield/eec/"
                     "etd/esca/e_total), «Sintesi annuale» (KPI aggregati).",
            )
        else:
            st.error(f"Errore generazione XLSX: {_xlsx_err}")

    with _dl_col2:
        # Costruisce contesto e genera PDF on-demand (solo al click).
        # ReportLab pure Python -> nessuna dipendenza di sistema.
        _pdf_ctx = {
            "df_res": df_res,
            "APP_MODE": APP_MODE,
            "plant_net_smch": plant_net_smch,
            "aux_factor": aux_factor,
            "ep_total": ep_total,
            "end_use": end_use,
            "ghg_threshold": ghg_threshold,
            "fossil_comparator": FOSSIL_COMPARATOR,
            "upgrading_opt": upgrading_opt,
            "offgas_opt": offgas_opt,
            "injection_opt": injection_opt,
            # BP DM 2022
            "bp_result": bp_result,
            "bp_tariffa_eur_mwh": bp_tariffa_eur_mwh,
            "bp_ribasso_pct": bp_ribasso_pct,
            "bp_tariffa_eff": bp_tariffa_eff,
            "bp_pnrr_pct": bp_pnrr_pct,




            "bp_durata_tariffa": BP_DURATA_TARIFFA_ANNI,
            # Aggregati comuni
            "tot_biomasse_t": float(df_res["Totale biomasse (t)"].sum()),
            "tot_sm3_netti": float(df_res["Sm³ netti"].sum()),
            "tot_mwh_netti": float(df_res["MWh netti"].sum()),
            "saving_avg": saving_annuale_pesato(df_res, comparator=FOSSIL_COMPARATOR),
            "valid_months": int(df_res["Validità"].str.startswith("✅").sum()),
            "tot_revenue": float(tot_revenue),
            "tot_mwh_basis": float(tot_revenue_base_mwh),
            "tariffa_media_ponderata": float(tariffa_media_ponderata),
            "revenue_rows": pdf_revenue_rows,
            "lang":         _LANG,
            # === BMT override audit (resa effettiva vs standard) ===
            "yield_audit_rows": list(_yield_audit_rows),
            "effective_yields": dict(_EFFECTIVE_YIELDS),
            # === Audit fattori emissivi reali (relazione tecnica) ===
            "emission_audit_rows": list(_emission_audit_rows),
            "emission_overrides":  dict(_EMISSION_OVERRIDES),
            # === Anagrafica UNI/TS 11567:2024 (audit OdC) ===
            "company_name":             COMPANY_NAME,
            "company_legal_address":    COMPANY_LEGAL_ADDRESS,
            "plant_name":                PLANT_NAME,
            "plant_operational_address": PLANT_OPERATIONAL_ADDRESS,
            "company_vat":               COMPANY_VAT,
            "plant_cui":                 PLANT_CUI,
            "responsible_name":          RESPONSIBLE_NAME,
            # Periodo di rendicontazione (usato per ID Lotto di Sostenibilità).
            # Default: data corrente. La tab "Gestione Giornaliera" sovrascrive
            # con anno/mese reali del periodo selezionato dall'utente.
            "year":  st.session_state.get("daily_year")  or __import__("datetime").datetime.now().year,
            "month": st.session_state.get("daily_month") or __import__("datetime").datetime.now().month,
            # Espone FEEDSTOCK_DB al PDF per popolare la sezione mass balance
            # (Annex IX / categoria per ciascuna biomassa attiva).
            "FEEDSTOCK_DB":              FEEDSTOCK_DB,
            "feedstock_totals_t":        st.session_state.get("monthly_feed_totals", {}),
            "sm3_gross":                 st.session_state.get("monthly_sm3_gross", 0.0),
            "sm3_netti":                 st.session_state.get("monthly_sm3_netti", 0.0),
            "saving_threshold_pct":      float(ghg_threshold) * 100.0 if ghg_threshold else 80.0,
            "sustainability_basis":      "LORDO (RED III All. V Parte C)",
            # Registro fornitori biomassa (UNI/TS 11567 cap. 2-3)
            "suppliers_registry":        st.session_state.get("suppliers_registry", []),
        }
        try:
            _pdf_buf = build_metaniq_pdf(_pdf_ctx)
            _pdf_data = _pdf_buf.getvalue()
            _pdf_ok = True
        except Exception as _exc:  # noqa: BLE001
            _pdf_data = None
            _pdf_ok = False
            _pdf_err = str(_exc)
        if _pdf_ok:
            st.download_button(
                _t("📄 Scarica Report PDF"),
                data=_pdf_data,
                file_name=f"metaniq_{APP_MODE}_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                help="Report PDF consulting-grade: cover, executive summary, "
                     "configurazione impianto, pianificazione mensile, "
                     "analisi ricavi, riferimenti normativi.",
            )
        else:
            st.error(f"Errore generazione PDF: {_pdf_err}")

    # ===== Colonna PPTX: Esportazione in PowerPoint =====
    with _dl_col_pptx:
        try:
            from export.pptx_export import build_metaniq_pptx
            _pptx_buf = build_metaniq_pptx(_pdf_ctx)
            _pptx_data = _pptx_buf.getvalue()
            _pptx_ok = True
        except Exception as _exc:  # noqa: BLE001
            _pptx_data = None
            _pptx_ok = False
            _pptx_err = str(_exc)
        
        if _pptx_ok:
            st.download_button(
                _t("📊 Presentazione PPTX"),
                data=_pptx_data,
                file_name=f"metaniq_{APP_MODE}_presentazione.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
                type="primary",
                help="Scarica una presentazione di 8 slide ad alto impatto con i risultati del progetto (stile moderno).",
            )
        else:
            st.error(f"Errore generazione PPTX: {_pptx_err}")

    # ===== Colonna 3: XLSX SNAPSHOT (read-only, valori statici) =====
    with _dl_col3:
        try:
            # Riusa lo stesso ctx dell'editabile, aggiungiamo df_res per i valori
            _xlsx_snap_ctx = dict(_xlsx_ctx)
            _xlsx_snap_ctx["df_res"] = df_res
            _xlsx_snap_buf = build_metaniq_xlsx(_xlsx_snap_ctx, snapshot=True)
            _xlsx_snap_data = _xlsx_snap_buf.getvalue()
            _xlsx_snap_ok = True
        except Exception as _xs_exc:  # noqa: BLE001
            _xlsx_snap_data = None
            _xlsx_snap_ok = False
            _xlsx_snap_err = str(_xs_exc)
        if _xlsx_snap_ok:
            st.download_button(
                _t("📋 Excel snapshot"),
                data=_xlsx_snap_data,
                file_name=f"metaniq_{APP_MODE}_snapshot.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
                help="Excel di sola lettura (snapshot dei numeri attuali, "
                     "no formule). Stessa estetica del file modificabile ma "
                     "con valori cristallizzati - ideale per archivio, "
                     "condivisione e print. Per modificare ore/biomasse usa "
                     "l'Excel modificabile a sinistra.",
            )
        else:
            st.error(f"Errore snapshot: {_xlsx_snap_err}")

    # ===== Colonna 4: CSV (piano mensile con intestazioni tradotte) =====
    with _dl_col4:
        _csv_data = None
        _csv_ok = False
        _csv_err = ""
        # Percorso nuovo (output_model) — se disponibile e abilitato.
        if _HAS_OUTPUT_MODEL and output_model is not None:
            try:
                _csv_data = _build_csv_from_output(output_model, sheet="monthly")
                _csv_ok = True
            except Exception as _csv_om_exc:  # noqa: BLE001
                _csv_ok = False
                _csv_err = f"output_model CSV: {_csv_om_exc}"
        # Fallback legacy
        if not _csv_ok:
            try:
                _csv_df = translate_df(df_res.copy(), _LANG)
                _csv_data = _csv_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
                _csv_ok = True
                _csv_err = ""
            except Exception as _csv_exc:
                _csv_data = None
                _csv_ok = False
                _csv_err = str(_csv_exc)
        if _csv_ok:
            _csv_fn = f"metaniq_{APP_MODE}_{'monthly_plan' if _LANG=='en' else 'piano_mensile'}.csv"
            st.download_button(
                _t("📥 Scarica CSV"),
                data=_csv_data,
                file_name=_csv_fn,
                mime="text/csv",
                use_container_width=True,
                type="secondary",
                help="CSV del piano mensile con intestazioni tradotte." if _LANG != "en"
                     else "CSV of the monthly plan with translated headers.",
            )
        else:
            st.error(f"CSV error: {_csv_err}")

    st.caption(
        "ℹ️ Database feedstock: letteratura tecnica / UNI/TS 11567:2024 / parametri "
        "Consorzio Monviso. Manure credit -45 gCO₂/MJ incorporato in `eec` "
        "(pollina ovaiole, liquame suino). Per certificazione GSE sostituire con "
        "valori reali d'impianto."
    )

    # ============================================================
    # ORIGINE DEI DATI E METODO DI CALCOLO  (Fase 2 refactor)
    # ------------------------------------------------------------
    # Sezione esplicativa unica che documenta provenienza rese, fattori
    # emissivi, metodo GHG e base normativa. Letta dall'output_model
    # explanations (con fallback a chiamate dirette per robustezza).
    # ============================================================
    if _HAS_OUTPUT_MODEL:
        try:
            _expl_ctx = {
                "lang":                 _LANG,
                "APP_MODE":             APP_MODE,
                "yield_audit_rows":     list(_yield_audit_rows),
                "emission_audit_rows":  list(_emission_audit_rows),
            }
            _expl = (output_model or {}).get("explanations") or {
                "yield_origin":           _explain_yield_origin(_expl_ctx),
                "emission_factor_origin": _explain_emission_factor_origin(_expl_ctx),
                "ghg_method":             _explain_ghg_method(_expl_ctx),
                "regulatory_basis":       _explain_regulatory_basis(_expl_ctx),
            }
            with st.expander(_t(
                "📚 Origine dei dati e metodo di calcolo "
                "(rese, fattori emissivi, GHG, base normativa)"),
                expanded=False,
            ):
                st.markdown(f"**{_t('Origine delle rese biomassa')}**")
                st.text(_expl.get("yield_origin", ""))
                st.markdown(f"**{_t('Origine dei fattori emissivi')}**")
                st.text(_expl.get("emission_factor_origin", ""))
                st.markdown(f"**{_t('Metodo di calcolo GHG (RED III)')}**")
                st.text(_expl.get("ghg_method", ""))
                st.markdown("**Base normativa applicata**")
                st.text(_expl.get("regulatory_basis", ""))
        except Exception as _expl_exc:  # noqa: BLE001
            st.caption(f"(Sezione spiegazioni non disponibile: {_expl_exc})")

    # =================================================================
    # 💼 BUSINESS PLAN COMPLETO (15 anni)
    # ------------------------------------------------------------
    # Sezione dedicata al BP economico-finanziario multi-anno con
    # IRR Project, IRR Equity, NPV @ WACC, Payback. Form CAPEX/OPEX
    # customizzabile. Output: tabella + grafico cash flow cumulato.
    # =================================================================
    st.divider()
    st.header("💼 " + _t("Business Plan Completo (15 anni)"))
    st.caption(_t(
        "Engine finanziario multi-anno con IRR, NPV, Payback. "
        "Personalizza CAPEX/OPEX/finanziamento per ottenere un piano economico "
        "accurato del tuo impianto. Default basati su benchmark settore 2025."
    ))

    try:
        from core.business_plan import (
            build_business_plan as _build_bp,
            DEFAULT_LEVERAGE_PCT,
            DEFAULT_INTEREST_RATE_PCT,
            DEFAULT_TAX_RATE_PCT,
            DEFAULT_INFLATION_PCT,
            DEFAULT_DISCOUNT_RATE_PCT,
            DEFAULT_LOAN_DURATION_YEARS,
        )
        from core.calculation_engine import (
            BP_CAPEX_DEFAULTS_PER_SMCH as _BP_CAPEX_D,
            BP_OPEX_DEFAULTS_PER_SMCH_YEAR as _BP_OPEX_D,
        )

        _default_capex = float(_BP_CAPEX_D.get(bp_plant_type,
                                                _BP_CAPEX_D.get("nuova_costruzione", 38_000)))
        _default_opex = float(sum(_BP_OPEX_D.values()) if _BP_OPEX_D else 5_350)

        with st.expander("⚙️ " + _t("Parametri CAPEX / OPEX / Finanziamento"),
                          expanded=False):
            _bpc1, _bpc2 = st.columns(2)
            with _bpc1:
                st.markdown("**" + _t("Investimento (CAPEX)") + "**")
                _bp_capex_unit = st.number_input(
                    "CAPEX €/Smc/h", min_value=5_000.0, max_value=80_000.0,
                    value=_default_capex, step=500.0, key="bp_input_capex",
                    help=_t("Benchmark settore 2025: 30-45k €/Smc/h "
                            "per nuova costruzione chiavi in mano"),
                )
                _bp_pnrr = st.slider(
                    "PNRR % " + _t("a fondo perduto"),
                    min_value=0.0, max_value=100.0, value=0.0, step=5.0,
                    key="bp_input_pnrr",
                    help=_t("Quota CAPEX coperta da contributo PNRR. "
                            "Tipico 30-40% se selezionato"),
                )
            with _bpc2:
                st.markdown("**" + _t("Costi operativi (OPEX)") + "**")
                _bp_opex_unit = st.number_input(
                    "OPEX €/Smc/h/anno",
                    min_value=1_000.0, max_value=15_000.0,
                    value=_default_opex, step=100.0, key="bp_input_opex",
                    help=_t("Manutenzione + personale + elettricità + "
                            "consumabili + assicurazioni + monitoraggio"),
                )
                _bp_inflation = st.slider(
                    _t("Inflazione OPEX") + " %",
                    min_value=0.0, max_value=8.0, value=DEFAULT_INFLATION_PCT,
                    step=0.1, key="bp_input_inflation",
                )

            st.markdown("**" + _t("Finanziamento") + "**")
            _bpf1, _bpf2, _bpf3, _bpf4 = st.columns(4)
            _bp_leverage = _bpf1.slider(
                _t("Leva debito") + " %",
                min_value=0.0, max_value=90.0, value=DEFAULT_LEVERAGE_PCT,
                step=5.0, key="bp_input_leverage",
            )
            _bp_rate = _bpf2.slider(
                _t("Tasso interesse") + " %",
                min_value=0.0, max_value=12.0, value=DEFAULT_INTEREST_RATE_PCT,
                step=0.25, key="bp_input_rate",
            )
            _bp_loan = _bpf3.slider(
                _t("Durata mutuo") + " (" + _t("anni") + ")",
                min_value=5, max_value=20,
                value=DEFAULT_LOAN_DURATION_YEARS, step=1,
                key="bp_input_loan",
            )
            _bp_discount = _bpf4.slider(
                _t("WACC discount") + " %",
                min_value=2.0, max_value=15.0, value=DEFAULT_DISCOUNT_RATE_PCT,
                step=0.5, key="bp_input_discount",
            )

        # Persisto override per hero KPI in cima
        st.session_state["_bp_hero_overrides"] = {
            "capex_unit": _bp_capex_unit,
            "opex_unit": _bp_opex_unit,
            "pnrr_pct": _bp_pnrr,
        }

        _bp = _build_bp(
            plant_smch=plant_net_smch,
            tariffa_eur_mwh=bp_tariffa_eff,
            capex_eur_per_smch=_bp_capex_unit,
            opex_eur_per_smch_year=_bp_opex_unit,
            pnrr_quota_pct=_bp_pnrr,
            leverage_pct=_bp_leverage,
            interest_rate_pct=_bp_rate,
            loan_duration_years=int(_bp_loan),
            tax_rate_pct=DEFAULT_TAX_RATE_PCT,
            inflation_pct=_bp_inflation,
            discount_rate_pct=_bp_discount,
        )

        # KPI sintetici BP
        _bpk1, _bpk2, _bpk3, _bpk4, _bpk5 = st.columns(5)
        _bpk1.metric(_t("CAPEX totale"),
                      f"{fmt_it(_bp.capex_total / 1_000_000, 2)} M€")
        _bpk2.metric(_t("Equity richiesto"),
                      f"{fmt_it(_bp.capex_equity / 1_000_000, 2)} M€",
                      delta=f"PNRR: {fmt_it(_bp.pnrr_grant / 1_000_000, 2)} M€"
                            if _bp.pnrr_grant > 0 else None)
        _bpk3.metric("IRR Equity",
                      f"{_bp.irr_equity * 100:.1f}%"
                      if -1 < _bp.irr_equity < 10 else "—",
                      help=_t("Rendimento interno sul capitale proprio investito"))
        _bpk4.metric("NPV @ " + f"{_bp.discount_rate_pct:.1f}%",
                      f"{fmt_it(_bp.npv_project / 1_000_000, 2)} M€",
                      help=_t("Valore Attuale Netto del progetto scontato a WACC"))
        _bpk5.metric(_t("Payback"),
                      f"{_bp.payback_years:.2f} {_t('anni')}"
                      if _bp.payback_years else "—",
                      help=_t("Anni per recuperare l'equity investito"))

        # Tabella BP 15 anni
        import pandas as _pd_bp
        _bp_df = _pd_bp.DataFrame([{
            _t("Anno"): r.year,
            _t("Ricavi"): r.ricavi,
            _t("OPEX"): r.opex,
            "EBITDA": r.ebitda,
            _t("Interessi"): r.interessi,
            _t("Imposte"): r.imposte,
            _t("CFO"): r.cfo,
            _t("Rata capitale"): r.rata_capitale,
            "FCF Equity": r.fcf_equity,
            _t("Debito residuo"): r.debito_residuo,
            _t("FCF cumulato"): r.fcf_cumulato,
        } for r in _bp.rows])
        st.dataframe(_bp_df.style.format({
            c: "{:,.0f}" for c in _bp_df.columns if c != _t("Anno")
        }), use_container_width=True, hide_index=True)

        # Grafico cash flow cumulato
        try:
            import plotly.graph_objects as _go_bp
            _bp_fig = _go_bp.Figure()
            _bp_fig.add_trace(_go_bp.Bar(
                x=[r.year for r in _bp.rows],
                y=[r.fcf_equity for r in _bp.rows],
                name="FCF Equity",
                marker_color=["#DC2626" if r.fcf_equity < 0 else "#059669"
                              for r in _bp.rows],
            ))
            _bp_fig.add_trace(_go_bp.Scatter(
                x=[r.year for r in _bp.rows],
                y=[r.fcf_cumulato for r in _bp.rows],
                name=_t("FCF cumulato"),
                mode="lines+markers",
                line=dict(color="#9A7B3C", width=3),
            ))
            _bp_fig.add_hline(y=0, line_dash="dash", line_color="#A49D8C")
            _bp_fig.update_layout(
                title=_t("Cash Flow Equity per anno + Cumulato (break-even visivo)"),
                xaxis_title=_t("Anno"),
                yaxis_title="€",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(_bp_fig, use_container_width=True)
        except Exception:  # noqa: BLE001
            pass
    except Exception as _bp_exc:  # noqa: BLE001
        _LOG.warning("Business Plan completo render failed: %s", _bp_exc)
        st.warning(f"⚠️ Business Plan non disponibile: {_bp_exc}")

    # ============================================================

with tab_daily:
    _render_daily_ops_panel()


# =============================================================================
# FOOTER SIDEBAR — link legali (Privacy, Terms, License) come expander
# Compare in fondo alla sidebar. Espandere mostra il contenuto inline.
# =============================================================================
def _load_legal_text(filename: str) -> str:
    """Best-effort load di un file markdown legale; restituisce stringa
    placeholder se non disponibile (es. deploy che non include legal/)."""
    try:
        p = Path(__file__).resolve().parent / "legal" / filename
        if p.is_file():
            return p.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return f"_({_t('Documento non disponibile')} — {filename})_"


with st.sidebar:
    st.markdown(
        "<div style='margin-top:24px; padding-top:14px; "
        "border-top:1px solid rgba(148,163,184,0.18);'></div>",
        unsafe_allow_html=True,
    )
    # Manuale Utente — PDF bilingue (servito in base alla lingua attiva _LANG)
    with st.expander("📖 " + _t("Manuale Utente"), expanded=False):
        _manual_lang_code = "EN" if str(_LANG).lower().startswith("en") else "IT"
        _manual_filename = f"Metan.iQ_Manuale_Utente_{_manual_lang_code}.pdf"
        _manual_path = (
            Path(__file__).resolve().parent
            / "docs" / "user_manual" / _manual_filename
        )
        # Fallback al PDF italiano se versione lingua mancante
        if not _manual_path.is_file():
            _manual_path = (
                Path(__file__).resolve().parent
                / "docs" / "user_manual" / "Metan.iQ_Manuale_Utente_IT.pdf"
            )
            _manual_filename = "Metan.iQ_Manuale_Utente_IT.pdf"
        if _manual_path.is_file():
            st.caption(_t(
                "Guida operativa completa: funzioni, calcoli GHG, workflow, "
                "vincoli normativi, FAQ. 12 capitoli + 3 appendici."
            ))
            try:
                _manual_bytes = _manual_path.read_bytes()
                st.download_button(
                    "⬇️ " + _t("Scarica Manuale (PDF)"),
                    data=_manual_bytes,
                    file_name=_manual_filename,
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_user_manual_sidebar",
                )
            except Exception as _man_exc:  # noqa: BLE001
                st.caption(_t("Manuale non disponibile") + f" ({_man_exc})")
        else:
            st.caption(_t("Manuale non disponibile."))
    with st.expander("📜 " + _t("Termini & Privacy"), expanded=False):
        _legal_t1, _legal_t2, _legal_t3 = st.tabs([
            _t("Privacy"), _t("Termini di Servizio"), _t("Licenza"),
        ])
        with _legal_t1:
            st.markdown(_load_legal_text("privacy.md"))
        with _legal_t2:
            st.markdown(_load_legal_text("terms.md"))
        with _legal_t3:
            try:
                _lic_path = Path(__file__).resolve().parent / "LICENSE"
                st.text(_lic_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                st.caption(_t("Licenza non disponibile."))
    st.markdown(
        f"<div style='font-size:0.65rem; color:#94A3B8; margin-top:6px; "
        f"text-align:center; opacity:0.8;'>"
        f"© 2026 Carlo Sicurini · Metan.iQ · v{_APP_VERSION}<br/>"
        f"<span style='font-size:0.6rem;'>{_html.escape(_t('Tutti i diritti riservati'))}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
