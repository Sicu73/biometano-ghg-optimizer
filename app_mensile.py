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
GHG_SAVING_THRESHOLD = 0.80                    # 80% soglia RED III biometano
TARGET_SAVING = 0.81                           # 81% target solver (margine sicurezza)
TARGET_E_MAX = FOSSIL_COMPARATOR * (1 - TARGET_SAVING)  # 17.86 gCO2eq/MJ
MAX_ALLOWED_EMISSIONS = FOSSIL_COMPARATOR * (1 - GHG_SAVING_THRESHOLD)  # 18.8
LHV_BIOMETHANE = 35.9                          # MJ/Nm3 (97% CH4)
NM3_TO_MWH = 0.00997                           # 1 Nm3 -> MWh
DEFAULT_AUX_FACTOR = 1.29                      # netto -> lordo (CHP+caldaia)
PLANT_NET_SMCH = 300.0                         # Sm3/h netti autorizzati

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
def e_total_feedstock(name: str) -> float:
    """Emissioni totali gCO2eq/MJ per singolo feedstock (semplificate)."""
    d = FEEDSTOCK_DB[name]
    return d["eec"] + d["etd"] - d["esca"]


def ghg_summary(masses: dict, aux: float):
    """
    Ritorna dict con: e_w, saving_pct, nm3_gross, nm3_net, mwh_net
    masses: {feedstock: mass_t}
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
        e = e_total_feedstock(name)
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
                                hours: float, aux: float) -> float:
    """
    Modalita' 3+1: risolve 1 incognita soddisfando SOLO la produzione lorda.
    """
    gross_target = PLANT_NET_SMCH * aux * hours
    covered = sum((fixed_masses.get(n) or 0.0) * FEEDSTOCK_DB[n]["yield"]
                  for n in FEED_NAMES if n != unknown)
    remaining = gross_target - covered
    return remaining / FEEDSTOCK_DB[unknown]["yield"]


def solve_2_unknowns_dual(fixed_masses: dict, unknowns: list,
                           hours: float, aux: float):
    """
    Modalita' 2+2: risolve sistema lineare 2x2.
      Eq.1 (produzione):
          sum(mass_i * yield_i) = 300 * aux * hours
      Eq.2 (saving = TARGET_SAVING, cioe' e_w = TARGET_E_MAX):
          sum((e_i - TARGET_E_MAX) * yield_i * mass_i) = 0
    Ritorna (masses_dict, feasible_bool, message_str)
      - feasible_bool = True se entrambi >= 0
      - se una soluzione e' negativa, la forza a 0 e ricalcola l'altra
        soddisfacendo la sola produzione.
    """
    gross_target = PLANT_NET_SMCH * aux * hours
    # RHS, togliendo contributi delle 2 fisse
    rhs_prod = gross_target
    rhs_sust = 0.0
    for n, m in fixed_masses.items():
        if m is None:
            m = 0.0
        d = FEEDSTOCK_DB[n]
        y = d["yield"]
        e = e_total_feedstock(n)
        rhs_prod -= m * y
        rhs_sust -= m * y * (e - TARGET_E_MAX)

    x, y_name = unknowns
    dx = FEEDSTOCK_DB[x]; dy = FEEDSTOCK_DB[y_name]
    yx = dx["yield"]; yy = dy["yield"]
    ex = e_total_feedstock(x) - TARGET_E_MAX
    ey = e_total_feedstock(y_name) - TARGET_E_MAX

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
    "Pianificazione mensile biomasse - impianto **300 Sm³/h netti** - "
    "solver dual-constraint **saving 81% + produzione 300 Sm³/h**"
)

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Parametri impianto")
    aux_factor = st.slider(
        "Fattore netto→lordo (CHP + caldaia)",
        min_value=1.20, max_value=1.50,
        value=DEFAULT_AUX_FACTOR, step=0.01,
    )
    st.metric("Taglia netta", f"{PLANT_NET_SMCH:.0f} Sm³/h")
    st.metric("Produzione lorda richiesta", f"{PLANT_NET_SMCH*aux_factor:.1f} Sm³/h")

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
            "saving %": round(
                (FOSSIL_COMPARATOR - e_total_feedstock(n)) / FOSSIL_COMPARATOR * 100, 1
            ),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "**Convenzione manure credit**: -45 gCO₂/MJ incorporato in `eec` "
        "per letami/deiezioni animali (prassi GSE)."
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
            f"per ottenere saving **{TARGET_SAVING*100:.0f}%** (margine su soglia RED III 80%) "
            f"e produzione **300 Sm³/h netti**."
        )
    else:
        st.info(
            f"**Modalità produzione-only**: inserisci 3 biomasse; "
            f"il sistema calcola **{unknown_feeds[0]}** per chiudere la produzione. "
            f"Il saving sarà una conseguenza (verificato in tabella)."
        )

# ------------------------- TABELLA INPUT -------------------------
st.subheader("📆 Tabella mensile – inserimento biomasse (t/mese FM)")

# Valori di default plausibili
defaults_all = {
    "Trinciato di mais": 1800.0,
    "Trinciato di sorgo": 400.0,
    "Pollina ovaiole": 300.0,
    "Liquame suino": 1500.0,
}

default_rows = []
for m, h in zip(MONTHS, MONTH_HOURS):
    row = {"Mese": m, "Ore": h}
    for f in fixed_feeds:
        row[f] = defaults_all[f]
    default_rows.append(row)
df_input = pd.DataFrame(default_rows)

col_cfg = {
    "Mese": st.column_config.TextColumn("Mese", disabled=True),
    "Ore": st.column_config.NumberColumn("Ore/mese", min_value=0, max_value=744, step=1, format="%d"),
}
for f in fixed_feeds:
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
    key=f"editor_{'dual' if is_dual_mode else 'single'}_{'-'.join(fixed_feeds)}",
)

# ------------------------- CALCOLI PER MESE -------------------------
results = []
warnings_list = []
for _, row in edited_df.iterrows():
    fixed_map = {n: float(row[n]) for n in fixed_feeds}
    hours = float(row["Ore"])

    if is_dual_mode:
        sol, feasible, msg = solve_2_unknowns_dual(fixed_map, unknown_feeds, hours, aux_factor)
        all_masses = {**fixed_map, **sol}
        if not feasible:
            warnings_list.append(f"**{row['Mese']}**: {msg}")
    else:
        computed = solve_1_unknown_production(fixed_map, unknown_feeds[0], hours, aux_factor)
        all_masses = dict(fixed_map)
        all_masses[unknown_feeds[0]] = max(computed, 0.0)
        feasible = (computed >= 0)
        if not feasible:
            warnings_list.append(
                f"**{row['Mese']}**: {unknown_feeds[0]} = {computed:.1f} t (<0). "
                f"Le 3 biomasse fisse gia' superano il fabbisogno lordo."
            )

    summary = ghg_summary(all_masses, aux_factor)

    # Validita' - DUE CONDIZIONI OBBLIGATORIE:
    #   (1) saving GHG >= 80% (calcolato su biometano LORDO, cosi' anche la
    #       quota assorbita dagli ausiliari CHP+caldaia e' rinnovabile >=80%)
    #   (2) produzione netta <= 300 Sm3/h. Non deve MAI superare 300 (tetto
    #       autorizzativo GSE). Sotto 300 e' valido ma sub-ottimale.
    #       Le biomasse dimensionano il LORDO = 300 x aux_factor.
    net_smch = summary["nm3_net"] / hours if hours > 0 else 0.0
    saving_ok = summary["saving"] >= GHG_SAVING_THRESHOLD * 100
    prod_ok = net_smch <= PLANT_NET_SMCH + 0.5   # tolleranza +0.5 Sm3/h
    target_hit = abs(net_smch - PLANT_NET_SMCH) < 0.5

    if saving_ok and prod_ok:
        validita = "✅ Valido"
    else:
        motivi = []
        if not saving_ok:
            motivi.append(f"saving {summary['saving']:.1f}% < 80%")
        if not prod_ok:
            motivi.append(f"netti {net_smch:.1f} > 300 Sm³/h (over-autorizz.)")
        validita = "❌ Non valido: " + "; ".join(motivi)

    if saving_ok and prod_ok and not target_hit:
        stato = f"⚠️ netti {net_smch:.1f} < 300 (sub-ottimale)"
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

# ------------------------- RISULTATI -------------------------
st.subheader("📊 Risultati")

# Evidenzia colonne calcolate (colori leggibili sia tema chiaro sia scuro:
# sfondo scuro + testo bianco funziona in entrambi)
unknown_set = set(unknown_feeds)
STYLE_CALC   = "background-color: #1565C0; color: white; font-weight: 700;"
STYLE_OK     = "background-color: #2E7D32; color: white; font-weight: 600;"
STYLE_WARN   = "background-color: #EF6C00; color: white; font-weight: 600;"
STYLE_ERROR  = "background-color: #C62828; color: white; font-weight: 600;"

def highlight_cols(row):
    styles = [""] * len(row)
    cols = list(row.index)
    for u in unknown_set:
        if u in cols:
            styles[cols.index(u)] = STYLE_CALC
    if "Validità" in cols:
        i = cols.index("Validità")
        v = row["Validità"]
        if v.startswith("✅"):
            styles[i] = STYLE_OK
        else:
            styles[i] = STYLE_ERROR
    # saving < 80%: evidenzia la cella
    if "Saving %" in cols:
        i = cols.index("Saving %")
        if row["Saving %"] < GHG_SAVING_THRESHOLD * 100:
            styles[i] = STYLE_ERROR
    # Sm3/h netti > 300: rosso (over-autorizz.); < 300: arancione (sub-ottimale)
    if "Sm³/h netti" in cols:
        i = cols.index("Sm³/h netti")
        if row["Sm³/h netti"] > PLANT_NET_SMCH + 0.5:
            styles[i] = STYLE_ERROR
        elif row["Sm³/h netti"] < PLANT_NET_SMCH - 0.5:
            styles[i] = STYLE_WARN
    return styles

fmt = {n: "{:.1f}" for n in FEED_NAMES}
fmt.update({
    "Totale biomasse (t)": "{:,.0f}",
    "Sm³ lordi": "{:,.0f}",
    "Sm³ netti": "{:,.0f}",
    "MWh netti": "{:,.1f}",
    "GHG (gCO₂/MJ)": "{:.2f}",
    "Saving %": "{:.1f}",
    "Sm³/h netti": "{:.1f}",
})

st.dataframe(
    df_res.style.format(fmt).apply(highlight_cols, axis=1),
    hide_index=True,
    use_container_width=True,
    height=470,
)

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
    fig2.add_hline(y=80, line_dash="dash", line_color="red",
                   annotation_text="Soglia RED III 80%",
                   annotation_position="top right")
    fig2.add_hline(y=81, line_dash="dot", line_color="green",
                   annotation_text="Target solver 81%",
                   annotation_position="bottom right")
    fig2.update_layout(title="Saving GHG mensile (%)",
                       yaxis_title="Saving (%)", height=450,
                       yaxis=dict(range=[60, 160]))
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=df_res["Mese"], y=df_res["Sm³ lordi"],
                          name="Sm³ lordi", marker_color="#90A4AE"))
    fig3.add_trace(go.Bar(x=df_res["Mese"], y=df_res["Sm³ netti"],
                          name="Sm³ netti", marker_color="#1E88E5"))
    fig3.update_layout(title="Produzione mensile Sm³",
                       barmode="group", height=450,
                       yaxis_title="Sm³ / mese")
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    annual = {n: max(df_res[n].sum(), 0) for n in FEED_NAMES}
    fig4 = px.pie(
        names=list(annual.keys()),
        values=list(annual.values()),
        color=list(annual.keys()),
        color_discrete_map={n: FEEDSTOCK_DB[n]["color"] for n in FEED_NAMES},
        title="Mix annuale biomasse (t/anno)", hole=0.4,
    )
    st.plotly_chart(fig4, use_container_width=True)

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
