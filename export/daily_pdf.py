# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""export/daily_pdf.py — Report PDF mensile Metan.iQ (multi-pagina, brand).

Layout:
  Pagina 1 (Cover)      : banner brand, periodo, esito ufficiale, 4 KPI cards
  Pagina 2 (Riepilogo)  : KPI completi, vincoli normativi, indicazioni operative
  Pagina 3+ (Daily)     : tabella giornaliera con conditional formatting
  Ultima pagina         : audit & anagrafica simulazione

Stile: brand Metan.iQ — Navy #1E3A5F, Amber #F59E0B, Success #059669,
Danger #DC2626. Header/footer su tutte le pagine con page numbering.
Font Helvetica (built-in ReportLab) per massima portabilità.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd


# ============================================================================
# BRAND PALETTE
# ============================================================================
_NAVY = "#1E3A5F"
_NAVY_DARK = "#0F1F33"
_AMBER = "#F59E0B"
_AMBER_DARK = "#D97706"
_GREEN = "#059669"
_RED = "#DC2626"
_GREY_TXT = "#475569"
_GREY_LIGHT = "#E2E8F0"
_TINT = "#F1F5F9"
_WHITE = "#FFFFFF"


def _try_reportlab():
    try:
        from reportlab.lib import colors  # noqa: F401
        return True
    except Exception:
        return False


# ============================================================================
# I18N dict — label PDF (IT default, EN se lang='en')
# ============================================================================
_LBL = {
    "it": {
        "report_tag": "// REPORT MENSILE DI SOSTENIBILITÀ",
        "tagline": "Pianificazione mensile e ottimizzazione GHG biometano",
        "periodo": "Periodo",
        "azienda": "Azienda",
        "regime": "Regime",
        "soglia_saving": "Soglia saving GHG",
        "esito_ufficiale": "ESITO UFFICIALE",
        "sostenibile": "SOSTENIBILE",
        "non_conforme": "NON CONFORME",
        "saving_mensile": "Saving GHG mensile",
        "soglia": "Soglia",
        "margine": "Margine",
        "punti_pct": "punti percentuali",
        "biomasse": "Biomasse",
        "sm3_netti": "Sm³ netti",
        "mwh_netti": "MWh netti",
        "saving_ghg": "Saving GHG",
        "riepilogo": "Riepilogo KPI mensili",
        "kpi": "KPI",
        "valore": "Valore",
        "unita": "Unità",
        "anno": "Anno",
        "mese": "Mese",
        "saving_pct": "Saving GHG",
        "soglia_norm": "Soglia normativa",
        "margine_v": "Margine",
        "esito": "Esito conformità",
        "vb_remi": "Vb REMI totale",
        "e_remi": "E REMI totale",
        "portata_media": "Portata media",
        "potenza_media": "Potenza media",
        "pci_medio": "PCI medio",
        "vincoli": "Vincoli normativi",
        "vincolo": "Vincolo",
        "limite": "Limite",
        "note": "Note",
        "indicazioni": "Indicazioni operative",
        "tabella_daily": "Tabella giornaliera — dettaglio per giorno",
        "tabella_intro": ("Verifica di sostenibilità: il controllo ufficiale è MENSILE. "
                         "I valori giornalieri di Saving GHG sono indicativi e non vincolanti."),
        "anagrafica": "Anagrafica simulazione & Audit Trail",
        "anagrafica_intro": ("Tracciabilità dei parametri usati per il calcolo di "
                            "sostenibilità (impianto, regime, soglie, override BMT/EF, "
                            "fattori emissivi)."),
        "voce": "Voce",
        "header_report": "REPORT GESTIONE GIORNALIERA",
        "generato_il": "Generato il",
        "report_generato": "Report generato il",
        "footer": "© Metan.iQ — Decision Intelligence Platform per biometano DM 2022 / RED III",
        "footer_cover": "© Metan.iQ · Decision Intelligence Platform · DM 2022 / RED III",
        "pagina": "Pagina",
    },
    "en": {
        "report_tag": "// MONTHLY SUSTAINABILITY REPORT",
        "tagline": "Monthly planning and GHG optimization for biomethane",
        "periodo": "Period",
        "azienda": "Company",
        "regime": "Regime",
        "soglia_saving": "GHG saving threshold",
        "esito_ufficiale": "OFFICIAL OUTCOME",
        "sostenibile": "COMPLIANT",
        "non_conforme": "NON-COMPLIANT",
        "saving_mensile": "Monthly GHG saving",
        "soglia": "Threshold",
        "margine": "Margin",
        "punti_pct": "percentage points",
        "biomasse": "Feedstocks",
        "sm3_netti": "Net Sm³",
        "mwh_netti": "Net MWh",
        "saving_ghg": "GHG Saving",
        "riepilogo": "Monthly KPI Summary",
        "kpi": "KPI",
        "valore": "Value",
        "unita": "Unit",
        "anno": "Year",
        "mese": "Month",
        "saving_pct": "GHG Saving",
        "soglia_norm": "Regulatory threshold",
        "margine_v": "Margin",
        "esito": "Compliance outcome",
        "vb_remi": "Total REMI Vb",
        "e_remi": "Total REMI E",
        "portata_media": "Average flow",
        "potenza_media": "Average power",
        "pci_medio": "Average LHV",
        "vincoli": "Regulatory constraints",
        "vincolo": "Constraint",
        "limite": "Limit",
        "note": "Notes",
        "indicazioni": "Operating recommendations",
        "tabella_daily": "Daily table — detail per day",
        "tabella_intro": ("Sustainability check: official verification is MONTHLY. "
                         "Daily GHG Saving values are indicative and not binding."),
        "anagrafica": "Simulation registry & Audit Trail",
        "anagrafica_intro": ("Traceability of parameters used for the sustainability "
                            "calculation (plant, regime, thresholds, BMT/EF overrides, "
                            "emission factors)."),
        "voce": "Item",
        "header_report": "DAILY MANAGEMENT REPORT",
        "generato_il": "Generated on",
        "report_generato": "Report generated on",
        "footer": "© Metan.iQ — Decision Intelligence Platform for biomethane DM 2022 / RED III",
        "footer_cover": "© Metan.iQ · Decision Intelligence Platform · DM 2022 / RED III",
        "pagina": "Page",
    },
}


def _fmt_num(value: float, decimals: int = 2, lang: str = "it") -> str:
    """Formatta numero locale-aware (IT 1.234,56 / EN 1,234.56)."""
    try:
        s = f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)
    if lang == "en":
        return s
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(d, lang: str = "it") -> str:
    """Formatta data locale-aware (IT dd/mm/yyyy / EN Mon dd, yyyy)."""
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = pd.to_datetime(d, errors="coerce")
            if pd.isna(d):
                return ""
        except Exception:
            return ""
    try:
        if lang == "en":
            return d.strftime("%b %d, %Y")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


# Alias backcompat (vecchio uso decimals-only IT).
def _it_num(value: float, decimals: int = 2) -> str:
    return _fmt_num(value, decimals, "it")


def build_daily_pdf(
    daily_df: pd.DataFrame,
    monthly_kpis: dict[str, Any],
    audit_trail: dict[str, Any] | None = None,
    guidance: list[str] | None = None,
    title: str | None = None,
    lang: str | None = None,
) -> bytes:
    """Crea report PDF mensile Metan.iQ multi-pagina con styling brand."""
    # Lang detection: parametro -> session_state -> default 'it'
    if lang is None:
        try:
            from i18n_runtime import get_lang as _gl
            lang = _gl()
        except Exception:
            lang = "it"
    if lang not in _LBL:
        lang = "it"
    L = _LBL[lang]
    if title is None:
        title = ("Daily Management — Monthly Sustainability"
                 if lang == "en" else "Gestione Giornaliera — Sostenibilità Mensile")

    def num(v, dec=2):
        return _fmt_num(v, dec, lang)
    def date_fmt(d):
        return _fmt_date(d, lang)

    if not _try_reportlab():
        # Fallback testuale
        txt = io.StringIO()
        txt.write(f"{title}\n" + "=" * len(title) + "\n\n")
        for k, v in (monthly_kpis or {}).items():
            txt.write(f"{k}: {v}\n")
        return txt.getvalue().encode("utf-8")

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
        TableStyle, PageBreak, KeepTogether,
    )
    from reportlab.platypus.flowables import HRFlowable

    audit_trail = audit_trail or {}
    guidance = guidance or []

    PAGE_W, PAGE_H = landscape(A4)

    # =========================================================================
    # STILI PARAGRAFI
    # =========================================================================
    s_title_h = ParagraphStyle(
        "TitleH", fontName="Helvetica-Bold", fontSize=28, leading=32,
        textColor=colors.HexColor(_WHITE), alignment=0,
    )
    s_subtitle = ParagraphStyle(
        "SubT", fontName="Helvetica", fontSize=11, leading=14,
        textColor=colors.HexColor(_GREY_LIGHT), alignment=0,
    )
    s_h2 = ParagraphStyle(
        "H2", fontName="Helvetica-Bold", fontSize=13, leading=16,
        textColor=colors.HexColor(_NAVY_DARK), spaceAfter=8, spaceBefore=12,
    )
    s_h3 = ParagraphStyle(
        "H3", fontName="Helvetica-Bold", fontSize=10, leading=13,
        textColor=colors.HexColor(_AMBER_DARK), spaceAfter=6, spaceBefore=10,
    )
    s_body = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=9, leading=12,
        textColor=colors.HexColor(_NAVY_DARK), alignment=0,
    )
    s_caption = ParagraphStyle(
        "Caption", fontName="Helvetica-Oblique", fontSize=8, leading=11,
        textColor=colors.HexColor(_GREY_TXT),
    )
    s_kpi_label = ParagraphStyle(
        "KpiLbl", fontName="Helvetica-Bold", fontSize=8, leading=10,
        textColor=colors.HexColor(_GREY_TXT), alignment=1,
    )
    s_kpi_value = ParagraphStyle(
        "KpiVal", fontName="Helvetica-Bold", fontSize=20, leading=24,
        textColor=colors.HexColor(_NAVY_DARK), alignment=1,
    )

    # =========================================================================
    # HEADER / FOOTER per pagine 2+
    # =========================================================================
    # XSS hardening: input utente sanitizzato. ReportLab Paragraph interpreta
    # tag XML/HTML (<b>, <font>, ...): valori non escape potrebbero rompere
    # il rendering o iniettare stile.
    import html as _html
    _plant_name = _html.escape(str(audit_trail.get("Nome impianto") or "—"))
    _company = _html.escape(str(audit_trail.get("Nome azienda") or "—"))
    _regime = str(monthly_kpis.get("regime") or audit_trail.get("Regime applicato") or "DM 2022")
    _gen_at = datetime.now().strftime("%d/%m/%Y %H:%M") if lang != "en" else datetime.now().strftime("%b %d, %Y %H:%M")

    def _draw_page_chrome(canvas, doc):
        """Header + footer brand su tutte le pagine eccetto la cover."""
        canvas.saveState()
        # Header bar
        canvas.setFillColor(colors.HexColor(_NAVY))
        canvas.rect(0, PAGE_H - 16 * mm, PAGE_W, 16 * mm, fill=1, stroke=0)
        # Amber accent strip
        canvas.setFillColor(colors.HexColor(_AMBER))
        canvas.rect(0, PAGE_H - 17.5 * mm, PAGE_W, 1.5 * mm, fill=1, stroke=0)
        # Brand logo text
        canvas.setFillColor(colors.HexColor(_WHITE))
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(15 * mm, PAGE_H - 10 * mm, "Metan.iQ")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor(_GREY_LIGHT))
        canvas.drawString(15 * mm, PAGE_H - 13.5 * mm,
                          f"{_company} · {_plant_name} · Regime: {_regime}")
        # Right side: title
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor(_AMBER))
        canvas.drawRightString(PAGE_W - 15 * mm, PAGE_H - 10 * mm,
                                L["header_report"])
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor(_GREY_LIGHT))
        canvas.drawRightString(PAGE_W - 15 * mm, PAGE_H - 13.5 * mm,
                                f"{L['generato_il']} {_gen_at}")

        # Footer
        canvas.setStrokeColor(colors.HexColor(_GREY_LIGHT))
        canvas.setLineWidth(0.4)
        canvas.line(15 * mm, 12 * mm, PAGE_W - 15 * mm, 12 * mm)
        canvas.setFillColor(colors.HexColor(_GREY_TXT))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 8 * mm, L["footer"])
        canvas.drawRightString(PAGE_W - 15 * mm, 8 * mm,
                                f"{L['pagina']} {canvas.getPageNumber()}")
        canvas.restoreState()

    def _draw_cover(canvas, doc):
        """Cover full-bleed brand."""
        canvas.saveState()
        # Sfondo gradient simulato (navy → navy dark) — riempimento full
        canvas.setFillColor(colors.HexColor(_NAVY_DARK))
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # Banda obliqua amber accent
        canvas.setFillColor(colors.HexColor(_AMBER))
        canvas.rect(0, PAGE_H - 6 * mm, PAGE_W, 6 * mm, fill=1, stroke=0)
        canvas.rect(0, 0, PAGE_W, 4 * mm, fill=1, stroke=0)
        # Footer cover
        canvas.setFillColor(colors.HexColor(_GREY_LIGHT))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(20 * mm, 10 * mm, L["footer_cover"])
        canvas.drawRightString(PAGE_W - 20 * mm, 10 * mm,
                                f"{L['report_generato']} {_gen_at}")
        canvas.restoreState()

    # =========================================================================
    # SETUP DOC con due page template (cover + standard)
    # =========================================================================
    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=24 * mm, bottomMargin=16 * mm,
    )
    frame_cover = Frame(
        20 * mm, 12 * mm, PAGE_W - 40 * mm, PAGE_H - 18 * mm,
        showBoundary=0,
    )
    frame_std = Frame(
        15 * mm, 14 * mm, PAGE_W - 30 * mm, PAGE_H - 36 * mm,
        showBoundary=0,
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame_cover], onPage=_draw_cover),
        PageTemplate(id="std", frames=[frame_std], onPage=_draw_page_chrome),
    ])

    story = []

    # =========================================================================
    # PAGINA 1 — COVER
    # =========================================================================
    _year = audit_trail.get("Anno") or monthly_kpis.get("year") or ""
    _month = audit_trail.get("Mese") or monthly_kpis.get("month") or ""
    _periodo = (f"{int(_month):02d} / {int(_year)}"
                if _year and _month else "—")
    _compliant = bool(monthly_kpis.get("compliant", False))
    _saving = float(monthly_kpis.get("saving_pct", 0.0))
    _thr = float(monthly_kpis.get("threshold", 0.0))

    # Spacer per centratura verticale
    story.append(Spacer(1, 25 * mm))

    # Tag "REPORT MENSILE"
    _tag = Table(
        [[Paragraph(L["report_tag"], ParagraphStyle(
            "TagS", fontName="Helvetica-Bold", fontSize=9, leading=11,
            textColor=colors.HexColor(_AMBER)))]],
        colWidths=[None], hAlign="LEFT",
    )
    _tag.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E3A5F")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(_tag)
    story.append(Spacer(1, 12))

    # Title "Metan.iQ"
    story.append(Paragraph(
        '<font size="48"><b>Metan<font color="#F59E0B">.</font>iQ</b></font>',
        ParagraphStyle("CoverT", fontName="Helvetica-Bold", fontSize=48,
                        leading=54, textColor=colors.HexColor(_WHITE))))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        L["tagline"],
        ParagraphStyle("CoverST", fontName="Helvetica", fontSize=13,
                        leading=16, textColor=colors.HexColor("#94A3B8"))))
    story.append(Spacer(1, 16))

    # Card periodo + impianto. Per evitare sovrapposizioni: ogni card è una
    # mini-tabella di 3 righe (label / valore principale / sotto-valore) con
    # leading esplicito per ciascuna fascia di font.
    def _card_3lines(label: str, main: str, sub: str, main_size: int = 16) -> Table:
        cells = [
            [Paragraph(
                f'<b>{label.upper()}</b>',
                ParagraphStyle("lbl", fontName="Helvetica-Bold",
                                fontSize=8, leading=10,
                                textColor=colors.HexColor(_AMBER)))],
            [Paragraph(
                f'<b>{main}</b>',
                ParagraphStyle("main", fontName="Helvetica-Bold",
                                fontSize=main_size, leading=main_size + 4,
                                textColor=colors.HexColor(_WHITE)))],
        ]
        if sub:
            cells.append([Paragraph(
                sub,
                ParagraphStyle("sub", fontName="Helvetica",
                                fontSize=9, leading=11,
                                textColor=colors.HexColor("#94A3B8")))])
        t = Table(cells, colWidths=[None])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 4),
            ("TOPPADDING", (0, 1), (0, 1), 0),
            ("BOTTOMPADDING", (0, 1), (0, 1), 3),
        ]))
        return t

    _info_data = [[
        _card_3lines(L["periodo"], _periodo, "", main_size=18),
        _card_3lines(L["azienda"], _company, _plant_name, main_size=13),
        _card_3lines(L["regime"], _regime, f"{L['soglia_saving']}: {_thr:.0f}%", main_size=13),
    ]]
    _info_tbl = Table(_info_data, colWidths=[(PAGE_W - 40 * mm) / 3] * 3, hAlign="LEFT")
    _info_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E3A5F")),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#F59E0B")),
        ("LINEAFTER", (0, 0), (1, 0), 0.4, colors.HexColor("#475569")),
    ]))
    story.append(_info_tbl)
    story.append(Spacer(1, 20))

    # Esito ufficiale BIG — 3 righe separate con leading esplicito per ogni
    # fascia di font (no sovrapposizioni: il <font size> dentro singolo
    # Paragraph usa il leading del Paragraph, non quello del singolo font).
    _esito_color = _GREEN if _compliant else _RED
    _esito_txt = L["sostenibile"] if _compliant else L["non_conforme"]
    _esito_icon = "[OK]" if _compliant else "[!]"

    _saving_str = num(_saving, 2)
    _margine_str = num(_saving - _thr, 2)
    if not _margine_str.startswith("-"):
        _margine_str = "+" + _margine_str

    _esito_cells = [
        [Paragraph(
            f'<b>{L["esito_ufficiale"]} — {_regime}</b>',
            ParagraphStyle("e1", fontName="Helvetica-Bold", fontSize=11,
                            leading=14, alignment=1,
                            textColor=colors.HexColor("#F8FAFC")))],
        [Paragraph(
            f'<b>{_esito_icon} {_esito_txt}</b>',
            ParagraphStyle("e2", fontName="Helvetica-Bold", fontSize=20,
                            leading=24, alignment=1,
                            textColor=colors.HexColor(_WHITE)))],
        [Paragraph(
            f'{L["saving_mensile"]}: <b>{_saving_str}%</b> · '
            f'{L["soglia"]}: {num(_thr, 0)}% · {L["margine"]}: {_margine_str} {L["punti_pct"]}',
            ParagraphStyle("e3", fontName="Helvetica", fontSize=11,
                            leading=14, alignment=1,
                            textColor=colors.HexColor("#F1F5F9")))],
    ]
    _esito = Table(_esito_cells, colWidths=[PAGE_W - 40 * mm], hAlign="CENTER")
    _esito.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_esito_color)),
        ("LEFTPADDING", (0, 0), (-1, -1), 22),
        ("RIGHTPADDING", (0, 0), (-1, -1), 22),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, 0), (0, 0), 4),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 4),
        ("TOPPADDING", (0, 2), (0, 2), 0),
        ("BOTTOMPADDING", (0, 2), (0, 2), 14),
    ]))
    story.append(_esito)
    story.append(Spacer(1, 18))

    # 4 KPI cards in row
    _bio_t = float(monthly_kpis.get("biomass_total_t", 0.0))
    _sm3 = float(monthly_kpis.get("sm3_netti", 0.0))
    _mwh = float(monthly_kpis.get("mwh", 0.0))

    def _kpi_card(label: str, value: str, unit: str = "") -> Table:
        # Card a 2 righe separate per evitare sovrapposizioni di leading
        inner = Table([
            [Paragraph(
                f'<b>{label.upper()}</b>',
                ParagraphStyle("kl", fontName="Helvetica-Bold", fontSize=8,
                                leading=10, alignment=1,
                                textColor=colors.HexColor(_AMBER)))],
            [Paragraph(
                (f'<b>{value}</b>'
                 + (f' <font size="10" color="#94A3B8">{unit}</font>' if unit else "")),
                ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=20,
                                leading=24, alignment=1,
                                textColor=colors.HexColor(_WHITE)))],
        ], colWidths=[None])
        inner.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 4),
            ("TOPPADDING", (0, 1), (0, 1), 0),
            ("BOTTOMPADDING", (0, 1), (0, 1), 0),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        t = Table([[inner]], colWidths=[None], hAlign="CENTER")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E3A5F")),
            ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#475569")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return t

    _kpi_row = Table(
        [[
            _kpi_card(L["biomasse"], num(_bio_t, 1), "t"),
            _kpi_card(L["sm3_netti"], num(_sm3, 0), "Sm³"),
            _kpi_card(L["mwh_netti"], num(_mwh, 1), "MWh"),
            _kpi_card(L["saving_ghg"], num(_saving, 2), "%"),
        ]],
        colWidths=[(PAGE_W - 52 * mm) / 4] * 4,
    )
    _kpi_row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(_kpi_row)

    # =========================================================================
    # PAGINA 2 — RIEPILOGO COMPLETO
    # =========================================================================
    # Switch al template standard (con header/footer) PRIMA del PageBreak
    # così la pagina successiva eredita il template "std".
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.append(NextPageTemplate("std"))
    story.append(PageBreak())

    story.append(Paragraph(L["riepilogo"], s_h2))
    _kpis_rows = [[L["kpi"], L["valore"], L["unita"]]]
    _kpi_def = [
        (L["anno"],                         monthly_kpis.get("year", "—"),                        ""),
        (L["mese"],                         monthly_kpis.get("month", "—"),                       ""),
        (L["regime"],                       monthly_kpis.get("regime", _regime),                  ""),
        (L["biomasse"],                     num(_bio_t, 1),                                        "t"),
        (L["sm3_netti"],                    num(_sm3, 0),                                          "Sm³"),
        (L["mwh_netti"],                    num(_mwh, 1),                                          "MWh"),
        (L["saving_pct"],                   num(_saving, 2),                                       "%"),
        (L["soglia_norm"],                  num(_thr, 2),                                          "%"),
        (L["margine_v"],                    _margine_str,                                          "pt"),
        (L["esito"],                        _esito_txt,                                            ""),
    ]
    if monthly_kpis.get("remi_vb_total", 0) > 0:
        _kpi_def.extend([
            (L["vb_remi"],                  num(monthly_kpis.get("remi_vb_total", 0), 0),         "Sm³"),
            (L["e_remi"],                   num(monthly_kpis.get("remi_e_total", 0), 0),          "kWh"),
            (L["portata_media"],            num(monthly_kpis.get("remi_portata_media_smch", 0), 1), "Sm³/h"),
            (L["potenza_media"],            num(monthly_kpis.get("remi_potenza_media_mw", 0), 3),  "MW"),
            (L["pci_medio"],                num(monthly_kpis.get("remi_energia_specifica_kwh_smc", 0), 3), "kWh/Sm³"),
        ])
    for k, v, u in _kpi_def:
        _kpis_rows.append([k, str(v), u])

    _kpi_tbl = Table(_kpis_rows, colWidths=[80 * mm, 50 * mm, 30 * mm], hAlign="LEFT", repeatRows=1)
    _kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_WHITE)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_NAVY_DARK)),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(_WHITE), colors.HexColor(_TINT)]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(_AMBER)),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_GREY_LIGHT)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(_kpi_tbl)

    # Vincoli normativi
    constraints = monthly_kpis.get("constraints_status") or []
    if constraints:
        story.append(Paragraph(L["vincoli"], s_h2))
        _con_rows = [[L["vincolo"], L["esito"], L["valore"], L["limite"], L["note"]]]
        for c in constraints:
            _con_rows.append([
                str(c.get("name", "")),
                "OK" if c.get("ok") else "KO",
                num(c.get("value", 0), 2),
                num(c.get("limit", 0), 2),
                str(c.get("msg", ""))[:90],
            ])
        _con_tbl = Table(_con_rows, colWidths=[60 * mm, 18 * mm, 28 * mm, 28 * mm, 130 * mm],
                          hAlign="LEFT", repeatRows=1)
        _ct_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_WHITE)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_NAVY_DARK)),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("ALIGN", (2, 1), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(_WHITE), colors.HexColor(_TINT)]),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(_AMBER)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_GREY_LIGHT)),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]
        # Conditional color per OK/KO
        for i, c in enumerate(constraints, start=1):
            if c.get("ok"):
                _ct_styles.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(_GREEN)))
                _ct_styles.append(("TEXTCOLOR", (1, i), (1, i), colors.HexColor(_WHITE)))
                _ct_styles.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
            else:
                _ct_styles.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(_RED)))
                _ct_styles.append(("TEXTCOLOR", (1, i), (1, i), colors.HexColor(_WHITE)))
                _ct_styles.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
        _con_tbl.setStyle(TableStyle(_ct_styles))
        story.append(_con_tbl)

    # Indicazioni operative
    if guidance:
        story.append(Paragraph(L["indicazioni"], s_h2))
        for g in guidance:
            story.append(Paragraph(f"• {g}", s_body))
        story.append(Spacer(1, 4))

    # =========================================================================
    # PAGINA 3+ — TABELLA GIORNALIERA
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph(L["tabella_daily"], s_h2))
    story.append(Paragraph(L["tabella_intro"], s_caption))
    story.append(Spacer(1, 6))

    df = daily_df.copy()
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").apply(
            lambda x: date_fmt(x) if pd.notna(x) else ""
        )

    # Razionalizzazione PDF: mostriamo SOLO le colonne essenziali del giorno.
    # (Il CSV/export mantiene tutte le colonne — eec/esca/etd, cumulati, REMI
    # tecnici, feed singoli — per chi serve il dettaglio completo.)
    _pdf_keep = [
        "Data",
        "Tot biomasse t",
        "remi_vb",
        "Sm³/h netti",
        "MWh",
        "ep",
        "Saving giornaliero (stima %)",
        "Cap OK",
    ]
    df = df[[c for c in _pdf_keep if c in df.columns]]

    # Cap OK booleano → testo leggibile (evita "True/False" nel PDF). La riga
    # TOTALE MESE può già avere un testo: in quel caso lo lasciamo com'è.
    if "Cap OK" in df.columns:
        df["Cap OK"] = df["Cap OK"].map(
            lambda v: v if isinstance(v, str) else ("OK" if bool(v) else "KO")
        )

    # Header brevi e leggibili
    _header_map = {
        "Tot biomasse t":               "Tot Biom. (t)",
        "remi_vb":                      "Sm³ reali",
        "ep":                           "ep (gCO2eq/MJ)",
        "Saving giornaliero (stima %)": "Saving %",
        "Cap OK":                       "Esito",
    }
    df_display = df.rename(columns={k: v for k, v in _header_map.items() if k in df.columns})

    headers = list(df_display.columns)
    body_rows = []
    for _, r in df_display.iterrows():
        row = []
        for c in headers:
            v = r[c]
            if isinstance(v, float):
                if "%" in c or "Saving" in c:
                    row.append(num(v, 2))
                elif "Sm³" in c and "ora" in c.lower():
                    row.append(num(v, 1))
                else:
                    row.append(num(v, 2))
            else:
                row.append("" if v is None else str(v))
        body_rows.append(row)

    # Larghezze colonne proporzionate al contenuto (non equidistribuite):
    # "Data" e le label brevi restano strette, "ep (gCO2eq/MJ)" più larga.
    # Default 1.0 per header non mappati → degrada a distribuzione uniforme.
    avail_w = PAGE_W - 30 * mm
    _w_weights = {
        "Data": 1.1,
        "Tot Biom. (t)": 1.2,
        "Sm³ reali": 1.1,
        "Sm³/h netti": 1.1,
        "MWh": 0.8,
        "ep (gCO2eq/MJ)": 1.6,
        "Saving %": 1.0,
        "Esito": 0.9,
    }
    _weights = [_w_weights.get(h, 1.0) for h in headers]
    _wsum = sum(_weights) or 1.0
    col_widths = [avail_w * w / _wsum for w in _weights]

    daily_tbl = Table([headers] + body_rows, colWidths=col_widths,
                      hAlign="LEFT", repeatRows=1)
    _styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_WHITE)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_NAVY_DARK)),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(_WHITE), colors.HexColor(_TINT)]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(_AMBER)),
        ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor(_GREY_LIGHT)),
        ("INNERGRID", (0, 1), (-1, -1), 0.2, colors.HexColor(_GREY_LIGHT)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    # Conditional color colonna "Esito" se presente
    esito_idx = None
    for j, h in enumerate(headers):
        if h.lower() == "esito":
            esito_idx = j
            break
    if esito_idx is not None:
        for i, row in enumerate(body_rows, start=1):
            cell = str(row[esito_idx]).upper()
            if "OK" in cell or "✅" in cell:
                _styles.append(("TEXTCOLOR", (esito_idx, i), (esito_idx, i), colors.HexColor(_GREEN)))
                _styles.append(("FONTNAME", (esito_idx, i), (esito_idx, i), "Helvetica-Bold"))
            elif "KO" in cell or "❌" in cell or "VIOLAZ" in cell.upper():
                _styles.append(("TEXTCOLOR", (esito_idx, i), (esito_idx, i), colors.HexColor(_RED)))
                _styles.append(("FONTNAME", (esito_idx, i), (esito_idx, i), "Helvetica-Bold"))
    daily_tbl.setStyle(TableStyle(_styles))
    story.append(daily_tbl)

    # =========================================================================
    # PAGINA ULTIMA — AUDIT & ANAGRAFICA
    # =========================================================================
    if audit_trail:
        story.append(PageBreak())
        story.append(Paragraph(L["anagrafica"], s_h2))
        story.append(Paragraph(L["anagrafica_intro"], s_caption))
        story.append(Spacer(1, 6))

        rows = [[L["voce"], L["valore"]]]
        for k, v in audit_trail.items():
            if isinstance(v, (list, tuple)):
                v = " | ".join(str(x) for x in v)
            rows.append([str(k), str(v)[:140]])
        at_tbl = Table(rows, colWidths=[90 * mm, (PAGE_W - 30 * mm) - 90 * mm],
                       hAlign="LEFT", repeatRows=1)
        at_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_WHITE)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_NAVY_DARK)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(_WHITE), colors.HexColor(_TINT)]),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(_AMBER)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_GREY_LIGHT)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(at_tbl)

    # =========================================================================
    # PAGINA FINALE — RIFERIMENTI NORMATIVI & VALIDATION WARNING
    # Per tracciabilità audit: ogni report mostra sempre fonti + disclaimer.
    # =========================================================================
    try:
        from core.version import (
            NORMATIVE_REFERENCES,
            VALIDATION_WARNING,
            __version__ as _sw_version,
        )
        story.append(PageBreak())
        story.append(Paragraph(
            ("Riferimenti normativi & Validazione" if lang != "en"
             else "Regulatory references & Validation"),
            s_h2,
        ))
        story.append(Paragraph(
            ("Fonti normative usate per i calcoli, versione software, "
             "data esportazione e disclaimer di validazione."
             if lang != "en" else
             "Regulatory sources used in calculations, software version, "
             "export date, and validation disclaimer."),
            s_caption,
        ))
        story.append(Spacer(1, 8))
        # Tabella riferimenti
        norm_rows = [
            ["Norma / Standard" if lang != "en" else "Standard",
             "Ambito" if lang != "en" else "Scope"]
        ]
        for k, v in NORMATIVE_REFERENCES.items():
            norm_rows.append([k, v])
        norm_tbl = Table(norm_rows, colWidths=[60 * mm, (PAGE_W - 30 * mm) - 60 * mm],
                          hAlign="LEFT", repeatRows=1)
        norm_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_WHITE)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_NAVY_DARK)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor(_WHITE), colors.HexColor(_TINT)]),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(_AMBER)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_GREY_LIGHT)),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(norm_tbl)
        story.append(Spacer(1, 12))

        # Metadata software + warning
        story.append(Paragraph(
            ("Metadati software" if lang != "en" else "Software metadata"),
            s_h3,
        ))
        meta_lines = [
            f"<b>Software</b>: Metan.iQ v{_sw_version}",
            f"<b>{'Data esportazione' if lang != 'en' else 'Export date'}</b>: {_gen_at}",
            f"<b>{'Metodo calcolo GHG' if lang != 'en' else 'GHG calculation method'}</b>: RED III Allegato V Parte C · UNI-TS 11567:2024",
            f"<b>{'Comparator fossile' if lang != 'en' else 'Fossil comparator'}</b>: 80 gCO₂/MJ (gas naturale) · 94 gCO₂/MJ (diesel trasporti)",
        ]
        for line in meta_lines:
            story.append(Paragraph(line, s_body))
        story.append(Spacer(1, 10))

        # Validation warning box
        warning_text = (VALIDATION_WARNING if lang != "en" else
                        "⚠️ The values reported are the result of a calculation "
                        "based on data entered by the operator and on standard "
                        "parameters (UNI-TS 11567:2024, RED III, JEC WTT v5). "
                        "For official certifications to GSE / competent "
                        "authorities, data must be validated by a qualified "
                        "technical consultant (RINA, SGS, ISCC) or via "
                        "dedicated internal audit.")
        # Helvetica (ReportLab) non ha glifi emoji: rimuovo il simbolo ⚠️ e lo
        # sostituisco con un marcatore testuale in grassetto, altrimenti nel PDF
        # esce un quadratino/glifo mancante.
        warning_text = warning_text.replace("⚠️", "").replace("⚠", "").strip()
        _warn_prefix = "ATTENZIONE — " if lang != "en" else "WARNING — "
        warn_tbl = Table(
            [[Paragraph("<b>" + _warn_prefix + "</b>" + warning_text, ParagraphStyle(
                "Warn", fontName="Helvetica", fontSize=9, leading=12,
                textColor=colors.HexColor("#7C2D12"),
            ))]],
            colWidths=[PAGE_W - 30 * mm],
        )
        warn_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(_AMBER)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(warn_tbl)
    except Exception:  # noqa: BLE001
        # Non-blocking: se import fallisce, l'export funziona comunque
        pass

    doc.build(story)
    return buf.getvalue()


__all__ = ["build_daily_pdf"]
