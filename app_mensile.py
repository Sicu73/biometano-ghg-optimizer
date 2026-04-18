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
        note.append(f"{x} richiederebbe {mx:.1f} t (<0)")
        mx = 0.0
        my = rhs_prod / yy
        if my < 0:
            my = 0.0
            note.append(f"anche {y_name} <0: entrambe azzerate")
    elif my < 0:
        note.append(f"{y_name} richiederebbe {my:.1f} t (<0)")
        my = 0.0
        mx = rhs_prod / yx
        if mx < 0:
            mx = 0.0
            note.append(f"anche {x} <0: entrambe azzerate")
    msg = "Infeasibile: " + "; ".join(note) + ". Saving e/o produzione non saranno entrambi soddisfatti."
    return {x: mx, y_name: my}, False, msg


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
    aux_factor = st.slider(
        "Fattore netto→lordo (CHP + caldaia)",
        min_value=1.20, max_value=1.50,
        value=DEFAULT_AUX_FACTOR, step=0.01,
    )
    st.metric("Taglia netta", f"{plant_net_smch:.0f} Sm³/h")
    st.metric("Produzione lorda richiesta", f"{plant_net_smch*aux_factor:.1f} Sm³/h")

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
              f"{ghg_threshold*100:.0f}%",
              delta=f"target solver {target_saving*100:.0f}%")

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

    ep_digestate = EP_DIGESTATE[digestate_opt]
    ep_upgrading = EP_UPGRADING[upgrading_opt]
    ep_offgas = EP_OFFGAS[offgas_opt]
    ep_heat = EP_HEAT[heat_opt]
    ep_elec = EP_ELEC[elec_opt]
    ep_total = ep_digestate + ep_upgrading + ep_offgas + ep_heat + ep_elec

    # Breakdown ep
    with st.expander(f"📊 Breakdown ep = {ep_total:+.1f} gCO₂/MJ", expanded=True):
        st.markdown(
            f"- Digestato: **{ep_digestate:+.1f}**\n"
            f"- Upgrading: **{ep_upgrading:+.1f}**\n"
            f"- Off-gas: **{ep_offgas:+.1f}**\n"
            f"- Calore: **{ep_heat:+.1f}**\n"
            f"- Elettricità: **{ep_elec:+.1f}**\n"
            f"- **Totale ep: {ep_total:+.1f} gCO₂/MJ**"
        )

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
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "**Formula RED III**: E = eec + ep + etd − esca. "
        "Manure credit −45 gCO₂/MJ in `eec` per liquame suino. "
        "Per certificazione GSE: sostituire con valori reali d'impianto."
    )

# ------------------------- MODE SELECTOR -------------------------
st.subheader("🎯 Modalità di calcolo")

mode = st.radio(
    "Scegli modalità:",
    options=[
        "2 biomasse fisse + 2 calcolate  (saving 81% + produzione 300 Sm³/h)",
        "3 biomasse fisse + 1 calcolata  (solo produzione 300 Sm³/h)",
    ],
    index=0,
    horizontal=False,
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
        )
        if len(fixed_feeds) != 2:
            st.warning("Seleziona esattamente 2 biomasse.")
            st.stop()
        unknown_feeds = [n for n in FEED_NAMES if n not in fixed_feeds]
    else:
        unknown_feed = st.selectbox(
            "Biomassa incognita (calcolata automaticamente):",
            FEED_NAMES, index=3,
        )
        fixed_feeds = [n for n in FEED_NAMES if n != unknown_feed]
        unknown_feeds = [unknown_feed]

with col2:
    if is_dual_mode:
        st.info(
            f"**Modalità dual-constraint**: inserisci le quantità (t/mese) di "
            f"**{fixed_feeds[0]}** e **{fixed_feeds[1]}**. "
            f"Il solver calcola **{unknown_feeds[0]}** e **{unknown_feeds[1]}** "
            f"per ottenere saving **{target_saving*100:.0f}%** (margine su soglia RED III {ghg_threshold*100:.0f}%) "
            f"e produzione **300 Sm³/h netti**."
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
                f"**{row['Mese']}**: {unknown_feeds[0]} = {computed:.1f} t (<0). "
                f"Le 3 biomasse fisse gia' superano il fabbisogno lordo."
            )

    summary = ghg_summary(all_masses, aux_factor, ep_total)

    # Validita' - DUE CONDIZIONI OBBLIGATORIE:
    #   (1) saving GHG >= soglia RED III (80/70/65% a seconda uso finale),
    #       calcolato su biometano LORDO (anche la quota autoconsumata dagli
    #       ausiliari CHP+caldaia deve essere rinnovabile per >=80%).
    #   (2) produzione netta <= plant_net_smch (taglia autorizzata).
    net_smch = summary["nm3_net"] / hours if hours > 0 else 0.0
    saving_ok = summary["saving"] >= ghg_threshold * 100
    prod_ok = net_smch <= plant_net_smch + 0.5   # tolleranza +0.5 Sm3/h
    target_hit = abs(net_smch - plant_net_smch) < 0.5

    if saving_ok and prod_ok:
        validita = "✅ Valido"
    else:
        motivi = []
        if not saving_ok:
            motivi.append(
                f"saving {summary['saving']:.1f}% < {ghg_threshold*100:.0f}%"
            )
        if not prod_ok:
            motivi.append(
                f"netti {net_smch:.1f} > {plant_net_smch:.0f} Sm³/h (over-autorizz.)"
            )
        validita = "❌ Non valido: " + "; ".join(motivi)

    if saving_ok and prod_ok and not target_hit:
        stato = f"⚠️ netti {net_smch:.1f} < {plant_net_smch:.0f} (sub-ottimale)"
    elif not feasible:
        stato = "clampato"
    else:
        stato = f"saving {summary['saving']:.1f}% · netti {net_smch:.1f}"

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
# Colonne editabili: Ore + biomasse fisse (label con ✏️)
# Colonne disabled: biomasse calcolate (🧮) + tutti i risultati
col_cfg = {
    "Mese": st.column_config.TextColumn("Mese", disabled=True),
    "Ore": st.column_config.NumberColumn(
        "Ore ✏️", min_value=0, max_value=744, step=1, format="%d",
        help="Ore operative del mese (modificabile)",
    ),
}
for f in fixed_feeds:
    col_cfg[f] = st.column_config.NumberColumn(
        f"{f} ✏️ (t)",
        min_value=0.0, step=10.0, format="%.1f",
        help=f"INPUT – Resa {FEEDSTOCK_DB[f]['yield']} Nm³/t FM",
    )
for u in unknown_feeds:
    col_cfg[u] = st.column_config.NumberColumn(
        f"{u} 🧮 (t)",
        disabled=True, format="%.1f",
        help=f"CALCOLATA dal solver – Resa {FEEDSTOCK_DB[u]['yield']} Nm³/t FM",
    )
col_cfg["Totale biomasse (t)"] = st.column_config.NumberColumn("Tot. t", disabled=True, format="%.0f")
col_cfg["Sm³ lordi"] = st.column_config.NumberColumn("Sm³ lordi", disabled=True, format="%.0f")
col_cfg["Sm³ netti"] = st.column_config.NumberColumn("Sm³ netti", disabled=True, format="%.0f")
col_cfg["MWh netti"] = st.column_config.NumberColumn("MWh netti", disabled=True, format="%.1f")
col_cfg["GHG (gCO₂/MJ)"] = st.column_config.NumberColumn("e_w", disabled=True, format="%.2f", help="Emissioni pesate gCO₂eq/MJ")
col_cfg["Saving %"] = st.column_config.NumberColumn(
    "Saving %", disabled=True, format="%.1f",
    help=f"Obbligatorio ≥ {ghg_threshold*100:.0f}% (RED III – {end_use})",
)
col_cfg["Sm³/h netti"] = st.column_config.NumberColumn(
    "Sm³/h netti", disabled=True, format="%.1f",
    help=f"Obbligatorio ≤ {plant_net_smch:.0f} (tetto autorizzativo)",
)
col_cfg["Validità"] = st.column_config.TextColumn("Validità", disabled=True, width="medium")
col_cfg["Note"] = st.column_config.TextColumn("Note", disabled=True, width="medium")

edited = st.data_editor(
    df_res,
    column_config=col_cfg,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    height=470,
    key=f"editor_unified_{state_key}",
)

# --- Se l'utente ha modificato una cella editabile, aggiorna state e rerun
edit_cols = ["Mese", "Ore"] + fixed_feeds
new_input = edited[edit_cols].reset_index(drop=True).copy()
new_input["Ore"] = new_input["Ore"].astype(int)
for f in fixed_feeds:
    new_input[f] = new_input[f].astype(float)
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
c1.metric("Tot. biomasse (t/anno)", f"{df_res['Totale biomasse (t)'].sum():,.0f}")
c2.metric("Sm³ netti (anno)", f"{df_res['Sm³ netti'].sum():,.0f}")
c3.metric("MWh netti (anno)", f"{df_res['MWh netti'].sum():,.0f}")
c4.metric("Saving medio (%)", f"{df_res['Saving %'].mean():.1f}")
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
    fig.update_layout(barmode="stack", height=450)
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
        text=[f"{v:.1f}%" for v in df_res["Saving %"]],
        textposition="outside",
    ))
    fig2.add_hline(y=ghg_threshold*100, line_dash="dash", line_color="red",
                   annotation_text=f"Soglia RED III {ghg_threshold*100:.0f}%",
                   annotation_position="top right")
    fig2.add_hline(y=target_saving*100, line_dash="dot", line_color="green",
                   annotation_text=f"Target solver {target_saving*100:.0f}%",
                   annotation_position="bottom right")
    fig2.update_layout(title="Saving GHG mensile (%)",
                       yaxis_title="Saving (%)", height=450,
                       yaxis=dict(range=[60, 160]))
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    # Etichette numeriche leggibili coerenti con la tabella (formato IT: 287.928)
    lordi_vals = df_res["Sm³ lordi"].astype(float)
    netti_vals = df_res["Sm³ netti"].astype(float)
    lordi_labels = [f"{v:,.0f}".replace(",", ".") for v in lordi_vals]
    netti_labels = [f"{v:,.0f}".replace(",", ".") for v in netti_vals]

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
        title=f"Produzione mensile Sm³  (aux_factor = {aux_factor:.2f})",
        barmode="group", height=500,
        yaxis_title="Sm³ / mese",
        yaxis=dict(tickformat=",.0f", separatethousands=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.caption(
        f"📐 **Dimensionamento**: Sm³ lordi = 300 × {aux_factor:.2f} × ore_mese · "
        f"Sm³ netti = Sm³ lordi ÷ {aux_factor:.2f} = 300 × ore_mese. "
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
            title=f"Mix t/anno (totale {sum(annual_t.values()):,.0f} t)".replace(",", "."),
            hole=0.4,
        )
        fig4a.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig4a, use_container_width=True)

    with colB:
        fig4b = px.pie(
            names=list(annual_mwh.keys()),
            values=list(annual_mwh.values()),
            color=list(annual_mwh.keys()),
            color_discrete_map=color_map,
            title=f"Mix MWh netti/anno (totale {sum(annual_mwh.values()):,.0f} MWh)".replace(",", "."),
            hole=0.4,
        )
        fig4b.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig4b, use_container_width=True)

    # Tabella di dettaglio per calcolo ricavi per biomassa
    st.markdown("##### 💶 Dettaglio per tipologia di biomassa (per calcolo ricavi)")
    detail_rows = []
    for n in FEED_NAMES:
        t = annual_t[n]
        nm3_lordi = t * FEEDSTOCK_DB[n]["yield"]
        nm3_netti = nm3_lordi / aux_factor
        mwh_netti = nm3_netti * NM3_TO_MWH
        detail_rows.append({
            "Biomassa": n,
            "t/anno (FM)": t,
            "Resa (Nm³/t)": FEEDSTOCK_DB[n]["yield"],
            "Sm³ lordi/anno": nm3_lordi,
            "Sm³ netti/anno": nm3_netti,
            "MWh netti/anno": mwh_netti,
            "Quota % MWh": (mwh_netti / sum(annual_mwh.values()) * 100)
                           if sum(annual_mwh.values()) > 0 else 0,
        })
    df_detail = pd.DataFrame(detail_rows)
    st.dataframe(
        df_detail.style.format({
            "t/anno (FM)": "{:,.0f}",
            "Resa (Nm³/t)": "{:.0f}",
            "Sm³ lordi/anno": "{:,.0f}",
            "Sm³ netti/anno": "{:,.0f}",
            "MWh netti/anno": "{:,.1f}",
            "Quota % MWh": "{:.1f}%",
        }),
        hide_index=True, use_container_width=True,
    )
    st.caption(
        f"📐 **Calcolo**: MWh netti per biomassa = t × resa_Nm³/t ÷ {aux_factor:.2f} (aux) × 0.00997 (LHV biometano). "
        "Moltiplica la colonna «MWh netti/anno» per la tariffa incentivante €/MWh per avere i ricavi per tipologia."
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
