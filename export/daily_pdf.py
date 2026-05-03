# -*- coding: utf-8 -*-
"""export/daily_pdf.py — Esportazione PDF giornaliero."""
from __future__ import annotations

import io
from typing import Any

import pandas as pd


def _try_reportlab():
    try:
        from reportlab.lib import colors  # noqa: F401
        from reportlab.lib.pagesizes import A4, landscape  # noqa: F401
        from reportlab.lib.styles import getSampleStyleSheet  # noqa: F401
        from reportlab.platypus import (  # noqa: F401
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
        return True
    except Exception:
        return False


def build_daily_pdf(daily_df: pd.DataFrame, monthly_kpis: dict[str, Any],
                    audit_trail: dict[str, Any] | None = None,
                    guidance: list[str] | None = None,
                    title: str = "Gestione Giornaliera - Sostenibilita' Mensile") -> bytes:
    """Crea un PDF con KPI mensili, tabella giornaliera, vincoli, guidance, audit."""
    if not _try_reportlab():
        # Fallback testuale (non blocca i test)
        txt = io.StringIO()
        txt.write(f"{title}\n")
        txt.write("=" * len(title) + "\n\n")
        for k, v in (monthly_kpis or {}).items():
            txt.write(f"{k}: {v}\n")
        txt.write("\n")
        for g in (guidance or []):
            txt.write(f"- {g}\n")
        txt.write("\n--- Tabella giornaliera ---\n")
        txt.write(daily_df.to_string(index=False))
        return txt.getvalue().encode("utf-8")

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )

    audit_trail = audit_trail or {}
    guidance = guidance or []

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 8))

    # Disclaimer compliance mensile
    story.append(Paragraph(
        "<b>Nota di compliance:</b> il controllo di sostenibilita' ufficiale e' "
        "MENSILE. I valori giornalieri di saving sono solo indicativi.",
        styles["Italic"],
    ))
    story.append(Spacer(1, 10))

    # KPI mensili
    story.append(Paragraph("KPI Mensili", styles["Heading2"]))
    kpi_data = [["KPI", "Valore"]]
    for k in ("year", "month", "regime", "biomass_total_t", "sm3_netti", "mwh",
              "saving_pct", "threshold", "margin", "compliant"):
        if k in monthly_kpis:
            v = monthly_kpis[k]
            if isinstance(v, float):
                v = f"{v:.3f}"
            kpi_data.append([k, str(v)])
    kpi_table = Table(kpi_data, hAlign="LEFT")
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # Vincoli
    constraints = monthly_kpis.get("constraints_status") or []
    if constraints:
        story.append(Paragraph("Vincoli regime", styles["Heading2"]))
        rows = [["Vincolo", "Esito", "Valore", "Limite", "Note"]]
        for c in constraints:
            rows.append([
                str(c.get("name", "")),
                "OK" if c.get("ok") else "KO",
                f"{c.get('value', 0):.2f}",
                f"{c.get('limit', 0):.2f}",
                str(c.get("msg", "")),
            ])
        ct = Table(rows, hAlign="LEFT")
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.append(ct)
        story.append(Spacer(1, 10))

    # Guidance
    if guidance:
        story.append(Paragraph("Indicazioni operative fine mese", styles["Heading2"]))
        for g in guidance:
            story.append(Paragraph(f"- {g}", styles["BodyText"]))
        story.append(Spacer(1, 10))

    # Audit Trail
    if audit_trail:
        story.append(Paragraph("Audit Trail", styles["Heading2"]))
        rows = [["Voce", "Valore"]]
        for k, v in audit_trail.items():
            if isinstance(v, (list, tuple)):
                v = " | ".join(str(x) for x in v)
            rows.append([str(k), str(v)])
        at = Table(rows, hAlign="LEFT")
        at.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.append(at)
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(Paragraph("Tabella giornaliera", styles["Heading2"]))

    # Tabella giornaliera (formattata)
    df = daily_df.copy()
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")
    # Limita colonne se troppo larghe
    keep_cols = list(df.columns)
    rows = [keep_cols]
    for _, r in df.iterrows():
        row = []
        for c in keep_cols:
            v = r[c]
            if isinstance(v, float):
                v = f"{v:.2f}"
            row.append(str(v))
        rows.append(row)
    dt = Table(rows, hAlign="LEFT", repeatRows=1)
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
    ]))
    story.append(dt)

    doc.build(story)
    return buf.getvalue()


__all__ = ["build_daily_pdf"]
