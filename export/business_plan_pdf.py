"""export/business_plan_pdf.py — PDF del Business Plan Completo (15 anni).

Genera un PDF brand Metan.iQ (navy/brass) della sezione «Business Plan
Completo» del tab Pianificazione: anagrafica, parametri di input, KPI
finanziari (CAPEX, equity, IRR, NPV, payback) e tabella anno-per-anno
(ricavi, OPEX, EBITDA, interessi, imposte, CFO, rata, FCF equity, debito
residuo, FCF cumulato).

Auto-contenuto: dipende solo da ReportLab. Riceve l'oggetto BusinessPlan
(core.business_plan.BusinessPlan) + un dict `meta` con i parametri di input
e l'anagrafica. Nessun import da app_mensile (evita import circolari).
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.graphics.shapes import Drawing, Rect, Line, String, PolyLine

# Brand tokens (allineati a export/daily_pdf.py / build_user_manual.py)
NAVY = colors.HexColor("#15242E")
BRASS = colors.HexColor("#9A7B3C")
INK = colors.HexColor("#1C1B16")
MUTED = colors.HexColor("#726C5E")
LINE = colors.HexColor("#E4DDCD")
PAPER_ALT = colors.HexColor("#FBF9F3")
WHITE = colors.white


def _fmt_eur(v: float, decimals: int = 0) -> str:
    """Formato numero italiano (1.234.567,89) senza simbolo."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    s = f"{v:,.{decimals}f}"            # 1,234,567.89 (stile US)
    # swap separatori -> IT
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _pct(v: float, decimals: int = 1) -> str:
    try:
        return f"{float(v):.{decimals}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "-"


# Sostituzioni per caratteri non presenti nei font standard ReportLab
# (Helvetica/WinAnsi): simboli matematici e frecce -> ASCII.
_CHAR_REPL = {
    "≥": ">=", "≤": "<=",      # ≥ ≤
    "−": "-",  "–": "-",       # − (minus) – (en dash)
    "—": "-",  "×": "x",       # — (em dash) × (times)
    "→": "->", "•": "-",       # → •
    "≈": "~",  "±": "+/-",     # ≈ ±
}


def _clean(s: Any) -> str:
    """Rende una stringa sicura per i font standard ReportLab: sostituisce i
    simboli matematici e rimuove tutto ciò che non è codificabile in WinAnsi
    (cp1252) — emoji come 🅰 🅱 🏭, che altrimenti diventano quadratini □."""
    if s is None:
        return ""
    s = str(s)
    for a, b in _CHAR_REPL.items():
        s = s.replace(a, b)
    out = []
    for ch in s:
        try:
            ch.encode("cp1252")       # WinAnsi: € · ³ ² à è ecc. OK
            out.append(ch)
        except UnicodeEncodeError:
            continue                  # emoji / glifi non rappresentabili -> via
    # comprimi spazi residui dopo rimozione emoji
    return " ".join("".join(out).split())


def _cashflow_drawing(rows, label: str, width: float = 760.0,
                      height: float = 215.0) -> Drawing:
    """Disegna il cash flow equity: barre FCF/anno (rosso<0, verde>=0) +
    linea FCF cumulato (brass) + linea zero. Nativo ReportLab, nessuna
    dipendenza esterna (funziona anche su Streamlit Cloud)."""
    d = Drawing(width, height)
    label = _clean(label)
    rows = list(rows or [])
    if not rows:
        return d
    years = [getattr(r, "year", i) for i, r in enumerate(rows)]
    eq = [float(getattr(r, "fcf_equity", 0.0)) for r in rows]
    cum = [float(getattr(r, "fcf_cumulato", 0.0)) for r in rows]
    n = len(rows)
    ml, mr, mt, mb = 58.0, 12.0, 26.0, 26.0
    pw, ph = width - ml - mr, height - mt - mb
    x0, y0 = ml, mb
    vmin = min(0.0, min(eq), min(cum))
    vmax = max(0.0, max(eq), max(cum))
    if vmax == vmin:
        vmax = vmin + 1.0

    def sy(v):
        return y0 + (v - vmin) / (vmax - vmin) * ph

    def sx(i):
        return x0 + (i + 0.5) / n * pw

    zero_y = sy(0.0)
    # titolo
    d.add(String(x0, height - 14, label, fontName="Helvetica-Bold",
                 fontSize=8.5, fillColor=NAVY))
    # gridlines + asse Y (k€)
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4.0
        yy = sy(v)
        d.add(Line(x0, yy, x0 + pw, yy, strokeColor=LINE, strokeWidth=0.4))
        d.add(String(x0 - 6, yy - 3,
                     _fmt_eur(v / 1000.0), fontName="Helvetica",
                     fontSize=6.5, fillColor=MUTED, textAnchor="end"))
    # barre FCF equity
    bw = pw / n * 0.55
    for i, v in enumerate(eq):
        cx, yv = sx(i), sy(v)
        top, bot = max(yv, zero_y), min(yv, zero_y)
        col = colors.HexColor("#059669") if v >= 0 else colors.HexColor("#DC2626")
        d.add(Rect(cx - bw / 2.0, bot, bw, max(top - bot, 0.6),
                   fillColor=col, strokeColor=None))
    # linea zero
    d.add(Line(x0, zero_y, x0 + pw, zero_y, strokeColor=MUTED, strokeWidth=0.8))
    # linea FCF cumulato
    pts = []
    for i, v in enumerate(cum):
        pts.extend([sx(i), sy(v)])
    d.add(PolyLine(pts, strokeColor=BRASS, strokeWidth=2.0))
    # etichette anni
    for i, yr in enumerate(years):
        d.add(String(sx(i), y0 - 12, str(yr), fontName="Helvetica",
                     fontSize=6.0, fillColor=MUTED, textAnchor="middle"))
    return d


def build_business_plan_pdf(bp: Any, meta: dict | None = None) -> BytesIO:
    """Costruisce il PDF del Business Plan 15 anni.

    Args:
        bp:   oggetto BusinessPlan (con .rows: list[BPYear] e KPI).
        meta: dict opzionale con parametri input + anagrafica. Chiavi usate:
              company_name, plant_name, plant_type_label, fascia_label,
              capex_unit, opex_unit, leverage_pct, interest_rate_pct,
              loan_years, inflation_pct, discount_rate_pct, pnrr_pct, lang.
    Returns:
        BytesIO con il PDF (cursore a 0).
    """
    meta = meta or {}
    L = str(meta.get("lang", "it")).lower().startswith("it")

    def T(it: str, en: str) -> str:
        return it if L else en

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm,
        title="Metan.iQ — Business Plan 15 anni",
        author="Metan.iQ",
    )
    styles = getSampleStyleSheet()
    h_title = ParagraphStyle(
        "BPTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, textColor=NAVY, spaceAfter=2, leading=23,
    )
    h_sub = ParagraphStyle(
        "BPSub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, textColor=MUTED, spaceAfter=10,
    )
    h_sec = ParagraphStyle(
        "BPSec", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11.5, textColor=NAVY, spaceBefore=12, spaceAfter=5,
    )
    body = ParagraphStyle(
        "BPBody", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, textColor=INK, leading=12,
    )
    note = ParagraphStyle(
        "BPNote", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.5, textColor=MUTED, leading=10, spaceBefore=8,
    )

    story: list = []

    # ---- Header ----
    story.append(Paragraph(
        T("Business Plan Completo — 15 anni",
          "Complete Business Plan — 15 years"), h_title))
    _comp = _clean(meta.get("company_name")) or "-"
    _plant = _clean(meta.get("plant_name")) or "-"
    story.append(Paragraph(
        f"Metan.iQ · {_comp} · {_plant} · "
        + T("impianto biometano DM 2022 / RED III",
            "biomethane plant DM 2022 / RED III"),
        h_sub))

    # ---- Parametri input ----
    story.append(Paragraph(T("Parametri di input", "Input parameters"), h_sec))
    _ptype = _clean(meta.get("plant_type_label")) or "-"
    _fascia = _clean(meta.get("fascia_label")) or "-"
    param_rows = [
        [T("Taglia impianto", "Plant size"),
         f"{_fmt_eur(getattr(bp, 'plant_smch', 0))} Sm³/h",
         T("Tariffa applicata", "Applied tariff"),
         f"{_fmt_eur(getattr(bp, 'tariffa_eur_mwh', 0), 1)} €/MWh"],
        [T("Tipologia", "Plant type"), str(_ptype),
         T("Fascia", "Bracket"), str(_fascia)],
        [T("CAPEX unitario", "Unit CAPEX"),
         f"{_fmt_eur(meta.get('capex_unit', 0))} €/Sm³·h",
         T("OPEX unitario", "Unit OPEX"),
         f"{_fmt_eur(meta.get('opex_unit', 0))} €/Sm³·h/" + T("a", "y")],
        [T("Leva debito", "Debt leverage"),
         _pct(meta.get("leverage_pct", 0)),
         T("Tasso interesse", "Interest rate"),
         _pct(meta.get("interest_rate_pct", 0), 2)],
        [T("Durata mutuo", "Loan duration"),
         f"{int(meta.get('loan_years', 0))} " + T("anni", "years"),
         T("WACC sconto", "Discount WACC"),
         _pct(meta.get("discount_rate_pct", getattr(bp, "discount_rate_pct", 0)))],
        [T("Inflazione OPEX", "OPEX inflation"),
         _pct(meta.get("inflation_pct", 0)),
         T("Quota PNRR", "PNRR share"),
         _pct(meta.get("pnrr_pct", 0))],
    ]
    pt = Table(param_rows, colWidths=[55 * mm, 60 * mm, 55 * mm, 60 * mm])
    pt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (3, 0), (3, -1), INK),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pt)

    # ---- KPI ----
    story.append(Paragraph(T("Indicatori sintetici", "Summary KPIs"), h_sec))

    def _meur(x):
        return f"{_fmt_eur((x or 0) / 1_000_000, 2)} M€"

    _irr_e = getattr(bp, "irr_equity", 0.0)
    _irr_p = getattr(bp, "irr_project", 0.0)
    _pb = getattr(bp, "payback_years", None)
    kpi_header = [
        T("CAPEX totale", "Total CAPEX"),
        T("Equity", "Equity"),
        T("Debito", "Debt"),
        "PNRR",
        "IRR project",
        "IRR equity",
        T("NPV @ WACC", "NPV @ WACC"),
        T("Payback", "Payback"),
    ]
    kpi_vals = [
        _meur(getattr(bp, "capex_total", 0)),
        _meur(getattr(bp, "capex_equity", 0)),
        _meur(getattr(bp, "capex_debt", 0)),
        _meur(getattr(bp, "pnrr_grant", 0)),
        _pct(_irr_p * 100) if -1 < _irr_p < 10 else "—",
        _pct(_irr_e * 100) if -1 < _irr_e < 10 else "—",
        _meur(getattr(bp, "npv_project", 0)),
        (f"{_fmt_eur(_pb, 2)} " + T("anni", "yrs")) if _pb else "—",
    ]
    kt = Table([kpi_header, kpi_vals], colWidths=[34 * mm] * 8)
    kt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("TEXTCOLOR", (0, 1), (-1, 1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("LINEABOVE", (0, 1), (-1, 1), 1.2, BRASS),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    story.append(kt)

    # ---- Tabella 15 anni ----
    story.append(Paragraph(
        T("Conto economico e flussi di cassa (anno per anno)",
          "Income statement and cash flows (year by year)"), h_sec))
    cols = [
        T("Anno", "Year"), T("Ricavi", "Revenue"), "OPEX", "EBITDA",
        T("Interessi", "Interest"), T("Imposte", "Taxes"), "CFO",
        T("Rata cap.", "Principal"), "FCF equity",
        T("Debito res.", "Debt left"), T("FCF cum.", "Cum. FCF"),
    ]
    tbl = [cols]
    for r in getattr(bp, "rows", []):
        tbl.append([
            str(getattr(r, "year", "")),
            _fmt_eur(getattr(r, "ricavi", 0)),
            _fmt_eur(getattr(r, "opex", 0)),
            _fmt_eur(getattr(r, "ebitda", 0)),
            _fmt_eur(getattr(r, "interessi", 0)),
            _fmt_eur(getattr(r, "imposte", 0)),
            _fmt_eur(getattr(r, "cfo", 0)),
            _fmt_eur(getattr(r, "rata_capitale", 0)),
            _fmt_eur(getattr(r, "fcf_equity", 0)),
            _fmt_eur(getattr(r, "debito_residuo", 0)),
            _fmt_eur(getattr(r, "fcf_cumulato", 0)),
        ])
    _wide = 26 * mm
    col_w = [14 * mm] + [_wide] * 10
    bpt = Table(tbl, colWidths=col_w, repeatRows=1)
    _style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BRASS),
        ("LINEBELOW", (0, 1), (-1, -1), 0.2, LINE),
    ]
    # Righe alternate
    for i in range(1, len(tbl)):
        if i % 2 == 0:
            _style.append(("BACKGROUND", (0, i), (-1, i), PAPER_ALT))
    # Colore FCF cumulato: rosso se < 0, verde se >= 0
    for i, r in enumerate(getattr(bp, "rows", []), start=1):
        _c = colors.HexColor("#059669") if getattr(r, "fcf_cumulato", 0) >= 0 \
            else colors.HexColor("#DC2626")
        _style.append(("TEXTCOLOR", (10, i), (10, i), _c))
        _style.append(("FONTNAME", (10, i), (10, i), "Helvetica-Bold"))
    bpt.setStyle(TableStyle(_style))
    story.append(bpt)

    # ---- Grafico cash flow equity (barre + cumulato) ----
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        T("Cash Flow Equity per anno + Cumulato (break-even visivo)",
          "Equity Cash Flow per year + Cumulative (visual break-even)"), h_sec))
    story.append(_cashflow_drawing(
        getattr(bp, "rows", []),
        T("Barre = FCF equity (verde ≥ 0, rosso < 0)  ·  linea ottone = FCF "
          "cumulato  ·  valori in k€",
          "Bars = equity FCF (green ≥ 0, red < 0)  ·  brass line = cumulative "
          "FCF  ·  values in k€"),
    ))

    story.append(Paragraph(_clean(
        T("Valori in € correnti. EBITDA = Ricavi − OPEX. CFO = EBITDA − "
          "interessi − imposte. FCF equity = CFO − rata capitale. IRR/NPV/"
          "payback calcolati sui flussi equity. Documento generato da "
          "Metan.iQ; i valori dipendono dai parametri impostati nella "
          "sezione Pianificazione & Business Plan.",
          "Values in current €. EBITDA = Revenue − OPEX. CFO = EBITDA − "
          "interest − taxes. Equity FCF = CFO − principal. IRR/NPV/payback "
          "computed on equity flows. Generated by Metan.iQ; figures depend "
          "on the parameters set in the Planning & Business Plan section.")),
        note))

    def _decorate(canvas, _doc):
        canvas.saveState()
        w, h = landscape(A4)
        # banda superiore navy sottile
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 6 * mm, w, 6 * mm, fill=1, stroke=0)
        canvas.setFillColor(BRASS)
        canvas.rect(0, h - 6.8 * mm, w, 0.8 * mm, fill=1, stroke=0)
        # footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(14 * mm, 7 * mm, "Metan.iQ — Decision Intelligence Platform")
        canvas.drawRightString(w - 14 * mm, 7 * mm, f"pag. {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    buf.seek(0)
    return buf
