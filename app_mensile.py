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

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from report_pdf import build_metaniq_pdf


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
    Euristica: se non c'e' virgola e c'e' almeno un punto, e gli eventuali
    gruppi dopo il punto hanno esattamente 3 cifre, i punti sono separatori di
    migliaia. Altrimenti il punto e' decimale.
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
                           and parts[1].isdigit())
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
def e_total_feedstock(name: str, ep: float = 0.0) -> float:
    """
    Emissioni totali gCO2eq/MJ biometano per singolo feedstock.
    Formula RED III semplificata: E = eec + ep + etd - esca
      (el, eu, eccs, eccr = 0 per biometano da residui/colture dedicate IT)
    ep: contributo impiantistico (processing), da configuratore impianto
        [digestato + upgrading + off-gas + calore + elettricita' ausiliari].
    """
    d = FEEDSTOCK_DB[name]
    return d["eec"] + ep + d["etd"] - d["esca"]


def ghg_summary(masses: dict, aux: float, ep: float = 0.0):
    """
    Ritorna dict con: e_w, saving_pct, nm3_gross, nm3_net, mwh_net
    masses: {feedstock: mass_t}
    ep: contributo processing [gCO2eq/MJ] da applicare a tutto il biometano.
    """
    total_mj = 0.0
    total_e_mj = 0.0
    total_nm3 = 0.0
    for name, m in masses.items():
        if m is None or m <= 0:
            continue
        d = FEEDSTOCK_DB[name]
        nm3 = m * d["yield"]
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
        saving = (FOSSIL_COMPARATOR - e_w) / FOSSIL_COMPARATOR * 100
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
        (fixed_masses.get(n) or 0.0) * FEEDSTOCK_DB[n]["yield"]
        for n in fixed_masses.keys() if n != unknown
    )
    remaining = gross_target - covered
    return remaining / FEEDSTOCK_DB[unknown]["yield"]


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
        y = d["yield"]
        e = e_total_feedstock(n, ep)
        rhs_prod -= m * y
        rhs_sust -= m * y * (e - target_e_max)

    x, y_name = unknowns
    dx = FEEDSTOCK_DB[x]; dy = FEEDSTOCK_DB[y_name]
    yx = dx["yield"]; yy = dy["yield"]
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
            y_n = FEEDSTOCK_DB[n]["yield"]
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

    /* ---------- Headings ---------- */
    h1, h2, h3, h4, h5, h6 {{
        font-weight: 600 !important;
        letter-spacing: -0.4px !important;
        color: {HEADING_COLOR} !important;
    }}
    h1 {{ font-weight: 700 !important; letter-spacing: -0.8px !important; }}
    h2 {{ font-size: 1.7rem !important; margin-top: 1.6rem !important;
          font-weight: 600 !important; letter-spacing: -0.5px !important; }}
    h3 {{ font-size: 1.25rem !important; font-weight: 600 !important; }}
    h4 {{ font-size: 1.05rem !important; font-weight: 600 !important; }}

    /* ---------- Brand header (hero) ---------- */
    .methaniq-header {{
        position: relative;
        background:
            radial-gradient(ellipse 70% 90% at 100% 0%, rgba(245,158,11,0.18) 0%, transparent 55%),
            radial-gradient(ellipse 60% 80% at 0% 100%, rgba(16,185,129,0.10) 0%, transparent 55%),
            linear-gradient(135deg, {NAVY} 0%, {NAVY_2} 100%);
        padding: 56px 40px 48px 40px;
        border-radius: 18px;
        color: white;
        margin-bottom: 14px;
        box-shadow:
            0 20px 40px -16px rgba(15, 23, 42, 0.45),
            0 4px 8px rgba(15, 23, 42, 0.20),
            inset 0 1px 0 rgba(255,255,255,0.06);
        text-align: left;
        overflow: hidden;
        border: 1px solid rgba(245, 158, 11, 0.18);
    }}
    /* Hex pattern SVG background — molecole CH4 stilizzate */
    .methaniq-header::before {{
        content: "";
        position: absolute;
        inset: 0;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='92' viewBox='0 0 80 92'><g fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='1'><polygon points='40,4 72,22 72,58 40,76 8,58 8,22'/><polygon points='40,28 56,38 56,58 40,68 24,58 24,38'/></g></svg>");
        background-size: 120px 138px;
        opacity: 0.55;
        pointer-events: none;
    }}
    .methaniq-header::after {{
        content: "";
        position: absolute;
        top: 50%; right: -40px;
        transform: translateY(-50%);
        width: 2px; height: 70%;
        background: linear-gradient(180deg, transparent 0%, {AMBER} 50%, transparent 100%);
        opacity: 0.6;
        pointer-events: none;
    }}
    .methaniq-header .eyebrow {{
        position: relative;
        z-index: 1;
        display: inline-block;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.72rem;
        font-weight: 500;
        color: {AMBER};
        text-transform: uppercase;
        letter-spacing: 2.5px;
        margin-bottom: 14px;
        padding: 4px 12px;
        background: rgba(245, 158, 11, 0.10);
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-radius: 4px;
    }}
    .methaniq-header h1 {{
        color: #FFFFFF !important;
        margin: 0 !important;
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        font-size: 3.4rem !important;
        font-weight: 700 !important;
        letter-spacing: -1.8px !important;
        line-height: 1.0;
        position: relative;
        z-index: 1;
    }}
    .methaniq-header .tagline {{
        color: #CBD5E1;
        font-weight: 400;
        font-size: 1.15rem;
        margin-top: 14px;
        letter-spacing: -0.1px;
        position: relative;
        z-index: 1;
        max-width: 640px;
    }}
    .methaniq-header .pills {{
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-top: 28px;
        position: relative;
        z-index: 1;
    }}
    .methaniq-header .pill {{
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.12);
        color: #E2E8F0;
        padding: 5px 12px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 500;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 0.2px;
    }}
    .methaniq-header .pill.accent {{
        background: rgba(245, 158, 11, 0.12);
        border-color: rgba(245, 158, 11, 0.35);
        color: {AMBER};
    }}

    /* ---------- Credit box ---------- */
    .methaniq-credit {{
        background: {CREDIT_BG};
        border: 1px solid {BORDER};
        border-left: 3px solid {AMBER};
        padding: 10px 16px;
        border-radius: 6px;
        font-size: 0.82rem;
        color: {TEXT_SECOND};
        margin-bottom: 20px;
        box-shadow: {SHADOW_CARD};
    }}
    .methaniq-credit b {{ color: {HEADING_COLOR}; font-weight: 600; }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] * {{
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

    /* ---------- Metrics (KPI cards) ---------- */
    [data-testid="stMetric"] {{
        background: {BG_SURFACE};
        padding: 18px 20px;
        border-radius: 10px;
        border: 1px solid {BORDER};
        border-top: 3px solid {AMBER};
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
        letter-spacing: 1.2px;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {HEADING_COLOR} !important;
        font-weight: 700 !important;
        font-size: 1.85rem !important;
        letter-spacing: -0.8px;
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        font-variant-numeric: tabular-nums;
    }}
    [data-testid="stMetricDelta"] {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
    }}

    /* ---------- Buttons ---------- */
    .stButton > button {{
        background: {NAVY};
        color: #FFFFFF !important;
        border: 1px solid {NAVY};
        border-radius: 8px;
        padding: 0.55rem 1.3rem;
        font-weight: 600;
        font-size: 0.92rem;
        letter-spacing: 0.1px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.10);
        transition: all 0.18s ease;
    }}
    .stButton > button:hover {{
        background: {NAVY_2};
        border-color: {AMBER};
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.20),
                    0 0 0 3px rgba(245, 158, 11, 0.08);
        transform: translateY(-1px);
    }}
    .stButton > button:active {{ transform: translateY(0); }}
    /* Primary button (mode/theme selectors when active) */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY_2} 100%);
        border: 1px solid {AMBER};
        color: #FFFFFF !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.20),
                    inset 0 1px 0 rgba(245, 158, 11, 0.15);
    }}
    /* Secondary button (theme toggle inactive, neutral actions) */
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
    .stDownloadButton > button {{
        background: {AMBER};
        color: #FFFFFF !important;
        border: 1px solid {AMBER};
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.2px;
        box-shadow: 0 1px 2px rgba(245, 158, 11, 0.20);
    }}
    .stDownloadButton > button:hover {{
        background: {AMBER_DK};
        border-color: {AMBER_DK};
        box-shadow: 0 6px 16px rgba(245, 158, 11, 0.30);
        transform: translateY(-1px);
    }}

    /* ---------- Expanders ---------- */
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
    }}

    /* ---------- Tabs ---------- */
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
        padding: 8px 16px;
        font-weight: 500;
        font-size: 0.92rem;
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

    /* ---------- Alerts ---------- */
    [data-testid="stAlert"] {{
        border-radius: 10px;
        border: none;
        box-shadow: {SHADOW_CARD};
    }}

    /* ---------- Inputs ---------- */
    .stNumberInput input, .stTextInput input,
    .stSelectbox [data-baseweb="select"] > div {{
        background: {INPUT_BG} !important;
        color: {TEXT_PRIMARY} !important;
        border-radius: 8px !important;
        border: 1px solid {BORDER} !important;
        transition: all 0.15s ease;
    }}
    .stNumberInput input:focus, .stTextInput input:focus {{
        border-color: {AMBER} !important;
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18) !important;
    }}
    .stSlider [data-baseweb="slider"] > div > div {{
        background: {NAVY} !important;
    }}
    .stSlider [data-baseweb="slider"] [role="slider"] {{
        background: {AMBER} !important;
        border: 2px solid {NAVY} !important;
        box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.15) !important;
    }}

    /* ---------- Dataframes ---------- */
    [data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        box-shadow: {SHADOW_CARD};
        border: 1px solid {BORDER};
    }}
    [data-testid="stDataFrame"] * {{
        color: {TEXT_PRIMARY} !important;
    }}

    /* ---------- Dividers ---------- */
    hr {{ border-color: {BORDER} !important; margin: 1.5rem 0 !important; }}

    /* ---------- Captions ---------- */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {TEXT_MUTED} !important;
        font-size: 0.85rem !important;
    }}

    /* ---------- Subtle section headings ---------- */
    .section-label {{
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: {SECTION_PILL_COLOR};
        background: {SECTION_PILL_BG};
        padding: 3px 10px;
        border-radius: 6px;
        margin-bottom: 6px;
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
    st.header("🌾 Biomasse del tuo impianto")
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
                    f"  · resa={fmt_it(FEEDSTOCK_DB[f]['yield'], 0)} Nm³/t",
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

    st.divider()
    st.header("⚙️ Parametri impianto")

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
    st.header("🏭 Configurazione impianto (ep)")
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
        st.header("🌿 DM 2018 — Sistema CIC")

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
        st.header("🔋 FER 2 — Tariffa e premi")

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

        st.subheader("💰 Tariffa FER 2 [€/MWh_el]")
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
    st.header("⚡ Fattore netto→lordo (aux_factor)")
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
    rows = []
    for n in active_feeds:
        d = FEEDSTOCK_DB[n]
        e_tot = e_total_feedstock(n, ep_total)
        rows.append({
            "Feedstock": n,
            "Categoria": d.get("cat", ""),
            "Resa (Nm³/t)": d["yield"],
            "eec": d["eec"],
            "ep": ep_total,
            "etd": d["etd"],
            "esca": d["esca"],
            "e_total": round(e_tot, 2),
            "saving %": round(
                (FOSSIL_COMPARATOR - e_tot) / FOSSIL_COMPARATOR * 100, 1
            ),
        })
    df_feed = pd.DataFrame(rows)
    styled_feed = df_feed.style.format({
        "Resa (Nm³/t)": lambda v: fmt_it(v, 0),
        "eec":          lambda v: fmt_it(v, 1, signed=True),
        "ep":           lambda v: fmt_it(v, 1, signed=True),
        "etd":          lambda v: fmt_it(v, 1, signed=True),
        "esca":         lambda v: fmt_it(v, 1, signed=True),
        "e_total":      lambda v: fmt_it(v, 2, signed=True),
        "saving %":     lambda v: fmt_it(v, 1, "%"),
    })
    st.dataframe(styled_feed, hide_index=True, use_container_width=True)
    st.caption(
        "**Formula RED III**: E = eec + ep + etd − esca. "
        "Manure credit da −45 a −10 gCO₂/MJ in `eec` per effluenti zootecnici "
        "(proporzionale a stoccaggio anaerobico evitato, IPCC 2019 Vol.4 Cap.10). "
        "Fonti: UNI-TS 11567:2024, JEC WTT v5, All. IX RED III, GSE LG 2024. "
        "Per certificazione finale: sostituire con valori reali d'impianto."
    )

# ------------------------- MODE SELECTOR -------------------------
st.subheader("🎯 Modalità di calcolo")

N_active = len(active_feeds)
MODE_DUAL = f"{N_active-2} biomasse fisse + 2 calcolate  (saving target + produzione)"
MODE_SINGLE = f"{N_active-1} biomasse fisse + 1 calcolata  (solo produzione)"

# --- Applica eventuali risultati ottimizzazione PRIMA di creare i widget ---
# (Streamlit non consente di modificare session_state di una chiave-widget
# dopo che qualunque widget e' stato renderizzato nello stesso run.)
_pending_opt = st.session_state.pop("_pending_optimization", None)
if _pending_opt is not None:
    if _pending_opt.get("is_mono"):
        # Caso mono: 1 sola biomassa attiva -> (N-1)+1 con la mono come
        # incognita calcolata e le altre (N-1) fisse a 0 (per ogni mese).
        mono = _pending_opt["mono"]
        others = [n for n in active_feeds if n != mono]
        st.session_state["mode_radio"] = MODE_SINGLE
        st.session_state["single_unknown_select"] = mono
        new_state_key = f"mens_in_single_{'-'.join(others)}"
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
        new_state_key = f"mens_in_dual_{'-'.join(_pending_opt['unused'])}"
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
st.subheader("📆 Tabella mensile – modifica le celle ✏️, il resto si ricalcola")

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

    summary = ghg_summary(all_masses, aux_factor, ep_total)

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
             f"Resa {fmt_it(FEEDSTOCK_DB[f]['yield'], 0)} Nm³/t FM",
    )
for u in unknown_feeds:
    col_cfg[u] = st.column_config.TextColumn(
        f"{u} 🧮 (t)",
        disabled=True,
        help=f"CALCOLATA dal solver – Resa {fmt_it(FEEDSTOCK_DB[u]['yield'], 0)} Nm³/t FM",
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
st.subheader("📈 Sintesi annuale")
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
tab1, tab2, tab3, tab4 = st.tabs([
    "🌾 Biomasse per mese",
    "🌍 Sostenibilità",
    "⚡ Produzione",
    "🥧 Mix annuale",
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
        n: max(df_res[n].sum(), 0) * FEEDSTOCK_DB[n]["yield"]
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
        nm3_lordi = t * FEEDSTOCK_DB[n]["yield"]
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
            "yield": FEEDSTOCK_DB[n]["yield"],
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
            "Resa (Nm³/t)":    fmt_it(FEEDSTOCK_DB[n]["yield"], 0),
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

# ------------------------- DOWNLOAD -------------------------
st.divider()
st.markdown(
    f"<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; "
    f"font-weight:600; letter-spacing:1.5px; text-transform:uppercase; "
    f"color:{TEXT_MUTED}; margin-bottom:10px;'>// EXPORT</div>",
    unsafe_allow_html=True,
)

_dl_col1, _dl_col2, _dl_col3 = st.columns([1, 1, 2])

with _dl_col1:
    csv = df_res.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "⬇️ Scarica CSV",
        data=csv,
        file_name=f"metaniq_{APP_MODE}_plan.csv",
        mime="text/csv",
        use_container_width=True,
        help="Risultati mensili completi in formato CSV (separatore «;», "
             "virgola decimale italiana, encoding UTF-8 con BOM per Excel).",
    )

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
            "📄 Scarica Report PDF",
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

st.caption(
    "ℹ️ Database feedstock: letteratura tecnica / UNI/TS 11567:2024 / parametri "
    "Consorzio Monviso. Manure credit -45 gCO₂/MJ incorporato in `eec` "
    "(pollina ovaiole, liquame suino). Per certificazione GSE sostituire con "
    "valori reali d'impianto."
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
