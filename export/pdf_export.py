# -*- coding: utf-8 -*-
"""export/pdf_export.py — Esportazione PDF da output_model.

Funzione pubblica:
  build_pdf_from_output(output_model) -> BytesIO

Questa funzione e' un ADAPTER che:
1. Ricostruisce il ctx compatibile con l'API di report_pdf.py (root level)
   a partire dall'output_model strutturato.
2. Chiama `report_pdf.build_metaniq_pdf(ctx)` esistente.

In questo modo il refactoring non richiede di toccare i 1673 righe di
report_pdf.py: la logica di generazione PDF resta invariata, ma ora
l'entry point ufficiale e' `build_pdf_from_output(output_model)`.

Se report_pdf.py non e' disponibile, genera un PDF di testo minimale
usando reportlab direttamente (senza lo styling consulting-grade).
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

try:
    from report_pdf import build_metaniq_pdf as _build_pdf_legacy  # type: ignore[import]
    _HAS_LEGACY_PDF = True
except ImportError:
    _HAS_LEGACY_PDF = False

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


def build_pdf_from_output(output_model: dict) -> BytesIO:
    """Genera file PDF da output_model.

    Args:
        output_model:   Dict prodotto da build_output_model().

    Returns:
        BytesIO con il file .pdf, pronto per st.download_button.

    Raises:
        RuntimeError:   Se ne reportlab ne legacy report_pdf disponibili.
    """
    if not isinstance(output_model, dict):
        raise ValueError(f"output_model deve essere un dict, ricevuto: {type(output_model)}")

    # --- Tenta via legacy (report_pdf.build_metaniq_pdf) -------------------
    if _HAS_LEGACY_PDF:
        try:
            ctx = _output_model_to_pdf_ctx(output_model)
            return _build_pdf_legacy(ctx)
        except Exception as exc:
            # Fallback a PDF minimale
            return _build_fallback_pdf(output_model, error=str(exc))

    # --- Fallback: PDF minimale con reportlab --------------------------------
    return _build_fallback_pdf(output_model)


# ---------------------------------------------------------------------------
# Adattatore output_model -> ctx legacy
# ---------------------------------------------------------------------------

def _output_model_to_pdf_ctx(output_model: dict) -> dict:
    """Ricostruisce il ctx dict compatibile con report_pdf.build_metaniq_pdf."""
    meta = output_model.get("metadata", {})
    inp = output_model.get("input_summary", {})
    plant = inp.get("plant", {})
    calc = output_model.get("calculation_summary", {})
    monthly_rows = output_model.get("monthly_table", [])
    expl = output_model.get("explanations", {})

    # Ricostruisci df_res
    df_res = None
    if _HAS_PANDAS and monthly_rows:
        df_res = pd.DataFrame(monthly_rows)

    app_mode = meta.get("app_mode", "biometano")
    is_chp = bool(plant.get("is_chp", False))
    is_chp_dm2012 = app_mode == "biogas_chp"
    is_fer2 = bool(plant.get("is_fer2", False))
    is_dm2018 = bool(plant.get("is_dm2018", False))
    is_dm2022 = bool(plant.get("is_dm2022", True))
    cic_active = bool(calc.get("cic_active", False))
    is_advanced = bool(calc.get("is_advanced", False))

    # Audit rows
    audit_rows = output_model.get("audit_trail", [])
    yield_audit = [r for r in audit_rows if r.get("tipo") == "BMT_yield_override"]
    emission_audit = [r for r in audit_rows if r.get("tipo") == "emission_factor_override"]

    # Revenue rows per PDF (atteso come lista di tuple (nome, dict_numeri))
    revenue_rows = []
    for fs_row in output_model.get("feedstock_table", []):
        revenue_rows.append((
            fs_row.get("biomassa", ""),
            {
                "ricavi":  fs_row.get("ricavi_eur", 0.0),
                "tariffa": fs_row.get("tariffa_eur_mwh", 0.0),
                "n_cic":   fs_row.get("n_cic", 0.0),
                "mwh":     fs_row.get("mwh_anno", 0.0),
                "t":       fs_row.get("tonnellate_anno", 0.0),
            },
        ))

    # BP result: ricostruisci dal business_plan_table se disponibile
    bp_result = _reconstruct_bp_result(output_model)

    ctx: dict[str, Any] = {
        "df_res":          df_res,
        "IS_CHP":          is_chp,
        "IS_CHP_DM2012":   is_chp_dm2012,
        "IS_FER2":         is_fer2,
        "IS_DM2018":       is_dm2018,
        "IS_DM2022":       is_dm2022,
        "APP_MODE":        app_mode,
        "plant_kwe":       plant.get("plant_kwe") or 0.0,
        "plant_kwe_net":   plant.get("plant_kwe") or 0.0,
        "plant_net_smch":  plant.get("plant_net_smch", 300.0),
        "eta_el":          0.40,
        "eta_th":          0.42,
        "aux_el_pct":      0.08,
        "aux_factor":      plant.get("aux_factor", 1.29),
        "ep_total":        plant.get("ep_total", 0.0),
        "end_use":         plant.get("end_use", ""),
        "ghg_threshold":   plant.get("ghg_threshold", 0.80),
        "fossil_comparator": plant.get("fossil_comparator", 80.0),
        "upgrading_opt":   plant.get("upgrading_opt", ""),
        "offgas_opt":      plant.get("offgas_opt", ""),
        "injection_opt":   plant.get("injection_opt", ""),
        # DM 2018
        "is_advanced":     is_advanced,
        "cic_active":      cic_active,
        "cic_double":      is_advanced and cic_active,
        "cic_price":       calc.get("cic_price", 375.0),
        "annex_mass_share": 0.0,
        "annex_threshold": 0.70,
        "tot_n_cic":       calc.get("tot_n_cic", 0.0),
        "MWH_PER_CIC":     11.628,
        "GCAL_PER_CIC":    10.0,
        # FER 2
        "fer2_kwe_cap":    300.0,
        "fer2_periodo_anni": 20,
        "fer2_subprod_share": 0.0,
        "fer2_matrice_threshold": 0.80,
        "fer2_qualified":  False,
        "fer2_tariffa_base": 256.0,
        "fer2_premio_matrice_eur": 30.0,
        "fer2_premio_car_eur": 10.0,
        "fer2_apply_matrice": False,
        "fer2_apply_car":  False,
        "fer2_tariffa_eff": 256.0,
        # BP (None se non DM 2022)
        "bp_result":       bp_result,
        "bp_tariffa_eur_mwh": 131.0,
        "bp_ribasso_pct":  1.0,
        "bp_tariffa_eff":  130.0,
        "bp_pnrr_pct":     40.0,
        "bp_capex_breakdown": None,
        "bp_capex_forfait": None,
        "bp_lt_tasso":     4.0,
        "bp_lt_durata":    15,
        "bp_lt_leva":      80.0,
        "bp_ebitda_target_pct": 25.0,
        "bp_inflazione_pct": 2.5,
        "bp_ch4_in_biogas_pct": 54.25,
        "bp_durata_tariffa": 15,
        # Aggregati
        "tot_biomasse_t":  calc.get("tot_biomasse_t", 0.0),
        "tot_sm3_netti":   calc.get("tot_sm3_netti", 0.0),
        "tot_mwh_netti":   calc.get("tot_mwh", 0.0),
        "tot_mwh_el_lordo": calc.get("tot_mwh_el_lordo", 0.0),
        "tot_mwh_el_netto": calc.get("tot_mwh_el_netto", 0.0),
        "saving_avg":      calc.get("saving_avg", 0.0),
        "valid_months":    calc.get("valid_months", 0),
        "tot_revenue":     calc.get("total_revenue", 0.0),
        "tot_mwh_basis":   calc.get("tot_mwh", 0.0),
        "tariffa_media_ponderata": calc.get("tariffa_media_ponderata", 0.0),
        "revenue_rows":    revenue_rows,
        "lang":            meta.get("language", "it"),
        # Audit
        "yield_audit_rows":    yield_audit,
        "effective_yields":    {},
        "emission_audit_rows": emission_audit,
        "emission_overrides":  {},
    }
    return ctx


def _reconstruct_bp_result(output_model: dict) -> dict | None:
    """Ricostruisce bp_result dal business_plan_table dell'output_model."""
    bp_rows = output_model.get("business_plan_table", [])
    if not bp_rows:
        return None
    return {
        "ricavi":         [r["ricavi_eur"] for r in bp_rows],
        "opex":           [r["opex_eur"] for r in bp_rows],
        "ebitda":         [r["ebitda_eur"] for r in bp_rows],
        "interessi":      [r["interessi_eur"] for r in bp_rows],
        "ammortamenti":   [r["ammortamenti_eur"] for r in bp_rows],
        "utile_ante":     [r["utile_ante_eur"] for r in bp_rows],
        "utile_netto":    [r["utile_netto_eur"] for r in bp_rows],
        "fcf":            [r["fcf_eur"] for r in bp_rows],
        "capex_totale":   0.0,
        "contributo":     0.0,
        "capex_netto":    0.0,
        "debito_lt":      0.0,
        "equity":         0.0,
        "rata_lt":        0.0,
        "irr_equity":     None,
        "payback_anno":   None,
        "fcf_tot":        sum(r["fcf_eur"] for r in bp_rows),
        "utile_netto_tot": sum(r["utile_netto_eur"] for r in bp_rows),
        "ebitda_medio":   sum(r["ebitda_eur"] for r in bp_rows) / len(bp_rows),
        "costo_biogas_eur_per_nm3": 0.0,
        "quota_biomasse_anno": 0.0,
        "fabbisogno_biogas_anno": 0.0,
        "ch4_frac":       0.5425,
        "biometano_smc_anno": 0.0,
        "biometano_mwh_anno": 0.0,
    }


# ---------------------------------------------------------------------------
# Fallback PDF minimale
# ---------------------------------------------------------------------------

def _build_fallback_pdf(output_model: dict, error: str | None = None) -> BytesIO:
    """Genera un PDF minimale se il generatore legacy non e' disponibile."""
    buf = BytesIO()
    if not _HAS_REPORTLAB:
        buf.seek(0)
        return buf

    meta = output_model.get("metadata", {})
    calc = output_model.get("calculation_summary", {})
    expl = output_model.get("explanations", {})
    warnings = output_model.get("warnings", [])
    errors = output_model.get("errors", [])

    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=18*mm, rightMargin=18*mm,
                             topMargin=22*mm, bottomMargin=22*mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(
        f"<b>{meta.get('software_name', 'Metan.iQ')} — Report di calcolo</b>",
        styles["Title"],
    ))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        f"Scenario: {meta.get('scenario_name', '')}  |  "
        f"Generato: {meta.get('generated_at', '')}  |  "
        f"Versione: {meta.get('version', '')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 6*mm))

    # KPI box (con doppia vista LORDO/NETTO + base sostenibilita' esplicita)
    kpi_data = [
        ["KPI", "Valore"],
        ["Totale biomasse (t/anno)", f"{calc.get('tot_biomasse_t', 0.0):,.0f}"],
        ["Sm³ LORDI/anno (base sostenibilita')",
         f"{calc.get('tot_sm3_lordi', 0.0):,.0f}"],
        ["Sm³ NETTI/anno (immesso in rete)",
         f"{calc.get('tot_sm3_netti', 0.0):,.0f}"],
        ["MWh LORDI/anno (base sostenibilita')",
         f"{calc.get('tot_mwh_lordi', 0.0):,.0f}"],
        ["MWh NETTI/anno (immesso in rete)",
         f"{calc.get('tot_mwh', 0.0):,.0f}"],
        ["Saving GHG medio (%) - base LORDA",
         f"{calc.get('saving_avg', 0.0):,.1f}"],
        ["Base sostenibilita'",
         str(calc.get("sustainability_basis", "LORDO"))],
        ["Mesi validi (≥soglia)",    f"{calc.get('valid_months', 0)}/12"],
        ["Ricavi totali (EUR)",      f"{calc.get('total_revenue', 0.0):,.0f}"],
    ]
    t = Table(kpi_data, colWidths=[90*mm, 60*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#F8FAFC"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # Piano mensile
    monthly_rows = output_model.get("monthly_table", [])
    if monthly_rows:
        story.append(Paragraph("<b>Piano mensile</b>", styles["Heading2"]))
        story.append(Spacer(1, 3*mm))
        headers = list(monthly_rows[0].keys())[:8]  # limita colonne
        table_data = [headers]
        for row in monthly_rows:
            table_data.append([str(row.get(h, "")) for h in headers])
        mt = Table(table_data)
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#F8FAFC"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ]))
        story.append(mt)
        story.append(Spacer(1, 6*mm))

    # Metodologia
    ghg_m = expl.get("ghg_method", "")
    if ghg_m:
        story.append(Paragraph("<b>Metodo di calcolo GHG</b>", styles["Heading2"]))
        story.append(Spacer(1, 2*mm))
        for line in ghg_m.split("\n"):
            if line.strip():
                story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 4*mm))

    reg = expl.get("regulatory_basis", "")
    if reg:
        story.append(Paragraph("<b>Base normativa</b>", styles["Heading2"]))
        story.append(Spacer(1, 2*mm))
        for line in reg.split("\n"):
            if line.strip():
                story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 4*mm))

    # Warnings / errors
    if warnings or errors:
        story.append(Paragraph("<b>Note e avvisi</b>", styles["Heading2"]))
        story.append(Spacer(1, 2*mm))
        for w in warnings:
            story.append(Paragraph(f"⚠ {w}", styles["Normal"]))
        for e in errors:
            story.append(Paragraph(f"✗ {e}", styles["Normal"]))

    if error:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            f"<i>Nota tecnica: il generatore PDF avanzato non era disponibile "
            f"({error}). Questo e' il PDF di fallback minimale.</i>",
            styles["Normal"],
        ))

    doc.build(story)
    buf.seek(0)
    return buf
