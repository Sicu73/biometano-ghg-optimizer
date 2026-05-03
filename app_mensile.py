# -*- coding: utf-8 -*-
"""
BioMethane Monthly Planner - Dual-Constraint Solver
---------------------------------------------------
Impianto 300 Sm3/h NETTI (DM 15/09/2022, PNRR).
Biomasse: Trinciato di mais, Trinciato di sorgo, Pollina ovaiole, Liquame suino.

Due modalita':
  A) 2 biomasse fisse + 2 calcolate -> soddisfa SIA produzione SIA saving 81%
  B) 3 biomasse fisse + 1 calcolata -> soddisfa solo produzione (saving residuo)

Riferimenti:
- RED III (Dir. 2023/2413) Allegato V Parte C
- UNI/TS 11567:2024
- DM 07/08/2024 (implementazione nazionale)
- Parametri feedstock: letteratura tecnica e valori tipici Consorzio Monviso
"""

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

# ── i18n: selettore lingua + funzione di traduzione ──────────────────────────
from i18n_runtime import t as _t, get_lang, render_lang_selector, translate_df

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
# REGISTRO NORMATIVA — verifica aggiornamenti via GitHub
# ============================================================
# Il file normativa_versions.json contiene tutte le norme (RED III,
# DM 2018, DM 2022, DM 2012, FER 2, GSE LG, UNI/TS, JEC) cablate nel
# codice + i valori-chiave codificati. Aggiornarlo (commit) quando si
# applica una modifica al codice o si aggiunge una nuova norma.
NORMATIVA_LOCAL_PATH = Path(__file__).parent / "normativa_versions.json"
NORMATIVA_REMOTE_URL = (
    "https://raw.githubusercontent.com/Sicu73/biometano-ghg-optimizer/"
    "master/normativa_versions.json"
)


def _load_normativa_local() -> dict:
    """Carica il JSON normativa locale dal repo (sempre disponibile)."""
    try:
        with open(NORMATIVA_LOCAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"File locale non trovato: {exc}"}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_normativa_remote(url: str = NORMATIVA_REMOTE_URL) -> dict:
    """Scarica il JSON normativa dal master GitHub. Cache 5 minuti."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Metan.iQ/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"GitHub fetch fallito: {exc}"}


# ============================================================
# FORMATO ITALIANO: punto = migliaia, virgola = decimali
# ============================================================
# ============================================================
# Metan.iQ chart theme — palette consulting-grade Navy/Amber
# Applicato a tutti i Plotly figs via apply_metaniq_theme(fig)
# ============================================================
METANIQ_PALETTE = [
    "#0F172A",  # navy 900 (primary)
    "#F59E0B",  # amber 500 (accent)
    "#0E9384",  # teal 600
    "#1E40AF",  # blue 800
    "#B45309",  # amber 700
    "#065F46",  # emerald 800
    "#7C3AED",  # violet 600
    "#475569",  # slate 600
    "#0891B2",  # cyan 600
    "#9F1239",  # rose 800
]

def apply_metaniq_theme(fig, *, dark: bool = False):
    """Applica palette + tipografia Metan.iQ a una figure Plotly."""
    text_color = "#F1F5F9" if dark else "#0F172A"
    grid_color = "rgba(148, 163, 184, 0.18)" if dark else "rgba(15, 23, 42, 0.08)"
    axis_color = "#475569" if dark else "#64748B"
    fig.update_layout(
        font=dict(family="Inter, -apple-system, sans-serif",
                  color=text_color, size=12),
        title_font=dict(family="Space Grotesk, Inter, sans-serif",
                        size=15, color=text_color),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=METANIQ_PALETTE,
        margin=dict(l=50, r=20, t=60, b=40),
        legend=dict(
            font=dict(family="Inter, sans-serif", size=11, color=text_color),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            font=dict(family="JetBrains Mono, monospace", size=11),
            bgcolor="#0F172A",
            bordercolor="#F59E0B",
            font_color="#F1F5F9",
        ),
        separators=",.",
    )
    fig.update_xaxes(
        gridcolor=grid_color, gridwidth=1,
        zerolinecolor=grid_color,
        tickfont=dict(family="JetBrains Mono, monospace",
                      size=10, color=axis_color),
        title_font=dict(family="Inter, sans-serif",
                        size=11, color=axis_color),
        showline=True, linewidth=1, linecolor=grid_color,
    )
    fig.update_yaxes(
        gridcolor=grid_color, gridwidth=1,
        zerolinecolor=grid_color,
        tickfont=dict(family="JetBrains Mono, monospace",
                      size=10, color=axis_color),
        title_font=dict(family="Inter, sans-serif",
                        size=11, color=axis_color),
        showline=False,
    )
    return fig


def fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:
    """Formatta un numero in stile italiano: 1.234.567,89

    signed=True -> prefisso '+' anche per valori positivi (utile per contributi ep).
    """
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "-"
    if signed:
        s = f"{value:+,.{decimals}f}"      # es. "+1,234.50" / "-4.00"
    else:
        s = f"{value:,.{decimals}f}"       # es. "1,234,567.89"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


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
    s = str(value).strip().replace("€", "").replace("%", "").strip()
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
COMPARATOR_CHP = 183.0   # biogas -> CHP -> elettricita' (mix EU)
FOSSIL_COMPARATOR = 80.0  # default biometano->rete; aggiornato dinamicamente
# Le soglie RED III variano per uso finale: 80% elettricita'/calore, 65% trasporti
LHV_BIOMETHANE = 35.9                          # MJ/Nm3 (97% CH4)
NM3_TO_MWH = 0.00997                           # 1 Nm3 -> MWh (PCI biometano)
DEFAULT_AUX_FACTOR = 1.29                      # netto -> lordo (CHP+caldaia)
DEFAULT_PLANT_NET_SMCH = 300.0                 # Sm3/h netti autorizzati (default)

# ============================================================
# COSTANTI BIOGAS CHP (modalita' cogenerazione)
# ============================================================
# Efficienze di default motore cogeneratore (CHP ad alto rendimento):
ETA_EL_DEFAULT = 0.40        # efficienza elettrica (40% tipica motori 500-1000 kWe)
ETA_TH_DEFAULT = 0.42        # efficienza termica (42% tipica con recupero fumi+acqua)
AUX_EL_DEFAULT = 0.08        # autoconsumo elettrico (pompe, agitatori, upgrading off)
# Default potenza CHP: 999 kWe (taglia tipica biogas agricolo <1 MWe - TO GSE)
DEFAULT_PLANT_KWE = 999.0

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
# DM 2 MARZO 2018 — Sistema CIC (Certificati Immissione in Consumo)
# ============================================================
# Riferimenti: DM 2/3/2018 (Decreto Biometano), aggiornato DM 15/9/2022
# e D.Lgs. 199/2021 (recepimento RED II).
#
# Conversione energia <-> CIC:
#   1 CIC = 10 Gcal = 11,628 MWh (1 toe = tonnellata di olio equivalente)
#   1 Gcal = 4,184 GJ = 1,1628 MWh
#
# Double counting biometano AVANZATO (matrici Annex IX RED II/III):
#   Il biometano avanzato vale doppio per la quota d'obbligo CIC
#   -> equivalente a 1 CIC ogni 5 Gcal (5,814 MWh) anziche' 10
#   -> n_CIC_avanzato = (energia / 10 Gcal) x 2
#
# Valore CIC: GSE ritira a prezzo regolato (~375 EUR base, variabile
# per anno di emissione e tipologia trasporti / altri usi). Sul
# mercato i CIC scambiati possono valere di piu' (rilancio scarsita').
#
# Soglia "biometano avanzato a livello di impianto":
#   Per qualificare l'IMPIANTO come avanzato, la matrice in input deve
#   essere prevalentemente Annex IX. Soglia operativa GSE: >= 70%
#   in massa di feedstock Annex IX (in Italia spesso interpretato
#   come 100% per evitare contestazioni). Default app: 70% con
#   override manuale.
# ============================================================
GCAL_PER_MWH       = 1.0 / 1.1628                  # ~0,860 Gcal per MWh
MWH_PER_GCAL       = 1.1628                        # 1 Gcal -> MWh
GCAL_PER_CIC       = 10.0                          # 1 CIC = 10 Gcal (= 1 toe)
MWH_PER_CIC        = GCAL_PER_CIC * MWH_PER_GCAL   # ~11,628 MWh per CIC
CIC_PRICE_DEFAULT  = 375.0                         # EUR/CIC base GSE
ANNEX_IX_THRESHOLD = 0.70                          # quota minima per "avanzato"

# Soglie saving GHG e comparator per DM 2018 (RED II / III recepito).
# Per trasporti: 50% impianti operativi pre-1/1/2021, 65% post.
# Per altri usi (rete/calore) e cogenerazione: 70% (RED II); 80% RED III nuovi.
DM2018_END_USES = {
    "Trasporti (BioGNL/BioCNG)":               {"sav": 0.65, "cmp": 94.0,
                                                "cic_premium": True},
    "Trasporti — impianti pre-1/1/2021":       {"sav": 0.50, "cmp": 94.0,
                                                "cic_premium": True},
    "Altri usi (rete gas / calore)":           {"sav": 0.70, "cmp": 80.0,
                                                "cic_premium": False},
    "Cogenerazione ad alto rendimento (CAR)":  {"sav": 0.70, "cmp": 80.0,
                                                "cic_premium": False},
}

# ============================================================
# DM 18 SETTEMBRE 2024 — "FER 2" / Biogas CHP piccoli impianti agricoli
# ============================================================
# Riferimenti: DM 18/9/2024 (Decreto FER 2), focus piccoli impianti
# biogas cogenerativi <= 300 kWe destinati ad agricoltura sostenibile.
#
# Caratteristiche normative:
#   - Taglia massima: 300 kWe (hard cap)
#   - Periodo incentivazione: 20 anni
#   - Matrice obbligatoria: >= 80% in MASSA da sottoprodotti, effluenti
#     zootecnici, residui colturali, FORSU. Cap colture dedicate <= 20%.
#   - Tariffa di Riferimento (TR) base: ~256 EUR/MWh_el (configurabile,
#     dipende da fascia/asta/registro). Default app: 256.
#   - Premio matrice: +30 EUR/MWh_el se >= 80% sottoprodotti/effluenti
#   - Premio CAR (Cogenerazione ad Alto Rendimento, PES > 10%): +10 EUR/MWh_el
#   - Soglia saving GHG: 80% RED III (comparator 183 gCO2/MJ mix EU)
#   - Tariffa applicata ai MWh elettrici NETTI immessi in rete
#     (lordo motore meno autoconsumi ausiliari)
#
# NB: i numeri esatti di tariffa e premi possono cambiare per asta/anno.
# I default qui sotto sono indicativi e configurabili dall'utente in app.
# ============================================================
FER2_KWE_CAP                  = 300.0    # kWe hard cap
DEFAULT_PLANT_KWE_FER2        = 250.0    # default plant size (sotto cap)
FER2_TARIFFA_BASE_DEFAULT     = 256.0    # EUR/MWh_el (TR base)
FER2_PREMIO_MATRICE_DEFAULT   = 30.0     # EUR/MWh_el (>=80% sottoprodotti)
FER2_PREMIO_CAR_DEFAULT       = 10.0     # EUR/MWh_el (CAR PES>10%)
FER2_FEEDSTOCK_REQ_THRESHOLD  = 0.80     # quota minima sottoprodotti/effluenti
FER2_PERIODO_ANNI             = 20       # durata incentivo (anni)
FER2_GHG_THRESHOLD            = 0.80     # RED III electricity

# ============================================================
# BUSINESS PLAN — DEFAULTS BENCHMARK (DM 2022 biometano)
# ============================================================
# Default derivati dal benchmark di un impianto medio biometano agricolo
# (250 Smc/h, costi medi di settore 2024) e adeguati 2026 con
# inflazione ISTAT 2024-2026 (~5% cumulato), tassi finanziamento
# aggiornati (BCE in calo) e prezzi materiali/manodopera.
#
# CAPEX intensity: €/(Smc/h) - normalizzazione su taglia 250 Smc/h.
# OPEX intensity: €/anno per (Smc/h) - normalizzazione lineare.
#
# Riferimento: impianto medio biometano agricolo, 250 Smc/h,
# CAPEX ~€10,35M, OPEX ~€477k/anno, tariffa GSE 124,48 €/MWh
# (storico 2024) - 1% ribasso d'asta tipico.
# ============================================================
BP_CAPEX_DEFAULTS_PER_SMCH = {
    # Macrovoci principali (€/(Smc/h)). Costi medi settore, ricalibrato +5% al 2026.
    "Movimenti terra":        3105.0,   # 739k/250 * 1.05 = 3105
    "Opere civili":          10428.0,   # 2.483k/250 * 1.05 = 10428
    "Impianto tecnologico":  15960.0,   # 3.800k/250 * 1.05 = 15960
    "Sezione upgrading":      9870.0,   # 2.350k/250 * 1.05 = 9870
    "Varie (antincendio, ill., recinzione, uffici)": 1777.0,  # 423k/250 * 1.05
}
# Voci forfait (non scalano linearmente con la taglia)
BP_CAPEX_FORFAIT_DEFAULTS = {
    "Connessione ENEL":          92000.0,
    "Connessione SNAM":               0.0,   # spesso caparra non onere
    "Acquisto terreno":         262000.0,
    "Progettazione e autorizzazioni": 65000.0,
    "Direzione lavori / CSE":    34000.0,
    "Altre spese":              105000.0,    # +5% vs 2024
}
BP_OPEX_DEFAULTS_PER_SMCH_YEAR = {
    "O&M digestione anaerobica":   210.0,    # 50k/250 * 1.05 = 210
    "O&M upgrading":               428.0,    # 102k/250 * 1.05 = 428
    "Service BMH":                 126.0,    # 30k/250 * 1.05 = 126
    "Gestore d'impianto":          630.0,    # 150k/250 * 1.05 = 630
    "Service amministrativo":       63.0,    # 15k/250 * 1.05
    "Service gestionale":          147.0,    # 35k/250 * 1.05
    "Adempimenti comune":          126.0,    # 30k/250 * 1.05
    "Energia elettrica":            13.0,    # 3k/250 * 1.05
    "Certificazioni / analisi":     34.0,    # 8k/250 * 1.05
    "Varie operative":              63.0,    # 15k/250 * 1.05
}
BP_OPEX_FORFAIT_DEFAULTS = {
    "Assicurazioni":   26000.0,
    "Tasse fisse":     10000.0,
}

# Schema finanziario — default benchmark impianto medio aggiornati al 2026
BP_FINANCE_DEFAULTS = {
    # Anticipo contributo PNRR (rimborsato anno 1)
    "anticipo_tasso":        5.0,    # % annuo
    "anticipo_durata":       1,      # anni
    # Finanziamento bancario lungo termine
    "lt_tasso":              4.0,    # % annuo (era 4,5 nel 2024, ora ~4)
    "lt_durata":             15,     # anni
    "lt_leva":               80.0,   # % CAPEX netto
    # Equity / soci
    "equity_tasso":          4.0,    # % annuo
    "equity_durata":         15,     # anni
    # Capitale circolante
    "tempo_incasso_gg":      60,     # gg fatturazione GSE
    "tempo_pagam_biomassa":  365,    # gg pagamento biomasse (consorzio agricolo)
    "tempo_pagam_altri":     60,     # gg altri pagamenti
}

# Tariffa biometano DM 2022 (aggiornamento 2026)
BP_TARIFFA_BASE_2026          = 131.0    # €/MWh (124,48 base 2024 + ISTAT)
BP_RIBASSO_DEFAULT_PCT        = 1.0      # % ribasso d'asta tipico (0-30%)
BP_DURATA_TARIFFA_ANNI        = 15       # DM 2022
BP_INFLAZIONE_DEFAULT_PCT     = 2.5      # % annua per OPEX
BP_AMMORTAMENTO_ANNI          = 22       # impianti biometano (10% media DLgs 38/2018)
BP_TAX_RATE_PCT               = 24.0     # IRES (no IRAP qui per semplicita')
BP_PNRR_QUOTA_PCT_DEFAULT     = 40.0     # % contributo a fondo perduto (M2C2)
BP_MASSIMALE_SPESA_EUR_PER_SMCH = 32817.23  # massimale GSE


def compute_business_plan(
    plant_smch: float,
    tariffa_eur_mwh: float,
    capex_breakdown: dict,
    capex_forfait: dict,
    opex_breakdown: dict,
    opex_forfait: dict,
    pnrr_quota_pct: float,
    inflazione_pct: float,
    finance: dict,
    target_ebitda_margin_pct: float = 25.0,   # margine EBITDA target ricavi
    durata_tariffa: int = BP_DURATA_TARIFFA_ANNI,
    ammort_anni: int = BP_AMMORTAMENTO_ANNI,
    tax_rate_pct: float = BP_TAX_RATE_PCT,
    massimale_eur_per_smch: float = BP_MASSIMALE_SPESA_EUR_PER_SMCH,
    ore_anno: float = 8500.0,
    pci_kwh_per_smc: float = 9.97,
    ch4_in_biogas_pct: float = 54.25,         # % CH4 nel biogas (tipico)
) -> dict:
    """Calcolo BP biometano DM 2022 multi-anno (15 anni standard).

    Ritorna dict con CE annuale (liste di 15 valori), KPI aggregati e
    schema finanziamento. Tutti i valori in euro nominali (non attualizzati).
    """
    # --- CAPEX ---
    capex_impiantistico = sum(capex_breakdown.values()) * plant_smch
    capex_forfait_tot = sum(capex_forfait.values())
    capex_totale = capex_impiantistico + capex_forfait_tot

    # --- Contributo PNRR (cap massimale) ---
    capex_eligible = min(capex_totale, massimale_eur_per_smch * plant_smch)
    contributo = capex_eligible * (pnrr_quota_pct / 100.0)
    capex_netto = capex_totale - contributo

    # --- Ricavi ---
    biometano_smc_anno = plant_smch * ore_anno
    # 1 Smc biometano (97% CH4) ~= 9,97 kWh -> tariffa €/Smc = €/MWh / 1000 * 9,97
    tariffa_eur_smc = tariffa_eur_mwh / 1000.0 * pci_kwh_per_smc
    ricavi_anno_base = biometano_smc_anno * tariffa_eur_smc
    biometano_mwh_anno = biometano_smc_anno * pci_kwh_per_smc / 1000.0

    # --- OPEX ---
    opex_scalabile_anno = sum(opex_breakdown.values()) * plant_smch
    opex_forfait_anno = sum(opex_forfait.values())
    opex_anno_base = opex_scalabile_anno + opex_forfait_anno

    # --- Schema finanziamento ---
    leva_lt = finance["lt_leva"] / 100.0
    debito_lt = capex_netto * leva_lt
    equity = capex_netto * (1.0 - leva_lt)

    # Rate ammortamento finanziamento LT (francese)
    def _rata_francese(C, i, n):
        i = i / 100.0
        if i == 0 or n == 0:
            return C / max(n, 1) if n > 0 else 0.0
        return C * i / (1 - (1 + i) ** -n)

    rata_lt = _rata_francese(debito_lt, finance["lt_tasso"], finance["lt_durata"])

    # Ammortamento contabile lineare
    ammort_anno = capex_totale / max(ammort_anni, 1)
    # Risconto contributo (riconosciuto come ricavo straordinario in 15 anni)
    risconto_contributo_anno = contributo / max(durata_tariffa, 1)

    # --- CE multi-anno ---
    n_anni = durata_tariffa
    infl = inflazione_pct / 100.0
    ricavi = []
    opex_lst = []
    ebitda = []
    interessi = []
    ammort_lst = []
    utile_ante = []
    utile_netto = []
    fcf = []
    debito_residuo = debito_lt
    cumulato_fcf = -equity

    payback_anno = None

    for y in range(1, n_anni + 1):
        # Ricavi tariffa fissi (DM 2022 non si aggiorna in nominale)
        r_y = ricavi_anno_base + risconto_contributo_anno
        # OPEX inflazionati
        opex_y = opex_anno_base * ((1 + infl) ** (y - 1))
        ebitda_y = r_y - opex_y
        # Interessi LT (su debito residuo)
        i_y = debito_residuo * (finance["lt_tasso"] / 100.0)
        # Quota capitale (rata - interessi)
        qc_y = max(rata_lt - i_y, 0.0)
        debito_residuo = max(debito_residuo - qc_y, 0.0)
        # Ammortamento entro anni di vita utile
        amm_y = ammort_anno if y <= ammort_anni else 0.0
        # Utile ante imposte
        u_ante = ebitda_y - i_y - amm_y
        # Imposte (solo su utile positivo)
        tax = max(u_ante * (tax_rate_pct / 100.0), 0.0)
        u_netto = u_ante - tax

        # FCF (free cash flow al netto debito): EBITDA - imposte - rata LT
        fcf_y = ebitda_y - tax - rata_lt

        ricavi.append(r_y)
        opex_lst.append(opex_y)
        ebitda.append(ebitda_y)
        interessi.append(i_y)
        ammort_lst.append(amm_y)
        utile_ante.append(u_ante)
        utile_netto.append(u_netto)
        fcf.append(fcf_y)
        cumulato_fcf += fcf_y
        if payback_anno is None and cumulato_fcf >= 0:
            # Stima lineare frazione di anno
            prev = cumulato_fcf - fcf_y
            frac = (-prev) / fcf_y if fcf_y != 0 else 0.0
            payback_anno = (y - 1) + max(0.0, min(frac, 1.0))

    # KPI aggregati
    ebitda_medio = sum(ebitda) / n_anni if n_anni else 0.0
    utile_netto_tot = sum(utile_netto)
    fcf_tot = sum(fcf)
    # IRR su flussi equity (semplice: -equity in y0, fcf in y1..n)
    flussi_equity = [-equity] + fcf

    def _irr(cf, guess=0.10, max_iter=100, tol=1e-7):
        rate = guess
        for _ in range(max_iter):
            npv = sum(c / (1 + rate) ** t for t, c in enumerate(cf))
            d_npv = sum(-t * c / (1 + rate) ** (t + 1) for t, c in enumerate(cf))
            if abs(d_npv) < 1e-12:
                break
            new_rate = rate - npv / d_npv
            if abs(new_rate - rate) < tol:
                rate = new_rate
                break
            rate = new_rate
            if rate < -0.99:
                rate = -0.99
        return rate

    try:
        irr_equity = _irr(flussi_equity)
        if not (-0.99 <= irr_equity <= 5.0):
            irr_equity = None
    except Exception:
        irr_equity = None

    # ============================================================
    # COSTO BIOGAS IMPLICITO (per liquidazione biomasse)
    # ============================================================
    # Approccio "back-derived feedstock cost":
    #   ricavi - OPEX - costo_biomasse = EBITDA_target (margine ricavi%)
    #   quota_biomasse = ricavi - OPEX - EBITDA_target
    #   costo_biogas €/Nm³ = quota_biomasse / fabbisogno_biogas
    #
    # NB: il costo biomasse NON e' incluso negli OPEX della funzione: e'
    # un'uscita ai consorziati derivata in modo tale da centrare il
    # margine EBITDA target. Anno di riferimento = 2 (regime).
    ch4_frac = max(ch4_in_biogas_pct / 100.0, 0.001)
    fabbisogno_biogas_anno = biometano_smc_anno / ch4_frac
    target_ebitda_anno_regime = (
        ricavi_anno_base * target_ebitda_margin_pct / 100.0
    )
    # Anno 2 (regime, post-anticipo contributo): OPEX inflazionato 1 anno
    opex_y2 = opex_anno_base * (1 + infl)
    quota_biomasse_anno = max(
        ricavi_anno_base - opex_y2 - target_ebitda_anno_regime,
        0.0,
    )
    costo_biogas_eur_per_nm3 = (
        quota_biomasse_anno / fabbisogno_biogas_anno
        if fabbisogno_biogas_anno > 0 else 0.0
    )

    return {
        "capex_totale":        capex_totale,
        "capex_impiantistico": capex_impiantistico,
        "capex_forfait_tot":   capex_forfait_tot,
        "capex_eligible":      capex_eligible,
        "contributo":          contributo,
        "capex_netto":         capex_netto,
        "debito_lt":           debito_lt,
        "equity":              equity,
        "rata_lt":             rata_lt,
        "ammort_anno":         ammort_anno,
        "risconto_contributo_anno": risconto_contributo_anno,
        "biometano_smc_anno":  biometano_smc_anno,
        "biometano_mwh_anno":  biometano_mwh_anno,
        "tariffa_eur_smc":     tariffa_eur_smc,
        "ricavi":              ricavi,
        "opex":                opex_lst,
        "ebitda":              ebitda,
        "ebitda_medio":        ebitda_medio,
        "interessi":           interessi,
        "ammortamenti":        ammort_lst,
        "utile_ante":          utile_ante,
        "utile_netto":         utile_netto,
        "fcf":                 fcf,
        "fcf_tot":             fcf_tot,
        "utile_netto_tot":     utile_netto_tot,
        "irr_equity":          irr_equity,
        "payback_anno":        payback_anno,
        "fabbisogno_biogas_anno":   fabbisogno_biogas_anno,
        "costo_biogas_eur_per_nm3": costo_biogas_eur_per_nm3,
        "quota_biomasse_anno":      quota_biomasse_anno,
        "target_ebitda_anno_regime": target_ebitda_anno_regime,
        "ch4_frac":                 ch4_frac,
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
    "APERTO (no copertura) - fattore IPCC/JEC":                    +15.0,
    "CHIUSO con recupero gas residuo all'upgrading":                 0.0,
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
LHV_BIOMETHANE_KWH = LHV_BIOMETHANE / 3.6   # 35.9 MJ/Sm3 = 9.972 kWh/Sm3

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
    "Trinciato di mais": {
        "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 104.0,
        "color": "#F5C518", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "UNI-TS 11567:2024 / JEC v5",
    },
    "Trinciato di sorgo": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 90.0,
        "color": "#8BC34A", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "UNI-TS 11567:2024",
    },
    "Triticale insilato": {
        "eec": 20.0, "esca": 0.0, "etd": 0.8, "yield": 85.0,
        "color": "#AED581", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "JEC v5 / KTBL",
    },
    "Segale insilata": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 80.0,
        "color": "#C5E1A5", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "JEC v5 / KTBL",
    },
    "Orzo insilato": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 82.0,
        "color": "#DCEDC8", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "JEC v5",
    },
    "Loietto insilato (ryegrass)": {
        "eec": 18.0, "esca": 0.0, "etd": 0.8, "yield": 75.0,
        "color": "#9CCC65", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "UNI-TS 11567:2024",
    },
    "Erba medica insilata": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 70.0,
        "color": "#7CB342", "cat": "Colture dedicate",
        "annex_ix": None,
        "src": "JEC v5 (azotofissazione)",
    },
    "Doppia coltura (2° raccolto)": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 95.0,
        "color": "#689F38", "cat": "Colture dedicate",
        # Coltivazione secondaria su stesso suolo: NON Annex IX di default
        # ma alcune interpretazioni la includono come "intermediate crop"
        # del par. (q) RED II All. IX. Default: NOT advanced (override
        # manuale possibile da sidebar).
        "annex_ix": None,
        "src": "GSE LG 2024 (art. doppia coltura)",
    },
    "Barbabietola da zucchero": {
        "eec": 12.0, "esca": 0.0, "etd": 0.8, "yield": 105.0,
        "color": "#CE93D8", "cat": "Colture dedicate",
        "annex_ix": None,
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
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 15.0,
        "color": "#8D6E63", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "RED III Annex VI / JEC v5",
    },
    "Liquame bovino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 20.0,
        "color": "#795548", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "RED III Annex VI",
    },
    "Liquame bufalino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 22.0,
        "color": "#6D4C41", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "JEC v5 / prassi GSE",
    },
    "Letame bovino palabile": {
        "eec": -30.0, "esca": 0.0, "etd": 0.8, "yield": 45.0,
        "color": "#A1887F", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019 Vol.4 Cap.10 + GSE",
    },
    "Letame equino": {
        "eec": -20.0, "esca": 0.0, "etd": 0.8, "yield": 35.0,
        "color": "#BCAAA4", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Pollina ovaiole (aerobico)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 90.0,
        "color": "#FF9800", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "GSE (no credit anaerobico)",
    },
    "Pollina broiler (lettiera)": {
        "eec": -15.0, "esca": 0.0, "etd": 0.8, "yield": 105.0,
        "color": "#FFA726", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019 / JEC v5",
    },
    "Pollina tacchini": {
        "eec": -10.0, "esca": 0.0, "etd": 0.8, "yield": 100.0,
        "color": "#FFB74D", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019",
    },
    "Deiezioni conigli": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 75.0,
        "color": "#FFCC80", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    # =========================================================
    # SOTTOPRODOTTI AGROINDUSTRIALI (All. IX RED II/III)
    # Tutti -> AVANZATI con double counting CIC.
    # - Sanse, vinacce, raspi, fecce, lolla -> All. IX A (h, i, k, m)
    # - Scarti caseari, panificazione, ortofrutta -> All. IX A (c, m)
    # - UCO, scarti macellazione cat. 3 -> All. IX B (oli/grassi)
    # =========================================================
    "Sansa di olive umida": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 120.0,
        "color": "#6A1B9A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5 / All. IX RED III",
    },
    "Sansa vergine": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 140.0,
        "color": "#7B1FA2", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Pastazzo di agrumi": {
        "eec": 6.0, "esca": 0.0, "etd": 0.8, "yield": 100.0,
        "color": "#FFB300", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    "Vinaccia (con raspi)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 130.0,
        "color": "#880E4F", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # All. IX A (i): grape marcs and wine lees
        "src": "JEC v5",
    },
    "Raspi d'uva": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 70.0,
        "color": "#AD1457", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    "Feccia vinicola": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 180.0,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Siero di latte": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 30.0,
        "color": "#FFF9C4", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    "Scotta (siero residuo)": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 22.0,
        "color": "#FFF59D", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Trebbie di birra": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 140.0,
        "color": "#D4A574", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # All. IX A (m): biomass fraction industrial waste
        "src": "JEC v5",
    },
    "Lolla/pula di riso": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 50.0,
        "color": "#F5DEB3", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # All. IX A (k): husks
        "src": "UNI-TS 11567:2024",
    },
    "Melasso": {
        "eec": 8.0, "esca": 0.0, "etd": 0.8, "yield": 180.0,
        "color": "#5D4037", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # sugar industry residue (canna)
        "src": "JEC v5",
    },
    "Scarti panificazione/pasticceria": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 280.0,
        "color": "#D7CCC8", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # All. IX A (c): bio-waste
        "src": "UNI-TS 11567:2024 (alta resa zuccheri)",
    },
    "Grassi esausti / UCO": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 700.0,
        "color": "#FFE082", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",  # All. IX B (a): used cooking oil
        "src": "JEC v5 (lipidi, All. IX parte B)",
    },
    "Scarti macellazione (cat. 3)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 180.0,
        "color": "#EF5350", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",  # All. IX B (b): cat 1/2 animal fats; cat 3
                            # comunemente trattato come avanzato in DM 2018
        "src": "JEC v5 / Reg. 1069/2009",
    },
    "Sottoprodotti ortofrutticoli": {
        "eec": 7.0, "esca": 0.0, "etd": 0.8, "yield": 100.0,
        "color": "#66BB6A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    "Scarti caseari vari": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 40.0,
        "color": "#E1BEE7", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Fanghi agro-industriali": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 55.0,
        "color": "#90A4AE", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
    "Polpe di barbabietola fresche": {
        # Sottoprodotto dello zuccherificio (residuo dopo estrazione saccarosio).
        # Come residuo di lavorazione: eec=0 (no oneri coltivazione allocati),
        # esca=0 (no LUC). Solo etd per trasporto/condizionamento.
        # Resa: ~50 Nm3/t FM (DM ~22-25%, biogas ~700 Nm3/t SV, 55% CH4).
        "eec": 0.0, "esca": 0.0, "etd": 2.0, "yield": 50.0,
        "color": "#F48FB1", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",  # sugar industry residue, analogo bagasse (h)
        "src": "UNI-TS 11567:2024 / JEC WTT v5 (by-product allocation)",
    },
    "Polpe di barbabietola insilate": {
        # Polpe surpressate insilate (DM ~28-30%): piu' dense delle fresche,
        # resa piu' alta per t FM. Sottoprodotto -> eec=0, esca=0.
        "eec": 0.0, "esca": 0.0, "etd": 2.5, "yield": 75.0,
        "color": "#EC407A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024 / JEC WTT v5",
    },
    "Melasso di barbabietola": {
        # Gia' presente come "Melasso" (canna); qui variante barbabietola.
        # Sottoprodotto liquido zuccherificio: resa alta, DM ~75-80%.
        "eec": 0.0, "esca": 0.0, "etd": 1.5, "yield": 280.0,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC WTT v5 / UNI-TS 11567:2024",
    },
    # =========================================================
    # FORSU / RIFIUTI (All. IX RED II/III, parte A)
    # All. IX A (c): bio-waste · (d): sewage sludge
    # Tutti -> AVANZATI con double counting CIC.
    # =========================================================
    "FORSU selezionata": {
        "eec": 8.0, "esca": 0.0, "etd": 0.8, "yield": 140.0,
        "color": "#546E7A", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "All. IX RED III / GSE LG 2024",
    },
    "Fanghi depurazione": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 60.0,
        "color": "#78909C", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024",
    },
}

# Tutti i feedstock disponibili (per retrocompatibilita' solver).
FEED_NAMES = list(FEEDSTOCK_DB.keys())

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


def _yield_of(name: str) -> float:
    """Resa effettiva [Nm3 CH4/t] = override BMT se attivo, altrimenti tabella.

    NB: il valore restituito ha la stessa unità della resa standard
    (Nm3 CH4/t) per coerenza con tutto il pipeline di calcolo a valle.
    L'unità BMT (Sm3 biometano/t) e' assimilabile per impianti Italia
    (gas a 97% CH4); la differenza ~5% Nm3-vs-Sm3 e' coerente con il
    resto del modello (vedi WARN-11 nell'audit normativo).
    """
    if name in _EFFECTIVE_YIELDS:
        return float(_EFFECTIVE_YIELDS[name])
    return float(FEEDSTOCK_DB[name]["yield"])


# Default biomasse attive: mix iniziale diversificato (colture + effluenti).
DEFAULT_ACTIVE_FEEDS = [
    "Trinciato di mais",
    "Trinciato di sorgo",
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


def _emission_factors_of(name: str, ep_default: float = 0.0) -> dict:
    """Fattori emissivi effettivi per una biomassa.

    Se esiste un override REALE attivo (relazione tecnica caricata),
    ritorna una COPIA dei fattori reali (la cache non viene mai
    mutata da chiamanti esterni). Altrimenti ritorna i fattori
    standard tabellari (FEEDSTOCK_DB) + ep impianto-wide.

    Output dict: eec, esca, etd, ep, extra, source.
    """
    if name in _EMISSION_OVERRIDES:
        # Defensive shallow copy: previene che eventuali mutazioni nei
        # consumer (display, audit, etc.) corrompano la cache runtime.
        return dict(_EMISSION_OVERRIDES[name])
    d = FEEDSTOCK_DB[name]
    return {
        "eec":   float(d["eec"]),
        "esca":  float(d["esca"]),
        "etd":   float(d["etd"]),
        "ep":    float(ep_default),
        "extra": 0.0,
        "source": EF_SOURCE_STD,
    }


def e_total_feedstock(name: str, ep: float = 0.0) -> float:
    """Emissioni totali gCO2eq/MJ per singolo feedstock.

    Formula coerente in tutto il software:
        e_total = eec + etd + ep - esca - crediti_extra

    Convenzione segno:
      - eec puo' essere negativo (manure credit gia' incorporato)
      - esca e' un credito positivo SOTTRATTO una sola volta
      - crediti_extra: crediti AGGIUNTIVI dichiarati nella relazione
        tecnica (default 0); MAI doppia sottrazione di voci gia' in esca

    Se l'utente ha attivato un override REALE da relazione tecnica
    per questa biomassa, usa i valori reali. Altrimenti usa i
    valori standard FEEDSTOCK_DB[name] e ep impianto-wide passato.
    """
    f = _emission_factors_of(name, ep)
    return calculate_emission_total(
        f["eec"], f["esca"], f["etd"], f["ep"], f.get("extra", 0.0)
    )


def ghg_summary(masses: dict, aux: float, ep: float = 0.0,
                fossil_comparator: float | None = None):
    """
    Ritorna dict con: e_w, saving_pct, nm3_gross, nm3_net, mwh_net
    masses: {feedstock: mass_t}
    ep: contributo processing [gCO2eq/MJ] da applicare a tutto il biometano.
    fossil_comparator: se None usa il globale FOSSIL_COMPARATOR (default).
      Passare esplicitamente per evitare race-condition multi-utente.
    """
    total_mj = 0.0
    total_e_mj = 0.0
    total_nm3 = 0.0
    for name, m in masses.items():
        if m is None or m <= 0:
            continue
        d = FEEDSTOCK_DB[name]
        nm3 = m * _yield_of(name)  # resa effettiva (BMT override se attivo)
        mj = nm3 * LHV_BIOMETHANE
        e = e_total_feedstock(name, ep)
        total_mj += mj
        total_e_mj += e * mj
        total_nm3 += nm3
    if total_mj <= 0:
        e_w = 0.0
        saving = 0.0
    else:
        e_w = total_e_mj / total_mj
        _cmp = fossil_comparator if fossil_comparator is not None else FOSSIL_COMPARATOR
        saving = (_cmp - e_w) / _cmp * 100
    nm3_net = total_nm3 / aux if aux > 0 else 0.0
    return {
        "e_w": e_w,
        "saving": saving,
        "nm3_gross": total_nm3,
        "nm3_net": nm3_net,
        "mwh_net": nm3_net * NM3_TO_MWH,
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
        return {x: 0.0, y_name: 0.0}, False, "Sistema singolare: le 2 biomasse incognite sono linearmente dipendenti."

    sol = np.linalg.solve(A, b)
    mx, my = float(sol[0]), float(sol[1])

    # Check feasibility
    if mx >= -1e-6 and my >= -1e-6:
        return {x: max(mx, 0), y_name: max(my, 0)}, True, ""

    # Infeasibile: forza il negativo a 0 e ricalcola l'altro con sola produzione
    note = []
    if mx < 0:
        note.append(f"{x} richiederebbe {fmt_it(mx, 1)} t (<0)")
        mx = 0.0
        my = rhs_prod / yy
        if my < 0:
            my = 0.0
            note.append(f"anche {y_name} <0: entrambe azzerate")
    elif my < 0:
        note.append(f"{y_name} richiederebbe {fmt_it(my, 1)} t (<0)")
        my = 0.0
        mx = rhs_prod / yx
        if mx < 0:
            mx = 0.0
            note.append(f"anche {x} <0: entrambe azzerate")
    msg = "Infeasibile: " + "; ".join(note) + ". Saving e/o produzione non saranno entrambi soddisfatti."
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


# ============================================================
# UI
# ============================================================
st.set_page_config(
    page_title="Metan.iQ — Biometano (DM 2018/2022) & Biogas CHP (DM 2012/FER 2)",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===========================================================
# Metan.iQ Theme Switcher (light / dark)
# ===========================================================
if "methaniq_theme" not in st.session_state:
    st.session_state.methaniq_theme = "light"

# Mini-toggle sidebar TOP (render before CSS cosi' theme e' gia' noto)
# ── LINGUA: selettore Italiano/English (prima cosa in sidebar) ──────────────
_LANG = render_lang_selector()

with st.sidebar:
    st.markdown(
        "<div style='font-size:0.7rem; font-weight:700; letter-spacing:1px; "
        "text-transform:uppercase; color:#64748B; margin-bottom:6px; padding-left:2px;'>"
        "🎨 Tema</div>",
        unsafe_allow_html=True,
    )
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        if st.button(
            "☀️ Chiaro",
            use_container_width=True,
            type="primary" if st.session_state.methaniq_theme == "light" else "secondary",
            key="btn_theme_light",
        ):
            st.session_state.methaniq_theme = "light"
            st.rerun()
    with _tc2:
        if st.button(
            "🌙 Scuro",
            use_container_width=True,
            type="primary" if st.session_state.methaniq_theme == "dark" else "secondary",
            key="btn_theme_dark",
        ):
            st.session_state.methaniq_theme = "dark"
            st.rerun()
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

# ===========================================================
# Metan.iQ Mode Selector (4 modalita' in griglia 2x2)
# - "biometano"        = legacy alias DM 2022 (mantenuto per session_state)
# - "biometano_2018"   = sistema CIC + double counting avanzato
# - "biogas_chp"       = CHP DM 6/7/2012 (<=1 MW agricolo) + premio CAR
# - "biogas_chp_fer2"  = CHP FER 2 (<=300 kWe), tariffa TR + premi matrice/CAR
# ===========================================================
_VALID_MODES = ("biometano", "biometano_2018",
                "biogas_chp", "biogas_chp_fer2")
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "biometano"

# Migrazione automatica session_state da etichette legacy
if st.session_state.app_mode not in _VALID_MODES:
    st.session_state.app_mode = "biometano"

with st.sidebar:
    st.markdown(
        "<div style='font-size:0.7rem; font-weight:700; letter-spacing:1px; "
        "text-transform:uppercase; color:#64748B; margin-bottom:6px; padding-left:2px;'>"
        "🏭 Tipologia impianto / regime incentivante</div>",
        unsafe_allow_html=True,
    )
    # Riga 1: regimi BIOMETANO
    _mc1, _mc2 = st.columns(2)
    with _mc1:
        if st.button(
            "🧬 DM 2022",
            use_container_width=True,
            type="primary" if st.session_state.app_mode == "biometano" else "secondary",
            key="btn_mode_biometano",
            help="Biometano DM 15/9/2022 — tariffa diretta €/MWh + premio "
                 "matrice/upgrading. Saving RED III per uso finale.",
        ):
            st.session_state.app_mode = "biometano"
            st.rerun()
    with _mc2:
        if st.button(
            "🌿 DM 2018 CIC",
            use_container_width=True,
            type="primary" if st.session_state.app_mode == "biometano_2018" else "secondary",
            key="btn_mode_biometano_2018",
            help="Biometano DM 2/3/2018 — sistema CIC con double counting "
                 "per matrici Annex IX (avanzato). Saving RED II/III.",
        ):
            st.session_state.app_mode = "biometano_2018"
            st.rerun()
    # Riga 2: regimi BIOGAS CHP
    _mc3, _mc4 = st.columns(2)
    with _mc3:
        if st.button(
            "⚡ CHP DM 2012",
            use_container_width=True,
            type="primary" if st.session_state.app_mode == "biogas_chp" else "secondary",
            key="btn_mode_chp",
            help="Biogas → cogenerazione elettrica DM 6/7/2012 (<=1 MW "
                 "agricolo). Tariffa Omnicomprensiva + premio CAR.",
        ):
            st.session_state.app_mode = "biogas_chp"
            st.rerun()
    with _mc4:
        if st.button(
            "🔋 CHP FER 2",
            use_container_width=True,
            type="primary" if st.session_state.app_mode == "biogas_chp_fer2" else "secondary",
            key="btn_mode_chp_fer2",
            help="Biogas CHP FER 2 (DM 18/9/2024) — taglia max 300 kWe, "
                 "matrice ≥80% sottoprodotti/effluenti, TR + premi "
                 "matrice/CAR, periodo 20 anni.",
        ):
            st.session_state.app_mode = "biogas_chp_fer2"
            st.rerun()
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

    # ============================================================
    # 📋 Normativa applicata + Verifica aggiornamenti
    # ============================================================
    with st.expander(
        "📋 Normativa & aggiornamenti",
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
                    f"border-bottom:1px solid #E2E8F0;'>"
                    f"{_badge} <b>{n.get('titolo', 'n/d')}</b><br/>"
                    f"<span style='color:#64748B; font-size:0.72rem;'>"
                    f"📍 {n.get('ambito', '')} · "
                    f"rev {n.get('ultima_revisione', 'n/d')}"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )

            st.markdown(
                "<div style='margin-top:10px;'></div>",
                unsafe_allow_html=True,
            )

            # Pulsante verifica aggiornamenti
            if st.button(
                "🔍 Verifica aggiornamenti GitHub",
                use_container_width=True,
                key="btn_check_normativa_updates",
                help="Confronta la versione locale del registry con "
                     "quella più recente su GitHub master. "
                     "Cache 5 minuti.",
            ):
                with st.spinner("Connessione a GitHub..."):
                    _norm_remote = _fetch_normativa_remote()

                if "_error" in _norm_remote:
                    st.error(f"❌ {_norm_remote['_error']}")
                else:
                    _local_v  = _norm_local.get("version", "")
                    _remote_v = _norm_remote.get("version", "")
                    _local_d  = _norm_local.get("last_review", "")
                    _remote_d = _norm_remote.get("last_review", "")

                    if _local_v == _remote_v and _local_d == _remote_d:
                        st.success(
                            f"✅ **Allineato**. Versione registry "
                            f"**{_local_v}** del {_local_d}: "
                            f"locale = produzione GitHub."
                        )
                    else:
                        st.warning(
                            f"⚠️ Disallineato: GitHub master ha versione "
                            f"**{_remote_v}** del {_remote_d}, "
                            f"tu vedi {_local_v} del {_local_d}. "
                            f"Forza Ctrl+F5 per aggiornare la cache "
                            f"del browser."
                        )

                    # Eventuali aggiornamenti pendenti pubblicati nel registry
                    _pendenti = _norm_remote.get("aggiornamenti_pendenti", [])
                    if _pendenti:
                        st.markdown("**🕐 Note normative pendenti:**")
                        for p in _pendenti:
                            st.markdown(
                                f"- **{p.get('norma', '?')}** "
                                f"({p.get('stato', 'in_review')})  "
                                f"\n  {p.get('descrizione', '')}"
                                + (f"  \n  🔗 [{p.get('link', '')}]"
                                   f"({p.get('link', '')})"
                                   if p.get("link") else "")
                            )

            st.caption(
                "ℹ️ Software fornito **«così com'è»**. Le norme cablate "
                "rispecchiano il rilascio corrente. Aggiornamenti "
                "successivi al rilascio non sono garantiti né inclusi. "
                "L'utente verifica autonomamente la coerenza con la "
                "normativa vigente prima di usare i risultati per "
                "certificazioni o adempimenti."
            )
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

APP_MODE       = st.session_state.app_mode
IS_CHP_DM2012  = APP_MODE == "biogas_chp"
IS_FER2        = APP_MODE == "biogas_chp_fer2"
IS_CHP         = IS_CHP_DM2012 or IS_FER2  # branche condivise (kW input, motore, biogas grezzo)
IS_DM2018      = APP_MODE == "biometano_2018"
IS_DM2022      = APP_MODE == "biometano"
# NB: branche "biometano generico" (DM 2022 + DM 2018) si esprimono come
# `not IS_CHP` -- entrambi i regimi condividono upgrading/off-gas/iniezione.
# `IS_CHP` cattura entrambi i CHP (DM 2012 + FER 2) per UI/calcoli condivisi;
# `IS_FER2` differenzia solo le specificita' FER 2 (cap 300 kW, premi).
# Comparator fossile aggiornato dinamicamente:
#  - mode CHP (qualsiasi): 183 gCO2/MJ (mix elettrico EU)
#  - mode DM 2022:         80 rete/elec/calore, 94 trasporti (per end_use)
#  - mode DM 2018:         94 trasporti, 80 altri usi/CAR (per end_use)
if IS_CHP:
    FOSSIL_COMPARATOR = COMPARATOR_CHP

IS_DARK = st.session_state.methaniq_theme == "dark"

# ============================================================
# Metan.iQ Design System v2 — "Navy Consulting Grade"
# Palette:
#   PRIMARY    Navy       #0F172A (slate-900)  - frame, headers, CTA primary
#   PRIMARY_2  Slate      #1E293B (slate-800)  - hover/depth
#   ACCENT     Amber      #F59E0B (amber-500)  - hero dot, highlight, download
#   ACCENT_DK  Amber dark #B45309 (amber-700)  - hover
#   BRAND      Forest     #065F46 (emerald-800) - "biomethane" semantic accent
#   BRAND_2    Emerald    #10B981 (emerald-500) - saving / positive metrics
#   CHART_NAVY #1E3A8A · CHART_TEAL #0E9384 · CHART_AMBER #D97706
# Font:  General Sans (display h1/h2) + Inter (body) + JetBrains Mono (code/KPI)
# ============================================================
NAVY        = "#0F172A"
NAVY_2      = "#1E293B"
AMBER       = "#F59E0B"
AMBER_DK    = "#B45309"
BRAND       = "#065F46"   # forest green per accenti "biometano"
BRAND_2     = "#10B981"   # mint per "saving %" positivi

if IS_DARK:
    BG_APP        = "linear-gradient(180deg, #0A0F1F 0%, #0F172A 100%)"
    BG_SURFACE    = "#15233D"
    BG_SURFACE_2  = "#0F172A"
    TEXT_PRIMARY  = "#F1F5F9"
    TEXT_SECOND   = "#CBD5E1"
    TEXT_MUTED    = "#94A3B8"
    BORDER        = "#1E293B"
    BORDER_HOVER  = AMBER
    INPUT_BG      = "#15233D"
    SIDEBAR_BG    = "linear-gradient(180deg, #0F172A 0%, #15233D 100%)"
    HEADING_COLOR = "#F8FAFC"
    CODE_BG       = "#1E293B"
    CODE_COLOR    = "#F1F5F9"
    SHADOW_CARD   = "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.25)"
    SHADOW_HOVER  = "0 8px 24px rgba(0,0,0,0.5)"
    CREDIT_BG     = "#15233D"
    SECTION_PILL_BG = "rgba(245, 158, 11, 0.12)"
    SECTION_PILL_COLOR = "#FCD34D"
else:
    BG_APP        = "linear-gradient(180deg, #F8FAFC 0%, #EEF2F7 100%)"
    BG_SURFACE    = "#FFFFFF"
    BG_SURFACE_2  = "#F8FAFC"
    TEXT_PRIMARY  = "#0F172A"
    TEXT_SECOND   = "#334155"
    TEXT_MUTED    = "#64748B"
    BORDER        = "#E2E8F0"
    BORDER_HOVER  = AMBER
    INPUT_BG      = "#FFFFFF"
    SIDEBAR_BG    = "linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)"
    HEADING_COLOR = NAVY
    CODE_BG       = "#F1F5F9"
    CODE_COLOR    = NAVY
    SHADOW_CARD   = "0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)"
    SHADOW_HOVER  = "0 8px 24px rgba(15, 23, 42, 0.10)"
    CREDIT_BG     = "#FFFFFF"
    SECTION_PILL_BG = "#FEF3C7"
    SECTION_PILL_COLOR = AMBER_DK

# ===========================================================
# Metan.iQ Design System — Commercial SaaS grade
# Palette:  primary #0B8A5A (verde petrolio) → #1CC491 (mint)
#           accent  #F59E0B (amber) · slate #0F172A · bg #F8FAFC
# Font:     Inter (Google Fonts) — standard SaaS moderno
# ===========================================================
st.markdown(
    f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

    <style>
    /* ---------- Global typography ---------- */
    /* Body: Inter · Display headings (h1/h2): Space Grotesk · Numbers/code: JetBrains Mono */
    html, body, .stApp, .stMarkdown, .stText,
    .stButton button, .stSelectbox label, .stNumberInput label,
    .stSlider label, .stCheckbox label, .stRadio label,
    .stExpander, .stDataFrame, .stTabs, .stAlert,
    p, h3, h4, h5, h6 {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
    h1, h2 {{
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    }}
    /* Preserve Material Icons / Symbols font (Streamlit internal) */
    [class*="material-icons"], [class*="material-symbols"],
    .material-icons, .material-symbols-outlined, .material-symbols-rounded,
    span[data-testid*="icon"], i[class*="icon"] {{
        font-family: 'Material Symbols Rounded', 'Material Icons',
                     'Material Symbols Outlined', sans-serif !important;
    }}
    code, pre, .stCode, code * {{
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        background: {CODE_BG} !important;
        color: {CODE_COLOR} !important;
    }}

    /* ---------- Page background ---------- */
    .stApp {{
        background: {BG_APP};
        color: {TEXT_PRIMARY};
    }}

    /* ---------- Body text ---------- */
    .stMarkdown p, .stMarkdown li, .stMarkdown span,
    .stText, [data-testid="stMarkdownContainer"] p {{
        color: {TEXT_PRIMARY} !important;
    }}

    /* ---------- Design tokens (radius scale) ---------- */
    /* Standardizzati: 6px (small) · 10px (medium) · 14px (large) */

    /* ---------- Headings (gerarchia + spaziatura coerente 8pt grid) ---------- */
    h1, h2, h3, h4, h5, h6 {{
        font-weight: 600 !important;
        letter-spacing: -0.3px !important;
        color: {HEADING_COLOR} !important;
        margin-bottom: 0.5rem !important;
    }}
    h1 {{ font-weight: 700 !important; letter-spacing: -0.6px !important; }}
    h2 {{ font-size: 1.5rem !important;
          margin-top: 1.5rem !important; margin-bottom: 0.75rem !important;
          font-weight: 600 !important; letter-spacing: -0.4px !important; }}
    h3 {{ font-size: 1.15rem !important; font-weight: 600 !important;
          margin-top: 1rem !important; }}
    h4 {{ font-size: 1rem !important; font-weight: 600 !important; }}

    /* ---------- Brand header (hero, ridotto) ---------- */
    .methaniq-header {{
        position: relative;
        background:
            radial-gradient(ellipse 70% 90% at 100% 0%, rgba(245,158,11,0.16) 0%, transparent 55%),
            radial-gradient(ellipse 60% 80% at 0% 100%, rgba(16,185,129,0.08) 0%, transparent 55%),
            linear-gradient(135deg, {NAVY} 0%, {NAVY_2} 100%);
        padding: 36px 36px 32px 36px;
        border-radius: 14px;
        color: white;
        margin-bottom: 12px;
        box-shadow:
            0 12px 32px -12px rgba(15, 23, 42, 0.40),
            0 2px 6px rgba(15, 23, 42, 0.15);
        text-align: left;
        overflow: hidden;
        border: 1px solid rgba(245, 158, 11, 0.16);
    }}
    /* Hex pattern SVG sottile */
    .methaniq-header::before {{
        content: "";
        position: absolute;
        inset: 0;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='92' viewBox='0 0 80 92'><g fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='1'><polygon points='40,4 72,22 72,58 40,76 8,58 8,22'/><polygon points='40,28 56,38 56,58 40,68 24,58 24,38'/></g></svg>");
        background-size: 110px 126px;
        opacity: 0.5;
        pointer-events: none;
    }}
    .methaniq-header .eyebrow {{
        position: relative;
        z-index: 1;
        display: inline-block;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.7rem;
        font-weight: 500;
        color: {AMBER};
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 10px;
        padding: 3px 10px;
        background: rgba(245, 158, 11, 0.10);
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-radius: 6px;
    }}
    .methaniq-header h1 {{
        color: #FFFFFF !important;
        margin: 0 !important;
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        letter-spacing: -1.2px !important;
        line-height: 1.05;
        position: relative;
        z-index: 1;
    }}
    .methaniq-header .tagline {{
        color: #CBD5E1;
        font-weight: 400;
        font-size: 1.02rem;
        margin-top: 10px;
        letter-spacing: 0;
        line-height: 1.5;
        position: relative;
        z-index: 1;
        max-width: 720px;
    }}
    .methaniq-header .pills {{
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-top: 20px;
        position: relative;
        z-index: 1;
    }}
    .methaniq-header .pill {{
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.12);
        color: #E2E8F0;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 500;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 0.2px;
    }}
    .methaniq-header .pill.accent {{
        background: rgba(245, 158, 11, 0.12);
        border-color: rgba(245, 158, 11, 0.40);
        color: {AMBER};
    }}

    /* ---------- Credit box ---------- */
    .methaniq-credit {{
        background: {CREDIT_BG};
        border: 1px solid {BORDER};
        border-left: 3px solid {AMBER};
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 0.8rem;
        color: {TEXT_SECOND};
        margin-bottom: 20px;
        box-shadow: {SHADOW_CARD};
        line-height: 1.5;
    }}
    .methaniq-credit b {{ color: {HEADING_COLOR}; font-weight: 600; }}

    /* ---------- Sidebar (color override piu' targetato) ---------- */
    /* Evita "*" che rompe i colori semantici di pillole, badge,
       link AMBER, success/error icons, ecc. */
    section[data-testid="stSidebar"] {{
        background: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] li,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        color: {TEXT_PRIMARY};
    }}
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        font-size: 1rem !important;
        color: {HEADING_COLOR} !important;
        margin-top: 1.2rem !important;
        padding-bottom: 6px;
        border-bottom: 1px solid {BORDER};
    }}

    /* ---------- Metrics (KPI cards, piu' impattanti) ---------- */
    [data-testid="stMetric"] {{
        background: {BG_SURFACE};
        padding: 16px 18px;
        border-radius: 10px;
        border: 1px solid {BORDER};
        border-top: 2px solid {AMBER};
        box-shadow: {SHADOW_CARD};
        transition: all 0.2s ease;
    }}
    [data-testid="stMetric"]:hover {{
        box-shadow: {SHADOW_HOVER};
        border-color: {BORDER_HOVER};
        border-top-color: {AMBER};
        transform: translateY(-2px);
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_MUTED} !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: 'JetBrains Mono', monospace !important;
        margin-bottom: 4px !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {HEADING_COLOR} !important;
        font-weight: 700 !important;
        font-size: 2.1rem !important;
        line-height: 1.1 !important;
        letter-spacing: -1px !important;
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        font-variant-numeric: tabular-nums;
    }}
    [data-testid="stMetricDelta"] {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.76rem !important;
        font-weight: 500 !important;
        margin-top: 2px !important;
    }}

    /* ---------- Buttons (gerarchia chiara: primary = navy, accent = amber) ---------- */
    .stButton > button {{
        background: {NAVY};
        color: #FFFFFF !important;
        border: 1px solid {NAVY};
        border-radius: 6px;
        padding: 0.5rem 1.2rem;
        font-weight: 600;
        font-size: 0.92rem;
        letter-spacing: 0;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
        transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .stButton > button:hover {{
        background: {NAVY_2};
        border-color: {AMBER};
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.18),
                    0 0 0 3px rgba(245, 158, 11, 0.10);
        transform: translateY(-1px);
    }}
    .stButton > button:active {{ transform: translateY(0); box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }}
    .stButton > button:focus-visible {{
        outline: 2px solid {AMBER};
        outline-offset: 2px;
    }}
    /* Primary button (mode/theme selectors quando attivo) */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY_2} 100%);
        border: 1px solid {AMBER};
        color: #FFFFFF !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.18),
                    inset 0 1px 0 rgba(245, 158, 11, 0.18);
    }}
    /* Secondary button (toggle inactive, neutral actions) */
    .stButton > button[kind="secondary"] {{
        background: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
        border: 1px solid {BORDER} !important;
        box-shadow: {SHADOW_CARD};
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: {AMBER} !important;
        background: {BG_SURFACE_2} !important;
        color: {HEADING_COLOR} !important;
    }}
    /* Download buttons = AZIONE PRIMARIA AMBER (CTA distintivo)
       TUTTI i download_button (primary o secondary) sono amber per
       coerenza visiva nella riga export. !important per battere
       eventuali override default di Streamlit per kind="secondary". */
    .stDownloadButton > button,
    .stDownloadButton > button[kind="primary"],
    .stDownloadButton > button[kind="secondary"],
    .stDownloadButton > button[data-testid="stBaseButton-secondary"],
    .stDownloadButton > button[data-testid="stBaseButton-primary"] {{
        background: {AMBER} !important;
        color: #FFFFFF !important;
        border: 1px solid {AMBER} !important;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.92rem;
        padding: 0.5rem 1.2rem;
        letter-spacing: 0.1px;
        box-shadow: 0 1px 3px rgba(245, 158, 11, 0.20);
        transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .stDownloadButton > button:hover {{
        background: {AMBER_DK} !important;
        border-color: {AMBER_DK} !important;
        box-shadow: 0 5px 14px rgba(245, 158, 11, 0.30),
                    0 0 0 3px rgba(245, 158, 11, 0.12);
        transform: translateY(-1px);
    }}
    .stDownloadButton > button:active {{ transform: translateY(0); }}

    /* ---------- Expanders (radius coerente 10px) ---------- */
    .streamlit-expanderHeader, details > summary {{
        background: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
        border-radius: 10px !important;
        border: 1px solid {BORDER} !important;
        font-weight: 600 !important;
        padding: 10px 14px !important;
        transition: all 0.15s ease;
    }}
    .streamlit-expanderHeader:hover {{
        border-color: {BORDER_HOVER} !important;
    }}
    [data-testid="stExpander"] {{
        background: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        margin-bottom: 8px;
    }}

    /* ---------- Tabs (font + padding piu' generosi) ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px;
        background: {BG_SURFACE};
        padding: 4px;
        border-radius: 10px;
        border: 1px solid {BORDER};
        box-shadow: {SHADOW_CARD};
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 6px;
        padding: 9px 18px;
        font-weight: 500;
        font-size: 0.95rem;
        color: {TEXT_MUTED};
        transition: all 0.15s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background: {BG_SURFACE_2};
        color: {TEXT_PRIMARY};
    }}
    .stTabs [aria-selected="true"] {{
        background: {NAVY} !important;
        color: #FFFFFF !important;
        font-weight: 600;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.25),
                    inset 0 -2px 0 {AMBER};
    }}

    /* ---------- Alerts (info/success/warning/error) ---------- */
    [data-testid="stAlert"] {{
        border-radius: 10px;
        border: 1px solid {BORDER};
        box-shadow: {SHADOW_CARD};
        padding: 12px 14px !important;
    }}

    /* ---------- Inputs (radius coerente 6px) ---------- */
    .stNumberInput input, .stTextInput input,
    .stSelectbox [data-baseweb="select"] > div {{
        background: {INPUT_BG} !important;
        color: {TEXT_PRIMARY} !important;
        border-radius: 6px !important;
        border: 1px solid {BORDER} !important;
        transition: all 0.15s ease;
    }}
    .stNumberInput input:focus, .stTextInput input:focus {{
        border-color: {AMBER} !important;
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18) !important;
    }}
    /* Slider: track navy + thumb amber con outline navy + ring */
    .stSlider [data-baseweb="slider"] > div > div {{
        background: {NAVY} !important;
    }}
    .stSlider [data-baseweb="slider"] [role="slider"] {{
        background: {AMBER} !important;
        border: 2px solid {NAVY} !important;
        box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.15) !important;
    }}
    /* Multiselect / chip styling */
    .stMultiSelect [data-baseweb="tag"] {{
        background: rgba(245, 158, 11, 0.12) !important;
        border: 1px solid rgba(245, 158, 11, 0.40) !important;
        color: {AMBER_DK} !important;
        border-radius: 6px !important;
    }}

    /* ---------- Dataframes (radius coerente 10px) ---------- */
    [data-testid="stDataFrame"] {{
        border-radius: 10px;
        overflow: hidden;
        box-shadow: {SHADOW_CARD};
        border: 1px solid {BORDER};
    }}
    [data-testid="stDataFrame"] * {{
        color: {TEXT_PRIMARY} !important;
    }}
    /* Hover row su data_editor (sottile) */
    [data-testid="stDataFrameRow"]:hover {{
        background: {BG_SURFACE_2} !important;
    }}

    /* ---------- Dividers ---------- */
    hr {{
        border: none !important;
        border-top: 1px solid {BORDER} !important;
        margin: 1.5rem 0 !important;
        opacity: 0.7;
    }}

    /* ---------- Captions ---------- */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {TEXT_MUTED} !important;
        font-size: 0.82rem !important;
        line-height: 1.55 !important;
    }}

    /* ---------- Subtle section headings ---------- */
    .section-label {{
        display: inline-block;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: {SECTION_PILL_COLOR};
        background: {SECTION_PILL_BG};
        padding: 3px 10px;
        border-radius: 6px;
        margin-bottom: 6px;
    }}

    /* ---------- Tooltip / help icons leggermente visibili ---------- */
    [data-testid="stTooltipIcon"] svg {{
        fill: {TEXT_MUTED} !important;
        opacity: 0.65;
        transition: opacity 0.15s ease;
    }}
    [data-testid="stTooltipIcon"]:hover svg {{
        opacity: 1;
        fill: {AMBER} !important;
    }}

    /* ---------- Spaziatura blocchi principali ---------- */
    [data-testid="stVerticalBlock"] > [data-testid="element-container"] {{
        margin-bottom: 0.4rem;
    }}
    </style>

    <div class="methaniq-header">
        <span class="eyebrow">// Decision Intelligence Platform</span>
        <h1>Metan<span style="color:""" + AMBER + """; font-weight:700;">.</span>iQ</h1>
        <div class="tagline">""" + (
            "DM 18/9/2024 · CHP biogas piccoli impianti agricoli ≤300 kWe. Tariffa di Riferimento + premi matrice (≥80% sottoprodotti) e CAR. Periodo 20 anni, saving 80% RED III."
            if IS_FER2 else
            "Pianificazione e business case per impianti biogas cogenerativi (DM 6/7/2012, ≤1 MW). Bilancio elettrico-termico, tariffa T.O. e saving RED III."
            if IS_CHP else
            "DM 2/3/2018 · sistema CIC con double counting per matrici Annex IX (biometano avanzato). Pianificazione mensile, sostenibilità RED II/III e simulazione CIC."
            if IS_DM2018 else
            "DM 15/9/2022 · pianificazione mensile e ottimizzazione GHG per biometano: tariffa diretta €/MWh, saving RED III/D.Lgs. 5/2026 per uso finale."
        ) + """</div>
        <div class="pills">
            <span class="pill accent">""" + (
                "BIOGAS · CHP · FER 2 (≤300 kW)" if IS_FER2 else
                "BIOGAS · CHP · DM 6/7/2012" if IS_CHP else
                "BIOMETANO · DM 2/3/2018 · CIC" if IS_DM2018 else
                "BIOMETANO · DM 15/9/2022"
            ) + """</span>
            <span class="pill">""" + (
                "DM 18/9/2024 · FER 2" if IS_FER2 else
                "RED II · ALL. IX (avanzato)" if IS_DM2018 else
                "RED III · D.LGS 5/2026"
            ) + """</span>
            <span class="pill">GSE LG 2024</span>
            <span class="pill">UNI-TS 11567:2024</span>
            <span class="pill">JEC WTT v5</span>
            <span class="pill">LP OPTIMIZER</span>
        </div>
    </div>
    <div class="methaniq-credit">
        Ideato e sviluppato da <b>Carlo Sicurini</b> &nbsp;·&nbsp; © 2026 &nbsp;·&nbsp;
        Pianificazione mensile e ottimizzazione GHG per impianti di biometano e biogas cogenerativo.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"<div style='background:{BG_SURFACE}; padding:14px 18px; border-radius:10px; "
    f"border:1px solid {BORDER}; margin-bottom:18px; "
    f"box-shadow: {SHADOW_CARD};'>"
    f"<span style='font-size:0.72rem; font-weight:700; letter-spacing:1px; "
    f"text-transform:uppercase; color:{SECTION_PILL_COLOR}; background:{SECTION_PILL_BG}; "
    f"padding:3px 10px; border-radius:6px; margin-right:10px;'>SOLVER</span>"
    f"<span style='color:{TEXT_SECOND}; font-size:0.95rem;'>"
    f"Pianificazione mensile biomasse — solver <b>dual-constraint</b> "
    f"(saving GHG + produzione target) con configurazione impianto <code style='background:{CODE_BG}; "
    f"padding:2px 6px; border-radius:4px; font-size:0.85em; color:{CODE_COLOR};'>ep</code> ex RED III."
    f"</span></div>",
    unsafe_allow_html=True,
)

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.markdown(
        """
        <div style='
            position: relative;
            padding: 18px 16px;
            background: linear-gradient(135deg, """ + NAVY + """ 0%, """ + NAVY_2 + """ 100%);
            border-radius: 10px;
            margin-bottom: 18px;
            box-shadow: 0 4px 12px rgba(15,23,42,0.20),
                        inset 0 1px 0 rgba(245,158,11,0.10);
            border: 1px solid rgba(245, 158, 11, 0.20);
            overflow: hidden;
        '>
            <div style='
                position: absolute; top: 0; right: 0; bottom: 0;
                width: 3px;
                background: linear-gradient(180deg, transparent 0%, """ + AMBER + """ 50%, transparent 100%);
            '></div>
            <div style='
                font-family: "JetBrains Mono", monospace;
                color: """ + AMBER + """;
                font-size: 0.62em;
                font-weight: 500;
                letter-spacing: 2px;
                text-transform: uppercase;
                margin-bottom: 6px;
            '>// PLATFORM</div>
            <div style='
                font-family: "Space Grotesk", "Inter", sans-serif;
                color: #FFFFFF;
                font-size: 1.55em;
                font-weight: 700;
                letter-spacing: -0.8px;
                line-height: 1;
            '>Metan<span style="color:""" + AMBER + """;">.</span>iQ</div>
            <div style='
                font-size: 0.72em;
                color: #94A3B8;
                margin-top: 6px;
                font-weight: 400;
            '>by <span style='color:#E2E8F0; font-weight:600;'>Carlo Sicurini</span></div>
            <div style='
                margin-top: 12px;
                padding-top: 10px;
                border-top: 1px solid rgba(255,255,255,0.08);
                font-family: "JetBrains Mono", monospace;
                font-size: 0.62em;
                color: #CBD5E1;
                font-weight: 400;
                letter-spacing: 1px;
                text-transform: uppercase;
            '>""" + ("Biogas · CHP · FER 2 (≤300 kW)" if IS_FER2
                    else "Biogas · CHP · DM 6/7/2012" if IS_CHP
                    else "Biometano · DM 2018 · CIC" if IS_DM2018
                    else "Biometano · DM 2022") + """</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.header(_t("🌾 Biomasse del tuo impianto"))
    st.caption(
        f"Seleziona le biomasse che userai (**{len(FEED_NAMES)} disponibili** nel "
        "database UNI-TS 11567:2024 / JEC v5 / RED III). Il solver considerera' "
        "solo queste nelle combinazioni di ottimizzazione."
    )

    # Selezione strutturata per categorie con expander
    if "active_feeds" not in st.session_state:
        st.session_state.active_feeds = list(DEFAULT_ACTIVE_FEEDS)

    with st.expander(
        f"📂 Scegli biomasse ({len(st.session_state.active_feeds)} attive)",
        expanded=False,
    ):
        st.caption("Raggruppate per categoria normativa. Spunta quelle presenti nel tuo impianto.")
        new_active = []
        for cat, feeds in FEEDSTOCK_CATEGORIES.items():
            st.markdown(f"**{cat}**")
            for f in feeds:
                checked = st.checkbox(
                    f"{f}  · eec={fmt_it(FEEDSTOCK_DB[f]['eec'], 1, signed=True)}"
                    f"  · resa={fmt_it(_yield_of(f), 0)} Nm³/t",
                    value=(f in st.session_state.active_feeds),
                    key=f"chk_feed_{f}",
                    help=f"Fonte: {FEEDSTOCK_DB[f].get('src', 'n/d')}",
                )
                if checked:
                    new_active.append(f)
        # Bottoni utility
        bc1, bc2, bc3 = st.columns(3)
        if bc1.button("🔄 Default", use_container_width=True, key="btn_feed_default"):
            st.session_state.active_feeds = list(DEFAULT_ACTIVE_FEEDS)
            # Pulisce i widget checkbox (saranno ricreati col default)
            for f in FEED_NAMES:
                st.session_state.pop(f"chk_feed_{f}", None)
            st.rerun()
        if bc2.button("✅ Tutte", use_container_width=True, key="btn_feed_all"):
            st.session_state.active_feeds = list(FEED_NAMES)
            for f in FEED_NAMES:
                st.session_state.pop(f"chk_feed_{f}", None)
            st.rerun()
        if bc3.button("❌ Nessuna", use_container_width=True, key="btn_feed_none"):
            st.session_state.active_feeds = []
            for f in FEED_NAMES:
                st.session_state.pop(f"chk_feed_{f}", None)
            st.rerun()

        if new_active != st.session_state.active_feeds:
            st.session_state.active_feeds = new_active
            st.rerun()

    active_feeds = st.session_state.active_feeds

    if len(active_feeds) < 2:
        st.error(
            f"⚠️ Seleziona almeno **2 biomasse** per usare il solver dual-constraint. "
            f"Attualmente: {len(active_feeds)}."
        )
        st.stop()

    # Riassunto compatto delle biomasse attive
    st.markdown(
        "<div style='font-size:0.78rem; color:#64748B; margin-top:-4px; margin-bottom:8px;'>"
        "🌱 <b>Attive nel mix:</b> " +
        " · ".join([f"<span style='color:{FEEDSTOCK_DB[f]['color']}; font-weight:600;'>{f}</span>"
                    for f in active_feeds[:8]]) +
        (f" <i>+ altre {len(active_feeds)-8}</i>" if len(active_feeds) > 8 else "") +
        "</div>",
        unsafe_allow_html=True,
    )

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
        st.caption(
            "Per ciascuna biomassa attiva puoi sostituire la resa standard "
            "(tabella interna UNI-TS / JEC v5) con una resa BMT certificata "
            "da laboratorio. Il certificato e' OBBLIGATORIO: senza file "
            "caricato l'override non viene applicato e viene mostrato un "
            "errore. La resa BMT vale SOLO per la biomassa selezionata; "
            "le altre continuano a usare la tabella standard. Lo scostamento "
            f"oltre il +/-{int(BMT_DEVIATION_WARN_THRESHOLD*100)}% rispetto "
            "alla tabella standard genera un warning di verifica."
        )

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
                f"🧪 {_bmt_name}  ·  attiva BMT certificato "
                f"(standard {fmt_it(_std_y, 0)} Nm³/t)",
                key=_key_active,
                value=st.session_state.get(_key_active, False),
                help=(
                    f"Se attivata, la resa standard {fmt_it(_std_y, 0)} "
                    f"Nm³/t verra' sostituita dal valore BMT certificato "
                    f"per **{_bmt_name}**. Il certificato e' obbligatorio."
                ),
            )

            if not _bmt_active:
                # Rimuovi eventuale override precedente
                st.session_state["bmt_overrides"].pop(_bmt_name, None)
                continue

            with st.container():
                _bmt_col1, _bmt_col2 = st.columns([1, 1])
                with _bmt_col1:
                    _bmt_value = st.number_input(
                        f"Resa BMT [{BMT_YIELD_UNIT}]",
                        min_value=0.0, max_value=2000.0,
                        value=float(st.session_state.get(
                            _key_value, _std_y)),
                        step=1.0, key=_key_value,
                        help=(
                            "Resa misurata da test BMT in laboratorio "
                            f"(unita': {BMT_YIELD_UNIT}). Deve essere > 0."
                        ),
                    )
                    _bmt_lab = st.text_input(
                        "Laboratorio",
                        value=st.session_state.get(_key_lab, ""),
                        key=_key_lab,
                        help="Nome/ragione sociale del laboratorio emittente.",
                    )
                with _bmt_col2:
                    _bmt_date = st.text_input(
                        "Data certificato (YYYY-MM-DD)",
                        value=st.session_state.get(_key_date, ""),
                        key=_key_date,
                        help="Data di emissione del rapporto di prova.",
                    )
                    _bmt_sample = st.text_input(
                        "Riferimento campione",
                        value=st.session_state.get(_key_sample, ""),
                        key=_key_sample,
                        help="Numero rapporto di prova / ID campione.",
                    )

                _bmt_cert_file = st.file_uploader(
                    f"📎 Certificato BMT — {_bmt_name} "
                    f"(formati: {', '.join(e.lstrip('.').upper() for e in ALLOWED_CERT_EXTS)})",
                    type=[e.lstrip(".") for e in ALLOWED_CERT_EXTS],
                    key=_key_cert,
                    accept_multiple_files=False,
                    help=(
                        "Carica il certificato di analisi BMT del "
                        "laboratorio. OBBLIGATORIO: senza file l'override "
                        "non viene applicato."
                    ),
                )

                _cert_uploaded = _bmt_cert_file is not None
                _cert_name = _bmt_cert_file.name if _cert_uploaded else ""
                _cert_size = _bmt_cert_file.size if _cert_uploaded else 0

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
                f"🧬 {_ef_name}  ·  usa fattori emissivi reali da relazione "
                f"(std: eec={fmt_it(_eec_std, 1, signed=True)}, "
                f"esca={fmt_it(_esca_std, 1)}, etd={fmt_it(_etd_std, 1)} {EMISSION_UNIT})",
                key=_key_active,
                value=st.session_state.get(_key_active, False),
                help=(
                    f"Se attivata, i fattori emissivi standard di **{_ef_name}** "
                    f"saranno sostituiti dai valori dichiarati nella relazione "
                    f"tecnica dell'impianto. La relazione tecnica e' obbligatoria."
                ),
            )

            if not _ef_active:
                st.session_state["emission_factor_overrides"].pop(_ef_name, None)
                continue

            with st.container():
                _ef_c1, _ef_c2 = st.columns([1, 1])
                with _ef_c1:
                    _ef_eec = st.number_input(
                        f"eec reale [{EMISSION_UNIT}]",
                        min_value=-200.0, max_value=300.0,
                        value=float(st.session_state.get(_key_eec, _eec_std)),
                        step=0.1, format="%.2f", key=_key_eec,
                        help="Emissioni eec dichiarate nella relazione tecnica. Puo' essere negativo (manure credit gia' incorporato).",
                    )
                    _ef_esca = st.number_input(
                        f"esca reale [{EMISSION_UNIT}] (credito, positivo)",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_esca, _esca_std)),
                        step=0.1, format="%.2f", key=_key_esca,
                        help="Credito esca: dichiarato come valore positivo, sottratto da e_total.",
                    )
                    _ef_etd = st.number_input(
                        f"etd reale [{EMISSION_UNIT}]",
                        min_value=0.0, max_value=50.0,
                        value=float(st.session_state.get(_key_etd, _etd_std)),
                        step=0.1, format="%.2f", key=_key_etd,
                    )
                with _ef_c2:
                    _ef_ep = st.number_input(
                        f"ep reale [{EMISSION_UNIT}] (per-biomassa)",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_ep, 0.0)),
                        step=0.1, format="%.2f", key=_key_ep,
                        help="Emissioni di processo dichiarate nella relazione (sostituisce l'ep impianto-wide per questa biomassa).",
                    )
                    _ef_extra = st.number_input(
                        f"Crediti emissivi extra [{EMISSION_UNIT}]",
                        min_value=0.0, max_value=200.0,
                        value=float(st.session_state.get(_key_extra, 0.0)),
                        step=0.1, format="%.2f", key=_key_extra,
                        help="Crediti AGGIUNTIVI dichiarati nella relazione (NON gia' inclusi in esca). Default 0. NON sottrarre due volte la stessa voce.",
                    )

                _ef_t1, _ef_t2 = st.columns([1, 1])
                with _ef_t1:
                    _ef_title = st.text_input(
                        "Titolo relazione",
                        value=st.session_state.get(_key_title, ""),
                        key=_key_title,
                    )
                    _ef_author = st.text_input(
                        "Autore / tecnico redattore",
                        value=st.session_state.get(_key_author, ""),
                        key=_key_author,
                    )
                    _ef_company = st.text_input(
                        "Societa' / studio tecnico",
                        value=st.session_state.get(_key_company, ""),
                        key=_key_company,
                    )
                    _ef_date = st.text_input(
                        "Data relazione (YYYY-MM-DD)",
                        value=st.session_state.get(_key_date, ""),
                        key=_key_date,
                    )
                with _ef_t2:
                    _ef_plant = st.text_input(
                        "Impianto di riferimento",
                        value=st.session_state.get(_key_plant, ""),
                        key=_key_plant,
                    )
                    _ef_sample = st.text_input(
                        "Riferimento campione / lotto",
                        value=st.session_state.get(_key_sample, ""),
                        key=_key_sample,
                    )
                    _ef_notes = st.text_area(
                        "Note metodologiche (opzionale)",
                        value=st.session_state.get(_key_notes, ""),
                        key=_key_notes, height=68,
                        help="Metodo dichiarato nella relazione: es. RED III All. V Parte C, JEC v5, ISCC, REDcert, ecc.",
                    )

                _ef_report_file = st.file_uploader(
                    f"📎 Relazione tecnica — {_ef_name} "
                    f"(formati: {', '.join(e.lstrip('.').upper() for e in ALLOWED_REPORT_EXTS)})",
                    type=[e.lstrip(".") for e in ALLOWED_REPORT_EXTS],
                    key=_key_report,
                    accept_multiple_files=False,
                    help="Carica la relazione tecnica dell'impianto. OBBLIGATORIO.",
                )

                _r_uploaded = _ef_report_file is not None
                _r_name = _ef_report_file.name if _r_uploaded else ""
                _r_size = _ef_report_file.size if _r_uploaded else 0

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
    st.header(_t("⚙️ Parametri impianto"))

    if IS_CHP:
        # Parametri CHP: input utente in kW_el LORDI (potenza nominale motore),
        # convertito internamente in Sm3/h CH4 al motore (unit del solver).
        eta_el = st.slider(
            "🔌 Efficienza elettrica CHP [η_el]",
            min_value=0.30, max_value=0.45,
            value=ETA_EL_DEFAULT, step=0.01,
            help="Rendimento elettrico motore cogeneratore. Tipico 38-42% "
                 "per motori biogas 500-1000 kWe (Jenbacher, MWM, Guascor).",
        )
        eta_th = st.slider(
            "🔥 Efficienza termica CHP [η_th]",
            min_value=0.30, max_value=0.50,
            value=ETA_TH_DEFAULT, step=0.01,
            help="Rendimento termico recuperato (fumi + acqua motore). "
                 "Tipico 40-45%. Per CAR richiesto PES > 10%.",
        )
        # Cap dimensionale: FER 2 ha hard cap a 300 kWe (DM 18/9/2024).
        # DM 6/7/2012 fino a 1 MW agricolo (cap pratico 999 kWe per evitare
        # passaggio a fascia successiva). Manteniamo max wide-range per
        # consentire scenari simulativi anche fuori normativa.
        if IS_FER2:
            _kwe_min   = 50.0
            _kwe_max   = FER2_KWE_CAP
            _kwe_value = min(DEFAULT_PLANT_KWE_FER2, FER2_KWE_CAP)
            _kwe_help  = (
                f"FER 2 (DM 18/9/2024): hard cap **{fmt_it(FER2_KWE_CAP, 0)} kWe**. "
                f"Targa motore = potenza ai morsetti alternatore. Esempi tipici "
                f"<300 kWe: Jenbacher JMC 312 GS = 250 kWe, MAN E0834 = 250 kWe."
            )
        else:
            _kwe_min   = 50.0
            _kwe_max   = 10000.0
            _kwe_value = DEFAULT_PLANT_KWE
            _kwe_help  = (
                "Potenza elettrica nominale al morsetti alternatore "
                "(dato di targa motore). Esempi: Jenbacher JMC 420 GS-BL = "
                "999 kWe, MWM TCG 2020V20 = 2000 kWe. L'autoconsumo "
                "ausiliari viene sottratto separatamente qui sotto."
            )
        plant_kwe = st.number_input(
            "🎯 Potenza elettrica LORDA (targa motore) [kW_el]"
            + (f" — max {fmt_it(FER2_KWE_CAP, 0)} kWe (cap FER 2)"
               if IS_FER2 else ""),
            min_value=_kwe_min, max_value=_kwe_max,
            value=_kwe_value, step=10.0,
            help=_kwe_help,
        )
        # Sanity check: se IS_FER2 e per qualche motivo plant_kwe > cap
        # (es. riapertura pagina con valore precedente da altro mode)
        if IS_FER2 and plant_kwe > FER2_KWE_CAP:
            st.error(
                f"❌ FER 2 prevede taglia max **{fmt_it(FER2_KWE_CAP, 0)} kWe**. "
                f"Impostato {fmt_it(plant_kwe, 0)} kWe → fuori normativa."
            )
            plant_kwe = FER2_KWE_CAP
        aux_el_pct = st.slider(
            "⚙️ Autoconsumo elettrico ausiliari [% del lordo]",
            min_value=0.0, max_value=20.0,
            value=AUX_EL_DEFAULT * 100, step=0.5,
            help="Assorbimento elettrico dei servizi d'impianto (pompe "
                 "alimentazione, agitatori digestori, desolforatore, "
                 "soffiante, PLC, illuminazione, trattamento digestato). "
                 "Tipico 8-10% del lordo. Impianti ben ottimizzati 5-7% "
                 "(con FV a supporto). Impianti vecchi/biologie difficili "
                 "10-13%.",
        ) / 100.0
        # Potenza netta immessa in rete (quella che fattura)
        plant_kwe_net = plant_kwe * (1.0 - aux_el_pct)
        # Conversione: il CH4 serve per il LORDO (prima del prelievo aux)
        # 1 Sm3/h CH4 eq → η_el × 9.97 kW_el lordo
        plant_net_smch = plant_kwe / (eta_el * 9.97)  # Sm3/h CH4 eq al motore
        st.caption(
            f"📐 **Bilancio elettrico**: "
            f"{fmt_it(plant_kwe, 0)} kW_el lordi − "
            f"{fmt_it(plant_kwe * aux_el_pct, 0)} kW aux "
            f"({fmt_it(aux_el_pct*100, 1, '%')}) = "
            f"**{fmt_it(plant_kwe_net, 0)} kW_el netti** (rete). "
            f"CH₄ al motore: {fmt_it(plant_net_smch, 1)} Sm³/h."
        )
        colA, colB, colC = st.columns(3)
        colA.metric("🔌 Lordo motore", fmt_it(plant_kwe, 0, " kWₑ"))
        colB.metric("⚡ Netto in rete", fmt_it(plant_kwe_net, 0, " kWₑ"),
                    delta=f"-{fmt_it(aux_el_pct*100, 1, '%')} aux")
        colC.metric("🔥 Termico", fmt_it(plant_kwe * eta_th / eta_el, 0, " kW_th"))
    else:
        plant_net_smch = st.number_input(
            "🎯 Netto autorizzato [Sm³/h netti]",
            min_value=10.0, max_value=2000.0,
            value=DEFAULT_PLANT_NET_SMCH, step=5.0,
            help="Taglia netta dell'impianto. Cambia il setpoint di produzione: "
                 "tutte le biomasse vengono ricalcolate per centrare questo valore.",
        )
        st.caption(
            "ℹ️ Il **fattore netto→lordo** viene calcolato automaticamente dalla "
            "configurazione impianto qui sotto (upgrading, fonte calore, fonte "
            "elettricita'). Puoi comunque sovrascriverlo manualmente."
        )
        st.metric("Taglia netta", fmt_it(plant_net_smch, 0, " Sm³/h"))
        # Per coerenza in mode biometano: eta_el/eta_th/aux_el_pct inutilizzati
        # ma definiti per evitare NameError in blocchi condivisi.
        eta_el = ETA_EL_DEFAULT
        eta_th = ETA_TH_DEFAULT
        aux_el_pct = 0.0
        plant_kwe = plant_net_smch * eta_el * 9.97  # info-only (non usato)
        plant_kwe_net = plant_kwe  # in biometano non c'è distinzione

    st.divider()
    st.header(_t("🏭 Configurazione impianto (ep)"))
    st.caption(
        "I parametri impiantistici concorrono a `ep` (processing), "
        "che incide direttamente sul saving GHG ex RED III."
    )

    # Destinazione d'uso -> soglia GHG saving (mode-aware)
    if IS_CHP:
        # Per biogas CHP: solo destinazione elettrica, soglia 80% (RED III).
        # Comparator 183 gCO2/MJ (mix elettrico EU).
        end_use = ("Elettricità CHP — FER 2 (DM 18/9/2024, ≤300 kW)"
                   if IS_FER2 else "Elettricità CHP — DM 6/7/2012 (≤1 MW)")
        ghg_threshold = 0.80
        # FOSSIL_COMPARATOR gia' settato a 183 nel mode selector
        if IS_FER2:
            st.info(
                "🔋 **Biogas → CHP FER 2** (DM 18/9/2024) · Taglia max "
                f"**{fmt_it(FER2_KWE_CAP, 0)} kWe** · Comparator fossile "
                "RED III: **183 gCO₂/MJ** (mix elettrico EU) · "
                "Soglia saving: 80% · Periodo incentivo: 20 anni"
            )
        else:
            st.info(
                "⚡ **Biogas → CHP DM 6/7/2012** · Taglia tipica ≤1 MWe "
                "agricolo · Comparator fossile RED III: **183 gCO₂/MJ** "
                "(mix elettrico EU) · Soglia saving: 80%"
            )
    elif IS_DM2018:
        # DM 2 marzo 2018: 4 destinazioni d'uso con soglie/comparator distinti.
        end_use = st.selectbox(
            "🎯 Destinazione biometano (→ soglia saving + comparator)",
            list(DM2018_END_USES.keys()),
            index=0,
            help="DM 2018: trasporti -> CIC con double counting per "
                 "matrici Annex IX (avanzato). Altri usi/CAR -> tariffa "
                 "diretta €/MWh (no CIC). Soglia saving e comparator "
                 "fossile cambiano per uso finale.",
        )
        _du = DM2018_END_USES[end_use]
        ghg_threshold = _du["sav"]
        FOSSIL_COMPARATOR = _du["cmp"]
        st.caption(
            f"📐 Comparator fossile **{fmt_it(FOSSIL_COMPARATOR, 0)} "
            f"gCO₂/MJ** "
            + ("(diesel sostituito · trasporti)" if FOSSIL_COMPARATOR == 94.0
               else "(gas naturale sostituito · rete/calore/CAR)")
            + (" · CIC double-counting attivo se matrice Annex IX"
               if _du["cic_premium"] else " · sistema tariffa fissa (no CIC)")
        )
    else:
        # DM 15 settembre 2022 (default biometano)
        end_use = st.selectbox(
            "🎯 Destinazione biometano (→ soglia saving + comparator)",
            list(END_USE_THRESHOLDS.keys()),
            index=0,
            help="RED III + D.Lgs. 5/2026: 80% per elettricita'/calore (impianto "
                 "nuovo ≥20/11/2023), 70% per esistenti <10 MW primi 15 anni, "
                 "65% per trasporti. Il comparator fossile (80 per rete/calore, "
                 "94 per trasporti) viene aggiornato di conseguenza.",
        )
        ghg_threshold = END_USE_THRESHOLDS[end_use]
        # Comparator mode-aware: 80 per rete/elec/calore, 94 per trasporti
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
    st.metric("Soglia saving obbligatoria",
              fmt_it(ghg_threshold * 100, 0, "%"),
              delta=f"target solver {fmt_it(target_saving * 100, 0, '%')}")

    # ============================================================
    # DM 2018 — Configurazione CIC e classificazione avanzato
    # ============================================================
    if IS_DM2018:
        st.divider()
        st.header(_t("🌿 DM 2018 — Sistema CIC"))

        # Conteggio Annex IX tra biomasse attive
        n_annex = sum(
            1 for f in active_feeds
            if FEEDSTOCK_DB[f].get("annex_ix") in ("A", "B")
        )
        n_total = max(len(active_feeds), 1)
        annex_pct_count = n_annex / n_total

        st.caption(
            f"📋 **Matrice attiva**: {n_annex} di {n_total} biomasse "
            f"selezionate sono classificate Annex IX RED II/III "
            f"({fmt_it(annex_pct_count*100, 0, '%')} per numero). "
            f"La quota effettiva in MASSA dell'impianto viene calcolata in "
            f"tab «🥧 Mix annuale» ed e' quella che determina lo status "
            f"avanzato dell'impianto."
        )

        # Soglia configurabile per "avanzato"
        annex_threshold = st.slider(
            "Soglia massa Annex IX per status «avanzato» [%]",
            min_value=50.0, max_value=100.0,
            value=ANNEX_IX_THRESHOLD * 100, step=5.0,
            help="Quota minima in MASSA di feedstock Annex IX richiesta "
                 "per qualificare l'impianto come «biometano avanzato» "
                 "(double counting CIC). Default 70% (interpretazione GSE). "
                 "Alcune autorita' richiedono 100% per evitare contestazioni.",
        ) / 100.0

        advanced_mode = st.radio(
            "Classificazione impianto",
            ["Auto (calcolata da matrice annuale)",
             "Forza AVANZATO (override manuale)",
             "Forza NON avanzato (override manuale)"],
            index=0,
            help="«Auto» determina lo status dalla quota in massa Annex IX "
                 "vs soglia. Override solo se hai certificazione GSE "
                 "specifica o vincoli contrattuali.",
        )

        # Valore CIC
        cic_price = st.number_input(
            "💰 Valore CIC [€/CIC]",
            min_value=0.0, max_value=600.0,
            value=CIC_PRICE_DEFAULT, step=5.0,
            help=f"Prezzo medio unitario del CIC. Riferimento GSE base "
                 f"~{fmt_it(CIC_PRICE_DEFAULT, 0)} €/CIC; sul mercato "
                 f"secondario (operatori obbligati) tipicamente "
                 f"300-450 €/CIC. Valore solo per simulazione ricavi.",
        )

        # Caption attiva CIC double counting solo se uso ammette CIC
        _cic_active = DM2018_END_USES[end_use]["cic_premium"]
        if _cic_active:
            st.success(
                f"✅ **Sistema CIC attivo** · 1 CIC = "
                f"{fmt_it(MWH_PER_CIC, 2)} MWh "
                f"({fmt_it(GCAL_PER_CIC, 0)} Gcal). Biometano avanzato → "
                f"double counting → 1 CIC ogni "
                f"{fmt_it(MWH_PER_CIC/2, 2)} MWh "
                f"({fmt_it(GCAL_PER_CIC/2, 0)} Gcal)."
            )
        else:
            st.warning(
                "ℹ️ **Uso non ammesso al sistema CIC**: per «altri usi» "
                "e CAR il DM 2018 prevede tariffa diretta €/MWh, NON CIC. "
                "Il prezzo CIC inserito sopra non viene applicato."
            )
    else:
        # Default per tutte le mode che non sono DM 2018 (dummy non usati)
        annex_threshold = ANNEX_IX_THRESHOLD
        advanced_mode = "Auto (calcolata da matrice annuale)"
        cic_price = 0.0

    # ============================================================
    # FER 2 — Configurazione tariffa + premi + check matrice
    # ============================================================
    if IS_FER2:
        st.divider()
        st.header(_t("🔋 FER 2 — Tariffa e premi"))

        # Sottoprodotti = Annex IX A/B + effluenti zootecnici (gia' tutti
        # marcati Annex IX A nel DB), tutto tranne le colture dedicate.
        # Soglia FER 2: ≥ 80% in MASSA da NON colture dedicate.
        # Gia' calcolato in tab4 (annex_mass_share usa Annex IX A/B che
        # corrisponde a tutto cio' che NON e' coltura dedicata).
        n_subprod = sum(
            1 for f in active_feeds
            if FEEDSTOCK_DB[f].get("annex_ix") in ("A", "B")
        )
        n_total = max(len(active_feeds), 1)
        st.caption(
            f"📋 **Matrice attiva**: {n_subprod} di {n_total} biomasse "
            f"sono sottoprodotti/effluenti (no colture dedicate). "
            f"FER 2 richiede **≥ 80% in MASSA** da sottoprodotti — "
            f"verifica reale calcolata in tab «🥧 Mix annuale» con "
            f"i tonnellaggi mensili."
        )

        fer2_matrice_threshold = st.slider(
            "Soglia massa sottoprodotti per accesso FER 2 [%]",
            min_value=70.0, max_value=100.0,
            value=FER2_FEEDSTOCK_REQ_THRESHOLD * 100, step=5.0,
            help=f"Quota minima sottoprodotti/effluenti zootecnici/residui "
                 f"per qualificare l'impianto a FER 2. Default "
                 f"{fmt_it(FER2_FEEDSTOCK_REQ_THRESHOLD*100, 0, '%')} (DM "
                 f"18/9/2024). Cap residuo per colture dedicate: 20%.",
        ) / 100.0

        st.subheader(_t("💰 Tariffa FER 2 [€/MWh_el]"))
        fer2_tariffa_base = st.number_input(
            "Tariffa di Riferimento (TR) base",
            min_value=0.0, max_value=500.0,
            value=FER2_TARIFFA_BASE_DEFAULT, step=1.0,
            help=f"Tariffa di Riferimento FER 2 base, applicata ai MWh_el "
                 f"NETTI immessi in rete. Default "
                 f"{fmt_it(FER2_TARIFFA_BASE_DEFAULT, 0)} €/MWh_el "
                 f"(piccoli impianti agricoli ≤300 kWe). Variabile "
                 f"per fascia/asta/registro: aggiorna se hai aggiudicato "
                 f"con tariffa specifica.",
        )

        col_pa, col_pb = st.columns(2)
        with col_pa:
            fer2_premio_matrice_attivo = st.checkbox(
                f"Premio matrice (+{fmt_it(FER2_PREMIO_MATRICE_DEFAULT, 0)} €/MWh)",
                value=True,
                help=f"Premio per matrice ≥{fmt_it(FER2_FEEDSTOCK_REQ_THRESHOLD*100, 0, '%')} "
                     f"sottoprodotti/effluenti. Si attiva automaticamente "
                     f"in tab «Ricavi» se la quota in massa supera la soglia.",
            )
        with col_pb:
            fer2_premio_car_attivo = st.checkbox(
                f"Premio CAR (+{fmt_it(FER2_PREMIO_CAR_DEFAULT, 0)} €/MWh)",
                value=True,
                help="Premio Cogenerazione ad Alto Rendimento. Richiede "
                     "PES > 10% (η_el + η_th_recuperato ≥ 75-80%). "
                     "Verifica certificato CAR del GSE.",
            )

        fer2_premio_matrice_eur = st.number_input(
            "Valore premio matrice [€/MWh]",
            min_value=0.0, max_value=100.0,
            value=FER2_PREMIO_MATRICE_DEFAULT, step=1.0,
            help="Valore del premio matrice (sommato alla TR base se la "
                 "soglia matrice e' raggiunta).",
        )
        fer2_premio_car_eur = st.number_input(
            "Valore premio CAR [€/MWh]",
            min_value=0.0, max_value=50.0,
            value=FER2_PREMIO_CAR_DEFAULT, step=1.0,
            help="Valore del premio CAR (sommato alla TR base se attivo).",
        )

        st.success(
            f"📐 **Tariffa target** (se entrambi i premi attivi): "
            f"{fmt_it(fer2_tariffa_base, 0)} TR + "
            f"{fmt_it(fer2_premio_matrice_eur, 0)} matrice + "
            f"{fmt_it(fer2_premio_car_eur, 0)} CAR = "
            f"**{fmt_it(fer2_tariffa_base + fer2_premio_matrice_eur + fer2_premio_car_eur, 0)} "
            f"€/MWh_el** · Periodo: {FER2_PERIODO_ANNI} anni"
        )
    else:
        # Default per non-FER 2 (dummy non usati)
        fer2_matrice_threshold     = FER2_FEEDSTOCK_REQ_THRESHOLD
        fer2_tariffa_base          = 0.0
        fer2_premio_matrice_attivo = False
        fer2_premio_car_attivo     = False
        fer2_premio_matrice_eur    = 0.0
        fer2_premio_car_eur        = 0.0

    # ============================================================
    # PRO FORMA / BUSINESS PLAN (solo DM 2022)
    # ============================================================
    # Defaults derivati da benchmark impianto medio biometano agricolo
    # (250 Smc/h, costi medi settore 2024), ricalibrati al 2026 con
    # inflazione ISTAT cumulata e tassi BCE.
    # ============================================================
    if IS_DM2022:
        with st.expander(
            "💼 Pro Forma · CAPEX / OPEX / Finanziamento "
            "(default benchmark impianto medio 2026)",
            expanded=False,
        ):
            st.caption(
                "Default basati sul **benchmark di un impianto medio biometano agricolo (250 Smc/h, costi medi 2024)** "
                "(maggio 2024) ricalibrato 2026 (+5% materiali ISTAT, "
                "tassi finanziamento aggiornati). Tutti i valori sono "
                "**editabili** per scenari custom."
            )
            # ---- Tariffa / contributo ----
            st.markdown("##### 💰 Tariffa GSE & contributo PNRR")
            bp_tariffa_eur_mwh = st.number_input(
                "Tariffa GSE base (DM 2022) [€/MWh]",
                min_value=50.0, max_value=300.0,
                value=BP_TARIFFA_BASE_2026, step=0.5,
                help=f"Tariffa di riferimento DM 15/9/2022 base "
                     f"{fmt_it(BP_TARIFFA_BASE_2026, 1)} €/MWh "
                     f"(~131 €/MWh post-aggiornamento ISTAT 2024-2026 "
                     f"sulla base 124,48 €/MWh storica). "
                     f"Sostituisci con il valore del tuo decreto.",
            )
            bp_ribasso_pct = st.slider(
                "Ribasso d'asta [%]",
                min_value=0.0, max_value=30.0,
                value=BP_RIBASSO_DEFAULT_PCT, step=0.5,
                help="Ribasso offerto in fase di asta GSE. Tariffa effettiva = "
                     "tariffa base × (1 − ribasso/100).",
            )
            bp_tariffa_eff = bp_tariffa_eur_mwh * (1 - bp_ribasso_pct / 100.0)
            bp_pnrr_pct = st.number_input(
                "Contributo PNRR [%] (M2C2 - biometano)",
                min_value=0.0, max_value=65.0,
                value=BP_PNRR_QUOTA_PCT_DEFAULT, step=1.0,
                help=f"Quota contributo a fondo perduto su CAPEX "
                     f"ammissibile (cap massimale GSE "
                     f"{fmt_it(BP_MASSIMALE_SPESA_EUR_PER_SMCH, 0)} €/(Smc/h)). "
                     f"Default {fmt_it(BP_PNRR_QUOTA_PCT_DEFAULT, 0)}%.",
            )

            # ---- CAPEX breakdown ----
            st.markdown("##### 🏗️ CAPEX (€/(Smc/h) per macrovoce)")
            st.caption(
                "Ogni voce viene moltiplicata per la taglia (Smc/h). "
                "Le voci forfait sono fisse a livello d'impianto."
            )
            bp_capex_breakdown = {}
            for k, v in BP_CAPEX_DEFAULTS_PER_SMCH.items():
                bp_capex_breakdown[k] = st.number_input(
                    f"{k}",
                    min_value=0.0, max_value=50000.0,
                    value=v, step=100.0,
                    key=f"bp_capex_{k}",
                    help=f"CAPEX €/(Smc/h). Default benchmark impianto medio 2026.",
                )
            st.markdown("**CAPEX forfait**")
            bp_capex_forfait = {}
            for k, v in BP_CAPEX_FORFAIT_DEFAULTS.items():
                bp_capex_forfait[k] = st.number_input(
                    f"{k}",
                    min_value=0.0, max_value=2000000.0,
                    value=v, step=1000.0,
                    key=f"bp_capex_ff_{k}",
                )

            # ---- OPEX ----
            st.markdown("##### 🔧 OPEX (€/anno per (Smc/h))")
            st.caption(
                "OPEX scalabili (digestione, upgrading, gestore) - voci "
                "fisse (assicurazioni, tasse) separate sotto."
            )
            bp_opex_breakdown = {}
            for k, v in BP_OPEX_DEFAULTS_PER_SMCH_YEAR.items():
                bp_opex_breakdown[k] = st.number_input(
                    f"{k}",
                    min_value=0.0, max_value=10000.0,
                    value=v, step=10.0,
                    key=f"bp_opex_{k}",
                )
            st.markdown("**OPEX fissi (€/anno)**")
            bp_opex_forfait = {}
            for k, v in BP_OPEX_FORFAIT_DEFAULTS.items():
                bp_opex_forfait[k] = st.number_input(
                    f"{k}",
                    min_value=0.0, max_value=200000.0,
                    value=v, step=500.0,
                    key=f"bp_opex_ff_{k}",
                )

            # ---- Finanziarie ----
            st.markdown("##### 🏦 Schema finanziamento")
            bp_lt_tasso = st.number_input(
                "Tasso finanziamento Lungo Termine [%]",
                min_value=0.0, max_value=15.0,
                value=BP_FINANCE_DEFAULTS["lt_tasso"], step=0.1,
                help=f"Tasso BCE 2026 ~{fmt_it(BP_FINANCE_DEFAULTS['lt_tasso'], 1)}% "
                     f"(era 4,5% nel 2024). Aggiorna se hai offerta vincolata.",
            )
            bp_lt_durata = st.slider(
                "Durata Lungo Termine [anni]",
                min_value=5, max_value=20,
                value=int(BP_FINANCE_DEFAULTS["lt_durata"]), step=1,
            )
            bp_lt_leva = st.slider(
                "Leva LT su CAPEX netto [%]",
                min_value=0.0, max_value=100.0,
                value=BP_FINANCE_DEFAULTS["lt_leva"], step=5.0,
                help="Quota CAPEX netto coperta da debito bancario "
                     "(resto = equity / soci).",
            )

            # ---- Parametri economici ----
            st.markdown("##### 📊 Parametri economici")
            bp_ebitda_target_pct = st.slider(
                "Margine EBITDA target [%] (per liquidazione biomasse)",
                min_value=10.0, max_value=50.0,
                value=24.5, step=0.5,
                help=f"EBITDA target / ricavi (tipico settore: 24,5%). "
                     f"Determina la quota disponibile per pagare "
                     f"le biomasse ai consorziati (= ricavi − OPEX − "
                     f"EBITDA target). Costo biogas implicito = "
                     f"quota / fabbisogno biogas.",
            )
            bp_inflazione_pct = st.number_input(
                "Inflazione OPEX annua [%]",
                min_value=0.0, max_value=10.0,
                value=BP_INFLAZIONE_DEFAULT_PCT, step=0.1,
                help="Rivalutazione ISTAT applicata agli OPEX anno per anno. "
                     "Default 2,5%. Tariffa GSE NON e' inflazionata "
                     "(DM 2022 nominal).",
            )
            bp_ch4_in_biogas_pct = st.slider(
                "Concentrazione CH₄ nel biogas grezzo [%]",
                min_value=45.0, max_value=70.0,
                value=54.25, step=0.25,
                help="% CH4 nel biogas pre-upgrading. Determina il "
                     "fabbisogno di biogas grezzo (= biometano / CH4%). "
                     "Default tipico 54,25%.",
            )
            bp_ore_anno = st.number_input(
                "Ore funzionamento annuo [h/anno]",
                min_value=4000.0, max_value=8760.0,
                value=8500.0, step=50.0,
                help="Ore equivalenti di funzionamento. Tipico "
                     "biometano agricolo: 8200-8500 h/anno.",
            )

        # Calcolo BP completo (se IS_DM2022 e abbastanza dati)
        try:
            _bp_finance = dict(BP_FINANCE_DEFAULTS)
            _bp_finance["lt_tasso"]  = bp_lt_tasso
            _bp_finance["lt_durata"] = bp_lt_durata
            _bp_finance["lt_leva"]   = bp_lt_leva
            bp_result = compute_business_plan(
                plant_smch=plant_net_smch,
                tariffa_eur_mwh=bp_tariffa_eff,
                capex_breakdown=bp_capex_breakdown,
                capex_forfait=bp_capex_forfait,
                opex_breakdown=bp_opex_breakdown,
                opex_forfait=bp_opex_forfait,
                pnrr_quota_pct=bp_pnrr_pct,
                inflazione_pct=bp_inflazione_pct,
                finance=_bp_finance,
                target_ebitda_margin_pct=bp_ebitda_target_pct,
                ore_anno=bp_ore_anno,
                ch4_in_biogas_pct=bp_ch4_in_biogas_pct,
            )
        except Exception as _bp_exc:  # noqa: BLE001
            bp_result = None
            st.error(f"Errore calcolo BP: {_bp_exc}")
    else:
        # Defaults per modalita' non DM 2022 (BP non applicabile)
        bp_tariffa_eur_mwh = 0.0
        bp_ribasso_pct = 0.0
        bp_tariffa_eff = 0.0
        bp_pnrr_pct = 0.0
        bp_capex_breakdown = {}
        bp_capex_forfait = {}
        bp_opex_breakdown = {}
        bp_opex_forfait = {}
        bp_lt_tasso = 0.0
        bp_lt_durata = 15
        bp_lt_leva = 0.0
        bp_ebitda_target_pct = 0.0
        bp_inflazione_pct = 0.0
        bp_ch4_in_biogas_pct = 54.25
        bp_ore_anno = 8500.0
        bp_result = None

    # Configuratore ep
    digestate_opt = st.selectbox(
        "Stoccaggio digestato",
        list(EP_DIGESTATE.keys()), index=1,
        help="RED III All.V Parte C + GSE LG 2024: riconosce solo APERTO "
             "(fattori IPCC 2019) o CHIUSO con recupero gas al processo "
             "(= 0). Nessuna soglia temporale nella normativa. Il gas "
             "residuo recuperato non da' bonus negativo: confluisce nel "
             "biogas lordo e aumenta la resa Nm³/t.",
    )

    # Upgrading / Off-gas / Iniezione rete: SOLO in modalita' biometano
    if IS_CHP:
        st.info(
            "⚡ **Biogas CHP**: il biogas grezzo viene bruciato direttamente "
            "nel cogeneratore. Non si applicano upgrading, combustione "
            "off-gas o iniezione in rete."
        )
        upgrading_opt = None
        offgas_opt = None
        injection_opt = None
        ep_upgrading = 0.0
        ep_offgas = 0.0
    else:
        upgrading_opt = st.selectbox("Tecnologia upgrading",
                                      list(EP_UPGRADING.keys()), index=1)
        offgas_opt = st.selectbox("Combustione off-gas",
                                   list(EP_OFFGAS.keys()), index=0)
        ep_upgrading = EP_UPGRADING[upgrading_opt]
        ep_offgas = EP_OFFGAS[offgas_opt]

    heat_opt = st.selectbox("Fonte calore processo",
                             list(EP_HEAT.keys()), index=0)
    elec_opt = st.selectbox("Elettricità ausiliari",
                             list(EP_ELEC.keys()), index=1)

    if not IS_CHP:
        injection_opt = st.selectbox(
            "Iniezione biometano in rete",
            list(INJECTION_PRESSURE.keys()), index=1,
            help="Pressione di consegna del biometano. Determina il consumo "
                 "elettrico del booster compressore a valle dell'upgrading "
                 "(0,05-0,25 kWh_e/Sm³).",
        )

    ep_digestate = EP_DIGESTATE[digestate_opt]
    ep_heat = EP_HEAT[heat_opt]
    ep_elec = EP_ELEC[elec_opt]
    ep_total = ep_digestate + ep_upgrading + ep_offgas + ep_heat + ep_elec

    # Breakdown ep (mode-aware)
    with st.expander(
        f"📊 Breakdown ep = {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ",
        expanded=True,
    ):
        _ep_lines = [f"- Digestato: **{fmt_it(ep_digestate, 1, signed=True)}**"]
        if not IS_CHP:
            _ep_lines.append(f"- Upgrading: **{fmt_it(ep_upgrading, 1, signed=True)}**")
            _ep_lines.append(f"- Off-gas: **{fmt_it(ep_offgas, 1, signed=True)}**")
        _ep_lines.append(f"- Calore: **{fmt_it(ep_heat, 1, signed=True)}**")
        _ep_lines.append(f"- Elettricità: **{fmt_it(ep_elec, 1, signed=True)}**")
        _ep_lines.append(
            f"- **Totale ep: {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ**"
        )
        st.markdown("\n".join(_ep_lines))

    st.divider()
    # ========================================================
    # AUX_FACTOR AUTOMATICO (bilancio energetico d'impianto)
    # ========================================================
    st.header(_t("⚡ Fattore netto→lordo (aux_factor)"))
    if IS_CHP:
        st.caption(
            "In modalità **Biogas CHP** il biogas grezzo va direttamente "
            "al motore: nessun autoconsumo per upgrading / iniezione / off-gas. "
            "L'autoconsumo elettrico ausiliari è gestito separatamente in "
            "«Autoconsumo elettrico ausiliari» (applicato sui kW_el lordi per "
            "ottenere i kW_el netti in rete). Qui resta solo il margine di "
            "perdite diffuse CH₄ + downtime."
        )
    else:
        st.caption(
            "Calcolato dal bilancio materiale/energetico in base alla "
            "configurazione scelta qui sopra. Determina quanta biomassa serve: "
            "lordo = netto × aux_factor."
        )

    margin_pct = st.slider(
        "Margine perdite reali + downtime [%]",
        min_value=0.0, max_value=10.0, value=3.0, step=0.5,
        help="Perdite diffuse (coperchi digestore, tubazioni, soffiatori) "
             "+ downtime manutenzione. Default 3% (impianti ben gestiti).",
    )

    if IS_CHP:
        # CHP: calcolo aux_factor semplificato (niente upgrading/offgas/rete)
        # Autoconsumo elettrico CHP (~8%) gia' scontato nel kW_el NETTO inserito.
        # aux_factor_chp = 1 / (1 - margine_perdite)
        aux_auto = 1.0 / max(1.0 - margin_pct / 100.0, 0.80)
        # Non uso compute_aux_factor: non si applica senza upgrading
        aux_auto_data = None
        # Variabili dummy per compatibilita' downstream (non usate in CHP)
        cogen_frac = 0.0
        recover_chp_heat = False
    else:
        cogen_frac = 0.6  # default: 60% elettricita' da CHP biogas, 40% FV
        recover_chp_heat = True
        if elec_opt == ELEC_IS_INTERNAL:
            cogen_frac = st.slider(
                "Quota cogen biogas nell'autoproduzione elettrica [%]",
                min_value=0.0, max_value=100.0, value=60.0, step=10.0,
                help="Se autoproduci elettricita' da CHP biogas + FV, indica "
                     "la quota coperta dal CHP (resto dalla FV). Il CHP biogas "
                     "consuma biogas interno, la FV no.",
            ) / 100.0
            recover_chp_heat = st.checkbox(
                "Recupero calore cogenerato dal CHP → digestori",
                value=True,
                help="Se il CHP cogenerativo recupera calore (η_t≈45%) e lo usa "
                     "per riscaldare i digestori, la caldaia dedicata consuma "
                     "meno biogas. Default ON (impianti ben progettati).",
            )

        aux_auto_data = compute_aux_factor(
            upgrading_opt=upgrading_opt,
            heat_opt=heat_opt,
            elec_opt=elec_opt,
            injection_opt=injection_opt,
            margin=margin_pct / 100.0,
            cogen_fraction=cogen_frac,
            recover_chp_heat=recover_chp_heat,
        )
        aux_auto = aux_auto_data["aux_factor"]

    manual_override = st.checkbox(
        "Sovrascrivi manualmente",
        value=False,
        help="Se hai dati misurati del tuo impianto, inserisci il valore "
             "reale. Altrimenti usa il calcolo automatico.",
    )
    if manual_override:
        aux_factor = st.slider(
            "aux_factor manuale",
            min_value=1.00 if IS_CHP else 1.05, max_value=1.60,
            value=round(aux_auto, 2), step=0.01,
        )
    else:
        aux_factor = aux_auto
        if IS_CHP:
            st.metric(
                "aux_factor calcolato",
                fmt_it(aux_factor, 3),
                delta=f"{fmt_it(margin_pct, 1, '%')} perdite diffuse",
            )
        else:
            st.metric(
                "aux_factor calcolato",
                fmt_it(aux_factor, 3),
                delta=f"{fmt_it(aux_auto_data['f_tot']*100, 1, '%')} autoconsumo totale",
            )

    # Breakdown aux_factor (solo in mode biometano: in CHP e' banale)
    if not IS_CHP:
        with st.expander(
            f"🔬 Breakdown aux_factor = {fmt_it(aux_auto, 3)}",
            expanded=False,
        ):
            st.markdown(
                f"**Formula**: aux = 1 / (1 − f_calore − f_elettr − f_slip − f_margine)\n\n"
                f"### 🔥 BILANCIO TERMICO\n"
                f"Fabbisogno termico lordo = **{fmt_it(aux_auto_data['heat_need_gross'], 3)} kWh_t/Sm³**\n"
                f"- Riscaldamento digestori (mesofilo): {fmt_it(HEAT_DIGESTORE, 3)}\n"
                f"- Calore upgrading ({upgrading_opt.split(' (')[0]}): "
                f"{fmt_it(HEAT_DEMAND_UPGRADING[upgrading_opt], 3)}\n\n"
                f"Recupero calore dal CHP cogenerativo: "
                f"**−{fmt_it(aux_auto_data['heat_recovered_chp'], 3)} kWh_t/Sm³** "
                f"{'✅ attivo' if recover_chp_heat and elec_opt==ELEC_IS_INTERNAL else '⏸ non applicato'}\n\n"
                f"→ Calore residuo caldaia: **{fmt_it(aux_auto_data['heat_need_residual'], 3)} kWh_t/Sm³**\n"
                f"→ **f_calore = {fmt_it(aux_auto_data['f_heat']*100, 2, '%')}** "
                f"(fonte: {heat_opt})\n\n"
                f"### ⚡ BILANCIO ELETTRICO\n"
                f"Fabbisogno elettrico totale = **{fmt_it(aux_auto_data['elec_need'], 3)} kWh_e/Sm³**\n"
                f"- Upgrading core ({upgrading_opt.split(' (')[0]}): "
                f"{fmt_it(aux_auto_data['elec_upgrading'], 3)}\n"
                f"- BOP = pretrattamento biogas + biologia + PLC: "
                f"{fmt_it(aux_auto_data['elec_bop'], 3)}\n"
                f"  &nbsp;&nbsp;(caricatore tramoggia + desolfo + carb. attivi: "
                f"{fmt_it(ELEC_PRETREATMENT, 3)}, "
                f"agitatori+pompe substrato: {fmt_it(ELEC_BIOLOGY, 3)}, "
                f"PLC+servizi: {fmt_it(ELEC_PLC_CONTROLS, 3)})\n"
                f"- Compressione iniezione rete "
                f"({injection_opt.split(' (')[0]}): "
                f"{fmt_it(aux_auto_data['elec_injection'], 3)}\n\n"
                f"→ **f_elettr = {fmt_it(aux_auto_data['f_elec']*100, 2, '%')}** "
                f"(fonte: {elec_opt}"
                f"{f', quota cogen {fmt_it(cogen_frac*100,0,chr(37))}' if elec_opt==ELEC_IS_INTERNAL else ''})\n\n"
                f"### 💨 ALTRE PERDITE\n"
                f"- Methane slip upgrading: **{fmt_it(aux_auto_data['f_slip']*100, 2, '%')}**\n"
                f"- Margine perdite diffuse + downtime: **{fmt_it(aux_auto_data['f_margin']*100, 1, '%')}**\n\n"
                f"### ∑ TOTALE AUTOCONSUMO: **{fmt_it(aux_auto_data['f_tot']*100, 2, '%')}**\n\n"
                f"*Rendimenti*: caldaia biogas η={fmt_it(ETA_BOILER_BIOGAS*100,0,'%')}, "
                f"CHP elettr. η={fmt_it(ETA_CHP_ELEC*100,0,'%')}, "
                f"CHP term. η={fmt_it(ETA_CHP_THERM*100,0,'%')} &nbsp;·&nbsp; "
                f"LHV biometano = {fmt_it(LHV_BIOMETHANE_KWH, 3)} kWh/Sm³."
            )

    _unit_lordo = "Sm³ CH₄/h" if IS_CHP else "Sm³/h"
    st.metric(
        "Produzione lorda richiesta"
        + (" (CH₄ equivalente, pre-perdite)" if IS_CHP else ""),
        fmt_it(plant_net_smch * aux_factor, 1, f" {_unit_lordo}"),
    )

    st.divider()
    st.header(f"📋 Database feedstock attivi ({len(active_feeds)}/{len(FEED_NAMES)})")
    # Refresh _EMISSION_OVERRIDES con ep_total impianto-wide per fattori
    # standard non-overridden (cosi' ep e' coerente nella tabella display)
    rows = []
    for n in active_feeds:
        d = FEEDSTOCK_DB[n]
        # Fattori effettivi (override real se attivo, altrimenti standard)
        f_used = _emission_factors_of(n, ep_total)
        e_tot = e_total_feedstock(n, ep_total)
        is_real = (f_used.get("source") == EF_SOURCE_REAL)
        rows.append({
            "Feedstock": n,
            "Categoria": d.get("cat", ""),
            "Resa (Nm³/t)": _yield_of(n),  # resa effettiva (BMT override se attivo)
            "eec": d["eec"],
            "ep": ep_total,
            "etd": d["etd"],
            "esca": d["esca"],
            "Resa (Nm³/t)": d["yield"],
            "eec":     f_used["eec"],
            "ep":      f_used["ep"],
            "etd":     f_used["etd"],
            "esca":    f_used["esca"],
            "crediti extra": f_used.get("extra", 0.0),
            "e_total": round(e_tot, 2),
            "saving %": round(
                (FOSSIL_COMPARATOR - e_tot) / FOSSIL_COMPARATOR * 100, 1
            ),
            "Origine fattori": ("🧬 Relazione tecnica" if is_real
                                 else "📚 Tab. standard"),
        })
    df_feed = pd.DataFrame(rows)
    styled_feed = df_feed.style.format({
        "Resa (Nm³/t)":   lambda v: fmt_it(v, 0),
        "eec":            lambda v: fmt_it(v, 1, signed=True),
        "ep":             lambda v: fmt_it(v, 1, signed=True),
        "etd":            lambda v: fmt_it(v, 1, signed=True),
        "esca":           lambda v: fmt_it(v, 1, signed=True),
        "crediti extra":  lambda v: fmt_it(v, 1),
        "e_total":        lambda v: fmt_it(v, 2, signed=True),
        "saving %":       lambda v: fmt_it(v, 1, "%"),
    })
    st.dataframe(styled_feed, hide_index=True, use_container_width=True)
    st.caption(
        "**Formula coerente**: e_total = eec + etd + ep − esca − crediti_extra. "
        "Origine fattori: 🧬 Relazione tecnica = override REALE attivo per quella biomassa; "
        "📚 Tab. standard = valori UNI-TS 11567:2024 / JEC WTT v5 / All. IX RED III / GSE LG 2024. "
        "Manure credit incorporato in `eec` (negativo). I crediti emissivi NON "
        "vengono mai sottratti due volte (esca e crediti_extra sono voci distinte)."
    )

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
MODE_DUAL = f"{N_active-2} biomasse fisse + 2 calcolate  (saving target + produzione)"
MODE_SINGLE = f"{N_active-1} biomasse fisse + 1 calcolata  (solo produzione)"

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
    # Hash chiave config attiva (deve combaciare con line ~3170).
    _opt_active_hash = str(hash(tuple(sorted(active_feeds))))[:8]
    if _pending_opt.get("is_mono"):
        # Caso mono: 1 sola biomassa attiva -> (N-1)+1 con la mono come
        # incognita calcolata e le altre (N-1) fisse a 0 (per ogni mese).
        mono = _pending_opt["mono"]
        others = [n for n in active_feeds if n != mono]
        st.session_state["mode_radio"] = MODE_SINGLE
        st.session_state["single_unknown_select"] = mono
        new_state_key = (
            f"mens_in_single_{_opt_active_hash}_{'-'.join(others)}"
        )
        rows_init = []
        for mm, hh in zip(MONTHS, MONTH_HOURS):
            r = {"Mese": mm, "Ore": hh}
            for f in others:
                r[f] = 0.0
            rows_init.append(r)
        st.session_state[new_state_key] = pd.DataFrame(rows_init)
    else:
        # Caso coppia: 2 biomasse attive -> (N-2)+2 con le (N-2) non attive
        # come "fisse a 0".
        st.session_state["mode_radio"] = MODE_DUAL
        st.session_state["fixed_multiselect"] = list(_pending_opt["unused"])
        new_state_key = (
            f"mens_in_dual_{_opt_active_hash}_"
            f"{'-'.join(_pending_opt['unused'])}"
        )
        rows_init = []
        for mm, hh in zip(MONTHS, MONTH_HOURS):
            r = {"Mese": mm, "Ore": hh}
            for f in _pending_opt["unused"]:
                r[f] = 0.0
            rows_init.append(r)
        st.session_state[new_state_key] = pd.DataFrame(rows_init)
    # Flag per banner informativo (consumato dopo il rendering dei controlli)
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
_prod_label = (
    f"{fmt_it(plant_kwe, 0)} kW_el lordi "
    f"(= {fmt_it(plant_kwe_net, 0)} kW_el netti in rete)"
    if IS_CHP
    else f"{fmt_it(plant_net_smch, 0)} Sm³/h netti"
)
st.markdown(
    f"##### ⚡ Auto-calcolo ottimale – enumera le **{_n_combinations} combinazioni** "
    f"possibili tra le {N_active} biomasse attive e minimizza la massa totale "
    f"(saving ≥ {fmt_it(ghg_threshold*100, 0, '%')}, produzione = {_prod_label})"
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
            "stoccaggio digestato coperto con recupero gas, recupero calore "
            "CHP per digestori, ottimizzare autoconsumi elettrici"
        ) if IS_CHP else (
            "stoccaggio digestato coperto, upgrading a membrane/amminico, "
            "off-gas RTO"
        )
        _unit_prod = (
            f"{fmt_it(plant_kwe, 0)} kW_el lordi "
            f"({fmt_it(plant_kwe_net, 0)} kW_el netti rete)"
            if IS_CHP
            else f"{fmt_it(plant_net_smch, 0)} Sm³/h"
        )
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

# -------- RADIO MODALITA' --------------------------------------------------
mode = st.radio(
    "Scegli modalità:",
    options=[MODE_DUAL, MODE_SINGLE],
    index=0,
    horizontal=False,
    key="mode_radio",
)

is_dual_mode = mode.startswith(f"{N_active-2} ") or (N_active == 2 and "calcolate" in mode)

col1, col2 = st.columns([2, 3])
with col1:
    if is_dual_mode:
        # Default: prime 2 biomasse attive (indipendente dal nome)
        default_fixed = active_feeds[:min(2, N_active)]
        # Se le biomasse attive sono cambiate, resetta il default
        prev_default = st.session_state.get("fixed_multiselect", [])
        if not all(p in active_feeds for p in prev_default):
            st.session_state["fixed_multiselect"] = default_fixed
        fixed_feeds = st.multiselect(
            f"Seleziona {N_active-2} biomasse fisse (le altre 2 saranno calcolate):" if N_active > 2
            else "Seleziona 0 biomasse fisse — il solver calcola entrambe:",
            options=active_feeds,
            default=default_fixed if "fixed_multiselect" not in st.session_state else None,
            max_selections=max(N_active - 2, 0),
            help="Suggerimento: lascia come 'calcolate' almeno 1 biomassa ad alta eec "
                 "(mais/sorgo) + 1 a manure credit (liquami). Il sistema risolve "
                 "2 equazioni: produzione + saving.",
            key="fixed_multiselect",
        )
        # Numero di fisse richieste: N-2 (possono essere 0 se N=2)
        required_fixed = max(N_active - 2, 0)
        if len(fixed_feeds) != required_fixed:
            st.warning(f"Seleziona esattamente **{required_fixed}** biomasse fisse "
                       f"(le altre 2 saranno calcolate). Attualmente: {len(fixed_feeds)}.")
            st.stop()
        unknown_feeds = [n for n in active_feeds if n not in fixed_feeds]
    else:
        unknown_feed = st.selectbox(
            "Biomassa incognita (calcolata automaticamente):",
            active_feeds,
            index=min(N_active - 1, 3),
            key="single_unknown_select",
        )
        fixed_feeds = [n for n in active_feeds if n != unknown_feed]
        unknown_feeds = [unknown_feed]

# Banner risultato ottimizzazione (mostrato 1 sola volta dopo click)
_opt_info = st.session_state.pop("_optimize_info", None)
if _opt_info:
    if _opt_info.get("is_mono"):
        mono = _opt_info["mono"]
        st.success(
            f"🚀 **Ottimo LP – MONO biomassa**: unica attiva **{mono}** "
            f"(le altre {N_active - 1} = 0). "
            f"Massa totale annua minima ≈ "
            f"**{fmt_it(_opt_info['total_year'], 0)} t/anno**. "
            f"Il saving e' oltre la soglia con la sola **{mono}**."
        )
    else:
        unused_str = ", ".join([f"**{u}**" for u in _opt_info['unused'][:6]])
        if len(_opt_info['unused']) > 6:
            unused_str += f" + altre {len(_opt_info['unused']) - 6}"
        st.success(
            f"🚀 **Ottimo LP**: biomasse attive **{_opt_info['pair'][0]}** + "
            f"**{_opt_info['pair'][1]}** (le altre = 0: {unused_str}). "
            f"Massa totale annua minima ≈ "
            f"**{fmt_it(_opt_info['total_year'], 0)} t/anno** "
            f"(saving target **{fmt_it(target_saving*100, 0, '%')}**, "
            f"produzione **{_prod_label}**)."
        )

with col2:
    if is_dual_mode:
        if N_active > 2:
            st.info(
                f"**Modalità dual-constraint**: inserisci le quantità (t/mese) di "
                f"**{N_active-2} biomasse fisse**. "
                f"Il solver calcola le 2 incognite (**{unknown_feeds[0]}** e "
                f"**{unknown_feeds[1]}**) per ottenere saving "
                f"**{fmt_it(target_saving*100, 0, '%')}** "
                f"e produzione **{_prod_label}**."
            )
        else:
            st.info(
                f"**Modalità dual-constraint** (N=2): il solver calcola entrambe "
                f"(**{unknown_feeds[0]}** + **{unknown_feeds[1]}**) per ottenere "
                f"saving **{fmt_it(target_saving*100, 0, '%')}** + produzione "
                f"**{_prod_label}**."
            )
    else:
        st.info(
            f"**Modalità produzione-only**: inserisci {N_active-1} biomasse; "
            f"il sistema calcola **{unknown_feeds[0]}** per chiudere la produzione. "
            f"Il saving sarà una conseguenza (verificato in tabella)."
        )

# ------------------------- TABELLA UNIFICATA (input + risultati) -------------------------
st.subheader(_t("📆 Tabella mensile – modifica le celle ✏️, il resto si ricalcola"))

# Valori di default plausibili per biomasse comuni; fallback generico per il resto
# (il cliente li riaggiusta a mano in tabella mensile)
defaults_all = {
    "Trinciato di mais": 1800.0,
    "Trinciato di sorgo": 400.0,
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

# --- Stato persistente: memorizzo SOLO le colonne editabili (Mese, Ore, fisse).
# Chiave state univoca per combinazione mode+fisse+active_feeds, cosi' cambio
# biomasse attive -> nuovo state (evita contaminazioni tra configurazioni diverse).
_active_hash = str(hash(tuple(sorted(active_feeds))))[:8]
state_key = f"mens_in_{'dual' if is_dual_mode else 'single'}_{_active_hash}_{'-'.join(fixed_feeds)}"
if state_key not in st.session_state:
    init_rows = []
    for m, h in zip(MONTHS, MONTH_HOURS):
        row = {"Mese": m, "Ore": h}
        for f in fixed_feeds:
            row[f] = _default_mass(f)
        init_rows.append(row)
    st.session_state[state_key] = pd.DataFrame(init_rows)

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

    if is_dual_mode:
        sol, feasible, msg = solve_2_unknowns_dual(
            fixed_map, unknown_feeds, hours, aux_factor, plant_net_smch,
            ep_total, target_e_max,
        )
        all_masses = {**fixed_map, **sol}
        if not feasible:
            warnings_list.append(f"**{row['Mese']}**: {msg}")
    else:
        computed = solve_1_unknown_production(
            fixed_map, unknown_feeds[0], hours, aux_factor, plant_net_smch
        )
        all_masses = dict(fixed_map)
        all_masses[unknown_feeds[0]] = max(computed, 0.0)
        feasible = (computed >= 0)
        if not feasible:
            warnings_list.append(
                f"**{row['Mese']}**: {unknown_feeds[0]} = {fmt_it(computed, 1)} t (<0). "
                f"Le 3 biomasse fisse gia' superano il fabbisogno lordo."
            )

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
    if IS_CHP:
        # In modalita' CHP: MWh_netti rappresenta l'energia CH4 equivalente
        # entrante nel cogeneratore → split in elettrico + termico.
        # MWh_el_lordo = CH4 × η_el (ai morsetti alternatore)
        # MWh_el_netto = lordo × (1 − aux%) (immessi in rete, fatturabili)
        _mwh_el_lordo = summary["mwh_net"] * eta_el
        res["MWh elettrici lordi"] = _mwh_el_lordo
        res["MWh elettrici netti"] = _mwh_el_lordo * (1.0 - aux_el_pct)
        res["MWh termici"] = summary["mwh_net"] * eta_th
        # kW lordi medi sull'ora = MWh_el_lordi × 1000 / Ore
        # E' la metrica chiave per il vincolo CHP: deve restare <= plant_kwe
        # (potenza LORDA targa motore). Quando l'utente lavora in modalita'
        # CHP, vede "kW lordi" invece di "Sm3/h netti" perche' e' la grandezza
        # rilevante autorizzativa.
        res["kW lordi medi"] = (
            (_mwh_el_lordo * 1000.0 / hours) if hours > 0 else 0.0
        )
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
if IS_CHP:
    df_disp["MWh elettrici lordi"] = df_disp["MWh elettrici lordi"].apply(
        lambda v: fmt_it(v, 1)
    )
    df_disp["MWh elettrici netti"] = df_disp["MWh elettrici netti"].apply(
        lambda v: fmt_it(v, 1)
    )
    df_disp["MWh termici"] = df_disp["MWh termici"].apply(
        lambda v: fmt_it(v, 1)
    )
    # kW lordi medi: vincolo CHP (<= plant_kwe targa motore)
    df_disp["kW lordi medi"] = df_disp["kW lordi medi"].apply(
        lambda v: fmt_it(v, 0)
    )
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
_lbl_lordo_col = "Sm³ CH₄ lordi" if IS_CHP else "Sm³ lordi"
_lbl_netto_col = "Sm³ CH₄ motore" if IS_CHP else "Sm³ netti"
col_cfg["Sm³ lordi"]   = st.column_config.TextColumn(
    _lbl_lordo_col, disabled=True,
    help=("CH₄ equivalente prodotto dalle biomasse (pre-perdite)"
          if IS_CHP else "Sm³ biometano lordi (pre-perdite upgrading/processo)"),
)
col_cfg["Sm³ netti"]   = st.column_config.TextColumn(
    _lbl_netto_col, disabled=True,
    help=("CH₄ effettivamente bruciato dal cogeneratore (post-perdite)"
          if IS_CHP else "Sm³ biometano immessi in rete (post-aux_factor)"),
)
col_cfg["MWh netti"]   = st.column_config.TextColumn(
    "MWh_CH₄ netti" if IS_CHP else "MWh netti",
    disabled=True,
    help=("Energia CH₄ in ingresso al cogeneratore (pre-conversione elettrica)"
          if IS_CHP else "Energia biometano netta immessa in rete"),
)
if IS_CHP:
    col_cfg["MWh elettrici lordi"] = st.column_config.TextColumn(
        "MWh_el lordi", disabled=True,
        help="MWh elettrici ai morsetti alternatore = MWh_CH₄ × η_el. "
             "Non fatturabili: occorre sottrarre gli autoconsumi ausiliari.",
    )
    col_cfg["MWh elettrici netti"] = st.column_config.TextColumn(
        "MWh_el netti rete", disabled=True,
        help="MWh elettrici NETTI immessi in rete = lordi × (1 − aux%). "
             "Base di calcolo della tariffa T.O. GSE.",
    )
    col_cfg["MWh termici"] = st.column_config.TextColumn(
        "MWh_th", disabled=True,
        help="MWh termici recuperati dal CHP = MWh_CH₄ × η_th. "
             "Utilizzabili per digestori, teleriscaldamento, processo.",
    )
    # kW lordi medi: il VINCOLO autorizzativo CHP (vs plant_kwe targa).
    col_cfg["kW lordi medi"] = st.column_config.TextColumn(
        "kW lordi (medi)", disabled=True,
        help=f"Potenza media oraria ai morsetti alternatore "
             f"(MWh_el lordi × 1000 / Ore). "
             f"VINCOLO normativo: ≤ {fmt_it(plant_kwe, 0)} kWe LORDI "
             f"(targa motore — dato di autorizzazione).",
    )
col_cfg["GHG (gCO₂/MJ)"] = st.column_config.TextColumn(
    "e_w", disabled=True, help="Emissioni pesate gCO₂eq/MJ",
)
col_cfg["Saving %"] = st.column_config.TextColumn(
    "Saving %", disabled=True,
    help=f"Obbligatorio ≥ {fmt_it(ghg_threshold*100, 0, '%')} (RED III – {end_use})",
)
# Sm³/h netti: visibile in biometano (vincolo autorizzativo).
# In CHP il vincolo e' kW lordi (mostrato sopra), Sm³/h CH4 e' solo
# informativo (CH4 al motore) - lo lasciamo nascosto al display tabella
# per ridurre rumore. La taglia CH4 motore e' gia' visibile in sidebar.
if IS_CHP:
    # Nascondiamo Sm³/h netti dalla vista (esiste in df_res ma non
    # appare in df_disp grazie a column_order).
    col_cfg["Sm³/h netti"] = st.column_config.TextColumn(
        "Sm³/h CH₄ motore", disabled=True,
        help=f"Flusso CH₄ al motore = MWh_CH₄ × 1000 / (Ore × {fmt_it(NM3_TO_MWH*1000, 2)}). "
             f"Info-only (il vincolo CHP e' kW lordi a sinistra). "
             f"Equivale a {fmt_it(plant_net_smch, 0)} Sm³/h come dato "
             f"di dimensionamento.",
    )
else:
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
new_input["Ore"] = new_input["Ore"].apply(parse_it).clip(lower=0).astype(int)
for f in fixed_feeds:
    new_input[f] = new_input[f].apply(parse_it).clip(lower=0).astype(float)

old_input = input_df[edit_cols].reset_index(drop=True).copy()
old_input["Ore"] = old_input["Ore"].astype(int)
for f in fixed_feeds:
    old_input[f] = old_input[f].astype(float)

if not new_input.equals(old_input):
    st.session_state[state_key] = new_input
    st.rerun()

if warnings_list:
    st.warning("⚠️ Mesi con problemi di fattibilità:\n\n" + "\n\n".join(f"- {w}" for w in warnings_list))

# ------------------------- SINTESI -------------------------
st.subheader(_t("📈 Sintesi annuale"))
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tot. biomasse (t/anno)",
          fmt_it(df_res["Totale biomasse (t)"].sum(), 0))
if IS_CHP:
    c2.metric("Sm³ CH₄ motore (anno)",
              fmt_it(df_res["Sm³ netti"].sum(), 0),
              help="CH₄ equivalente effettivamente bruciato dal cogeneratore")
    c3.metric("MWh_el netti rete (anno)",
              fmt_it(df_res["MWh elettrici netti"].sum(), 0),
              help="Energia elettrica NETTA immessa in rete (post-aux)")
else:
    c2.metric("Sm³ netti (anno)",
              fmt_it(df_res["Sm³ netti"].sum(), 0))
    c3.metric("MWh netti (anno)",
              fmt_it(df_res["MWh netti"].sum(), 0))
c4.metric("Saving medio (%)",
          fmt_it(df_res["Saving %"].mean(), 1))
valid_months = df_res["Validità"].str.startswith("✅").sum()
c5.metric("Mesi validi", f"{valid_months}/12",
          delta="OK" if valid_months == 12 else f"{12-valid_months} NON validi",
          delta_color="normal" if valid_months == 12 else "inverse")

# ------------------------- GRAFICI -------------------------
# Tab "Business Plan" visibile solo in DM 2022 (BP applicabile)
if IS_DM2022:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        _t("🌾 Biomasse per mese"),
        _t("🌍 Sostenibilità"),
        _t("⚡ Produzione"),
        _t("🥧 Mix annuale"),
        _t("💼 Business Plan"),
    ])
else:
    tab1, tab2, tab3, tab4 = st.tabs([
        _t("🌾 Biomasse per mese"),
        _t("🌍 Sostenibilità"),
        _t("⚡ Produzione"),
        _t("🥧 Mix annuale"),
    ])
    tab5 = None

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
        "Sm³ CH₄ lordi (biomasse)" if IS_CHP else "Sm³ lordi (biomasse)"
    )
    _lbl_netto = (
        "Sm³ CH₄ al motore" if IS_CHP else "Sm³ netti (immessi in rete)"
    )
    _lbl_title = (
        "Produzione mensile CH₄ equivalente (biogas CHP)" if IS_CHP
        else "Produzione mensile Sm³"
    )
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

    colA, colB = st.columns(2)
    with colA:
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
        _pie_mwh_label = (
            "MWh_el netti rete" if IS_CHP else "MWh netti"
        )
        _pie_total = (
            sum(annual_mwh.values()) * eta_el * (1.0 - aux_el_pct)
            if IS_CHP else sum(annual_mwh.values())
        )
        _pie_values = (
            [v * eta_el * (1.0 - aux_el_pct) for v in annual_mwh.values()]
            if IS_CHP else list(annual_mwh.values())
        )
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

    if IS_DM2018:
        if advanced_mode == "Forza AVANZATO (override manuale)":
            is_advanced = True
        elif advanced_mode == "Forza NON avanzato (override manuale)":
            is_advanced = False
        else:  # auto da quota Annex IX in massa
            is_advanced = annex_mass_share >= annex_threshold
        # CIC double counting attivo SOLO se end_use ammette CIC
        # (trasporti) E impianto avanzato.
        _cic_premium_use = DM2018_END_USES[end_use]["cic_premium"]
        cic_double = is_advanced and _cic_premium_use
        cic_active  = _cic_premium_use  # CIC system in use (single or double)
    else:
        is_advanced  = False
        cic_double   = False
        cic_active   = False

    # ============================================================
    # CALCOLO STATUS FER 2 (matrice >=80% sottoprodotti)
    # ============================================================
    if IS_FER2:
        # Stessa logica della quota Annex IX in massa: i sottoprodotti
        # FER 2 = tutti i feedstock con annex_ix in ("A","B").
        # Le colture dedicate (annex_ix=None) NON contano come sottoprodotti.
        fer2_subprod_share = annex_mass_share  # alias semantico
        fer2_qualified = fer2_subprod_share >= fer2_matrice_threshold
        # Premi effettivi (toggle utente AND condizione fisica)
        fer2_apply_matrice = fer2_premio_matrice_attivo and fer2_qualified
        fer2_apply_car = fer2_premio_car_attivo
        fer2_tariffa_eff = (
            fer2_tariffa_base
            + (fer2_premio_matrice_eur if fer2_apply_matrice else 0.0)
            + (fer2_premio_car_eur if fer2_apply_car else 0.0)
        )
    else:
        fer2_subprod_share   = 0.0
        fer2_qualified       = False
        fer2_apply_matrice   = False
        fer2_apply_car       = False
        fer2_tariffa_eff     = 0.0

    # ============================================================
    # TARIFFA PER BIOMASSA — applicabile solo se NON in regime CIC
    # ============================================================
    # In regime CIC (DM 2018 trasporti) il prezzo e' unico per tutto il
    # biometano (cic_price € per CIC), non personalizzato per biomassa.
    # In regime FER 2 la tariffa e' calcolata da TR + premi (uniforme),
    # ma resta editabile per biomassa per scenari custom.
    if IS_FER2:
        _tar_unit = "€/MWh_el"
        _tar_default = fer2_tariffa_eff
    elif IS_CHP:
        _tar_unit = "€/MWh_el"
        _tar_default = 280.0
    elif IS_DM2018 and not cic_active:
        _tar_unit = "€/MWh"
        _tar_default = 110.0   # DM 2018 altri usi/CAR: tariffa base
    else:
        _tar_unit = "€/MWh"
        _tar_default = 120.0
    st.markdown(
        f"##### 💶 Dettaglio per tipologia di biomassa"
        + (
            f" (regime CIC unico — tariffa €/MWh non applicabile per biomassa)"
            if cic_active else f" (tariffa {_tar_unit} editabile ✏️)"
        )
    )
    if IS_FER2:
        # Box riepilogo FER 2
        if fer2_qualified:
            st.success(
                f"🔋 **FER 2 · QUOTA MATRICE OK** "
                f"({fmt_it(fer2_subprod_share*100, 1, '%')} sottoprodotti, "
                f"soglia {fmt_it(fer2_matrice_threshold*100, 0, '%')}). "
                f"Tariffa effettiva: "
                f"**{fmt_it(fer2_tariffa_base, 0)} TR**"
                + (f" **+ {fmt_it(fer2_premio_matrice_eur, 0)} matrice**"
                   if fer2_apply_matrice else
                   f" + ~~{fmt_it(fer2_premio_matrice_eur, 0)} matrice~~")
                + (f" **+ {fmt_it(fer2_premio_car_eur, 0)} CAR**"
                   if fer2_apply_car else
                   f" + ~~{fmt_it(fer2_premio_car_eur, 0)} CAR~~")
                + f" = **{fmt_it(fer2_tariffa_eff, 0)} €/MWh_el**. "
                f"Periodo incentivo: {FER2_PERIODO_ANNI} anni."
            )
        else:
            st.error(
                f"❌ **FER 2 · QUOTA MATRICE INSUFFICIENTE** "
                f"({fmt_it(fer2_subprod_share*100, 1, '%')} sottoprodotti vs "
                f"soglia richiesta {fmt_it(fer2_matrice_threshold*100, 0, '%')}). "
                f"Premio matrice DISATTIVATO. Riduci la quota di colture "
                f"dedicate (cap normativo 20%) o aumenta sottoprodotti/effluenti. "
                f"Tariffa effettiva: **{fmt_it(fer2_tariffa_eff, 0)} €/MWh_el**."
            )
    elif IS_CHP:
        st.caption(
            "⚡ **Modalità Biogas CHP DM 6/7/2012**: tariffa €/MWh_el "
            "applicata ai **MWh elettrici NETTI immessi in rete** "
            f"(= MWh_el lordi × (1 − aux%), con aux = {fmt_it(aux_el_pct*100, 1, '%')}). "
            "Default **280 €/MWh** (TO base DM 6/7/2012 per biogas agricolo "
            "<1 MW + premio CAR + premio matrice sottoprodotti). "
            "Modificabile per scenari FER-X, PPA, vendita spot."
        )
    elif IS_DM2018 and cic_active:
        if is_advanced:
            st.success(
                f"🌿 **DM 2018 · BIOMETANO AVANZATO** "
                f"(quota Annex IX in massa: "
                f"{fmt_it(annex_mass_share*100, 1, '%')}, soglia "
                f"{fmt_it(annex_threshold*100, 0, '%')}). "
                f"Sistema CIC con **double counting**: 1 CIC ogni "
                f"{fmt_it(MWH_PER_CIC/2, 2)} MWh "
                f"({fmt_it(GCAL_PER_CIC/2, 0)} Gcal). "
                f"Valore CIC: **{fmt_it(cic_price, 0)} €/CIC**."
            )
        else:
            st.warning(
                f"⚠️ **DM 2018 · BIOMETANO NON AVANZATO** "
                f"(quota Annex IX in massa: "
                f"{fmt_it(annex_mass_share*100, 1, '%')}, sotto soglia "
                f"{fmt_it(annex_threshold*100, 0, '%')}). "
                f"Sistema CIC **senza** double counting: 1 CIC ogni "
                f"{fmt_it(MWH_PER_CIC, 2)} MWh "
                f"({fmt_it(GCAL_PER_CIC, 0)} Gcal). "
                f"Valore CIC: **{fmt_it(cic_price, 0)} €/CIC**."
            )
    elif IS_DM2018 and not cic_active:
        st.info(
            f"ℹ️ **DM 2018 · {end_use}**: regime tariffa diretta €/MWh "
            f"(non CIC). Modifica le tariffe per biomassa qui sotto "
            f"per simulare scenari diversi."
        )

    # Stato persistente: tariffe per biomassa (separate per mode).
    # In FER 2 la tariffa e' uniforme (TR+premi) e calcolata dinamicamente:
    # forziamo ogni run a fer2_tariffa_eff per riflettere subito le modifiche
    # sidebar (TR, premi). Niente cache per biomassa.
    _tar_key = f"tariffs_eur_mwh_{APP_MODE}"
    if IS_FER2:
        st.session_state[_tar_key] = {n: fer2_tariffa_eff for n in active_feeds}
    else:
        if _tar_key not in st.session_state:
            st.session_state[_tar_key] = {n: _tar_default for n in active_feeds}
        # Retrocompat: se mancano chiavi per nuove biomasse
        for n in active_feeds:
            if n not in st.session_state[_tar_key]:
                st.session_state[_tar_key][n] = _tar_default

    # MWh totale (base CIC nel caso DM 2018)
    _tot_mwh_basis_raw = sum(annual_mwh.values())  # MWh CH4 netto per biometano

    detail_rows = []
    pdf_revenue_rows = []  # raw numerics per il report PDF
    tot_n_cic = 0.0
    for n in active_feeds:
        t = annual_t[n]
        nm3_lordi = t * _yield_of(n)  # resa effettiva (BMT override se attivo)
        nm3_netti = nm3_lordi / aux_factor
        mwh_netti = nm3_netti * NM3_TO_MWH

        # --- Calcolo ricavi mode-aware ---
        if IS_CHP:
            mwh_el_lordo = mwh_netti * eta_el
            mwh_el_netto_rete = mwh_el_lordo * (1.0 - aux_el_pct)
            mwh_revenue = mwh_el_netto_rete  # tariffa T.O. applicata al netto rete
            tariffa = st.session_state[_tar_key][n]
            ricavi = mwh_revenue * tariffa
            n_cic = 0.0
        elif IS_DM2018 and cic_active:
            # CIC SYSTEM: prezzo unico, ricavi = n_CIC * cic_price.
            # double counting plant-level (vedi cic_double).
            mwh_el_lordo = 0.0
            mwh_el_netto_rete = 0.0
            mwh_revenue = mwh_netti
            cic_factor = 2.0 if cic_double else 1.0
            n_cic = (mwh_netti / MWH_PER_CIC) * cic_factor
            tariffa = cic_price  # informativo, non per biomassa
            ricavi = n_cic * cic_price
        else:
            # DM 2022 o DM 2018 altri usi: tariffa diretta €/MWh
            mwh_el_lordo = 0.0
            mwh_el_netto_rete = 0.0
            mwh_revenue = mwh_netti
            tariffa = st.session_state[_tar_key][n]
            ricavi = mwh_revenue * tariffa
            n_cic = 0.0
        tot_n_cic += n_cic
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
        }
        if IS_CHP:
            row_detail["MWh_el lordi/anno"] = fmt_it(mwh_el_lordo, 1)
            row_detail["MWh_el netti rete/anno"] = fmt_it(mwh_el_netto_rete, 1)
            row_detail["MWh termici/anno"] = fmt_it(mwh_netti * eta_th, 1)
        if IS_DM2018:
            _aix = FEEDSTOCK_DB[n].get("annex_ix")
            row_detail["Annex IX"] = (
                "✅ A" if _aix == "A" else
                "✅ B" if _aix == "B" else
                "—"
            )
            if cic_active:
                row_detail["CIC/anno"] = fmt_it(n_cic, 2)
        row_detail["Quota % MWh"] = fmt_it(quota, 1, "%")
        if cic_active:
            # In regime CIC mostriamo "Tariffa €/CIC" uniforme (non editabile per riga)
            row_detail[f"Tariffa €/CIC"] = fmt_it(cic_price, 2)
        else:
            row_detail[f"Tariffa {_tar_unit}"] = fmt_it(tariffa, 2)
        row_detail["Ricavi €/anno"] = fmt_it(ricavi, 0, " €")
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
            help=("CIC × valore CIC" if cic_active
                  else f"MWh {'elettrici netti rete' if IS_CHP else 'netti'}"
                       f" × tariffa {_tar_unit}")
                 + " (si ricalcola al variare dei parametri)",
        ),
    }
    if cic_active:
        detail_col_cfg["Tariffa €/CIC"] = st.column_config.TextColumn(
            "Valore CIC €", disabled=True,
            help="Prezzo unitario CIC fissato in sidebar. Uniforme per "
                 "tutto il biometano (no editing per biomassa in regime CIC).",
        )
    elif IS_FER2:
        detail_col_cfg[f"Tariffa {_tar_unit}"] = st.column_config.TextColumn(
            "Tariffa eff. €/MWh_el", disabled=True,
            help="Tariffa effettiva FER 2 = TR base + premio matrice "
                 "(se attivo) + premio CAR (se attivo). Uniforme: "
                 "modifica TR/premi in sidebar per aggiornare.",
        )
    else:
        detail_col_cfg[f"Tariffa {_tar_unit}"] = st.column_config.TextColumn(
            f"Tariffa {_tar_unit} ✏️",
            help=f"Tariffa incentivante/PPA [{_tar_unit}] in formato "
                 f"italiano (es. 1.234,56). Modificabile per simulazioni.",
        )
    if IS_CHP:
        detail_col_cfg["MWh_el lordi/anno"] = st.column_config.TextColumn(
            "MWh_el lordi/anno", disabled=True,
            help="MWh elettrici lordi ai morsetti alternatore "
                 "(= MWh netti × η_el). Non fatturabili direttamente: "
                 "occorre sottrarre gli autoconsumi ausiliari.",
        )
        detail_col_cfg["MWh_el netti rete/anno"] = st.column_config.TextColumn(
            "MWh_el netti rete/anno", disabled=True,
            help="MWh elettrici NETTI immessi in rete e fatturati a tariffa T.O. "
                 "(= MWh_el lordi × (1 − aux%)). Questa è la base ricavi.",
        )
        detail_col_cfg["MWh termici/anno"] = st.column_config.TextColumn(
            "MWh_th/anno", disabled=True,
            help="MWh termici recuperati dal cogeneratore "
                 "(= MWh netti × η_th). Usabili per teleriscaldamento / processo.",
        )
    if IS_DM2018:
        detail_col_cfg["Annex IX"] = st.column_config.TextColumn(
            "All. IX", disabled=True,
            help="Classificazione Annex IX RED II/III. Parte A = "
                 "letame, FORSU, sottoprodotti agroindustriali, paglia. "
                 "Parte B = oli/grassi (UCO, scarti macellazione cat. 3). "
                 "Solo le matrici Annex IX qualificano per double counting "
                 "CIC quando l'impianto e' classificato «avanzato».",
        )
        if cic_active:
            detail_col_cfg["CIC/anno"] = st.column_config.TextColumn(
                "CIC/anno 🧮", disabled=True,
                help=(f"Numero CIC generati = MWh / "
                      f"{fmt_it(MWH_PER_CIC if not cic_double else MWH_PER_CIC/2, 2)}"
                      f" MWh per CIC"
                      + (" (×2 double counting avanzato)" if cic_double else "")),
            )

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
    # NB1: in regime CIC le tariffe non sono editabili (cic_price unico in sidebar).
    # NB2: in regime FER 2 la tariffa e' uniforme TR+premi (forzata in sidebar).
    if not cic_active and not IS_FER2:
        _tar_col = f"Tariffa {_tar_unit}"
        new_tariffs = {
            row["Biomassa"]: max(parse_it(row[_tar_col]), 0.0)
            for _, row in edited_detail.iterrows()
        }
        if new_tariffs != st.session_state[_tar_key]:
            st.session_state[_tar_key] = new_tariffs
            st.rerun()

    # ============================================================
    # TOTALI RICAVI (mode-aware)
    # ============================================================
    tot_mwh = sum(annual_mwh.values())
    # Base MWh su cui si calcola la tariffa:
    #  - biometano DM 2022 / DM 2018 altri usi -> MWh netti
    #  - CHP -> MWh elettrici netti rete (lordo × (1 − aux%))
    #  - DM 2018 CIC -> n_CIC × cic_price (gia' aggregato in tot_n_cic)
    if IS_CHP:
        _chp_factor = eta_el * (1.0 - aux_el_pct)
    else:
        _chp_factor = 1.0
    tot_revenue_base_mwh = tot_mwh * _chp_factor
    if cic_active:
        tot_revenue = tot_n_cic * cic_price
        tariffa_media_ponderata = (
            (tot_revenue / tot_mwh) if tot_mwh > 0 else 0.0
        )  # equivalente €/MWh per confronto cross-mode
    else:
        tot_revenue = sum(
            annual_mwh[n] * _chp_factor * st.session_state[_tar_key][n]
            for n in active_feeds
        )
        tariffa_media_ponderata = (
            (tot_revenue / tot_revenue_base_mwh) if tot_revenue_base_mwh > 0 else 0.0
        )
    if IS_CHP:
        tot_mwh_el_lordo = tot_mwh * eta_el
        tot_mwh_el_netto = tot_mwh_el_lordo * (1.0 - aux_el_pct)
        tot_mwh_el_aux = tot_mwh_el_lordo - tot_mwh_el_netto
        tot_mwh_th = tot_mwh * eta_th
        cA, cB, cC, cD = st.columns(4)
        cA.metric("MWh_el lordi/anno", fmt_it(tot_mwh_el_lordo, 0),
                  delta=f"−{fmt_it(tot_mwh_el_aux, 0)} aux",
                  delta_color="inverse")
        cB.metric("⚡ MWh_el netti rete/anno", fmt_it(tot_mwh_el_netto, 0))
        cC.metric("🔥 MWh termici/anno", fmt_it(tot_mwh_th, 0))
        cD.metric("💰 Ricavi elettrici/anno", fmt_it(tot_revenue, 0, " €"))
        if IS_FER2:
            st.caption(
                f"📐 **Calcolo FER 2 (≤{fmt_it(FER2_KWE_CAP, 0)} kWe)**: "
                f"MWh_el lordi = MWh_CH₄ × η_el "
                f"({fmt_it(eta_el*100, 0, '%')}) · "
                f"MWh_el netti rete = lordi × (1 − aux%) "
                f"(aux = {fmt_it(aux_el_pct*100, 1, '%')}) · "
                f"**Tariffa effettiva = TR ({fmt_it(fer2_tariffa_base, 0)})"
                + (f" + matrice ({fmt_it(fer2_premio_matrice_eur, 0)})"
                   if fer2_apply_matrice else "")
                + (f" + CAR ({fmt_it(fer2_premio_car_eur, 0)})"
                   if fer2_apply_car else "")
                + f" = {fmt_it(fer2_tariffa_eff, 0)} €/MWh_el** · "
                f"Ricavi = MWh_el netti × tariffa effettiva. "
                f"Cumulo nel periodo {FER2_PERIODO_ANNI} anni: "
                f"~{fmt_it(tot_revenue * FER2_PERIODO_ANNI / 1_000_000, 1)} M€."
            )
        else:
            st.caption(
                f"📐 **Calcolo CHP DM 6/7/2012**: MWh_el lordi = MWh netti × η_el "
                f"({fmt_it(eta_el*100, 0, '%')}) · "
                f"MWh_el netti rete = lordi × (1 − aux%) "
                f"(aux = {fmt_it(aux_el_pct*100, 1, '%')}) · "
                f"MWh termici = MWh netti × η_th "
                f"({fmt_it(eta_th*100, 0, '%')}) · "
                f"**Ricavi = MWh_el netti rete × tariffa €/MWh_el** "
                f"(è l'energia realmente immessa in rete e fatturata al GSE). "
                f"Il calore può generare ricavi aggiuntivi (teleriscaldamento, "
                f"processo, essiccazione digestato) non inclusi qui."
            )
    elif cic_active:
        cA, cB, cC, cD = st.columns(4)
        cA.metric("MWh netti totali/anno", fmt_it(tot_mwh, 0))
        cB.metric("CIC/anno",
                  fmt_it(tot_n_cic, 1),
                  delta=("AVANZATO ×2" if cic_double else "non avanzato"),
                  delta_color="normal" if cic_double else "off")
        cC.metric("Quota Annex IX (massa)",
                  fmt_it(annex_mass_share*100, 1, "%"),
                  delta=f"soglia {fmt_it(annex_threshold*100, 0, '%')}",
                  delta_color="normal" if is_advanced else "inverse")
        cD.metric("💰 Ricavi CIC/anno", fmt_it(tot_revenue, 0, " €"),
                  delta=f"≈ {fmt_it(tariffa_media_ponderata, 1)} €/MWh equiv.")
        st.caption(
            f"📐 **Calcolo DM 2018 CIC**: 1 CIC = "
            f"{fmt_it(MWH_PER_CIC, 2)} MWh "
            f"({fmt_it(GCAL_PER_CIC, 0)} Gcal). "
            + (f"**Double counting AVANZATO** → 1 CIC ogni "
               f"{fmt_it(MWH_PER_CIC/2, 2)} MWh "
               f"({fmt_it(GCAL_PER_CIC/2, 0)} Gcal). "
               if cic_double else
               "Non avanzato → single counting. ")
            + f"**Ricavi = N_CIC × {fmt_it(cic_price, 0)} €/CIC**. "
            f"NB: per certificazione GSE serve dichiarazione di sostenibilità "
            f"con tracciabilità feedstock per ogni periodo di rendicontazione."
        )
    else:
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
# TAB 5 — BUSINESS PLAN (solo DM 2022)
# ============================================================
if IS_DM2022 and tab5 is not None and bp_result is not None:
    with tab5:
        st.markdown(
            "<div style='font-family:\"JetBrains Mono\", monospace; "
            "font-size:0.7rem; font-weight:600; letter-spacing:1.5px; "
            f"text-transform:uppercase; color:{TEXT_MUTED}; "
            "margin-bottom:8px;'>// PRO FORMA · DM 2022</div>",
            unsafe_allow_html=True,
        )
        st.subheader(_t("💼 Business Plan — pro forma 15 anni"))
        st.caption(
            "Modello derivato dal **benchmark di un impianto medio biometano agricolo (250 Smc/h)** "
            "(maggio 2024), aggiornato 2026 con inflazione ISTAT cumulata e "
            "tassi finanziamento BCE. Personalizza i parametri nella sidebar "
            "(expander «💼 Pro Forma»). Tariffa GSE applicata in nominale "
            f"per {BP_DURATA_TARIFFA_ANNI} anni · OPEX rivalutati ISTAT."
        )

        # ===== KPI tiles in 4 columns =====
        bp_cA, bp_cB, bp_cC, bp_cD = st.columns(4)
        bp_cA.metric(
            "CAPEX totale",
            fmt_it(bp_result["capex_totale"]/1000, 0, " k€"),
            delta=f"netto {fmt_it(bp_result['capex_netto']/1000, 0)} k€ "
                  f"(post PNRR {fmt_it(bp_pnrr_pct, 0, '%')})",
        )
        bp_cB.metric(
            "Ricavi anno regime",
            fmt_it(bp_result["ricavi"][0]/1000, 0, " k€/a"),
            delta=f"{fmt_it(bp_result['biometano_smc_anno']/1000, 0)} kSmc · "
                  f"tariffa {fmt_it(bp_tariffa_eff, 1)} €/MWh",
        )
        bp_cC.metric(
            "EBITDA medio (pre-biomasse)",
            fmt_it(bp_result["ebitda_medio"]/1000, 0, " k€/a"),
            delta=f"target margin {fmt_it(bp_ebitda_target_pct, 1, '%')}",
        )
        bp_cD.metric(
            "💰 Costo biogas implicito",
            fmt_it(bp_result["costo_biogas_eur_per_nm3"], 4, " €/Nm³"),
            delta=f"q.biomasse {fmt_it(bp_result['quota_biomasse_anno']/1000, 0)} k€/a",
        )

        st.divider()

        # ===== CAPEX breakdown table =====
        st.markdown("##### 🏗️ CAPEX — composizione")
        capex_rows = []
        for k, v in bp_capex_breakdown.items():
            tot_v = v * plant_net_smch
            capex_rows.append({
                "Voce": k,
                "Tipo": "Scalabile (€/(Smc/h))",
                "Importo unitario": fmt_it(v, 0, " €/(Smc/h)"),
                "Totale": fmt_it(tot_v, 0, " €"),
                "Quota %": fmt_it(tot_v / bp_result["capex_totale"] * 100, 1, "%"),
            })
        for k, v in bp_capex_forfait.items():
            capex_rows.append({
                "Voce": k,
                "Tipo": "Forfait",
                "Importo unitario": "—",
                "Totale": fmt_it(v, 0, " €"),
                "Quota %": fmt_it(v / bp_result["capex_totale"] * 100, 1, "%"),
            })
        capex_rows.append({
            "Voce": "**TOTALE CAPEX**",
            "Tipo": "—",
            "Importo unitario": "—",
            "Totale": fmt_it(bp_result["capex_totale"], 0, " €"),
            "Quota %": "100,0%",
        })
        capex_rows.append({
            "Voce": "Contributo PNRR (M2C2)",
            "Tipo": "—",
            "Importo unitario": fmt_it(bp_pnrr_pct, 0, "%"),
            "Totale": fmt_it(-bp_result["contributo"], 0, " €"),
            "Quota %": fmt_it(-bp_result["contributo"] /
                              bp_result["capex_totale"] * 100, 1, "%"),
        })
        capex_rows.append({
            "Voce": "**CAPEX NETTO** (post-PNRR)",
            "Tipo": "—",
            "Importo unitario": "—",
            "Totale": fmt_it(bp_result["capex_netto"], 0, " €"),
            "Quota %": fmt_it(bp_result["capex_netto"] /
                              bp_result["capex_totale"] * 100, 1, "%"),
        })
        st.dataframe(
            pd.DataFrame(capex_rows),
            hide_index=True, use_container_width=True,
        )

        # ===== CE multi-anno chart =====
        st.divider()
        st.markdown("##### 📊 Conto Economico 15 anni")
        anni = list(range(1, len(bp_result["ricavi"]) + 1))
        df_ce = pd.DataFrame({
            "Anno": anni,
            "Ricavi (k€)": [r/1000 for r in bp_result["ricavi"]],
            "OPEX (k€)": [-o/1000 for o in bp_result["opex"]],
            "EBITDA pre-biomasse (k€)": [e/1000 for e in bp_result["ebitda"]],
            "Interessi (k€)": [-i/1000 for i in bp_result["interessi"]],
            "Ammortamenti (k€)": [-a/1000 for a in bp_result["ammortamenti"]],
            "Utile netto (k€)": [u/1000 for u in bp_result["utile_netto"]],
            "FCF (k€)": [f/1000 for f in bp_result["fcf"]],
        })

        fig_bp = go.Figure()
        fig_bp.add_trace(go.Bar(
            x=anni, y=df_ce["Ricavi (k€)"],
            name="Ricavi", marker_color=AMBER,
        ))
        fig_bp.add_trace(go.Bar(
            x=anni, y=df_ce["OPEX (k€)"],
            name="OPEX (inflaz.)", marker_color="#94A3B8",
        ))
        fig_bp.add_trace(go.Scatter(
            x=anni, y=df_ce["EBITDA pre-biomasse (k€)"],
            name="EBITDA pre-biomasse",
            mode="lines+markers",
            line=dict(color=NAVY, width=3),
            marker=dict(size=8, color=NAVY),
        ))
        fig_bp.add_trace(go.Scatter(
            x=anni, y=df_ce["Utile netto (k€)"],
            name="Utile netto", mode="lines+markers",
            line=dict(color="#10B981", width=2, dash="dot"),
            marker=dict(size=6),
        ))
        fig_bp.update_layout(
            barmode="relative", height=480,
            yaxis_title="k€ / anno",
            xaxis_title="Anno",
            xaxis=dict(tickmode="linear", dtick=1),
            legend=dict(orientation="h", yanchor="bottom",
                        y=1.02, xanchor="right", x=1),
        )
        apply_metaniq_theme(fig_bp, dark=IS_DARK)
        st.plotly_chart(fig_bp, use_container_width=True)

        # ===== CE table =====
        df_ce_disp = df_ce.copy()
        for col in df_ce_disp.columns:
            if col != "Anno":
                df_ce_disp[col] = df_ce_disp[col].apply(
                    lambda v: fmt_it(v, 0)
                )
        df_ce_disp["Anno"] = df_ce_disp["Anno"].apply(lambda v: f"Anno {v}")
        st.dataframe(df_ce_disp, hide_index=True, use_container_width=True)

        # ===== Cash Flow & Debito =====
        st.divider()
        st.markdown("##### 💵 Cash Flow & Schema finanziamento")
        fin_cA, fin_cB, fin_cC = st.columns(3)
        fin_cA.metric(
            "Debito LT iniziale",
            fmt_it(bp_result["debito_lt"]/1000, 0, " k€"),
            delta=f"leva {fmt_it(bp_lt_leva, 0, '%')}",
        )
        fin_cB.metric(
            "Equity (soci)",
            fmt_it(bp_result["equity"]/1000, 0, " k€"),
            delta=f"leva {fmt_it(100-bp_lt_leva, 0, '%')}",
        )
        fin_cC.metric(
            "Rata LT/anno",
            fmt_it(bp_result["rata_lt"]/1000, 0, " k€/a"),
            delta=f"{fmt_it(bp_lt_durata, 0)} anni @ "
                  f"{fmt_it(bp_lt_tasso, 2, '%')}",
        )

        # ===== KPI finanziari =====
        st.markdown("##### 🎯 Indicatori finanziari")
        kpi_cA, kpi_cB, kpi_cC, kpi_cD = st.columns(4)
        irr_value = bp_result["irr_equity"]
        kpi_cA.metric(
            "IRR equity",
            (fmt_it(irr_value*100, 1, "%")
             if irr_value is not None else "n/d"),
            delta=("eccellente" if irr_value and irr_value > 0.15 else
                   "buono" if irr_value and irr_value > 0.10 else
                   "marginale" if irr_value and irr_value > 0.05 else
                   "basso"),
            delta_color="normal" if irr_value and irr_value > 0.10 else "inverse",
        )
        kpi_cB.metric(
            "Payback equity",
            (f"{fmt_it(bp_result['payback_anno'], 1)} anni"
             if bp_result["payback_anno"] is not None else "> 15 anni"),
        )
        kpi_cC.metric(
            "FCF cumulato 15a",
            fmt_it(bp_result["fcf_tot"]/1000, 0, " k€"),
        )
        kpi_cD.metric(
            "Utile netto cum.",
            fmt_it(bp_result["utile_netto_tot"]/1000, 0, " k€"),
        )

        # ===== Liquidazione biomasse calcolata =====
        st.divider()
        st.markdown(
            "##### 🌾 Liquidazione biomasse (derivata dal BP)"
        )
        st.caption(
            f"Calcolata come **resa CH₄/ton × costo biogas implicito** "
            f"({fmt_it(bp_result['costo_biogas_eur_per_nm3'], 4)} €/Nm³ "
            f"al CH₄ {fmt_it(bp_ch4_in_biogas_pct, 1, '%')} nel biogas). "
            f"Confronto con benchmark settore (mais 230 → 71,71 €/t)."
        )
        # Per ogni biomassa attiva, calcola la liquidazione €/ton
        # = resa Nm3 CH4/t / ch4_frac × costo_biogas €/Nm3 (biogas)
        liq_rows = []
        for f in active_feeds[:15]:  # limita a 15 per leggibilità
            yld = _yield_of(f)  # Nm3 CH4/t — resa effettiva (BMT override se attivo)
            biogas_per_t = yld / bp_result["ch4_frac"]
            liq_eur_t = biogas_per_t * bp_result["costo_biogas_eur_per_nm3"]
            liq_rows.append({
                "Biomassa": f,
                "Resa CH₄ Nm³/t": fmt_it(yld, 0),
                "Resa biogas Nm³/t": fmt_it(biogas_per_t, 0),
                "Liquidazione €/t (FM)": fmt_it(liq_eur_t, 2, " €"),
            })
        st.dataframe(
            pd.DataFrame(liq_rows),
            hide_index=True, use_container_width=True,
        )
elif IS_DM2022 and tab5 is not None:
    with tab5:
        st.warning(
            "Il calcolo BP non è disponibile. Verifica i parametri Pro Forma "
            "nella sidebar (expander «💼 Pro Forma»)."
        )

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
            "APP_MODE_LABEL":    {
                "biometano":        "Biometano DM 2022",
                "biometano_2018":   "Biometano DM 2018 (CIC)",
                "biogas_chp":       "Biogas CHP DM 6/7/2012",
                "biogas_chp_fer2":  "Biogas CHP FER 2 (≤300 kW)",
            }.get(APP_MODE, APP_MODE),
            "lang":              _LANG,
            # Flag normativi
            "IS_CHP":            IS_CHP,
            "IS_CHP_DM2012":     IS_CHP_DM2012,
            "IS_FER2":           IS_FER2,
            "IS_DM2018":         IS_DM2018,
            "IS_DM2022":         IS_DM2022,
            # Impianto
            "plant_net_smch":    plant_net_smch,
            "plant_kwe":         plant_kwe,
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
            "saving_avg":        float(df_res["Saving %"].mean()),
            "valid_months":      int(df_res["Validità"].str.startswith("✅").sum()),
            "tot_revenue":       float(tot_revenue),
            "tot_n_cic":         float(tot_n_cic) if IS_DM2018 else 0.0,
            "cic_active":        bool(cic_active) if IS_DM2018 else False,
            "is_advanced":       bool(is_advanced) if IS_DM2018 else False,
            "tariffa_media_ponderata": float(tariffa_media_ponderata)
                                       if 'tariffa_media_ponderata' in dir() else 0.0,
            "tot_mwh_el_lordo":  float(df_res["MWh elettrici lordi"].sum())
                                 if IS_CHP and "MWh elettrici lordi" in df_res
                                 else 0.0,
            "tot_mwh_el_netto":  float(df_res["MWh elettrici netti"].sum())
                                 if IS_CHP and "MWh elettrici netti" in df_res
                                 else 0.0,
            # Business plan (DM 2022)
            "bp_result":         bp_result if IS_DM2022 else None,
            # Audit
            "yield_audit_rows":     list(_yield_audit_rows),
            "emission_audit_rows":  list(_emission_audit_rows),
            "emission_overrides":   dict(_EMISSION_OVERRIDES),
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
st.caption(
    "**Excel autocalcolante** ✏️: scarica il file `.xlsx`, modifica le "
    "celle gialle (Ore + Biomasse) direttamente in Excel/Numbers/LibreOffice "
    "e tutti i calcoli (produzione, saving GHG, validità) si aggiornano "
    "**istantaneamente** grazie alle formule live integrate. "
    "Niente upload, niente roundtrip — il file fa tutto da solo."
)

# ===== Riga unica: 3 download (XLSX primario, PDF, CSV legacy) =====
_dl_col1, _dl_col2, _dl_col3, _dl_col4 = st.columns([1.2, 1.0, 0.8, 0.8])

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
            "APP_MODE_LABEL":    {
                "biometano":        "Biometano DM 2022",
                "biometano_2018":   "Biometano DM 2018 (CIC)",
                "biogas_chp":       "Biogas CHP DM 6/7/2012",
                "biogas_chp_fer2":  "Biogas CHP FER 2 (≤300 kW)",
            }.get(APP_MODE, APP_MODE),
            "end_use":           end_use,
            # === CHP-specific (per validazione kW lordi) ===
            "IS_CHP":            IS_CHP,
            "plant_kwe":         plant_kwe,        # potenza LORDA targa motore
            "plant_kwe_net":     plant_kwe_net,    # info-only
            "eta_el":            eta_el,
            "eta_th":            eta_th,
            "aux_el_pct":        aux_el_pct,
        }
        # === Aggiunge contesto Business Plan (mode-aware) ===
        # Tariffa effettiva e parametri BP per la sheet "Business Plan".
        # Per ogni mode calcoliamo:
        #   - bp_tariffa_eff_mwh: €/MWh equivalenti (per BP unico mode-agnostic)
        #   - bp_ore_anno: ore funzionamento (default 8500)
        if IS_FER2:
            _bp_tariffa_mwh = float(fer2_tariffa_eff)
        elif IS_CHP_DM2012:
            # CHP DM 6/7/2012: TO 280 €/MWh_el (tipico)
            # se l'utente ha gia' impostato tariffa per biomassa la
            # prendiamo come weighted average.
            try:
                _tk = f"tariffs_eur_mwh_{APP_MODE}"
                _tar_dict = st.session_state.get(_tk, {})
                _vals = list(_tar_dict.values())
                _bp_tariffa_mwh = sum(_vals) / len(_vals) if _vals else 280.0
            except Exception:
                _bp_tariffa_mwh = 280.0
        elif IS_DM2018:
            if cic_active:
                # CIC system: tariffa €/MWh equivalente = ricavi / mwh_netti
                _mwh_for_calc = float(df_res["MWh netti"].sum()) or 1.0
                _bp_tariffa_mwh = float(tot_revenue) / _mwh_for_calc
            else:
                # DM 2018 altri usi: tariffa diretta media
                try:
                    _tk = f"tariffs_eur_mwh_{APP_MODE}"
                    _tar_dict = st.session_state.get(_tk, {})
                    _vals = list(_tar_dict.values())
                    _bp_tariffa_mwh = sum(_vals) / len(_vals) if _vals else 110.0
                except Exception:
                    _bp_tariffa_mwh = 110.0
        else:
            # Biometano DM 2022 (default app)
            _bp_tariffa_mwh = (
                float(bp_tariffa_eff) if IS_DM2022 and bp_result is not None
                else 131.0
            )

        # Ore anno default 8500 (puo' essere editato in Excel)
        _bp_ore_anno = 8500.0

        # CAPEX/OPEX defaults per BP: leggi dalle costanti
        _xlsx_ctx.update({
            "bp_tariffa_eff_mwh":        _bp_tariffa_mwh,
            "bp_ore_anno":               _bp_ore_anno,
            "bp_lt_tasso":               BP_FINANCE_DEFAULTS["lt_tasso"]
                                          if not IS_DM2022 else bp_lt_tasso,
            "bp_lt_durata":              (BP_FINANCE_DEFAULTS["lt_durata"]
                                           if not IS_DM2022 else bp_lt_durata),
            "bp_lt_leva":                (BP_FINANCE_DEFAULTS["lt_leva"]
                                           if not IS_DM2022 else bp_lt_leva),
            "bp_inflazione_pct":         (BP_INFLAZIONE_DEFAULT_PCT
                                           if not IS_DM2022 else bp_inflazione_pct),
            "bp_durata_tariffa":         BP_DURATA_TARIFFA_ANNI,
            "bp_pnrr_pct":               (BP_PNRR_QUOTA_PCT_DEFAULT
                                           if not IS_DM2022 else bp_pnrr_pct),
            "bp_ebitda_target_pct":      (24.5 if not IS_DM2022
                                           else bp_ebitda_target_pct),
            "bp_tax_rate_pct":           BP_TAX_RATE_PCT,
            "bp_ammort_anni":            BP_AMMORTAMENTO_ANNI,
            "bp_npv_disc_rate_pct":      6.0,
            "bp_massimale_eur_per_smch": BP_MASSIMALE_SPESA_EUR_PER_SMCH,
            # CAPEX/OPEX breakdown: passa quelli del BP se disponibili
            "bp_capex_breakdown":        (bp_capex_breakdown
                                           if IS_DM2022 else None),
            "bp_capex_forfait":          (bp_capex_forfait
                                           if IS_DM2022 else None),
            "bp_opex_breakdown":         (bp_opex_breakdown
                                           if IS_DM2022 else None),
            "bp_opex_forfait":           (bp_opex_forfait
                                           if IS_DM2022 else None),
            "NM3_TO_MWH":                NM3_TO_MWH,
            "lang":                      _LANG,
            # === BMT override audit (resa effettiva vs standard) ===
            "yield_audit_rows":          list(_yield_audit_rows),
            "effective_yields":          dict(_EFFECTIVE_YIELDS),
            # === Audit fattori emissivi reali (relazione tecnica) ===
            "emission_audit_rows":       list(_emission_audit_rows),
            "emission_overrides":        dict(_EMISSION_OVERRIDES),
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
        "IS_CHP": IS_CHP,
        "IS_CHP_DM2012": IS_CHP_DM2012,
        "IS_FER2": IS_FER2,
        "IS_DM2018": IS_DM2018,
        "IS_DM2022": IS_DM2022,
        "APP_MODE": APP_MODE,
        "plant_kwe": plant_kwe,
        "plant_kwe_net": plant_kwe_net,
        "plant_net_smch": plant_net_smch,
        "eta_el": eta_el,
        "eta_th": eta_th,
        "aux_el_pct": aux_el_pct,
        "aux_factor": aux_factor,
        "ep_total": ep_total,
        "end_use": end_use,
        "ghg_threshold": ghg_threshold,
        "fossil_comparator": FOSSIL_COMPARATOR,
        "upgrading_opt": upgrading_opt,
        "offgas_opt": offgas_opt,
        "injection_opt": injection_opt,
        # DM 2018 specifics
        "is_advanced": is_advanced,
        "cic_active": cic_active,
        "cic_double": cic_double,
        "cic_price": cic_price,
        "annex_mass_share": annex_mass_share,
        "annex_threshold": annex_threshold,
        "tot_n_cic": tot_n_cic,
        "MWH_PER_CIC": MWH_PER_CIC,
        "GCAL_PER_CIC": GCAL_PER_CIC,
        # FER 2 specifics
        "fer2_kwe_cap": FER2_KWE_CAP,
        "fer2_periodo_anni": FER2_PERIODO_ANNI,
        "fer2_subprod_share": fer2_subprod_share,
        "fer2_matrice_threshold": fer2_matrice_threshold,
        "fer2_qualified": fer2_qualified,
        "fer2_tariffa_base": fer2_tariffa_base,
        "fer2_premio_matrice_eur": fer2_premio_matrice_eur,
        "fer2_premio_car_eur": fer2_premio_car_eur,
        "fer2_apply_matrice": fer2_apply_matrice,
        "fer2_apply_car": fer2_apply_car,
        "fer2_tariffa_eff": fer2_tariffa_eff,
        # BP DM 2022 specifics (None se non DM 2022)
        "bp_result": bp_result if IS_DM2022 else None,
        "bp_tariffa_eur_mwh": bp_tariffa_eur_mwh if IS_DM2022 else None,
        "bp_ribasso_pct": bp_ribasso_pct if IS_DM2022 else None,
        "bp_tariffa_eff": bp_tariffa_eff if IS_DM2022 else None,
        "bp_pnrr_pct": bp_pnrr_pct if IS_DM2022 else None,
        "bp_capex_breakdown": bp_capex_breakdown if IS_DM2022 else None,
        "bp_capex_forfait": bp_capex_forfait if IS_DM2022 else None,
        "bp_lt_tasso": bp_lt_tasso if IS_DM2022 else None,
        "bp_lt_durata": bp_lt_durata if IS_DM2022 else None,
        "bp_lt_leva": bp_lt_leva if IS_DM2022 else None,
        "bp_ebitda_target_pct": bp_ebitda_target_pct if IS_DM2022 else None,
        "bp_inflazione_pct": bp_inflazione_pct if IS_DM2022 else None,
        "bp_ch4_in_biogas_pct": bp_ch4_in_biogas_pct if IS_DM2022 else None,
        "bp_durata_tariffa": BP_DURATA_TARIFFA_ANNI,
        # Aggregati comuni
        "tot_biomasse_t": float(df_res["Totale biomasse (t)"].sum()),
        "tot_sm3_netti": float(df_res["Sm³ netti"].sum()),
        "tot_mwh_netti": float(df_res["MWh netti"].sum()),
        "tot_mwh_el_lordo": float(df_res["MWh elettrici lordi"].sum())
                             if IS_CHP and "MWh elettrici lordi" in df_res
                             else 0.0,
        "tot_mwh_el_netto": float(df_res["MWh elettrici netti"].sum())
                             if IS_CHP and "MWh elettrici netti" in df_res
                             else 0.0,
        "saving_avg": float(df_res["Saving %"].mean()),
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
        with st.expander(
            "📚 Origine dei dati e metodo di calcolo "
            "(rese, fattori emissivi, GHG, base normativa)",
            expanded=False,
        ):
            st.markdown("**Origine delle rese biomassa**")
            st.text(_expl.get("yield_origin", ""))
            st.markdown("**Origine dei fattori emissivi**")
            st.text(_expl.get("emission_factor_origin", ""))
            st.markdown("**Metodo di calcolo GHG (RED III)**")
            st.text(_expl.get("ghg_method", ""))
            st.markdown("**Base normativa applicata**")
            st.text(_expl.get("regulatory_basis", ""))
    except Exception as _expl_exc:  # noqa: BLE001
        st.caption(f"(Sezione spiegazioni non disponibile: {_expl_exc})")

# ============================================================
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
    from output.daily_table_view import build_daily_dataframe as _build_daily_df
    from output.monthly_kpis import build_monthly_kpis as _build_kpis
    from output.guidance import compute_end_of_month_guidance as _build_guidance
    from export.daily_csv import build_daily_csv as _build_daily_csv
    from export.daily_excel import build_daily_excel as _build_daily_xlsx
    from export.daily_pdf import build_daily_pdf as _build_daily_pdf
    _DAILY_OPS_AVAILABLE = True
except Exception as _daily_imp_exc:  # noqa: BLE001
    _DAILY_OPS_AVAILABLE = False
    _DAILY_IMP_ERR = str(_daily_imp_exc)

if _DAILY_OPS_AVAILABLE:
    st.markdown("---")
    st.subheader("📅 Gestione Giornaliera — Verifica sostenibilità mensile")
    st.info(
        "ℹ️ **Il controllo ufficiale è MENSILE.** "
        "Gli indicatori giornalieri (saving) sono solo informativi: anche se "
        "alcuni giorni risultano isolatamente \"non sostenibili\", il mese "
        "può chiudere sostenibile aggregando il totale biomasse."
    )

    _today = _dt.date.today()
    _col_a, _col_b, _col_c = st.columns([1, 1, 2])
    with _col_a:
        _do_year = st.number_input(
            "Anno", min_value=2020, max_value=2100,
            value=int(_today.year), step=1, key="do_year",
        )
    with _col_b:
        _do_month = st.selectbox(
            "Mese", list(range(1, 13)),
            index=_today.month - 1,
            format_func=lambda m: _mlabel(int(_do_year), int(m), _LANG),
            key="do_month",
        )
    with _col_c:
        _do_plant = st.text_input(
            "ID impianto",
            value=st.session_state.get("do_plant_id", "default"),
            key="do_plant_id",
        )

    _do_key = f"do_data_{_do_plant}_{int(_do_year)}_{int(_do_month)}"
    if _do_key not in st.session_state:
        try:
            _init_db()
            _loaded = _load_month(int(_do_year), int(_do_month), plant_id=_do_plant)
        except Exception as _load_exc:  # noqa: BLE001
            st.warning(f"Impossibile caricare il mese salvato: {_load_exc}")
            _loaded = []
        _all_days = _gen_days(int(_do_year), int(_do_month))
        _data_map: dict = {d: {} for d in _all_days}
        for _e in _loaded:
            if _e.date in _data_map:
                _data_map[_e.date] = dict(_e.feedstocks)
        st.session_state[_do_key] = _data_map

    _bcol1, _bcol2, _bcol3 = st.columns([1, 1, 4])
    with _bcol1:
        if st.button("🔄 Ricarica da DB", key="do_btn_reload"):
            try:
                _init_db()
                _loaded = _load_month(int(_do_year), int(_do_month), plant_id=_do_plant)
                _all_days = _gen_days(int(_do_year), int(_do_month))
                _data_map = {d: {} for d in _all_days}
                for _e in _loaded:
                    if _e.date in _data_map:
                        _data_map[_e.date] = dict(_e.feedstocks)
                st.session_state[_do_key] = _data_map
                st.success("Mese ricaricato.")
            except Exception as _exc:  # noqa: BLE001
                st.warning(f"Errore ricarica: {_exc}")
    with _bcol2:
        if st.button("🆕 Nuovo mese (vuoto)", key="do_btn_new"):
            _all_days = _gen_days(int(_do_year), int(_do_month))
            st.session_state[_do_key] = {d: {} for d in _all_days}
            st.success("Mese azzerato.")

    _do_active_feeds = list(active_feeds) if active_feeds else list(FEED_NAMES)[:6]
    _data_map = st.session_state[_do_key]
    _all_days = sorted(_data_map.keys())

    _edit_rows = []
    for _d in _all_days:
        _row = {"Data": _d}
        for _fname in _do_active_feeds:
            _row[_fname] = float((_data_map.get(_d) or {}).get(_fname, 0.0))
        _edit_rows.append(_row)
    _edit_df = _pd_daily.DataFrame(_edit_rows)

    st.caption(
        f"Inserisci le biomasse t/giorno. Mese: **{_mlabel(int(_do_year), int(_do_month), _LANG)}** "
        f"({len(_all_days)} giorni). Tipologie modificabili: "
        f"{len(_do_active_feeds)} (basate sulle biomasse attive nella sidebar)."
    )

    _edited = st.data_editor(
        _edit_df,
        key=f"do_editor_{_do_key}",
        num_rows="fixed",
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", disabled=True, format="DD/MM/YYYY"),
            **{
                _f: st.column_config.NumberColumn(_f, min_value=0.0, step=0.1, format="%.2f")
                for _f in _do_active_feeds
            },
        },
        use_container_width=True,
    )

    try:
        for _, _r in _edited.iterrows():
            _d = _r["Data"]
            if hasattr(_d, "to_pydatetime"):
                _d = _d.to_pydatetime().date()
            elif isinstance(_d, _dt.datetime):
                _d = _d.date()
            _data_map[_d] = {
                _f: float(_r[_f] or 0.0) for _f in _do_active_feeds
                if (_r[_f] or 0.0) > 0
            }
        st.session_state[_do_key] = _data_map
    except Exception as _upd_exc:  # noqa: BLE001
        st.warning(f"Aggiornamento tabella fallito: {_upd_exc}")

    _ctx = {
        "aux_factor": float(aux_factor),
        "ep": float(ep_total),
        "fossil_comparator": float(FOSSIL_COMPARATOR),
        "plant_net_smch": float(plant_net_smch),
        "hours_per_day": 24.0,
    }
    _entries_list: list = []
    _computed_list: list = []
    for _d in _all_days:
        _entry = _DEntry(date=_d, feedstocks=dict(_data_map.get(_d) or {}))
        _entries_list.append(_entry)
        try:
            _computed_list.append(_compute_daily(_entry, ctx=_ctx))
        except Exception as _cexc:  # noqa: BLE001
            st.warning(f"Calcolo giornaliero fallito per {_d}: {_cexc}")

    _agg = _agg_month(_computed_list, ctx=_ctx,
                       year=int(_do_year), month=int(_do_month))

    _regime_lbl = "DM 2022 (RED III)" if IS_DM2022 else (
        "DM 2018" if IS_DM2018 else APP_MODE
    )
    _regime_constraints = {
        "max_sm3h_authorized": float(plant_net_smch) if plant_net_smch else None,
    }
    _sust = _eval_sust(_agg, regime=_regime_lbl,
                        threshold=float(ghg_threshold),
                        regime_constraints=_regime_constraints)
    _kpis = _build_kpis(_agg, _sust)

    st.markdown("### 📊 KPI Mensili (esito ufficiale)")
    _k1, _k2, _k3, _k4 = st.columns(4)
    _k1.metric("Saving GHG mese",
               f"{_kpis['saving_pct']:.2f}%",
               delta=f"{_kpis['margin']:+.2f} pt vs soglia")
    _k2.metric("Soglia normativa", f"{_kpis['threshold']:.2f}%")
    _k3.metric("Biomassa totale", f"{_kpis['biomass_total_t']:,.1f} t".replace(",", "."))
    _k4.metric("MWh netti mese", f"{_kpis['mwh']:,.1f}".replace(",", "."))

    if _kpis["compliant"]:
        st.success(
            f"✅ **MESE COMPLIANT** ({_regime_lbl}) — "
            f"saving {_kpis['saving_pct']:.2f}% ≥ soglia {_kpis['threshold']:.2f}%."
        )
    else:
        st.error(
            f"❌ **MESE NON COMPLIANT** ({_regime_lbl}) — "
            f"saving {_kpis['saving_pct']:.2f}% < soglia {_kpis['threshold']:.2f}%."
        )

    if _kpis.get("constraints_status"):
        with st.expander("📋 Stato vincoli regime", expanded=False):
            for _c in _kpis["constraints_status"]:
                _icon = "✅" if _c.get("ok") else "❌"
                st.write(f"{_icon} **{_c.get('name','?')}** — {_c.get('msg','')}")

    with st.expander("📋 Tabella giornaliera dettagliata (cumulati inclusi)",
                     expanded=False):
        _daily_df = _build_daily_df(_entries_list, _computed_list,
                                     feed_columns=_do_active_feeds)
        st.dataframe(_daily_df, use_container_width=True, hide_index=True)

    _guidance = _build_guidance(_agg, _sust, regime=_regime_lbl)
    with st.expander("🎯 Indicazioni operative fine mese", expanded=True):
        for _g in _guidance:
            st.write(f"- {_g}")

    _audit = {
        "Regime applicato": _regime_lbl,
        "Soglia normativa (%)": f"{_kpis['threshold']:.2f}",
        "Comparatore fossile (gCO2eq/MJ)": f"{FOSSIL_COMPARATOR:.2f}",
        "Aux factor (lordo/netto)": f"{aux_factor:.4f}",
        "EP totale (gCO2eq/MJ)": f"{ep_total:.3f}",
        "Plant net (Sm³/h)": f"{plant_net_smch:.2f}",
        "Origine rese": "BMT override se attivo, altrimenti standard FEEDSTOCK_DB",
        "Origine fattori emissivi": "Override relazione tecnica se attivo, altrimenti UNI-TS 11567:2024",
        "Formula sostenibilità (mensile)": "Sostenibile_mese = (saving_GHG_mese >= soglia) AND (vincoli regime OK)",
        "Giorni con dati": f"{_kpis['n_days_with_data']}",
        "Giorni cap autorizzativo violato": f"{len(_kpis.get('cap_violation_days', []))}",
    }
    with st.expander("🧾 Audit Trail mese", expanded=False):
        for _k, _v in _audit.items():
            st.write(f"- **{_k}**: {_v}")

    st.markdown("### 💾 Salva ed esporta")
    _scol1, _scol2, _scol3, _scol4 = st.columns(4)
    with _scol1:
        if st.button("💾 Salva mese", key="do_btn_save"):
            try:
                _init_db()
                _has_err = False
                for _e in _entries_list:
                    _ok, _errs, _ = _validate_daily(
                        _e.date, _e.feedstocks, allowed_feeds=list(FEED_NAMES))
                    if not _ok:
                        st.warning(f"{_e.date}: {'; '.join(_errs)}")
                        _has_err = True
                if not _has_err:
                    _n = _save_month(
                        int(_do_year), int(_do_month), _entries_list,
                        plant_id=_do_plant, regime=_regime_lbl,
                        threshold=float(ghg_threshold),
                    )
                    st.success(f"Mese salvato ({_n} record).")
            except Exception as _exc:  # noqa: BLE001
                st.error(f"Errore salvataggio: {_exc}")

    _daily_df_full = _build_daily_df(_entries_list, _computed_list,
                                      feed_columns=_do_active_feeds)

    with _scol2:
        try:
            _csv_bytes = _build_daily_csv(_daily_df_full)
            st.download_button(
                "⬇️ CSV giornaliero",
                _csv_bytes,
                file_name=f"giornaliero_{int(_do_year)}_{int(_do_month):02d}.csv",
                mime="text/csv", key="do_btn_csv",
            )
        except Exception as _exc:  # noqa: BLE001
            st.warning(f"CSV non disponibile: {_exc}")
    with _scol3:
        try:
            _xlsx_bytes = _build_daily_xlsx(_daily_df_full, _kpis, _audit)
            st.download_button(
                "⬇️ Excel giornaliero+mensile",
                _xlsx_bytes,
                file_name=f"giornaliero_{int(_do_year)}_{int(_do_month):02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="do_btn_xlsx",
            )
        except Exception as _exc:  # noqa: BLE001
            st.warning(f"Excel non disponibile: {_exc}")
    with _scol4:
        try:
            _pdf_bytes = _build_daily_pdf(_daily_df_full, _kpis, _audit, _guidance)
            st.download_button(
                "⬇️ PDF report",
                _pdf_bytes,
                file_name=f"giornaliero_{int(_do_year)}_{int(_do_month):02d}.pdf",
                mime="application/pdf", key="do_btn_pdf",
            )
        except Exception as _exc:  # noqa: BLE001
            st.warning(f"PDF non disponibile: {_exc}")
else:
    st.markdown("---")
    st.warning(
        "📅 Gestione Giornaliera non disponibile in questa build "
        f"({_DAILY_IMP_ERR if '_DAILY_IMP_ERR' in dir() else 'moduli mancanti'})."
    )

st.markdown("<div style='margin-top:40px;'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div style='
        position: relative;
        text-align: center;
        padding: 32px 28px;
        margin-top: 20px;
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border-radius: 12px;
        color: #ffffff;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
        border: 1px solid rgba(245, 158, 11, 0.18);
        overflow: hidden;
    '>
        <div style='
            position: absolute; top: 0; right: 0; bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, transparent 0%, #F59E0B 50%, transparent 100%);
            pointer-events: none;
        '></div>
        <div style='
            font-family: "JetBrains Mono", monospace;
            font-size: 0.68rem; font-weight: 500;
            color: #F59E0B; letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 8px;
            position: relative; z-index: 1;
        '>// Metan.iQ Platform</div>
        <div style='
            font-family: "Space Grotesk", "Inter", sans-serif;
            font-size: 1.7rem; font-weight: 700; letter-spacing: -0.8px;
            color: #FFFFFF;
            position: relative; z-index: 1;
            line-height: 1;
        '>Metan<span style="color:#F59E0B; font-weight:700;">.</span>iQ</div>
        <div style='
            font-size: 0.9rem; color: #94A3B8;
            margin-top: 8px; position: relative; z-index: 1;
            max-width: 640px; line-height: 1.5;
        '>Decision intelligence platform per la pianificazione mensile e
        l'ottimizzazione GHG di impianti di biometano e biogas cogenerativo.</div>
        <div style='
            margin-top: 18px; padding-top: 16px;
            border-top: 1px solid rgba(148, 163, 184, 0.12);
            font-size: 0.78rem; color: #CBD5E1;
            position: relative; z-index: 1;
            display: flex; justify-content: space-between; align-items: center;
            flex-wrap: wrap; gap: 12px;
        '>
            <div>
                Ideato e sviluppato da
                <b style='color:#FFFFFF; font-weight:600;'>Carlo Sicurini</b>
                &nbsp;·&nbsp; © 2026 &nbsp;·&nbsp; Tutti i diritti riservati
                &nbsp;·&nbsp;
                <span style='color:#94A3B8; font-style:italic;'>
                    Software fornito «così com'è», senza garanzie né assistenza
                </span>
            </div>
            <div style='display: flex; gap: 6px; flex-wrap: wrap;'>
                <span style='background: rgba(245, 158, 11, 0.10);
                    border: 1px solid rgba(245, 158, 11, 0.28);
                    color: #F59E0B; padding: 3px 10px; border-radius: 4px;
                    font-family: "JetBrains Mono", monospace;
                    font-size: 0.66rem; font-weight: 500; letter-spacing: 0.4px;
                '>RED III · Dir. 2023/2413</span>
                <span style='background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    color: #CBD5E1; padding: 3px 10px; border-radius: 4px;
                    font-family: "JetBrains Mono", monospace;
                    font-size: 0.66rem; font-weight: 500; letter-spacing: 0.4px;
                '>GSE LG 2024</span>
                <span style='background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    color: #CBD5E1; padding: 3px 10px; border-radius: 4px;
                    font-family: "JetBrains Mono", monospace;
                    font-size: 0.66rem; font-weight: 500; letter-spacing: 0.4px;
                '>UNI-TS 11567:2024</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
