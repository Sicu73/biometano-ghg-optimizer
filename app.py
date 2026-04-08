"""
BioMethane GHG Optimizer – RED III Compliance Tool v2

Normative basis:
- EU Directive 2023/2413 (RED III), Annex V Part C – GHG methodology for biomethane
- Italian DM 07/08/2024 (GU n.211) – national implementation of RED III
- UNI/TS 11567:2024 – technical standard for biomethane GHG calculation
- Procedure Applicative GSE v7.0
- DM 15 settembre 2022 (PNRR – Investimento 1.4) – incentive scheme via
  competitive auction (asta al ribasso). Two tariff types:
  TO (tariffa onnicomprensiva): only for plants ≤ 250 Smc/h on mandatory
    third-party access grids; GSE buys gas + GO; revenue = tariff × MWh.
  TP (tariffa premio): mandatory for plants > 250 Smc/h; producer sells gas
    and GO on market; GSE pays delta: TP = tariff_agg - PSV - GO_price;
    total revenue = tariff_agg × MWh (same total, different structure).
  Base tariff (Allegato 2, 4th PNRR tranche 2024):
    ≤ 100 Smc/h → 128.39 €/MWh; > 100 Smc/h → 122.81 €/MWh
  Auction discount: minimum 1%; tariff_agg = tariff_base × (1 - discount%)
  Duration: 15 years from commercial operation.
  Energy crops (e.g. mais trinciato) NOT eligible as primary feedstock.

Core formula (RED III Annex V Part C):
    E_total = eec + el + ep + etd + eu - esca - eccs - eccr
    GHG_saving (%) = (fossil_comparator - E_total) / fossil_comparator × 100

Fossil comparator: 94 gCO2eq/MJ (natural gas, RED III Annex V Part C)
GHG saving threshold: ≥ 80% for new plants injecting into the grid
Max allowed emissions: 94 × (1 - 0.80) = 18.8 gCO2eq/MJ

GROSS vs NET logic:
    The GHG calculation and feedstock sizing must be applied to GROSS biomethane
    production (net + auxiliaries CHP/boiler), not just the net volume injected
    into the grid. Default auxiliary factor: +29% (CHP 300 kWe + boiler 80 kWth).
    Undersizing feedstock on net flow only would cause a ~29% production deficit,
    risking loss of GSE incentive (PMG – Produzione Minima Garantita).

Energy conversion for revenue:
    1 Nm³ biomethane (97% CH4) = 9.97 kWh = 0.00997 MWh

Dependencies: streamlit, plotly, pandas, numpy, scipy, reportlab
"""

import io
import datetime
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import minimize

# ── Constants ──────────────────────────────────────────────────────────────────
FOSSIL_COMPARATOR = 94.0        # gCO2eq/MJ (natural gas, RED III Annex V Part C)
GHG_SAVING_THRESHOLD = 0.80     # 80%
MAX_ALLOWED_EMISSIONS = FOSSIL_COMPARATOR * (1 - GHG_SAVING_THRESHOLD)  # 18.8
LHV_BIOMETHANE = 35.9           # MJ/Nm³ (used for GHG energy weighting)
NM3_TO_MWH = 0.00997            # 1 Nm³ biomethane (97% CH4) = 9.97 kWh = 0.00997 MWh
DEFAULT_AUX_FACTOR = 1.29       # CHP 300 kWe + boiler 80 kWth on 53% CH4 biogas
INCENTIVE_YEARS = 15            # DM 15/09/2022: 15 years duration

# DM 15/09/2022 Allegato 2 – original 2022 base tariffs (agricultural new plants)
TARIFF_ALLEGATO2_LE100 = 115.0  # €/MWh original 2022 value for plants ≤ 100 Smc/h
TARIFF_ALLEGATO2_GT100 = 110.0  # €/MWh original 2022 value for plants > 100 Smc/h
# Inflation adjustment Nov-2021 → Apr-2024 (NIC index, ~+11.6%):
# 115 × 1.116 = 128.39 / 110 × 1.116 = 122.81
TARIFF_INFLATION_ADJ_LE100 = 128.39   # €/MWh inflation-adjusted Allegato 2 value
TARIFF_INFLATION_ADJ_GT100 = 122.81   # €/MWh inflation-adjusted Allegato 2 value
# 4th PNRR bando mandatory -2% reduction applied to inflation-adjusted values:
TARIFF_BASE_LE100 = round(TARIFF_INFLATION_ADJ_LE100 * 0.98, 2)  # 125.82 €/MWh
TARIFF_BASE_GT100 = round(TARIFF_INFLATION_ADJ_GT100 * 0.98, 2)  # 120.35 €/MWh
TARIFF_THRESHOLD_REGIME = 250   # Smc/h: above this only TP is allowed
TARIFF_THRESHOLD_CLASS = 100    # Smc/h: base tariff step
DEFAULT_AUCTION_DISCOUNT = 2.0  # % additional discount offered by bidder (min 1% by law)
DEFAULT_PSV = 38.0              # €/MWh PSV gas natural price (indicative)
DEFAULT_GO_PRICE = 5.0          # €/MWh Garanzia di Origine (indicative)

# Default GHG values per feedstock (gCO2eq/MJ of biomethane produced)
FEEDSTOCK_DEFAULTS = {
    "Mais trinciato": {"eec": 26.0,  "esca":  0.0, "etd": 0.8},
    "Pollina solida": {"eec":  5.0,  "esca": -4.0, "etd": 0.8},
    "Liquame suino":  {"eec": -45.0, "esca":  0.0, "etd": 0.8},
}

# Standard biomethane yield parameters (Nm³/t FM)
YIELD_DEFAULTS = {
    "Mais trinciato": {"biogas_yield": 200, "ch4_content": 0.52, "biomethane_yield": 104},
    "Pollina solida": {"biogas_yield":  80, "ch4_content": 0.55, "biomethane_yield":  44},
    "Liquame suino":  {"biogas_yield":  25, "ch4_content": 0.60, "biomethane_yield":  15},
}

FEEDSTOCK_NAMES = list(FEEDSTOCK_DEFAULTS.keys())
FEEDSTOCK_COLORS = ["#F39C12", "#8E44AD", "#2980B9"]


# ── Helper functions ───────────────────────────────────────────────────────────

def compute_e_net(eec: float, esca: float, etd: float) -> float:
    """Compute net emission factor: E_net = eec - esca + etd.
    el, ep, eu, eccs, eccr are all zero for grid-injected biomethane."""
    return eec - esca + etd


def compute_energy_fractions(mass_fractions: dict, yield_params: dict) -> dict:
    """Return energy-based fractions from mass-based fractions and yield parameters."""
    energies = {}
    for name in FEEDSTOCK_NAMES:
        bm_yield = yield_params[name]["biomethane_yield"]
        energies[name] = mass_fractions[name] * bm_yield * LHV_BIOMETHANE
    total = sum(energies.values())
    if total == 0:
        return {n: 0.0 for n in FEEDSTOCK_NAMES}
    return {n: energies[n] / total for n in FEEDSTOCK_NAMES}


def compute_weighted_e_total(mass_fractions: dict, ghg_values: dict, yield_params: dict) -> float:
    """Compute E_total as energy-weighted average of E_net per feedstock."""
    energy_fracs = compute_energy_fractions(mass_fractions, yield_params)
    e_total = 0.0
    for name in FEEDSTOCK_NAMES:
        v = ghg_values[name]
        e_net = compute_e_net(v["eec"], v["esca"], v["etd"])
        e_total += energy_fracs[name] * e_net
    return e_total


def compute_ghg_saving(e_total: float) -> float:
    """GHG saving (%) = (94 - E_total) / 94 × 100."""
    return (FOSSIL_COMPARATOR - e_total) / FOSSIL_COMPARATOR * 100


def compute_feedstock_masses(energy_fracs: dict, gross_annual_nm3: float, yield_params: dict) -> dict:
    """Compute annual feedstock tonnage from gross production and energy fractions."""
    masses = {}
    for name in FEEDSTOCK_NAMES:
        bm_yield = yield_params[name]["biomethane_yield"]
        energy_share_nm3 = energy_fracs[name] * gross_annual_nm3
        masses[name] = energy_share_nm3 / bm_yield if bm_yield > 0 else 0.0
    return masses


# ── PDF generation ─────────────────────────────────────────────────────────────

def generate_pdf(net_capacity, aux_factor, gross_capacity, annual_hours,
                 mass_fractions, ghg_values, yield_params,
                 e_total, ghg_saving, compliant,
                 net_annual_nm3, gross_annual_nm3, net_annual_mwh,
                 feedstock_masses, energy_fracs,
                 tariff_type, tariff_base, auction_discount, auction_tariff,
                 psv_price, go_price,
                 revenue_incentive, revenue_gas_sale, revenue_go,
                 revenue_total, revenue_15y, capex_contribution):
    """Generate a PDF compliance report using reportlab. Returns PDF bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=13, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=10, spaceAfter=3)
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=7, textColor=colors.grey)
    elements = []

    today = datetime.date.today().strftime("%d/%m/%Y")

    # Header
    elements.append(Paragraph("Verifica Preliminare Sostenibilità GHG – RED III", title_style))
    elements.append(Paragraph(f"BioMethane GHG Optimizer v2 — {today}", normal))
    elements.append(Spacer(1, 6 * mm))

    # Plant specs
    elements.append(Paragraph("Parametri impianto", h2))
    aux_sm3h = gross_capacity - net_capacity
    spec_data = [
        ["Biometano netto autorizzato GSE", f"{net_capacity:.1f} Sm³/h"],
        ["Fattore ausiliari (CHP + caldaia)", f"×{aux_factor:.2f} (+{(aux_factor-1)*100:.0f}%)"],
        ["Ausiliari equivalenti", f"{aux_sm3h:.1f} Sm³/h"],
        ["Base calcolo GHG (biometano lordo)", f"{gross_capacity:.1f} Sm³/h"],
        ["Ore operative annue", f"{annual_hours} h/anno"],
        ["Produzione netta annua", f"{net_annual_nm3:,.0f} Nm³/anno  |  {net_annual_mwh:,.1f} MWh/anno"],
        ["Produzione lorda annua (base GHG)", f"{gross_annual_nm3:,.0f} Nm³/anno"],
    ]
    t = Table(spec_data, colWidths=[80 * mm, 80 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#FFF3CD")),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 5 * mm))

    # GHG result
    elements.append(Paragraph("Risultato GHG", h2))
    status_text = "CONFORME RED III" if compliant else "NON CONFORME"
    status_bg = colors.HexColor("#D5F5E3") if compliant else colors.HexColor("#FADBD8")
    ghg_data = [
        ["E_total (mix ponderato)", f"{e_total:.2f} gCO2eq/MJ"],
        ["GHG saving", f"{ghg_saving:.1f}%"],
        ["Soglia minima RED III", f"≥ 80%  (max {MAX_ALLOWED_EMISSIONS:.1f} gCO2eq/MJ)"],
        ["Esito verifica", status_text],
    ]
    t = Table(ghg_data, colWidths=[80 * mm, 80 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 3), (-1, 3), status_bg),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 5 * mm))

    # GHG per feedstock
    elements.append(Paragraph("Valori GHG per matrice", h2))
    ghg_detail = [["Matrice", "eec", "esca", "etd", "E_net", "Quota energetica"]]
    for name in FEEDSTOCK_NAMES:
        v = ghg_values[name]
        e_net = compute_e_net(v["eec"], v["esca"], v["etd"])
        ghg_detail.append([
            name,
            f"{v['eec']:.1f}", f"{v['esca']:.1f}", f"{v['etd']:.1f}",
            f"{e_net:.1f}",
            f"{energy_fracs[name]*100:.1f}%",
        ])
    t = Table(ghg_detail, colWidths=[35*mm, 18*mm, 18*mm, 18*mm, 18*mm, 25*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 5 * mm))

    # Feedstock tonnage
    elements.append(Paragraph("Fabbisogno matrici (calcolato su produzione lorda)", h2))
    fm_data = [["Matrice", "% mix (massa)", "t FM/anno", "Resa bm (Nm³/t FM)"]]
    for name in FEEDSTOCK_NAMES:
        fm_data.append([
            name,
            f"{mass_fractions[name]*100:.0f}%",
            f"{feedstock_masses[name]:,.0f}",
            f"{yield_params[name]['biomethane_yield']}",
        ])
    t = Table(fm_data, colWidths=[40*mm, 30*mm, 35*mm, 35*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Il fabbisogno è calcolato sulla produzione lorda ({gross_capacity:.0f} Sm³/h). "
        "Sottodimensionare le matrici sui soli Sm³/h netti determinerebbe un deficit "
        f"produttivo del {(aux_factor-1)*100:.0f}% con rischio decadimento incentivo GSE (PMG).",
        small,
    ))
    elements.append(Spacer(1, 5 * mm))

    # Revenue estimate (DM 15/09/2022)
    elements.append(Paragraph("Struttura ricavi (DM 15/09/2022 PNRR)", h2))
    tariff_label = "TO — Onnicomprensiva" if tariff_type == "TO" else "TP — Premio (obbligatorio > 250 Smc/h)"
    tp_premio_val = auction_tariff - psv_price - go_price
    rev_data = [
        ["Regime tariffario", tariff_label],
        ["Tariffa base Allegato 2 (4° bando 2024)", f"{tariff_base:.2f} €/MWh"],
        ["Ribasso d'asta offerto", f"{auction_discount:.1f}%"],
        ["Tariffa aggiudicata", f"{auction_tariff:.2f} €/MWh"],
        ["Produzione netta annua", f"{net_annual_mwh:,.1f} MWh/anno"],
    ]
    if tariff_type == "TO":
        rev_data.append(["Ricavo incentivo GSE (onnicomprensivo)", f"€ {revenue_incentive:,.0f}/anno"])
    else:
        rev_data.append(["Prezzo PSV gas naturale", f"{psv_price:.2f} €/MWh"])
        rev_data.append(["Prezzo GO – Garanzia di Origine", f"{go_price:.2f} €/MWh"])
        rev_data.append([f"Premio TP = {auction_tariff:.2f}–{psv_price:.2f}–{go_price:.2f}", f"{tp_premio_val:.2f} €/MWh"])
        rev_data.append(["Ricavo premio GSE (TP)", f"€ {revenue_incentive:,.0f}/anno"])
        rev_data.append(["Ricavo vendita gas (PSV)", f"€ {revenue_gas_sale:,.0f}/anno"])
        rev_data.append(["Ricavo GO", f"€ {revenue_go:,.0f}/anno"])
    rev_data.append(["RICAVO TOTALE annuo", f"€ {revenue_total:,.0f}/anno"])
    rev_data.append([f"RICAVO TOTALE su {INCENTIVE_YEARS} anni (non attualizzato)", f"€ {revenue_15y:,.0f}"])
    if capex_contribution > 0:
        rev_data.append(["Contributo conto capitale (una tantum)", f"€ {capex_contribution:,.0f}"])

    t = Table(rev_data, colWidths=[95 * mm, 65 * mm])
    style_commands = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]
    for row_idx, row in enumerate(rev_data):
        if "RICAVO TOTALE" in row[0]:
            style_commands.append(("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"))
            style_commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#E8F5E9")))
    t.setStyle(TableStyle(style_commands))
    elements.append(t)
    elements.append(Spacer(1, 8 * mm))

    # Footer
    elements.append(Paragraph(
        "Calcolato su base lorda (netti + ausiliari CHP/caldaia) — "
        "RED III (Dir. 2023/2413/UE) Allegato V | DM 07/08/2024 (GU n.211) | "
        "DM 15/09/2022 (PNRR Inv. 1.4) | "
        "UNI/TS 11567:2024 | Procedure Applicative GSE v7.0 | "
        f"Comparatore fossile: {FOSSIL_COMPARATOR} gCO2eq/MJ | Soglia GHG saving: ≥ 80%",
        small,
    ))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


# ── Streamlit App ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BioMethane GHG Optimizer v2",
    page_icon="🌿",
    layout="wide",
)

st.title("🌿 BioMethane GHG Optimizer – RED III Compliance Tool v2")

# Permanent info banner (top of page)
st.info(
    "ℹ️ **La verifica GHG è eseguita sulla produzione LORDA di biometano equivalente "
    "(netti + ausiliari CHP/caldaia)**, non sulla sola quota immessa in rete. "
    "Questo garantisce la sostenibilità dell'intera filiera di approvvigionamento matrici."
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:

    # Section 1 – Plant parameters
    st.header("⚙️ Parametri impianto")

    net_capacity = st.number_input(
        "Portata netta autorizzata GSE (Sm³/h)",
        min_value=10.0, max_value=5000.0, value=300.0, step=10.0,
        key="net_capacity",
    )

    aux_factor = st.slider(
        "Fattore ausiliari (CHP + caldaia) — default +29%",
        min_value=1.10, max_value=1.50, value=DEFAULT_AUX_FACTOR, step=0.01,
        key="aux_factor",
        help="Incremento dovuto a CHP e caldaia. Default calcolato su CHP 300 kWe + "
             "caldaia 80 kWth con biogas al 53% CH4.",
    )

    gross_capacity = net_capacity * aux_factor
    aux_delta_sm3h = gross_capacity - net_capacity

    # Highlighted calculated field (gross flow)
    st.markdown(
        f"""
        <div style='background-color:#FFF3CD;color:#856404;padding:10px 12px;
        border-radius:6px;border:1px solid #FFEEBA;font-size:0.9em;margin:6px 0;'>
        ⚠️ <b>Base calcolo GHG — Biometano lordo (Sm³/h):</b><br>
        <span style='font-size:1.6em;font-weight:bold;'>{gross_capacity:.1f}</span>
        <span style='font-size:0.85em;'> = {net_capacity:.0f} netti + {aux_delta_sm3h:.1f} ausiliari</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    annual_hours = st.slider(
        "Ore operative annue",
        min_value=6000, max_value=8760, value=8000, step=100,
        key="annual_hours",
    )

    st.markdown("---")

    # Section 2 – Feedstock mix
    st.header("🌾 Mix matrici (%)")
    st.caption("La somma deve essere 100%")

    pct_mais    = st.slider("Trinciato di mais (%)", 0, 100, 40, key="pct_mais")
    pct_pollina = st.slider("Pollina solida (%)",    0, 100, 30, key="pct_pollina")
    pct_liquame = st.slider("Liquame suino (%)",     0, 100, 30, key="pct_liquame")

    total_pct = pct_mais + pct_pollina + pct_liquame
    sum_ok = total_pct == 100

    if not sum_ok:
        st.error(f"⛔ Somma attuale: **{total_pct}%** — deve essere 100%")

    st.markdown("---")

    # Section 3 – Revenue parameters (DM 15/09/2022)
    st.header("💰 Parametri ricavi (DM 15/09/2022)")

    # Auto-determine tariff class and allowed regime from net capacity.
    # Chain: Allegato 2 (2022) → inflation adj. (NIC Nov21–Apr24) → –2% bando → user discount
    if net_capacity <= TARIFF_THRESHOLD_CLASS:
        tariff_allegato2 = TARIFF_ALLEGATO2_LE100
        tariff_infl_adj  = TARIFF_INFLATION_ADJ_LE100
        tariff_base      = TARIFF_BASE_LE100
        tariff_class_label = f"≤ {TARIFF_THRESHOLD_CLASS} Smc/h"
    else:
        tariff_allegato2 = TARIFF_ALLEGATO2_GT100
        tariff_infl_adj  = TARIFF_INFLATION_ADJ_GT100
        tariff_base      = TARIFF_BASE_GT100
        tariff_class_label = f"> {TARIFF_THRESHOLD_CLASS} Smc/h"

    only_tp = net_capacity > TARIFF_THRESHOLD_REGIME

    # Show tariff derivation chain
    st.markdown(
        f"<div style='background:#E8EAF6;color:#1a237e;padding:8px 10px;"
        f"border-radius:6px;font-size:0.82em;margin:4px 0;line-height:1.6;'>"
        f"📋 <b>Catena tariffaria ({tariff_class_label}):</b><br>"
        f"Allegato 2 originale (2022): {tariff_allegato2:.2f} €/MWh<br>"
        f"→ Adeguamento inflazione NIC (Nov21–Apr24, +11,6%): {tariff_infl_adj:.2f} €/MWh<br>"
        f"→ Riduzione obbligatoria 4° bando PNRR (–2%): <b>{tariff_base:.2f} €/MWh</b> ← base d'asta"
        f"</div>",
        unsafe_allow_html=True,
    )

    # TO/TP regime
    if only_tp:
        tariff_type = "TP"
        st.markdown(
            "<div style='background:#FFF3CD;color:#856404;padding:8px 10px;"
            "border-radius:6px;font-size:0.85em;margin:4px 0;'>"
            "⚠️ <b>Portata > 250 Smc/h → regime ESCLUSIVAMENTE TP</b><br>"
            "(Tariffa Premio: il produttore vende gas + GO sul mercato)</div>",
            unsafe_allow_html=True,
        )
    else:
        tariff_type = st.radio(
            "Tipologia tariffa (scelta per impianti ≤ 250 Smc/h)",
            options=["TO", "TP"],
            format_func=lambda x: (
                "TO — Onnicomprensiva (GSE ritira gas + GO)"
                if x == "TO" else
                "TP — Premio (produttore vende gas + GO sul mercato)"
            ),
            key="tariff_type",
        )

    # Auction discount
    auction_discount = st.number_input(
        "Ribasso aggiuntivo offerto in asta (%)",
        min_value=1.0, max_value=30.0, value=DEFAULT_AUCTION_DISCOUNT, step=0.5,
        key="auction_discount",
        help="Ribasso offerto dal concorrente sulla base d'asta (min 1% per legge). "
             "Nota: la base d'asta è già ridotta del 2% rispetto all'Allegato 2 aggiornato. "
             "Tariffa aggiudicata = base_d_asta × (1 – ribasso%). Default: 2%.",
    )

    # Computed awarded tariff (read-only display)
    auction_tariff = tariff_base * (1 - auction_discount / 100)
    st.markdown(
        f"<div style='background:#E8F5E9;color:#1B5E20;padding:8px 10px;"
        f"border-radius:6px;font-size:0.9em;margin:4px 0;'>"
        f"📌 <b>Tariffa aggiudicata:</b> "
        f"{tariff_base:.2f} × (1 – {auction_discount:.1f}%) = "
        f"<b>{auction_tariff:.2f} €/MWh</b></div>",
        unsafe_allow_html=True,
    )

    # PSV and GO prices (always needed for TP; shown for info in TO)
    psv_price = st.number_input(
        "Prezzo PSV gas naturale (€/MWh)",
        min_value=10.0, max_value=150.0, value=DEFAULT_PSV, step=1.0,
        key="psv_price",
        help="Prezzo di mercato del gas al PSV (fonte: GME o ARERA). "
             "Usato nel calcolo del premio TP. Valore indicativo: 35–45 €/MWh.",
    )

    go_price = st.number_input(
        "Prezzo GO – Garanzia di Origine (€/MWh)",
        min_value=0.0, max_value=30.0, value=DEFAULT_GO_PRICE, step=0.5,
        key="go_price",
        help="Valore medio mensile delle Garanzie di Origine del biometano. "
             "Valore indicativo: 3–8 €/MWh. Fonte: GME.",
    )

    capex_pct = st.number_input(
        "Contributo conto capitale GSE (%)",
        min_value=0.0, max_value=40.0, value=0.0, step=1.0,
        key="capex_pct",
        help="DM 15/09/2022 art. 6: max 40% spese ammissibili. "
             "Inserire 0 se non richiesto o già capitalizzato.",
    )

    capex_amount = 0.0
    if capex_pct > 0:
        capex_amount = st.number_input(
            "CAPEX totale impianto (€)",
            min_value=0.0, value=5_000_000.0, step=100_000.0,
            key="capex_amount",
            help="Costo totale dell'investimento (spese ammissibili).",
        )

    st.markdown("---")

    # Section 4 – Advanced parameters
    with st.expander("🔬 Parametri avanzati (GHG + rese)"):
        st.caption("Override valori di default (gCO2eq/MJ e Nm³/t FM)")

        ghg_values = {}
        yield_params = {}

        for name in FEEDSTOCK_NAMES:
            st.markdown(f"**{name}**")
            dg = FEEDSTOCK_DEFAULTS[name]
            dy = YIELD_DEFAULTS[name]

            c1, c2, c3 = st.columns(3)
            eec  = c1.number_input("eec",  value=dg["eec"],  step=0.5, key=f"eec_{name}")
            esca = c2.number_input("esca", value=dg["esca"], step=0.5, key=f"esca_{name}")
            etd  = c3.number_input("etd",  value=dg["etd"],  step=0.1, key=f"etd_{name}")
            ghg_values[name] = {"eec": eec, "esca": esca, "etd": etd}

            bm_yield = st.number_input(
                f"Resa biometano (Nm³/t FM)",
                value=float(dy["biomethane_yield"]), step=1.0, min_value=1.0,
                key=f"bm_yield_{name}",
            )
            yield_params[name] = {
                "biogas_yield": dy["biogas_yield"],
                "ch4_content": dy["ch4_content"],
                "biomethane_yield": bm_yield,
            }
            st.markdown("<hr style='margin:6px 0;border-color:#444;'>", unsafe_allow_html=True)

    st.markdown("---")

    # Normative footer
    st.caption(
        "**Riferimenti normativi:**\n\n"
        "RED III (Dir. 2023/2413/UE) – Allegato V | DM 07/08/2024 (GU n.211) | "
        "DM 15/09/2022 (PNRR Inv. 1.4) | "
        "UNI/TS 11567:2024 | Procedure Applicative GSE v7.0\n\n"
        f"Comparatore fossile: {FOSSIL_COMPARATOR} gCO2eq/MJ | Soglia GHG saving: ≥ 80%\n\n"
        "Base calcolo: **produzione lorda biometano equivalente (netti + ausiliari)**"
    )

# ── Guard: block if mix doesn't sum to 100% ────────────────────────────────────
if not sum_ok:
    st.warning("⚠️ Regola i cursori nella barra laterale affinché la somma sia 100% per procedere al calcolo.")
    st.stop()

# ── Core calculations ──────────────────────────────────────────────────────────
mass_fractions = {
    "Mais trinciato": pct_mais    / 100,
    "Pollina solida": pct_pollina / 100,
    "Liquame suino":  pct_liquame / 100,
}

energy_fracs = compute_energy_fractions(mass_fractions, yield_params)
e_total      = compute_weighted_e_total(mass_fractions, ghg_values, yield_params)
ghg_saving   = compute_ghg_saving(e_total)
compliant    = ghg_saving >= 80.0

# Production volumes
net_annual_nm3   = net_capacity   * annual_hours       # Nm³/year net (grid injection)
gross_annual_nm3 = gross_capacity * annual_hours       # Nm³/year gross (GHG base)
net_annual_mwh   = net_annual_nm3 * NM3_TO_MWH         # MWh/year (DM 15/09/2022 basis)

# Revenue calculations (DM 15/09/2022)
# Both TO and TP yield the same gross revenue = auction_tariff × MWh
# but with different payment structure:
#   TO: GSE pays full tariff, takes gas + GO → revenue_incentive = auction_tariff × MWh
#   TP: GSE pays premium (tariff - PSV - GO), producer sells gas+GO on market
#       → revenue_premium = (auction_tariff - psv_price - go_price) × MWh
#       → revenue_gas_go  = (psv_price + go_price) × MWh
#       → total same = auction_tariff × MWh
if tariff_type == "TO":
    revenue_incentive  = auction_tariff * net_annual_mwh   # GSE pays all-in
    revenue_gas_sale   = 0.0
    revenue_go         = 0.0
    revenue_total      = revenue_incentive
else:  # TP
    tp_premio          = auction_tariff - psv_price - go_price   # can be negative
    revenue_incentive  = tp_premio * net_annual_mwh              # GSE premium
    revenue_gas_sale   = psv_price * net_annual_mwh              # producer sells gas
    revenue_go         = go_price  * net_annual_mwh              # producer sells GO
    revenue_total      = auction_tariff * net_annual_mwh         # = incentive+gas+GO
revenue_15y        = revenue_total * INCENTIVE_YEARS
capex_contribution = capex_amount * (capex_pct / 100) if capex_pct > 0 else 0.0

# Feedstock masses based on GROSS production
feedstock_masses = compute_feedstock_masses(energy_fracs, gross_annual_nm3, yield_params)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 – GHG Compliance Dashboard
# ══════════════════════════════════════════════════════════════════════════════
st.header("1 – Dashboard conformità GHG")
st.caption(
    f"Verifica GHG calcolata su **{gross_capacity:.1f} Sm³/h lordi** "
    f"(netti {net_capacity:.0f} + ausiliari {aux_delta_sm3h:.1f} Sm³/h)"
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("E_total (gCO2eq/MJ)", f"{e_total:.2f}")
    if e_total <= MAX_ALLOWED_EMISSIONS:
        st.success(f"✅ ≤ {MAX_ALLOWED_EMISSIONS:.1f} gCO2eq/MJ")
    else:
        st.error(f"❌ > {MAX_ALLOWED_EMISSIONS:.1f} gCO2eq/MJ")

with col2:
    st.metric("GHG saving (%)", f"{ghg_saving:.1f}%")
    if ghg_saving >= 80:
        st.success("✅ ≥ 80%")
    else:
        st.error("❌ < 80%")

with col3:
    if compliant:
        st.markdown(
            f"<div style='background-color:#27AE60;color:white;padding:16px 10px;border-radius:10px;"
            f"text-align:center;font-size:1.1em;font-weight:bold;margin-top:6px;'>"
            f"✅ CONFORME RED III<br>"
            f"<span style='font-size:0.75em;font-weight:normal;'>"
            f"Base calcolo: {gross_capacity:.0f} Sm³/h lordi</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background-color:#E74C3C;color:white;padding:16px 10px;border-radius:10px;"
            "text-align:center;font-size:1.2em;font-weight:bold;margin-top:6px;'>"
            "❌ NON CONFORME</div>",
            unsafe_allow_html=True,
        )

# Validation warnings
if mass_fractions["Mais trinciato"] > 0.60 and ghg_saving < 80:
    st.warning(
        "⚠️ Quota mais superiore al 60% compromette la conformità GHG. "
        "Incrementare liquame suino o pollina."
    )
if mass_fractions["Liquame suino"] == 0 and ghg_saving < 80:
    st.info(
        "ℹ️ Il liquame suino (E_net = -44.2 gCO2eq/MJ) è la leva più efficace "
        "per il risparmio GHG con questa composizione."
    )

# Detail table
st.subheader("Dettaglio emissioni per matrice")
detail_rows = []
for name in FEEDSTOCK_NAMES:
    v = ghg_values[name]
    e_net = compute_e_net(v["eec"], v["esca"], v["etd"])
    detail_rows.append({
        "Matrice":              name,
        "eec (gCO2eq/MJ)":     v["eec"],
        "esca (gCO2eq/MJ)":    v["esca"],
        "etd (gCO2eq/MJ)":     v["etd"],
        "E_net (gCO2eq/MJ)":   round(e_net, 2),
        "Quota massa (%)":      f"{mass_fractions[name]*100:.0f}",
        "Quota energia (%)":    f"{energy_fracs[name]*100:.1f}",
    })
st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 – Production Balance & Revenue (DM 15/09/2022)
# ══════════════════════════════════════════════════════════════════════════════
st.header("2 – Bilancio produttivo e ricavi")

# PNRR warning about energy crops
st.warning(
    "⚠️ **ATTENZIONE – DM 15/09/2022 (PNRR):** le colture dedicate (es. mais trinciato) "
    "non sono ammesse come feedstock prevalente. L'incentivo è riservato a impianti alimentati "
    "principalmente da sottoprodotti e rifiuti (liquame suino, pollina, FORSU, ecc.). "
    "Verificare la quota massima di mais trinciato consentita nel proprio fascicolo di domanda GSE."
)

col_net, col_rev = st.columns(2)

# Column A — Net production (GSE contract base)
with col_net:
    st.subheader("📤 Produzione netta (GSE)")
    st.metric("Biometano immesso in rete", f"{net_capacity:.1f} Sm³/h")
    st.metric("Produzione netta annua", f"{net_annual_nm3:,.0f} Nm³/anno")
    st.metric("Energia netta annua", f"{net_annual_mwh:,.1f} MWh/anno")
    st.caption(f"Conversione: 1 Nm³ biometano (97% CH4) = {NM3_TO_MWH*1000:.2f} kWh = {NM3_TO_MWH} MWh")

# Column B — Revenue structure (DM 15/09/2022)
with col_rev:
    st.subheader("💰 Struttura ricavi (DM 15/09/2022)")

    # Tariff regime badge
    if only_tp:
        regime_badge = "🟡 TP — Tariffa Premio (obbligatorio > 250 Smc/h)"
    elif tariff_type == "TO":
        regime_badge = "🟢 TO — Tariffa Onnicomprensiva"
    else:
        regime_badge = "🔵 TP — Tariffa Premio"

    st.markdown(f"**Regime:** {regime_badge}")
    st.markdown(
        f"**Tariffa base:** {tariff_base:.2f} €/MWh &nbsp;|&nbsp; "
        f"**Ribasso:** {auction_discount:.1f}% &nbsp;|&nbsp; "
        f"**Aggiudicata:** **{auction_tariff:.2f} €/MWh**"
    )

    if tariff_type == "TO":
        st.metric("Ricavo incentivo GSE (tariffa onnicomprensiva)", f"€ {revenue_incentive:,.0f}/anno")
        st.caption("Il GSE ritira il biometano e le Garanzie di Origine (GO).")
    else:  # TP
        tp_premio_val = auction_tariff - psv_price - go_price
        st.markdown(f"**Premio TP** = {auction_tariff:.2f} – {psv_price:.2f} – {go_price:.2f} = **{tp_premio_val:.2f} €/MWh**")
        st.metric("Premio GSE (TP)", f"€ {revenue_incentive:,.0f}/anno")
        st.metric("Ricavo vendita gas (PSV)", f"€ {revenue_gas_sale:,.0f}/anno")
        st.metric("Ricavo GO – Garanzie Origine", f"€ {revenue_go:,.0f}/anno")

    st.divider()
    st.metric("RICAVO TOTALE annuo", f"€ {revenue_total:,.0f}/anno")
    st.metric(f"RICAVO TOTALE su {INCENTIVE_YEARS} anni (non attualizzato)", f"€ {revenue_15y:,.0f}")

    if capex_contribution > 0:
        st.metric("Contributo conto capitale (una tantum)", f"€ {capex_contribution:,.0f}")

# Explanatory note on incentive mechanism
st.caption(
    "La tariffa incentivante del DM 15/09/2022 è determinata tramite procedura competitiva "
    "(asta al ribasso). Il valore di aggiudicazione dipende dall'offerta presentata in sede di gara. "
    "La tariffa base (Allegato 2) viene aggiornata mensilmente dal GSE per inflazione (indice NIC). "
    f"Durata incentivo: {INCENTIVE_YEARS} anni dalla data di entrata in esercizio commerciale."
)

st.markdown("---")

# Feedstock demand (gross basis)
st.subheader("🏭 Fabbisogno lordo matrici (base calcolo GHG)")

fb_col1, fb_col2 = st.columns([1, 1])
with fb_col1:
    st.metric("Biometano equivalente lordo", f"{gross_capacity:.1f} Sm³/h")
    st.metric("Produzione lorda annua", f"{gross_annual_nm3:,.0f} Nm³/anno")

with fb_col2:
    fm_rows = []
    for name in FEEDSTOCK_NAMES:
        bm_yield_nm3 = energy_fracs[name] * gross_annual_nm3
        fm_rows.append({
            "Matrice":             name,
            "% mix":               f"{mass_fractions[name]*100:.0f}%",
            "t FM/anno":           f"{feedstock_masses[name]:,.0f}",
            "Nm³ biometano/anno":  f"{bm_yield_nm3:,.0f}",
        })
    st.dataframe(pd.DataFrame(fm_rows), use_container_width=True, hide_index=True)

# PMG warning note
st.caption(
    f"ℹ️ **Il fabbisogno matrici è calcolato sulla produzione lorda ({gross_capacity:.0f} Sm³/h)** "
    f"perché il biogas per CHP e caldaia richiede ugualmente feedstock in ingresso al digestore. "
    f"Sottodimensionare le matrici sui soli {net_capacity:.0f} Sm³/h netti determinerebbe un deficit "
    f"produttivo del {(aux_factor-1)*100:.0f}% con rischio decadimento incentivo GSE "
    f"(PMG — Produzione Minima Garantita)."
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 – Energy contribution pie chart
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 – Contributo energetico per matrice")

fig_pie = go.Figure(data=[go.Pie(
    labels=FEEDSTOCK_NAMES,
    values=[energy_fracs[n] for n in FEEDSTOCK_NAMES],
    marker_colors=FEEDSTOCK_COLORS,
    textinfo="label+percent",
    hole=0.38,
)])
fig_pie.update_layout(
    title=f"Contributo energetico al mix lordo ({gross_capacity:.0f} Sm³/h)",
    margin=dict(t=50, b=20, l=20, r=20),
    height=380,
)
st.plotly_chart(fig_pie, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 – Sensitivity Heatmap
# ══════════════════════════════════════════════════════════════════════════════
st.header("4 – Analisi di sensitività")
st.caption("GHG saving (%) in funzione di mais trinciato e liquame suino (pollina = residuo, grigio = mix non valido)")

steps = list(range(0, 101, 10))
z_data = np.full((len(steps), len(steps)), np.nan)

for i, pct_liq in enumerate(steps):
    for j, pct_m in enumerate(steps):
        pct_pol = 100 - pct_m - pct_liq
        if pct_pol < 0:
            continue
        fracs = {
            "Mais trinciato": pct_m    / 100,
            "Pollina solida": pct_pol  / 100,
            "Liquame suino":  pct_liq  / 100,
        }
        et = compute_weighted_e_total(fracs, ghg_values, yield_params)
        z_data[i, j] = compute_ghg_saving(et)

# 4-tone colorscale: red < 75, orange 75-80, yellow 80-85, green > 85
colorscale = [
    [0.00, "#E74C3C"],
    [0.30, "#E74C3C"],
    [0.40, "#E67E22"],
    [0.50, "#E67E22"],
    [0.60, "#F1C40F"],
    [0.70, "#F1C40F"],
    [0.80, "#27AE60"],
    [1.00, "#27AE60"],
]

fig_heatmap = go.Figure()

fig_heatmap.add_trace(go.Heatmap(
    z=z_data,
    x=[f"{s}%" for s in steps],
    y=[f"{s}%" for s in steps],
    colorscale=colorscale,
    zmin=50, zmax=100,
    colorbar=dict(title="GHG saving (%)"),
    hovertemplate="Mais: %{x}<br>Liquame: %{y}<br>GHG saving: %{z:.1f}%<extra></extra>",
))

# Mark current operating point
fig_heatmap.add_trace(go.Scatter(
    x=[f"{pct_mais}%"],
    y=[f"{pct_liquame}%"],
    mode="markers+text",
    marker=dict(symbol="star", size=20, color="white", line=dict(width=2, color="black")),
    text=["Punto operativo"],
    textposition="top center",
    textfont=dict(color="white", size=11),
    showlegend=False,
))

fig_heatmap.update_layout(
    xaxis_title="Mais trinciato (%)",
    yaxis_title="Liquame suino (%)",
    margin=dict(t=30, b=50, l=50, r=20),
    height=520,
    annotations=[
        dict(
            x=0.5, y=1.03, xref="paper", yref="paper",
            text="🔴 < 75%  |  🟠 75–80%  |  🟡 80–85%  |  🟢 > 85%  |  ☆ = punto operativo",
            showarrow=False, font=dict(size=11),
        )
    ],
)
st.plotly_chart(fig_heatmap, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 – Monthly GSE Sustainability Verification
# GSE requires monthly declaration of feedstock quantities and GHG compliance
# for each invoicing period (Procedure Applicative GSE v7.0, art. 12)
# ══════════════════════════════════════════════════════════════════════════════
st.header("5 – Verifica mensile sostenibilità matrici (GSE)")
st.caption(
    "Dichiarazione mensile obbligatoria ai fini della fatturazione GSE "
    "(Procedure Applicative GSE v7.0, art. 12). "
    "La sostenibilità GHG deve essere verificata su ogni lotto mensile immesso in rete."
)

MONTHS_IT = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
             "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

with st.expander("📅 Parametri operativi mensili", expanded=False):
    st.caption("Inserisci le ore operative effettive per ogni mese (default: distribuzione uniforme delle ore annue).")
    hours_per_month_default = [round(annual_hours / 12) for _ in range(12)]
    # Adjust last month to match total exactly
    hours_per_month_default[11] = annual_hours - sum(hours_per_month_default[:11])

    monthly_hours = []
    cols_m = st.columns(6)
    for i in range(12):
        h = cols_m[i % 6].number_input(
            MONTHS_IT[i], min_value=0, max_value=744,
            value=int(hours_per_month_default[i]),
            key=f"month_hours_{i}",
        )
        monthly_hours.append(h)

    total_monthly = sum(monthly_hours)
    if abs(total_monthly - annual_hours) > 10:
        st.warning(f"⚠️ Totale ore mensili ({total_monthly} h) ≠ ore annue impostate ({annual_hours} h). Verificare.")

# Build monthly table
monthly_rows = []
for i, month in enumerate(MONTHS_IT):
    h = monthly_hours[i]
    # Net and gross production for the month
    nm3_net_m   = net_capacity   * h          # Nm³ net
    nm3_gross_m = gross_capacity * h          # Nm³ gross (GHG base)
    mwh_net_m   = nm3_net_m * NM3_TO_MWH      # MWh net

    # Feedstock mass per month (based on gross production)
    fm_m = compute_feedstock_masses(energy_fracs, nm3_gross_m, yield_params)

    # GHG saving is constant (same mix) — included for GSE declaration
    row = {
        "Mese":                   month,
        "Ore":                    h,
        "Nm³ netti":              f"{nm3_net_m:,.0f}",
        "MWh netti":              f"{mwh_net_m:,.1f}",
        "Nm³ lordi (GHG)":        f"{nm3_gross_m:,.0f}",
        "Mais (t FM)":            f"{fm_m['Mais trinciato']:,.1f}",
        "Pollina (t FM)":         f"{fm_m['Pollina solida']:,.1f}",
        "Liquame (t FM)":         f"{fm_m['Liquame suino']:,.1f}",
        "GHG saving (%)":         f"{ghg_saving:.1f}",
        "Conforme":               "✅" if compliant else "❌",
    }
    monthly_rows.append(row)

# Totals row
total_nm3_net   = sum(net_capacity   * monthly_hours[i] for i in range(12))
total_nm3_gross = sum(gross_capacity * monthly_hours[i] for i in range(12))
total_mwh       = total_nm3_net * NM3_TO_MWH
total_fm        = compute_feedstock_masses(energy_fracs, total_nm3_gross, yield_params)
monthly_rows.append({
    "Mese":                   "**TOTALE**",
    "Ore":                    sum(monthly_hours),
    "Nm³ netti":              f"{total_nm3_net:,.0f}",
    "MWh netti":              f"{total_mwh:,.1f}",
    "Nm³ lordi (GHG)":        f"{total_nm3_gross:,.0f}",
    "Mais (t FM)":            f"{total_fm['Mais trinciato']:,.1f}",
    "Pollina (t FM)":         f"{total_fm['Pollina solida']:,.1f}",
    "Liquame (t FM)":         f"{total_fm['Liquame suino']:,.1f}",
    "GHG saving (%)":         f"{ghg_saving:.1f}",
    "Conforme":               "✅" if compliant else "❌",
})

df_monthly = pd.DataFrame(monthly_rows)
st.dataframe(df_monthly, use_container_width=True, hide_index=True)

# Monthly production chart (Nm³ net per month)
fig_monthly = go.Figure()
fig_monthly.add_trace(go.Bar(
    x=MONTHS_IT,
    y=[net_capacity * monthly_hours[i] for i in range(12)],
    name="Nm³ netti/mese",
    marker_color="#2980B9",
))
fig_monthly.add_trace(go.Bar(
    x=MONTHS_IT,
    y=[(gross_capacity - net_capacity) * monthly_hours[i] for i in range(12)],
    name="Nm³ ausiliari (CHP/caldaia)",
    marker_color="#E67E22",
))
fig_monthly.update_layout(
    barmode="stack",
    title="Produzione mensile biometano — netti vs ausiliari",
    xaxis_title="Mese",
    yaxis_title="Nm³/mese",
    height=320,
    margin=dict(t=40, b=30, l=40, r=20),
    legend=dict(orientation="h", y=1.1),
)
st.plotly_chart(fig_monthly, use_container_width=True)

st.caption(
    "ℹ️ Il GHG saving è calcolato sul mix annuo; la verifica mensile GSE "
    "richiede che ogni lotto (batch) sia tracciabile con documentazione "
    "delle matrici in ingresso al digestore nel periodo di riferimento. "
    "Se il mix mensile differisce dal mix annuo, aggiornare i cursori e "
    "ricalcolare per il periodo specifico."
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 – Optimizer
# ══════════════════════════════════════════════════════════════════════════════
st.header("6 – Ottimizzatore mix")

with st.expander("Apri ottimizzatore", expanded=False):
    st.markdown(
        "Trova il mix che **massimizza la quota di mais trinciato** garantendo "
        "un GHG saving ≥ 80% (vincolo RED III)."
    )

    if st.button("Ottimizza mix: massimizza mais con GHG saving ≥ 80%"):

        def objective(x):
            return -x[0]

        def ghg_con(x):
            fracs = {"Mais trinciato": x[0], "Pollina solida": x[1], "Liquame suino": x[2]}
            et = compute_weighted_e_total(fracs, ghg_values, yield_params)
            return compute_ghg_saving(et) - 80.0

        result = minimize(
            objective,
            x0=[0.33, 0.34, 0.33],
            method="SLSQP",
            bounds=[(0, 1), (0, 1), (0, 1)],
            constraints=[
                {"type": "eq",   "fun": lambda x: x[0] + x[1] + x[2] - 1.0},
                {"type": "ineq", "fun": ghg_con},
            ],
        )

        if result.success:
            opt_fracs = {"Mais trinciato": result.x[0], "Pollina solida": result.x[1], "Liquame suino": result.x[2]}
            opt_et = compute_weighted_e_total(opt_fracs, ghg_values, yield_params)
            opt_gs = compute_ghg_saving(opt_et)

            st.success(f"✅ Soluzione trovata — GHG saving ottimizzato: **{opt_gs:.1f}%**")

            opt_rows = []
            for name in FEEDSTOCK_NAMES:
                current   = mass_fractions[name] * 100
                optimized = opt_fracs[name] * 100
                opt_rows.append({
                    "Matrice":           name,
                    "Attuale (%)":       f"{current:.1f}",
                    "Ottimizzato (%)":   f"{optimized:.1f}",
                    "Delta (pp)":        f"{optimized - current:+.1f}",
                })
            st.dataframe(pd.DataFrame(opt_rows), use_container_width=True, hide_index=True)
            st.metric("E_total ottimizzato (gCO2eq/MJ)", f"{opt_et:.2f}")
        else:
            st.error("❌ Ottimizzazione non riuscita. Nessun mix soddisfa i vincoli con i valori GHG correnti.")


# ══════════════════════════════════════════════════════════════════════════════
# PDF Export
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("📄 Esporta Report GHG")

if st.button("Genera PDF — Verifica Preliminare Sostenibilità GHG"):
    try:
        pdf_bytes = generate_pdf(
            net_capacity, aux_factor, gross_capacity, annual_hours,
            mass_fractions, ghg_values, yield_params,
            e_total, ghg_saving, compliant,
            net_annual_nm3, gross_annual_nm3, net_annual_mwh,
            feedstock_masses, energy_fracs,
            tariff_type, tariff_base, auction_discount, auction_tariff,
            psv_price, go_price,
            revenue_incentive, revenue_gas_sale, revenue_go,
            revenue_total, revenue_15y, capex_contribution,
        )
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        st.download_button(
            label="⬇️ Scarica PDF",
            data=pdf_bytes,
            file_name=f"GHG_Verifica_RED3_{today_str}.pdf",
            mime="application/pdf",
        )
    except ImportError:
        st.error("Libreria reportlab non disponibile. Esegui: pip install reportlab")
