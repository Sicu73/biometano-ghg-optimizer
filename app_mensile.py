# -*- coding: utf-8 -*-
"""
BioMethane Monthly Planner - Dual-Constraint Solver
---------------------------------------------------
Impianto 300 Sm3/h NETTI (DM 15/09/2022, PNRR).
Biomasse: Trinciato di mais, Trinciato di sorgo, Pollina ovaiole, Liquame suino.

L'utente fissa 3 biomasse/mese, la 4a viene calcolata automaticamente per
soddisfare il vincolo di produzione (300 Sm3/h netti * ore_mese * aux_factor).
Il sistema verifica anche il vincolo di sostenibilita' RED III (saving >= 80%).

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
GHG_SAVING_THRESHOLD = 0.80                    # 80% soglia biometano
MAX_ALLOWED_EMISSIONS = FOSSIL_COMPARATOR * (1 - GHG_SAVING_THRESHOLD)  # 18.8
LHV_BIOMETHANE = 35.9                          # MJ/Nm3 (97% CH4)
NM3_TO_MWH = 0.00997                           # 1 Nm3 -> MWh
DEFAULT_AUX_FACTOR = 1.29                      # netto -> lordo (CHP+caldaia)
PLANT_NET_SMCH = 300.0                         # Sm3/h netti autorizzati

# ============================================================
# DATABASE FEEDSTOCK
# Valori tipici da letteratura tecnica, UNI/TS 11567:2024 e
# parametri utilizzati nel Consorzio Monviso (ordine di grandezza).
# Per certificazione GSE sostituire con valori reali o NUTS2 ufficiali.
# ============================================================
FEEDSTOCK_DB = {
    "Trinciato di mais": {
        "eec": 26.0,   # coltivazione (gCO2eq/MJ biometano)
        "esca": 0.0,   # accumulo C suolo
        "etd": 0.8,    # trasporto
        "yield": 104.0,# resa Nm3/t FM
        "color": "#F5C518",
    },
    "Trinciato di sorgo": {
        "eec": 22.0,   # leggermente inferiore al mais (minor fertilizzazione N)
        "esca": 0.0,
        "etd": 0.8,
        "yield": 90.0, # Nm3/t FM (letteratura: 85-95)
        "color": "#8BC34A",
    },
    "Pollina ovaiole": {
        "eec": 4.0,    # residuo zootecnico, emissioni coltivazione nulle
        "esca": -45.0, # credito metano evitato (RED III manure bonus)
        "etd": 0.8,
        "yield": 90.0, # Nm3/t FM - pollina ovaiole (valore realistico medio)
        "color": "#FF9800",
    },
    "Liquame suino": {
        "eec": -45.0,  # manure credit incorporato nel database esistente
        "esca": 0.0,
        "etd": 0.8,
        "yield": 15.0, # Nm3/t FM
        "color": "#8D6E63",
    },
}

FEED_NAMES = list(FEEDSTOCK_DB.keys())

MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
# Ore/mese (funzionamento h24, 365 gg)
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]


# ============================================================
# FUNZIONI DI CALCOLO
# ============================================================
def e_total_feedstock(name: str) -> float:
    """Emissioni totali gCO2eq/MJ per singolo feedstock (semplificate)."""
    d = FEEDSTOCK_DB[name]
    return d["eec"] + d["etd"] - d["esca"]


def weighted_ghg(masses: dict) -> tuple:
    """
    GHG medio pesato sull'energia prodotta.
    masses: {feedstock_name: mass_t}
    Ritorna (e_total_gCO2_MJ, saving_pct, nm3_gross)
    """
    total_mj = 0.0
    total_e = 0.0
    total_nm3 = 0.0
    for name, m in masses.items():
        if m is None or m <= 0:
            continue
        d = FEEDSTOCK_DB[name]
        nm3 = m * d["yield"]
        mj = nm3 * LHV_BIOMETHANE
        e = e_total_feedstock(name)
        total_mj += mj
        total_e += e * mj
        total_nm3 += nm3
    if total_mj <= 0:
        return 0.0, 0.0, 0.0
    e_w = total_e / total_mj
    saving = (FOSSIL_COMPARATOR - e_w) / FOSSIL_COMPARATOR
    return e_w, saving * 100, total_nm3


def solve_unknown_mass(fixed: dict, unknown: str, hours: float, aux: float) -> float:
    """
    Risolve la massa mancante (t) per soddisfare la produzione lorda:
       sum(mass_i * yield_i) = 300 * aux * hours
    fixed: {name: mass_t} per le 3 biomasse bloccate
    unknown: nome della biomassa incognita
    """
    gross_target_nm3 = PLANT_NET_SMCH * aux * hours
    covered = sum((fixed.get(n) or 0.0) * FEEDSTOCK_DB[n]["yield"]
                  for n in FEED_NAMES if n != unknown)
    remaining = gross_target_nm3 - covered
    y = FEEDSTOCK_DB[unknown]["yield"]
    return remaining / y


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
    "**Pianificazione mensile delle biomasse** per impianto **300 Sm³/h netti** "
    "con vincoli RED III (saving ≥ 80%). L'utente inserisce 3 biomasse, "
    "la 4ª viene calcolata automaticamente."
)

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Parametri impianto")
    aux_factor = st.slider(
        "Fattore netto→lordo (CHP + caldaia)",
        min_value=1.20, max_value=1.50,
        value=DEFAULT_AUX_FACTOR, step=0.01,
        help="Rapporto fra biometano lordo prodotto e netto immesso in rete. "
             "Tipico: 1.25-1.35 (autoconsumi cogenerazione e caldaia biogas).",
    )
    plant_gross = PLANT_NET_SMCH * aux_factor
    st.metric("Taglia netta", f"{PLANT_NET_SMCH:.0f} Sm³/h")
    st.metric("Produzione lorda richiesta", f"{plant_gross:.1f} Sm³/h")

    st.divider()
    st.header("📋 Database feedstock")
    rows = []
    for n, d in FEEDSTOCK_DB.items():
        rows.append({
            "Feedstock": n,
            "Resa (Nm³/t)": d["yield"],
            "eec": d["eec"],
            "esca": d["esca"],
            "etd": d["etd"],
            "e_total": round(e_total_feedstock(n), 2),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Valori da letteratura / UNI/TS 11567 / Consorzio Monviso")

# ------------------------- MODE SELECT -------------------------
st.subheader("🎯 Seleziona la biomassa da calcolare")
col_a, col_b = st.columns([2, 3])
with col_a:
    unknown_feed = st.selectbox(
        "Biomassa incognita (calcolata automaticamente):",
        FEED_NAMES,
        index=3,
        help="Le altre 3 biomasse sono inserite da te; questa viene calcolata "
             "per chiudere il bilancio produttivo di 300 Sm³/h netti.",
    )
with col_b:
    st.info(
        f"**Modalità corrente**: inserisci le quantità (t/mese) delle altre "
        f"tre biomasse in tabella. Il sistema calcolerà automaticamente "
        f"**{unknown_feed}** per raggiungere i {plant_gross:.1f} Sm³/h lordi. "
        f"Verifica poi che la **sostenibilità sia ≥ 80%**."
    )

# ------------------------- TABELLA MENSILE -------------------------
st.subheader("📆 Tabella mensile – biomasse fisse (t/mese FM)")

editable_feeds = [n for n in FEED_NAMES if n != unknown_feed]

# Default suggerito (quantità fissa uguale per tutti i mesi - modificabile)
default_rows = []
for m, h in zip(MONTHS, MONTH_HOURS):
    row = {"Mese": m, "Ore": h}
    # Default plausibili: mais 1500, sorgo 500, pollina 200, suino 2000
    defaults_all = {
        "Trinciato di mais": 1500.0,
        "Trinciato di sorgo": 500.0,
        "Pollina ovaiole": 200.0,
        "Liquame suino": 2000.0,
    }
    for f in editable_feeds:
        row[f] = defaults_all[f]
    default_rows.append(row)

df_input = pd.DataFrame(default_rows)

# Config colonne
col_cfg = {
    "Mese": st.column_config.TextColumn("Mese", disabled=True),
    "Ore": st.column_config.NumberColumn(
        "Ore/mese", min_value=0, max_value=744, step=1, format="%d"
    ),
}
for f in editable_feeds:
    col_cfg[f] = st.column_config.NumberColumn(
        f"{f} (t)",
        min_value=0.0, step=10.0, format="%.1f",
        help=f"Resa {FEEDSTOCK_DB[f]['yield']} Nm³/t FM",
    )

edited_df = st.data_editor(
    df_input,
    column_config=col_cfg,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key="monthly_editor",
)

# ------------------------- CALCOLI -------------------------
results = []
for _, row in edited_df.iterrows():
    fixed = {n: float(row[n]) for n in editable_feeds}
    computed = solve_unknown_mass(fixed, unknown_feed, float(row["Ore"]), aux_factor)

    masses = dict(fixed)
    masses[unknown_feed] = computed

    e_w, saving, nm3_gross = weighted_ghg(masses)
    nm3_net = nm3_gross / aux_factor if aux_factor > 0 else 0.0
    mwh_net = nm3_net * NM3_TO_MWH

    feasible = computed >= 0
    sustainable = saving >= 80.0
    if not feasible:
        status = "❌ Impossibile (produzione eccedente)"
    elif not sustainable:
        status = "⚠️ Produzione OK, saving < 80%"
    else:
        status = "✅ Conforme"

    res = {
        "Mese": row["Mese"],
        "Ore": int(row["Ore"]),
    }
    for n in FEED_NAMES:
        res[n] = masses[n]
    res["Totale biomasse (t)"] = sum(masses.values())
    res["Sm³ lordi"] = nm3_gross
    res["Sm³ netti"] = nm3_net
    res["MWh netti"] = mwh_net
    res["GHG (gCO₂/MJ)"] = e_w
    res["Saving %"] = saving
    res["Stato"] = status
    results.append(res)

df_res = pd.DataFrame(results)

# ------------------------- RISULTATI -------------------------
st.subheader(f"📊 Risultati – {unknown_feed} calcolata automaticamente")

# Evidenzia la colonna calcolata
def highlight_cols(row):
    styles = [""] * len(row)
    cols = list(row.index)
    # sfondo colonna incognita
    if unknown_feed in cols:
        i = cols.index(unknown_feed)
        styles[i] = "background-color: #E3F2FD; font-weight: 600;"
    # stato
    if "Stato" in cols:
        i = cols.index("Stato")
        s = row["Stato"]
        if s.startswith("✅"):
            styles[i] = "background-color: #C8E6C9;"
        elif s.startswith("⚠️"):
            styles[i] = "background-color: #FFF9C4;"
        else:
            styles[i] = "background-color: #FFCDD2;"
    return styles

fmt = {
    "Trinciato di mais": "{:.1f}",
    "Trinciato di sorgo": "{:.1f}",
    "Pollina ovaiole": "{:.1f}",
    "Liquame suino": "{:.1f}",
    "Totale biomasse (t)": "{:,.0f}",
    "Sm³ lordi": "{:,.0f}",
    "Sm³ netti": "{:,.0f}",
    "MWh netti": "{:,.1f}",
    "GHG (gCO₂/MJ)": "{:.2f}",
    "Saving %": "{:.1f}",
}

st.dataframe(
    df_res.style.format(fmt).apply(highlight_cols, axis=1),
    hide_index=True,
    use_container_width=True,
    height=470,
)

# ------------------------- SINTESI ANNUALE -------------------------
st.subheader("📈 Sintesi annuale")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tot. biomasse (t/anno)", f"{df_res['Totale biomasse (t)'].sum():,.0f}")
c2.metric("Sm³ netti (anno)", f"{df_res['Sm³ netti'].sum():,.0f}")
c3.metric("MWh netti (anno)", f"{df_res['MWh netti'].sum():,.0f}")
c4.metric("Saving medio (%)", f"{df_res['Saving %'].mean():.1f}")
compliant = (df_res["Saving %"] >= 80).sum()
c5.metric("Mesi conformi", f"{compliant}/12",
          delta="OK" if compliant == 12 else f"{12-compliant} non conformi",
          delta_color="normal" if compliant == 12 else "inverse")

# Warning se la biomassa calcolata e' negativa
neg_months = df_res[df_res[unknown_feed] < 0]
if not neg_months.empty:
    st.error(
        f"⚠️ In {len(neg_months)} mese/i la biomassa calcolata **{unknown_feed}** "
        f"risulta **negativa**: le quantita' fisse gia' superano il fabbisogno lordo. "
        f"Riduci una delle biomasse bloccate."
    )

low_saving = df_res[(df_res["Saving %"] < 80) & (df_res[unknown_feed] >= 0)]
if not low_saving.empty:
    st.warning(
        f"⚠️ In {len(low_saving)} mese/i la sostenibilita' e' **< 80%** pur "
        f"raggiungendo i 300 Sm³/h netti. Aumenta la quota di feedstock con "
        f"credito manure (Liquame suino, Pollina ovaiole) per alzare il saving."
    )

# ------------------------- GRAFICI -------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🌾 Biomasse per mese",
    "🌍 Sostenibilita'",
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
        title="Ripartizione mensile biomasse (t/mese)",
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
            cmin=60, cmax=100,
            colorbar=dict(title="Saving %"),
        ),
        text=[f"{v:.1f}%" for v in df_res["Saving %"]],
        textposition="outside",
    ))
    fig2.add_hline(y=80, line_dash="dash", line_color="red",
                   annotation_text="Soglia 80% RED III",
                   annotation_position="top right")
    fig2.update_layout(
        title="Saving GHG mensile (%)",
        yaxis_title="Saving (%)", height=450,
        yaxis=dict(range=[60, 105]),
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=df_res["Mese"], y=df_res["Sm³ lordi"],
        name="Sm³ lordi", marker_color="#90A4AE",
    ))
    fig3.add_trace(go.Bar(
        x=df_res["Mese"], y=df_res["Sm³ netti"],
        name="Sm³ netti", marker_color="#1E88E5",
    ))
    fig3.update_layout(
        title="Produzione mensile Sm³ (lordi vs netti)",
        barmode="group", height=450,
        yaxis_title="Sm³ / mese",
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    annual = {n: df_res[n].sum() for n in FEED_NAMES}
    fig4 = px.pie(
        names=list(annual.keys()),
        values=[max(v, 0) for v in annual.values()],
        color=list(annual.keys()),
        color_discrete_map={n: FEEDSTOCK_DB[n]["color"] for n in FEED_NAMES},
        title="Mix annuale biomasse (t/anno)",
        hole=0.4,
    )
    st.plotly_chart(fig4, use_container_width=True)

# ------------------------- DOWNLOAD CSV -------------------------
st.divider()
csv = df_res.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
st.download_button(
    "⬇️ Scarica risultati (CSV)",
    data=csv,
    file_name="biomethane_monthly_plan.csv",
    mime="text/csv",
)

st.caption(
    "ℹ️ Valori feedstock di default da letteratura tecnica, UNI/TS 11567:2024 e "
    "parametri tipici Consorzio Monviso. Per la certificazione GSE sostituire "
    "con i valori reali d'impianto o con i default NUTS2 ufficiali. "
    "La pollina ovaiole include il credito `esca` per metano evitato (manure bonus)."
)
