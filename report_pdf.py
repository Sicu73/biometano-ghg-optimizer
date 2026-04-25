"""Metan.iQ — Generatore report PDF (consulting-grade, palette Navy + Amber).

Punto d'ingresso: build_metaniq_pdf(ctx) -> BytesIO

ctx e' un dict con tutte le variabili necessarie. Vedi `app_mensile.py`
per il payload completo. Nessuna dipendenza da Streamlit (puro reportlab),
testabile in isolamento.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)


# ============================================================
# Design tokens (mirror app_mensile.py palette)
# ============================================================
NAVY      = colors.HexColor("#0F172A")
NAVY_2    = colors.HexColor("#1E293B")
AMBER     = colors.HexColor("#F59E0B")
AMBER_DK  = colors.HexColor("#B45309")
AMBER_BG  = colors.HexColor("#FEF3C7")
SLATE_50  = colors.HexColor("#F8FAFC")
SLATE_100 = colors.HexColor("#F1F5F9")
SLATE_200 = colors.HexColor("#E2E8F0")
SLATE_400 = colors.HexColor("#94A3B8")
SLATE_500 = colors.HexColor("#64748B")
SLATE_600 = colors.HexColor("#475569")
SLATE_700 = colors.HexColor("#334155")
EMERALD   = colors.HexColor("#10B981")
RED       = colors.HexColor("#DC2626")
WHITE     = colors.white

PAGE_W, PAGE_H = A4
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 22 * mm
MARGIN_B = 22 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ============================================================
# Helpers
# ============================================================
def _fmt_it(value, decimals: int = 0, suffix: str = "", signed: bool = False) -> str:
    """Formatta in italiano: 1.234.567,89"""
    if value is None:
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if signed:
        s = f"{f:+,.{decimals}f}"
    else:
        s = f"{f:,.{decimals}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def _styles():
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=base["Normal"],
            fontName="Courier-Bold", fontSize=8,
            textColor=AMBER, leading=10, spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=42,
            textColor=NAVY, leading=46, spaceAfter=8,
        ),
        "h1_white": ParagraphStyle(
            "h1_white", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=44,
            textColor=WHITE, leading=48, spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=15,
            textColor=NAVY, leading=20, spaceAfter=8, spaceBefore=4,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=11,
            textColor=NAVY, leading=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5,
            textColor=SLATE_700, leading=14, spaceAfter=4,
        ),
        "lead": ParagraphStyle(
            "lead", parent=base["Normal"],
            fontName="Helvetica", fontSize=11,
            textColor=SLATE_600, leading=17, spaceAfter=10,
        ),
        "lead_white": ParagraphStyle(
            "lead_white", parent=base["Normal"],
            fontName="Helvetica", fontSize=11,
            textColor=colors.HexColor("#CBD5E1"), leading=17, spaceAfter=10,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            textColor=SLATE_500, leading=11,
        ),
        "muted_white": ParagraphStyle(
            "muted_white", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            textColor=colors.HexColor("#94A3B8"), leading=11,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"],
            fontName="Courier-Bold", fontSize=7,
            textColor=SLATE_500, leading=9,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=20,
            textColor=NAVY, leading=24,
        ),
        "kpi_unit": ParagraphStyle(
            "kpi_unit", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            textColor=SLATE_500, leading=10,
        ),
        "tag_amber": ParagraphStyle(
            "tag_amber", parent=base["Normal"],
            fontName="Courier-Bold", fontSize=7,
            textColor=AMBER_DK, leading=9, alignment=TA_CENTER,
        ),
    }


# ============================================================
# Page templates with header/footer
# ============================================================
def _draw_cover_decoration(canvas, doc):
    """Cover page: full-bleed navy with amber side stripe."""
    canvas.saveState()
    # Full navy background
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Amber side stripe (right edge)
    canvas.setFillColor(AMBER)
    canvas.rect(PAGE_W - 6 * mm, 0, 6 * mm, PAGE_H, fill=1, stroke=0)
    # Subtle geometric mark — hex outline top-right
    canvas.setStrokeColor(colors.HexColor("#1E293B"))
    canvas.setLineWidth(0.6)
    cx, cy, r = PAGE_W - 38 * mm, PAGE_H - 38 * mm, 18 * mm
    import math
    pts = []
    for i in range(6):
        a = math.radians(60 * i - 30)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    p = canvas.beginPath()
    p.moveTo(*pts[0])
    for x, y in pts[1:]:
        p.lineTo(x, y)
    p.close()
    canvas.drawPath(p, stroke=1, fill=0)
    # Inner hex
    r2 = r * 0.55
    pts2 = []
    for i in range(6):
        a = math.radians(60 * i - 30)
        pts2.append((cx + r2 * math.cos(a), cy + r2 * math.sin(a)))
    p2 = canvas.beginPath()
    p2.moveTo(*pts2[0])
    for x, y in pts2[1:]:
        p2.lineTo(x, y)
    p2.close()
    canvas.drawPath(p2, stroke=1, fill=0)
    canvas.restoreState()


def _draw_content_chrome(canvas, doc):
    """Inner pages: subtle header + footer."""
    canvas.saveState()
    # Top bar — thin amber line
    canvas.setStrokeColor(AMBER)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_L, PAGE_H - 12 * mm, PAGE_W - MARGIN_R, PAGE_H - 12 * mm)
    # Header text (left) + page indicator (right)
    canvas.setFont("Courier-Bold", 7)
    canvas.setFillColor(SLATE_500)
    canvas.drawString(MARGIN_L, PAGE_H - 9 * mm,
                      "// METAN.IQ  ·  REPORT DI PIANIFICAZIONE")
    title = doc.metaniq_subtitle or ""
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 9 * mm, title.upper())

    # Footer — thin slate line + page number + date + author
    canvas.setStrokeColor(SLATE_200)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, MARGIN_B - 8 * mm,
                PAGE_W - MARGIN_R, MARGIN_B - 8 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE_500)
    canvas.drawString(MARGIN_L, MARGIN_B - 12 * mm,
                      "Carlo Sicurini · Metan.iQ · "
                      f"{doc.metaniq_date}")
    canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 12 * mm,
                           f"Pagina {doc.page}")
    canvas.restoreState()


# ============================================================
# Section builders
# ============================================================
def _kpi_tile(label: str, value: str, unit: str = "", styles=None,
              accent: colors.Color = AMBER) -> Table:
    """Card KPI: top stripe color + label uppercase + value bold + unit muted."""
    s = styles or _styles()
    tbl = Table(
        [
            [Paragraph(label.upper(), s["kpi_label"])],
            [Paragraph(value, s["kpi_value"])],
            [Paragraph(unit, s["kpi_unit"])],
        ],
        colWidths=[CONTENT_W / 4 - 4 * mm],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("LINEABOVE", (0, 0), (-1, 0), 2, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 10),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 2),
        ("TOPPADDING", (0, 2), (0, 2), 0),
        ("BOTTOMPADDING", (0, 2), (0, 2), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _build_cover(ctx, styles):
    """Cover page: hero navy + amber stripe."""
    s = styles
    flow = []
    flow.append(Spacer(1, 60 * mm))
    flow.append(Paragraph(
        "// METAN.IQ DECISION INTELLIGENCE", s["eyebrow"]))
    flow.append(Paragraph(
        "Metan<font color='#F59E0B'>.</font>iQ", s["h1_white"]))
    flow.append(Spacer(1, 4 * mm))
    flow.append(Paragraph(
        "Report di pianificazione mensile<br/>e business case",
        ParagraphStyle("h_sub", fontName="Helvetica", fontSize=20,
                       textColor=colors.HexColor("#CBD5E1"), leading=26),
    ))
    flow.append(Spacer(1, 18 * mm))

    # Info table
    mode_label = ("Biogas — Cogenerazione (CHP)"
                  if ctx["IS_CHP"] else "Biometano — Upgrading e immissione")
    info_rows = [
        ["Modalità", mode_label],
        ["Periodo analizzato", "12 mesi · pianificazione annuale"],
        ["Soglia GHG saving",
         f"{_fmt_it(ctx['ghg_threshold']*100, 0, '%')}  "
         f"(comparator {_fmt_it(ctx['fossil_comparator'], 0)} gCO₂/MJ)"],
        ["Generato il", ctx["report_date_full"]],
    ]
    info_tbl = Table(info_rows, colWidths=[42 * mm, CONTENT_W - 42 * mm])
    info_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Courier-Bold"),
        ("FONTSIZE", (0, 0), (0, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), AMBER),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (1, 0), (1, -1), 11),
        ("TEXTCOLOR", (1, 0), (1, -1), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4,
         colors.HexColor("#1E293B")),
    ]))
    flow.append(info_tbl)
    flow.append(Spacer(1, 35 * mm))

    flow.append(Paragraph(
        "Ideato e sviluppato da",
        ParagraphStyle("c_lbl", fontName="Helvetica", fontSize=8,
                       textColor=colors.HexColor("#94A3B8"), leading=10),
    ))
    flow.append(Paragraph(
        "<b>Carlo Sicurini</b>",
        ParagraphStyle("c_name", fontName="Helvetica-Bold", fontSize=14,
                       textColor=WHITE, leading=18, spaceAfter=2),
    ))
    flow.append(Paragraph(
        "Consulenza tecnica · Biometano · Biogas · Sostenibilità",
        ParagraphStyle("c_role", fontName="Helvetica", fontSize=8,
                       textColor=colors.HexColor("#CBD5E1"), leading=11),
    ))
    return flow


def _build_executive_summary(ctx, styles):
    s = styles
    flow = []
    flow.append(Paragraph("// EXECUTIVE SUMMARY", s["eyebrow"]))
    flow.append(Paragraph("Sintesi annuale", s["h2"]))
    flow.append(Spacer(1, 4 * mm))

    # 4 KPI in row
    if ctx["IS_CHP"]:
        kpi1 = _kpi_tile("Biomasse",
                         _fmt_it(ctx["tot_biomasse_t"], 0),
                         "t/anno (FM)", styles=s)
        kpi2 = _kpi_tile("Energia el. netta rete",
                         _fmt_it(ctx["tot_mwh_el_netto"], 0),
                         "MWh/anno", styles=s)
        kpi3 = _kpi_tile("Saving GHG medio",
                         _fmt_it(ctx["saving_avg"], 1, "%"),
                         f"≥ {_fmt_it(ctx['ghg_threshold']*100, 0, '%')} RED III",
                         styles=s,
                         accent=EMERALD if ctx["saving_avg"] >= ctx["ghg_threshold"]*100 else RED)
        kpi4 = _kpi_tile("Ricavi elettrici",
                         _fmt_it(ctx["tot_revenue"]/1000, 0),
                         "k€/anno", styles=s)
    else:
        kpi1 = _kpi_tile("Biomasse",
                         _fmt_it(ctx["tot_biomasse_t"], 0),
                         "t/anno (FM)", styles=s)
        kpi2 = _kpi_tile("Biometano netto",
                         _fmt_it(ctx["tot_sm3_netti"]/1000, 0),
                         "k Sm³/anno · "
                         f"{_fmt_it(ctx['tot_mwh_netti'], 0)} MWh",
                         styles=s)
        kpi3 = _kpi_tile("Saving GHG medio",
                         _fmt_it(ctx["saving_avg"], 1, "%"),
                         f"≥ {_fmt_it(ctx['ghg_threshold']*100, 0, '%')} RED III",
                         styles=s,
                         accent=EMERALD if ctx["saving_avg"] >= ctx["ghg_threshold"]*100 else RED)
        kpi4 = _kpi_tile("Ricavi",
                         _fmt_it(ctx["tot_revenue"]/1000, 0),
                         "k€/anno", styles=s)
    kpi_row = Table(
        [[kpi1, kpi2, kpi3, kpi4]],
        colWidths=[CONTENT_W / 4] * 4,
    )
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(kpi_row)
    flow.append(Spacer(1, 8 * mm))

    # Highlights box
    valid_months = ctx["valid_months"]
    saving_pass = ctx["saving_avg"] >= ctx["ghg_threshold"] * 100
    bullets = []
    bullets.append(
        f"• Validità mensile: <b>{valid_months}/12 mesi</b> "
        f"({'tutti conformi' if valid_months == 12 else 'verificare i mesi non conformi'}) "
        f"rispetto alle due condizioni RED III: saving GHG ≥ "
        f"{_fmt_it(ctx['ghg_threshold']*100, 0, '%')} e produzione ≤ tetto autorizzativo."
    )
    bullets.append(
        f"• Saving GHG medio annuale <b>{_fmt_it(ctx['saving_avg'], 1, '%')}</b> "
        f"contro soglia RED III {_fmt_it(ctx['ghg_threshold']*100, 0, '%')} → "
        f"<font color='{'#10B981' if saving_pass else '#DC2626'}'>"
        f"<b>{'CONFORME' if saving_pass else 'NON CONFORME'}</b></font>."
    )
    if ctx["IS_CHP"]:
        bullets.append(
            f"• Bilancio elettrico CHP: lordo motore "
            f"<b>{_fmt_it(ctx['plant_kwe'], 0)} kW</b> meno "
            f"{_fmt_it(ctx['aux_el_pct']*100, 1, '%')} ausiliari = "
            f"<b>{_fmt_it(ctx['plant_kwe_net'], 0)} kW netti</b> immessi in rete. "
            f"Tariffa media ponderata "
            f"<b>{_fmt_it(ctx['tariffa_media_ponderata'], 2, ' €/MWh_el')}</b>."
        )
    else:
        bullets.append(
            f"• Taglia netta autorizzata: <b>{_fmt_it(ctx['plant_net_smch'], 0)} "
            f"Sm³/h</b> · fattore aux <b>{_fmt_it(ctx['aux_factor'], 2)}</b> · "
            f"tariffa media ponderata "
            f"<b>{_fmt_it(ctx['tariffa_media_ponderata'], 2, ' €/MWh')}</b>."
        )
    bullets.append(
        f"• Configurazione impiantistica: ep totale "
        f"<b>{_fmt_it(ctx['ep_total'], 1, ' gCO₂/MJ', signed=True)}</b> · "
        f"destinazione <b>{ctx['end_use']}</b>."
    )

    box_rows = [[Paragraph("KEY HIGHLIGHTS", s["kpi_label"])]]
    for b in bullets:
        box_rows.append([Paragraph(b, s["body"])])
    hl = Table(box_rows, colWidths=[CONTENT_W])
    hl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("LINEBEFORE", (0, 0), (0, -1), 2, AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(hl)
    return flow


def _build_plant_config(ctx, styles):
    s = styles
    flow = []
    flow.append(Paragraph("// PLANT CONFIGURATION", s["eyebrow"]))
    flow.append(Paragraph("Parametri impianto", s["h2"]))
    flow.append(Spacer(1, 3 * mm))

    rows = [
        ["Parametro", "Valore", "Note"],
    ]
    if ctx["IS_CHP"]:
        rows.extend([
            ["Tipologia",
             "Biogas → Cogenerazione (CHP)",
             "Biogas grezzo al motore, no upgrading"],
            ["Potenza elettrica LORDA",
             f"{_fmt_it(ctx['plant_kwe'], 0)} kW_el",
             "Targa motore (morsetti alternatore)"],
            ["Autoconsumo ausiliari",
             f"{_fmt_it(ctx['aux_el_pct']*100, 1, '%')}",
             "Pompe, agitatori, desolforatore, PLC"],
            ["Potenza NETTA in rete",
             f"{_fmt_it(ctx['plant_kwe_net'], 0)} kW_el",
             "Lordo × (1 − aux%) — base ricavi"],
            ["Rendimento elettrico η_el",
             f"{_fmt_it(ctx['eta_el']*100, 1, '%')}", ""],
            ["Rendimento termico η_th",
             f"{_fmt_it(ctx['eta_th']*100, 1, '%')}",
             "Recupero fumi + acqua motore"],
            ["CH₄ al motore",
             f"{_fmt_it(ctx['plant_net_smch'], 1)} Sm³/h",
             "= kW_el lordi / (η_el × 9,97)"],
        ])
    else:
        rows.extend([
            ["Tipologia",
             "Biometano (upgrading + immissione rete)",
             ""],
            ["Taglia netta autorizzata",
             f"{_fmt_it(ctx['plant_net_smch'], 0)} Sm³/h",
             "Tetto autorizzativo immissione"],
            ["Tecnologia upgrading",
             ctx.get("upgrading_opt") or "—", ""],
            ["Combustione off-gas",
             ctx.get("offgas_opt") or "—", ""],
            ["Iniezione in rete",
             ctx.get("injection_opt") or "—", ""],
        ])
    rows.extend([
        ["Aux factor (netto→lordo)",
         _fmt_it(ctx["aux_factor"], 3),
         "Bilancio energetico impianto"],
        ["Configurazione ep",
         _fmt_it(ctx["ep_total"], 1, " gCO₂/MJ", signed=True),
         "Processing emissions (RED III All. V)"],
        ["Destinazione finale",
         ctx["end_use"],
         f"Soglia saving "
         f"{_fmt_it(ctx['ghg_threshold']*100, 0, '%')} · "
         f"comparator {_fmt_it(ctx['fossil_comparator'], 0)} gCO₂/MJ"],
    ])
    cfg_tbl = Table(rows, colWidths=[60 * mm, 50 * mm, CONTENT_W - 110 * mm])
    cfg_tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        # Body
        ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 1), (2, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (0, -1), SLATE_700),
        ("TEXTCOLOR", (1, 1), (1, -1), NAVY),
        ("TEXTCOLOR", (2, 1), (2, -1), SLATE_500),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        # Zebra
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ("LINEABOVE", (0, 1), (-1, -1), 0.3, SLATE_200),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
    ]))
    flow.append(cfg_tbl)
    return flow


def _build_monthly_table(ctx, styles):
    s = styles
    flow = []
    flow.append(Paragraph("// MONTHLY PLAN", s["eyebrow"]))
    flow.append(Paragraph("Pianificazione mensile", s["h2"]))
    flow.append(Spacer(1, 3 * mm))

    df = ctx["df_res"]
    if ctx["IS_CHP"]:
        cols = ["Mese", "Ore", "Totale biomasse (t)",
                "Sm³ netti", "MWh elettrici netti", "Saving %", "Validità"]
        headers = ["Mese", "Ore", "Biomasse (t)", "CH₄ motore (Sm³)",
                   "MWh_el netti", "Saving %", "Validità"]
    else:
        cols = ["Mese", "Ore", "Totale biomasse (t)",
                "Sm³ netti", "MWh netti", "Saving %", "Validità"]
        headers = ["Mese", "Ore", "Biomasse (t)", "Sm³ netti",
                   "MWh netti", "Saving %", "Validità"]

    data = [headers]
    for _, r in df.iterrows():
        row = [
            str(r["Mese"]),
            _fmt_it(r["Ore"], 0),
            _fmt_it(r["Totale biomasse (t)"], 0),
            _fmt_it(r["Sm³ netti"], 0),
            _fmt_it(r[cols[4]], 1),
            _fmt_it(r["Saving %"], 1, "%"),
            "OK" if str(r["Validità"]).startswith("✅") else "KO",
        ]
        data.append(row)

    # Totals row
    totals = [
        "TOTALE/MEDIA",
        _fmt_it(df["Ore"].sum(), 0),
        _fmt_it(df["Totale biomasse (t)"].sum(), 0),
        _fmt_it(df["Sm³ netti"].sum(), 0),
        _fmt_it(df[cols[4]].sum(), 1),
        _fmt_it(df["Saving %"].mean(), 1, "%"),
        f"{ctx['valid_months']}/12",
    ]
    data.append(totals)

    col_w = [22*mm, 14*mm, 24*mm, 28*mm, 28*mm, 22*mm, 16*mm]
    # Adjust to content width
    scale = CONTENT_W / sum(col_w)
    col_w = [w * scale for w in col_w]
    monthly_tbl = Table(data, colWidths=col_w, repeatRows=1)
    monthly_tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (1, 0), (-1, 0), "RIGHT"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        # Body numbers right-aligned
        ("FONTNAME", (0, 1), (0, -2), "Helvetica"),
        ("FONTNAME", (1, 1), (-2, -2), "Helvetica"),
        ("FONTNAME", (-1, 1), (-1, -2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -2), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -2), SLATE_700),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -2), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 5),
        # Zebra
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SLATE_50]),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, SLATE_200),
        # Totals row
        ("BACKGROUND", (0, -1), (-1, -1), SLATE_100),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 9),
        ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
        ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
        ("TOPPADDING", (0, -1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        # Validità coloring
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
    ]))
    flow.append(monthly_tbl)
    return flow


def _build_revenue(ctx, styles):
    s = styles
    flow = []
    flow.append(Paragraph("// REVENUE & MIX", s["eyebrow"]))
    flow.append(Paragraph("Mix biomasse e analisi ricavi", s["h2"]))
    flow.append(Spacer(1, 3 * mm))

    tar_unit = "€/MWh_el" if ctx["IS_CHP"] else "€/MWh"
    headers = ["Biomassa", "t/anno", "Resa", "MWh netti",
               f"Tariffa ({tar_unit})", "Ricavi €/anno", "Quota %"]
    data = [headers]
    for n, r in ctx["revenue_rows"]:
        data.append([
            n,
            _fmt_it(r["t_anno"], 0),
            _fmt_it(r["yield"], 0),
            _fmt_it(r["mwh_basis"], 1),
            _fmt_it(r["tariffa"], 2),
            _fmt_it(r["ricavi"], 0, " €"),
            _fmt_it(r["quota"], 1, "%"),
        ])
    # Totals
    data.append([
        "TOTALE",
        _fmt_it(ctx["tot_biomasse_t"], 0),
        "—",
        _fmt_it(ctx["tot_mwh_basis"], 0),
        _fmt_it(ctx["tariffa_media_ponderata"], 2),
        _fmt_it(ctx["tot_revenue"], 0, " €"),
        "100,0%",
    ])

    col_w_rel = [40, 18, 14, 20, 22, 28, 14]
    total_rel = sum(col_w_rel)
    col_w = [w / total_rel * CONTENT_W for w in col_w_rel]
    rev_tbl = Table(data, colWidths=col_w, repeatRows=1)
    rev_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (1, 0), (-1, 0), "RIGHT"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (0, -2), "Helvetica"),
        ("FONTNAME", (1, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -2), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -2), SLATE_700),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -2), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SLATE_50]),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, SLATE_200),
        ("BACKGROUND", (0, -1), (-1, -1), AMBER_BG),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 9),
        ("TEXTCOLOR", (0, -1), (-1, -1), AMBER_DK),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, AMBER),
        ("TOPPADDING", (0, -1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
    ]))
    flow.append(rev_tbl)
    flow.append(Spacer(1, 8 * mm))

    # Revenue summary card
    if ctx["IS_CHP"]:
        rev_caption = (
            f"<b>Calcolo CHP</b> · MWh_el lordi = MWh_CH₄ × η_el "
            f"({_fmt_it(ctx['eta_el']*100, 0, '%')}) · "
            f"MWh_el netti rete = lordi × (1 − aux%) "
            f"({_fmt_it(ctx['aux_el_pct']*100, 1, '%')}) · "
            f"Ricavi = MWh_el netti rete × tariffa €/MWh_el. "
            f"I ricavi termici da recupero calore "
            f"({_fmt_it(ctx['eta_th']*100, 0, '%')}) non sono inclusi."
        )
    else:
        rev_caption = (
            f"<b>Calcolo</b> · MWh netti = t × resa Nm³/t ÷ "
            f"{_fmt_it(ctx['aux_factor'], 2)} × 0,00997 · "
            f"Ricavi = MWh netti × tariffa €/MWh. Tariffe modificabili "
            f"in app per scenari PPA / FER-X / mercato spot."
        )
    flow.append(Paragraph(rev_caption, s["muted"]))
    return flow


def _build_methodology(ctx, styles):
    s = styles
    flow = []
    flow.append(Paragraph("// METHODOLOGY & DISCLAIMER", s["eyebrow"]))
    flow.append(Paragraph("Riferimenti normativi e metodologia",
                           s["h2"]))
    flow.append(Spacer(1, 3 * mm))

    items = [
        ("RED III · Direttiva (UE) 2023/2413",
         "Annex V (biocarburanti/biometano) e Annex VI (biomassa per "
         "elettricità/calore). Soglie saving GHG: 80% biometano nuovi "
         "≥ 20/11/2023, 65% biocarburanti trasporti, 80% elettricità "
         "CHP. Comparator fossile: 80 gCO₂/MJ (rete/calore), 94 "
         "(trasporti), 183 (elettricità EU mix)."),
        ("D.Lgs. 5 marzo 2026 (recepimento RED III)",
         "Disposizioni nazionali sui criteri di sostenibilità per "
         "biomasse, biogas e biometano. Schemi di certificazione GSE."),
        ("GSE Linee Guida 2024 — Biometano",
         "Riconoscimento crediti gestione liquami (manure credit "
         "−45 gCO₂/MJ in eec). Stoccaggio digestato chiuso con "
         "recupero gas = 0 gCO₂/MJ."),
        ("UNI/TS 11567:2024",
         "Resa specifica biogas/biometano per categoria di matrice. "
         "Database alimentato anche da JEC WTT v5 e parametri "
         "operativi Consorzio Italiano Biogas."),
        ("DM 6 luglio 2012 (per biogas CHP)",
         "Tariffa Omnicomprensiva biogas agricolo ≤ 1 MW. "
         "Premio CAR (PES > 10%) e premio matrice sottoprodotti "
         "applicati alla TO base."),
    ]
    rows = []
    for title, body in items:
        rows.append([
            Paragraph(f"<b>{title}</b>", s["body"]),
            Paragraph(body, s["body"]),
        ])
    meth_tbl = Table(rows, colWidths=[60 * mm, CONTENT_W - 60 * mm])
    meth_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, SLATE_200),
    ]))
    flow.append(meth_tbl)

    flow.append(Spacer(1, 6 * mm))
    flow.append(Paragraph("Disclaimer", s["h3"]))
    flow.append(Paragraph(
        "Il presente documento è generato automaticamente dalla piattaforma "
        "Metan.iQ a partire dai parametri impiantistici e dai dati di "
        "produzione mensile inseriti dall'utente. I risultati hanno valore "
        "<b>indicativo a supporto delle decisioni di pianificazione e "
        "business case</b>. La certificazione di sostenibilità ai sensi "
        "del RED III e l'accesso agli incentivi richiedono la validazione "
        "tramite organismi accreditati e l'utilizzo di parametri "
        "specifici dell'impianto reale (in luogo dei valori di "
        "letteratura usati come default).",
        s["body"],
    ))
    flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph(
        f"Generato il {ctx['report_date_full']} · "
        f"Carlo Sicurini · Metan.iQ · © 2026",
        s["muted"],
    ))
    return flow


# ============================================================
# Public API
# ============================================================
def build_metaniq_pdf(ctx: dict) -> BytesIO:
    """Costruisce il PDF Metan.iQ.

    ctx richiesto: vedi `app_mensile.py` per la lista completa dei campi.
    """
    buf = BytesIO()

    now = datetime.now()
    months_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio",
                 "giugno", "luglio", "agosto", "settembre", "ottobre",
                 "novembre", "dicembre"]
    ctx.setdefault(
        "report_date_full",
        f"{now.day} {months_it[now.month - 1]} {now.year}, "
        f"ore {now.hour:02d}:{now.minute:02d}",
    )
    ctx.setdefault("report_date_short", now.strftime("%d/%m/%Y"))

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title=f"Metan.iQ — Report {ctx['report_date_short']}",
        author="Carlo Sicurini",
        subject="Report di pianificazione Metan.iQ",
    )
    # Metadata accessible by canvas callbacks
    doc.metaniq_subtitle = ("Biogas — CHP" if ctx["IS_CHP"]
                            else "Biometano — Upgrading")
    doc.metaniq_date = ctx["report_date_short"]

    cover_frame = Frame(0, 0, PAGE_W, PAGE_H,
                        leftPadding=MARGIN_L, rightPadding=MARGIN_R + 6 * mm,
                        topPadding=MARGIN_T, bottomPadding=MARGIN_B,
                        showBoundary=0)
    content_frame = Frame(MARGIN_L, MARGIN_B,
                          CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
                          leftPadding=0, rightPadding=0,
                          topPadding=0, bottomPadding=0,
                          showBoundary=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame],
                     onPage=_draw_cover_decoration),
        PageTemplate(id="content", frames=[content_frame],
                     onPage=_draw_content_chrome),
    ])

    s = _styles()
    flow = []
    # Cover
    flow.extend(_build_cover(ctx, s))
    flow.append(NextPageTemplate("content"))
    flow.append(PageBreak())
    # Executive
    flow.extend(_build_executive_summary(ctx, s))
    flow.append(Spacer(1, 8 * mm))
    flow.extend(_build_plant_config(ctx, s))
    flow.append(PageBreak())
    # Monthly
    flow.extend(_build_monthly_table(ctx, s))
    flow.append(PageBreak())
    # Revenue
    flow.extend(_build_revenue(ctx, s))
    flow.append(PageBreak())
    # Methodology
    flow.extend(_build_methodology(ctx, s))

    doc.build(flow)
    buf.seek(0)
    return buf
