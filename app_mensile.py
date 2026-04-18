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


# ============================================================
# FORMATO ITALIANO: punto = migliaia, virgola = decimali
# ============================================================
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
FOSSIL_COMPARATOR = 94.0                       # gCO2eq/MJ (comparator fossile)
# Le soglie RED III variano per uso finale: 80% elettricita'/calore, 65% trasporti
LHV_BIOMETHANE = 35.9                          # MJ/Nm3 (97% CH4)
NM3_TO_MWH = 0.00997                           # 1 Nm3 -> MWh
DEFAULT_AUX_FACTOR = 1.29                      # netto -> lordo (CHP+caldaia)
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
# EP (processing) - contributi impiantistici [gCO2eq/MJ biometano]
# Valori medi da letteratura JRC-CONCAWE v5, UNI/TS 11567:2024, default RED III.
# NB: valori indicativi; per certificazione GSE servono misure reali d'impianto.
# ============================================================
EP_DIGESTATE = {
    "Stoccaggio APERTO (no copertura)":                 +15.0,
    "Coperto anaerobico ~20 giorni":                     +3.0,
    "Coperto ≥30 giorni con recupero gas residuo":       -5.0,
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
    "Trinciato di mais": {
        "eec": 26.0,   # coltivazione (gCO2eq/MJ biometano)
        "esca": 0.0,
        "etd": 0.8,
        "yield": 104.0,
        "color": "#F5C518",
    },
    "Trinciato di sorgo": {
        "eec": 22.0,   # minor fertilizzazione N rispetto al mais
        "esca": 0.0,
        "etd": 0.8,
        "yield": 90.0,
        "color": "#8BC34A",
    },
    "Pollina ovaiole": {
        # Allineata a v1: la pollina ovaiole in stabulazione moderna
        # (stoccaggio aerobico/nastro) NON riceve il manure credit RED III
        # completo, riservato a letami/liquami stoccati anaerobicamente.
        "eec": 5.0,    # coltivazione/handling (residuo zootecnico secco)
        "esca": 0.0,   # nessun credito anaerobico
        "etd": 0.8,
        "yield": 90.0, # Nm3/t FM
        "color": "#FF9800",
    },
    "Liquame suino": {
        "eec": -45.0,  # manure credit
        "esca": 0.0,
        "etd": 0.8,
        "yield": 15.0,
        "color": "#8D6E63",
    },
}

FEED_NAMES = list(FEEDSTOCK_DB.keys())

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
    Modalita' 3+1: risolve 1 incognita soddisfando SOLO la produzione lorda.
    plant_net: taglia netta autorizzata (Sm3/h); default 300.
    """
    gross_target = plant_net * aux * hours
    covered = sum((fixed_masses.get(n) or 0.0) * FEEDSTOCK_DB[n]["yield"]
                  for n in FEED_NAMES if n != unknown)
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
                      target_e_max: float):
    """
    Trova il mix di biomasse (1 o 2 attive, le altre a 0) che MINIMIZZA la
    massa totale rispettando:
      - produzione lorda = plant_net * aux * ore (vincolo di uguaglianza)
      - e_w <= target_e_max  (saving GHG >= target solver, leggermente sopra
        la soglia RED III)

    Ritorna (pair, total_per_hour, masses_per_hour) o None se infeasibile.
    `pair` e' sempre una tuple di 2 nomi (se mono, il 2o nome e' incluso ma
    con massa 0) per retrocompatibilita' con il codice chiamante.

    Teoria LP: con 2 vincoli (produzione = equality, saving = inequality) e
    4 variabili non-negative, l'ottimo e' su un vertice con <=2 variabili
    positive.  Due famiglie di vertici:
      (a) MONO: 1 sola biomassa attiva; richiede che il suo e_total sia gia'
          <= target_e_max (saving >= target).  Massa = gross_target / yield.
      (b) COPPIA: 2 biomasse attive, vincolo saving attivo (=target).
          Sistema 2x2 risolto da solve_2_unknowns_dual.

    NB: la coppia ottimale NON dipende dalle ore: la soluzione scala
    linearmente, quindi il mix migliore per 1 h e' lo stesso per ogni mese.
    """
    from itertools import combinations

    gross_target = plant_net * aux * 1.0  # per 1 ora
    best = None  # (pair_tuple, total_per_hour, masses_per_hour)

    # --- (a) MONO: enumera 4 singole biomasse -------------------------------
    # Con vincolo saving in forma di DISUGUAGLIANZA, se una singola biomassa
    # ha gia' e_total <= target_e_max (over-performance rispetto alla soglia)
    # allora soddisfa entrambi i vincoli da sola, e la sua massa e'
    # gross_target / yield.  Candidato naturale per minima massa totale.
    for n in FEED_NAMES:
        e_n = e_total_feedstock(n, ep)
        if e_n <= target_e_max + 1e-9:  # saving >= target
            y_n = FEEDSTOCK_DB[n]["yield"]
            if y_n <= 0:
                continue
            m_n = gross_target / y_n
            masses_h = {k: 0.0 for k in FEED_NAMES}
            masses_h[n] = m_n
            total_h = m_n
            # Per retrocompat col banner (2 nomi sempre), "completo" con la
            # biomassa a massa zero che ha e_total minima (piu' amica).
            other = min(
                (x for x in FEED_NAMES if x != n),
                key=lambda x: e_total_feedstock(x, ep),
            )
            pair_tuple = (n, other)
            if best is None or total_h < best[1] - 1e-9:
                best = (pair_tuple, total_h, masses_h)

    # --- (b) COPPIE: enumera C(4,2)=6 vertici con saving=target -------------
    for pair in combinations(FEED_NAMES, 2):
        fixed0 = {n: 0.0 for n in FEED_NAMES if n not in pair}
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
    page_title="BioMethane Monthly Planner",
    page_icon="📅",
    layout="wide",
)

st.title("📅 BioMethane Monthly Planner")
st.markdown(
    "Pianificazione mensile biomasse - solver dual-constraint "
    "**saving GHG + produzione target** con configurazione impianto (ep) ex RED III."
)

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Parametri impianto")
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

    st.divider()
    st.header("🏭 Configurazione impianto (ep)")
    st.caption(
        "I parametri impiantistici concorrono a `ep` (processing), "
        "che incide direttamente sul saving GHG ex RED III."
    )

    # Destinazione d'uso -> soglia GHG saving
    end_use = st.selectbox(
        "🎯 Destinazione biometano (→ soglia saving)",
        list(END_USE_THRESHOLDS.keys()),
        index=0,
        help="RED III + D.Lgs. 5/2026: 80% per elettricita'/calore (impianto "
             "nuovo >=20/11/2023), 70% per esistenti <10 MW primi 15 anni, "
             "65% per trasporti.",
    )
    ghg_threshold = END_USE_THRESHOLDS[end_use]
    target_saving = ghg_threshold + 0.01  # +1 pp margine sicurezza
    target_e_max = FOSSIL_COMPARATOR * (1 - target_saving)
    max_allowed_e = FOSSIL_COMPARATOR * (1 - ghg_threshold)
    st.metric("Soglia saving obbligatoria",
              fmt_it(ghg_threshold * 100, 0, "%"),
              delta=f"target solver {fmt_it(target_saving * 100, 0, '%')}")

    # Configuratore ep
    digestate_opt = st.selectbox("Stoccaggio digestato",
                                  list(EP_DIGESTATE.keys()), index=1)
    upgrading_opt = st.selectbox("Tecnologia upgrading",
                                  list(EP_UPGRADING.keys()), index=1)
    offgas_opt = st.selectbox("Combustione off-gas",
                               list(EP_OFFGAS.keys()), index=0)
    heat_opt = st.selectbox("Fonte calore processo",
                             list(EP_HEAT.keys()), index=0)
    elec_opt = st.selectbox("Elettricità ausiliari",
                             list(EP_ELEC.keys()), index=1)
    injection_opt = st.selectbox(
        "Iniezione biometano in rete",
        list(INJECTION_PRESSURE.keys()), index=1,
        help="Pressione di consegna del biometano. Determina il consumo "
             "elettrico del booster compressore a valle dell'upgrading "
             "(0,05-0,25 kWh_e/Sm³).",
    )

    ep_digestate = EP_DIGESTATE[digestate_opt]
    ep_upgrading = EP_UPGRADING[upgrading_opt]
    ep_offgas = EP_OFFGAS[offgas_opt]
    ep_heat = EP_HEAT[heat_opt]
    ep_elec = EP_ELEC[elec_opt]
    ep_total = ep_digestate + ep_upgrading + ep_offgas + ep_heat + ep_elec

    # Breakdown ep
    with st.expander(
        f"📊 Breakdown ep = {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ",
        expanded=True,
    ):
        st.markdown(
            f"- Digestato: **{fmt_it(ep_digestate, 1, signed=True)}**\n"
            f"- Upgrading: **{fmt_it(ep_upgrading, 1, signed=True)}**\n"
            f"- Off-gas: **{fmt_it(ep_offgas, 1, signed=True)}**\n"
            f"- Calore: **{fmt_it(ep_heat, 1, signed=True)}**\n"
            f"- Elettricità: **{fmt_it(ep_elec, 1, signed=True)}**\n"
            f"- **Totale ep: {fmt_it(ep_total, 1, signed=True)} gCO₂/MJ**"
        )

    st.divider()
    # ========================================================
    # AUX_FACTOR AUTOMATICO (bilancio energetico d'impianto)
    # ========================================================
    st.header("⚡ Fattore netto→lordo (aux_factor)")
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

    cogen_frac = 0.6  # default: 60% elettricita' da CHP biogas, 40% FV
    recover_chp_heat = True
    if elec_opt == ELEC_IS_INTERNAL:
        cogen_frac = st.slider(
            "Quota cogen biogas nell'autoproduzione elettrica [%]",
            min_value=0.0, max_value=100.0, value=60.0, step=10.0,
            help="Se autoproduci elettricita' da CHP biogas + FV, indica "
                 "la quota coperta dal CHP (resto dalla FV). Il CHP biogas "
                 "consuma biometano interno, la FV no.",
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
            min_value=1.05, max_value=1.60,
            value=round(aux_auto, 2), step=0.01,
        )
    else:
        aux_factor = aux_auto
        st.metric(
            "aux_factor calcolato",
            fmt_it(aux_factor, 3),
            delta=f"{fmt_it(aux_auto_data['f_tot']*100, 1, '%')} autoconsumo totale",
        )

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

    st.metric("Produzione lorda richiesta",
              fmt_it(plant_net_smch * aux_factor, 1, " Sm³/h"))

    st.divider()
    st.header("📋 Database feedstock (con ep applicato)")
    rows = []
    for n, d in FEEDSTOCK_DB.items():
        e_tot = e_total_feedstock(n, ep_total)
        rows.append({
            "Feedstock": n,
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
        "Manure credit −45 gCO₂/MJ in `eec` per liquame suino. "
        "Per certificazione GSE: sostituire con valori reali d'impianto."
    )

# ------------------------- MODE SELECTOR -------------------------
st.subheader("🎯 Modalità di calcolo")

MODE_DUAL = "2 biomasse fisse + 2 calcolate  (saving 81% + produzione 300 Sm³/h)"
MODE_SINGLE = "3 biomasse fisse + 1 calcolata  (solo produzione 300 Sm³/h)"

# --- Applica eventuali risultati ottimizzazione PRIMA di creare i widget ---
# (Streamlit non consente di modificare session_state di una chiave-widget
# dopo che qualunque widget e' stato renderizzato nello stesso run.)
_pending_opt = st.session_state.pop("_pending_optimization", None)
if _pending_opt is not None:
    if _pending_opt.get("is_mono"):
        # Caso mono: 1 sola biomassa attiva -> modalita' 3+1 con la mono come
        # incognita calcolata e le altre 3 fisse a 0 (per ogni mese).
        mono = _pending_opt["mono"]
        others = [n for n in FEED_NAMES if n != mono]
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
        # Caso coppia: 2 biomasse attive -> modalita' 2+2 con le 2 inutilizzate
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
st.markdown(
    f"##### ⚡ Auto-calcolo ottimale – minimizza la somma totale delle biomasse "
    f"rispettando saving ≥ {fmt_it(ghg_threshold*100, 0, '%')} e produzione = "
    f"{fmt_it(plant_net_smch, 0)} Sm³/h netti"
)
optimize_clicked = st.button(
    "🚀 OTTIMIZZA  (minimizza massa totale biomasse)",
    help="Enumera le 6 coppie di biomasse e sceglie quella con massa totale "
         "minima che soddisfa entrambi i vincoli (produzione + saving GHG). "
         "Le altre 2 biomasse vengono azzerate. Si imposta in modalità dual "
         "con le 2 non-utilizzate come 'fisse a zero'.",
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
    )
    if best is None:
        st.error(
            "❌ Nessuna coppia di biomasse riesce a soddisfare simultaneamente "
            f"saving ≥ {fmt_it(ghg_threshold*100, 0, '%')} e produzione "
            f"{fmt_it(plant_net_smch, 0)} Sm³/h con la configurazione ep "
            f"attuale ({fmt_it(ep_total, 1, signed=True)} gCO₂/MJ). "
            "Prova a migliorare la configurazione impianto (stoccaggio "
            "digestato coperto, upgrading a membrane/amminico, off-gas RTO)."
        )
    else:
        pair, total_h, masses_h = best
        # Se solo una biomassa ha massa > 0 -> ottimo MONO
        active = [n for n, v in masses_h.items() if v > 1e-9]
        is_mono = len(active) == 1
        unused = [n for n in FEED_NAMES if n not in pair]
        annual_hours = sum(MONTH_HOURS)
        st.session_state["_pending_optimization"] = {
            "pair": list(pair),
            "unused": unused,
            "total_year": total_h * annual_hours,
            "is_mono": is_mono,
            "mono": active[0] if is_mono else None,
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

is_dual_mode = mode.startswith("2")

col1, col2 = st.columns([2, 3])
with col1:
    if is_dual_mode:
        fixed_feeds = st.multiselect(
            "Seleziona le 2 biomasse che inserirai (le altre 2 saranno calcolate):",
            options=FEED_NAMES,
            default=["Trinciato di mais", "Liquame suino"],
            max_selections=2,
            help="Suggerimento: scegli 1 biomassa ad alta eec (mais/sorgo) + "
                 "1 a credito (pollina/liquame). Se scegli entrambe dello "
                 "stesso 'tipo' il sistema puo' diventare infeasibile.",
            key="fixed_multiselect",
        )
        if len(fixed_feeds) != 2:
            st.warning("Seleziona esattamente 2 biomasse.")
            st.stop()
        unknown_feeds = [n for n in FEED_NAMES if n not in fixed_feeds]
    else:
        unknown_feed = st.selectbox(
            "Biomassa incognita (calcolata automaticamente):",
            FEED_NAMES, index=3,
            key="single_unknown_select",
        )
        fixed_feeds = [n for n in FEED_NAMES if n != unknown_feed]
        unknown_feeds = [unknown_feed]

# Banner risultato ottimizzazione (mostrato 1 sola volta dopo click)
_opt_info = st.session_state.pop("_optimize_info", None)
if _opt_info:
    if _opt_info.get("is_mono"):
        mono = _opt_info["mono"]
        others = [n for n in FEED_NAMES if n != mono]
        st.success(
            f"🚀 **Ottimo LP – MONO biomassa**: unica attiva **{mono}** "
            f"(le altre 3 = 0). "
            f"Massa totale annua minima ≈ "
            f"**{fmt_it(_opt_info['total_year'], 0)} t/anno**. "
            f"Il saving e' oltre la soglia con la sola **{mono}**; "
            f"modalita' 3+1 impostata automaticamente "
            f"({mono} calcolata, le altre a 0)."
        )
    else:
        st.success(
            f"🚀 **Ottimo LP**: biomasse attive **{_opt_info['pair'][0]}** + "
            f"**{_opt_info['pair'][1]}** "
            f"(**{_opt_info['unused'][0]}** e **{_opt_info['unused'][1]}** = 0). "
            f"Massa totale annua minima ≈ "
            f"**{fmt_it(_opt_info['total_year'], 0)} t/anno** "
            f"(saving target **{fmt_it(target_saving*100, 0, '%')}**, "
            f"produzione **{fmt_it(plant_net_smch, 0)} Sm³/h netti**)."
        )

with col2:
    if is_dual_mode:
        st.info(
            f"**Modalità dual-constraint**: inserisci le quantità (t/mese) di "
            f"**{fixed_feeds[0]}** e **{fixed_feeds[1]}**. "
            f"Il solver calcola **{unknown_feeds[0]}** e **{unknown_feeds[1]}** "
            f"per ottenere saving **{fmt_it(target_saving*100, 0, '%')}** "
            f"(margine su soglia RED III {fmt_it(ghg_threshold*100, 0, '%')}) "
            f"e produzione **{fmt_it(plant_net_smch, 0)} Sm³/h netti**."
        )
    else:
        st.info(
            f"**Modalità produzione-only**: inserisci 3 biomasse; "
            f"il sistema calcola **{unknown_feeds[0]}** per chiudere la produzione. "
            f"Il saving sarà una conseguenza (verificato in tabella)."
        )

# ------------------------- TABELLA UNIFICATA (input + risultati) -------------------------
st.subheader("📆 Tabella mensile – modifica le celle ✏️, il resto si ricalcola")

# Valori di default plausibili
defaults_all = {
    "Trinciato di mais": 1800.0,
    "Trinciato di sorgo": 400.0,
    "Pollina ovaiole": 300.0,
    "Liquame suino": 1500.0,
}

# --- Stato persistente: memorizzo SOLO le colonne editabili (Mese, Ore, fisse).
# Chiave state univoca per combinazione mode+fisse, cosi' cambio mode -> nuovo state.
state_key = f"mens_in_{'dual' if is_dual_mode else 'single'}_{'-'.join(fixed_feeds)}"
if state_key not in st.session_state:
    init_rows = []
    for m, h in zip(MONTHS, MONTH_HOURS):
        row = {"Mese": m, "Ore": h}
        for f in fixed_feeds:
            row[f] = defaults_all[f]
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
    for n in FEED_NAMES:
        res[n] = all_masses[n]
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
             f"Resa {fmt_it(FEEDSTOCK_DB[f]['yield'], 0)} Nm³/t FM",
    )
for u in unknown_feeds:
    col_cfg[u] = st.column_config.TextColumn(
        f"{u} 🧮 (t)",
        disabled=True,
        help=f"CALCOLATA dal solver – Resa {fmt_it(FEEDSTOCK_DB[u]['yield'], 0)} Nm³/t FM",
    )
col_cfg["Totale biomasse (t)"] = st.column_config.TextColumn("Tot. t", disabled=True)
col_cfg["Sm³ lordi"]   = st.column_config.TextColumn("Sm³ lordi", disabled=True)
col_cfg["Sm³ netti"]   = st.column_config.TextColumn("Sm³ netti", disabled=True)
col_cfg["MWh netti"]   = st.column_config.TextColumn("MWh netti", disabled=True)
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
        id_vars="Mese", value_vars=FEED_NAMES,
        var_name="Biomassa", value_name="t/mese",
    )
    fig = px.bar(
        df_melt, x="Mese", y="t/mese", color="Biomassa",
        color_discrete_map={n: FEEDSTOCK_DB[n]["color"] for n in FEED_NAMES},
        title="Ripartizione mensile biomasse",
    )
    fig.update_layout(barmode="stack", height=450, separators=",.")
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
                       yaxis=dict(range=[60, 160]),
                       separators=",.")
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    # Etichette numeriche leggibili coerenti con la tabella (formato IT: 287.928)
    lordi_vals = df_res["Sm³ lordi"].astype(float)
    netti_vals = df_res["Sm³ netti"].astype(float)
    lordi_labels = [fmt_it(v, 0) for v in lordi_vals]
    netti_labels = [fmt_it(v, 0) for v in netti_vals]

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=df_res["Mese"], y=lordi_vals,
        name="Sm³ lordi (biomasse)", marker_color="#90A4AE",
        text=lordi_labels, textposition="outside",
        hovertemplate="<b>%{x}</b><br>Sm³ lordi: %{text}<extra></extra>",
    ))
    fig3.add_trace(go.Bar(
        x=df_res["Mese"], y=netti_vals,
        name="Sm³ netti (immessi in rete)", marker_color="#1E88E5",
        text=netti_labels, textposition="outside",
        hovertemplate="<b>%{x}</b><br>Sm³ netti: %{text}<extra></extra>",
    ))
    fig3.update_layout(
        title=f"Produzione mensile Sm³  (aux_factor = {fmt_it(aux_factor, 2)})",
        barmode="group", height=500,
        yaxis_title="Sm³ / mese",
        yaxis=dict(tickformat=",.0f", separatethousands=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        separators=",.",
    )
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
    annual_t = {n: max(df_res[n].sum(), 0) for n in FEED_NAMES}
    # Mix in MWh netti: ogni biomassa contribuisce in proporzione a (massa x yield)
    # MWh_netti_n = massa_n x yield_n / aux_factor x NM3_TO_MWH
    annual_mwh = {
        n: max(df_res[n].sum(), 0) * FEEDSTOCK_DB[n]["yield"]
           / aux_factor * NM3_TO_MWH
        for n in FEED_NAMES
    }
    color_map = {n: FEEDSTOCK_DB[n]["color"] for n in FEED_NAMES}

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
        fig4a.update_layout(separators=",.")
        st.plotly_chart(fig4a, use_container_width=True)

    with colB:
        fig4b = px.pie(
            names=list(annual_mwh.keys()),
            values=list(annual_mwh.values()),
            color=list(annual_mwh.keys()),
            color_discrete_map=color_map,
            title=f"Mix MWh netti/anno (totale {fmt_it(sum(annual_mwh.values()), 0)} MWh)",
            hole=0.4,
        )
        fig4b.update_traces(textposition="inside", textinfo="percent+label")
        fig4b.update_layout(separators=",.")
        st.plotly_chart(fig4b, use_container_width=True)

    # Tabella di dettaglio per calcolo ricavi per biomassa (tariffa editabile)
    st.markdown("##### 💶 Dettaglio per tipologia di biomassa (tariffa €/MWh editabile ✏️)")

    # Stato persistente: tariffe per biomassa
    if "tariffs_eur_mwh" not in st.session_state:
        st.session_state["tariffs_eur_mwh"] = {n: 120.0 for n in FEED_NAMES}
    # Retrocompat: se mancano chiavi per nuove biomasse
    for n in FEED_NAMES:
        if n not in st.session_state["tariffs_eur_mwh"]:
            st.session_state["tariffs_eur_mwh"][n] = 120.0

    detail_rows = []
    for n in FEED_NAMES:
        t = annual_t[n]
        nm3_lordi = t * FEEDSTOCK_DB[n]["yield"]
        nm3_netti = nm3_lordi / aux_factor
        mwh_netti = nm3_netti * NM3_TO_MWH
        tariffa = st.session_state["tariffs_eur_mwh"][n]
        ricavi = mwh_netti * tariffa
        quota = ((mwh_netti / sum(annual_mwh.values()) * 100)
                 if sum(annual_mwh.values()) > 0 else 0)
        detail_rows.append({
            "Biomassa": n,
            # Read-only pre-formattate in italiano
            "t/anno (FM)":     fmt_it(t, 0),
            "Resa (Nm³/t)":    fmt_it(FEEDSTOCK_DB[n]["yield"], 0),
            "Sm³ netti/anno":  fmt_it(nm3_netti, 0),
            "MWh netti/anno":  fmt_it(mwh_netti, 1),
            "Quota % MWh":     fmt_it(quota, 1, "%"),
            # Editabile: TextColumn con formato italiano (parse_it in scrittura)
            "Tariffa €/MWh":   fmt_it(tariffa, 2),
            "Ricavi €/anno":   fmt_it(ricavi, 0, " €"),
        })
    df_detail = pd.DataFrame(detail_rows)

    detail_col_cfg = {
        "Biomassa":       st.column_config.TextColumn("Biomassa", disabled=True),
        "t/anno (FM)":    st.column_config.TextColumn("t/anno (FM)", disabled=True),
        "Resa (Nm³/t)":   st.column_config.TextColumn("Resa Nm³/t", disabled=True),
        "Sm³ netti/anno": st.column_config.TextColumn("Sm³ netti/anno", disabled=True),
        "MWh netti/anno": st.column_config.TextColumn("MWh netti/anno", disabled=True),
        "Quota % MWh":    st.column_config.TextColumn("Quota % MWh", disabled=True),
        "Tariffa €/MWh": st.column_config.TextColumn(
            "Tariffa €/MWh ✏️",
            help="Tariffa incentivante/PPA per biomassa [€/MWh] in formato "
                 "italiano (es. 1.234,56). Modificabile per simulazioni di ricavi.",
        ),
        "Ricavi €/anno": st.column_config.TextColumn(
            "Ricavi €/anno 🧮", disabled=True,
            help="MWh netti × tariffa €/MWh (si ricalcola al variare della tariffa)",
        ),
    }

    edited_detail = st.data_editor(
        df_detail,
        column_config=detail_col_cfg,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="editor_revenue_detail",
    )

    # Se l'utente ha modificato una tariffa -> salva e rerun (parse_it per IT)
    # Clamp: tariffe negative non hanno senso fisico -> >=0.
    new_tariffs = {
        row["Biomassa"]: max(parse_it(row["Tariffa €/MWh"]), 0.0)
        for _, row in edited_detail.iterrows()
    }
    if new_tariffs != st.session_state["tariffs_eur_mwh"]:
        st.session_state["tariffs_eur_mwh"] = new_tariffs
        st.rerun()

    # Totali ricavi
    tot_mwh = sum(annual_mwh.values())
    tot_revenue = sum(
        annual_mwh[n] * st.session_state["tariffs_eur_mwh"][n]
        for n in FEED_NAMES
    )
    tariffa_media_ponderata = (tot_revenue / tot_mwh) if tot_mwh > 0 else 0.0
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
csv = df_res.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
st.download_button(
    "⬇️ Scarica risultati (CSV)",
    data=csv,
    file_name="biomethane_monthly_plan.csv",
    mime="text/csv",
)

st.caption(
    "ℹ️ Database feedstock: letteratura tecnica / UNI/TS 11567:2024 / parametri "
    "Consorzio Monviso. Manure credit -45 gCO₂/MJ incorporato in `eec` "
    "(pollina ovaiole, liquame suino). Per certificazione GSE sostituire con "
    "valori reali d'impianto."
)
