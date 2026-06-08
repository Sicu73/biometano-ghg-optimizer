# -*- coding: utf-8 -*-
"""
dossier_conformita.py — Dossier di conformità OdC (RINA/SGS/ISCC) per Metan.iQ.

Genera un PDF autoportante che, per OGNI biomassa del FEEDSTOCK_DB, dichiara:
  - fattore emissivo eec [gCO2eq/MJ] e tier di difendibilità (A/B/C/D)
  - resa [Nm3 CH4/t t.q.] e sostanza secca standard
  - classificazione Annex IX RED III
  - fonte normativa del valore (src)

Più il quadro normativo applicato (formula GHG RED III All. V Parte C,
comparatori FFC, soglie saving, GWP) e la legenda dei tier.

Obiettivo: rendere ogni valore difendibile per costruzione in sede di audit.
Non dipende da Streamlit: testabile in isolamento.

API:
  build_conformity_dossier(feedstock_db, *, lang="it", company="", plant="",
                           cui="", date_str="", manure_credit_declared=False)
    -> bytes (PDF)
"""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NAVY = colors.HexColor("#15242E")
BRASS = colors.HexColor("#9A7B3C")
INK = colors.HexColor("#1C1B16")
SLATE_50 = colors.HexColor("#F1EEE6")
LINE = colors.HexColor("#D9D2C2")
WHITE = colors.white

# Colori per tier (badge)
TIER_BG = {
    "A": colors.HexColor("#E4EFE8"),  # verde tenue
    "B": colors.HexColor("#E4EFE8"),
    "C": colors.HexColor("#F6EFD9"),  # giallo tenue
    "D": colors.HexColor("#F6E2CF"),  # arancio tenue
}


def eec_tier_code(src: str, eec) -> str:
    """A=default normativo, B=zero da regola, C=conservativo, D=credito."""
    s = (src or "").strip()
    sl = s.lower()
    try:
        e = float(eec or 0.0)
    except (TypeError, ValueError):
        e = 0.0
    if s.startswith("UNI-TS"):
        return "A"
    if "manure credit red iii" in sl or e < 0:
        return "D"
    if e == 0.0:
        return "B"
    return "C"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=22, textColor=WHITE, leading=26),
        "eyebrow": ParagraphStyle("e", parent=base["Normal"], fontName="Helvetica",
                                  fontSize=9, textColor=BRASS, leading=13, tracking=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica",
                              fontSize=10, textColor=colors.HexColor("#CBD5E1"), leading=14),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=13, textColor=NAVY, leading=17, spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("b", parent=base["Normal"], fontName="Helvetica",
                               fontSize=8.5, textColor=INK, leading=12, spaceAfter=3),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontName="Helvetica",
                                fontSize=7.5, textColor=colors.HexColor("#5C5849"), leading=10),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontName="Helvetica",
                               fontSize=7.5, textColor=INK, leading=9.5),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontName="Helvetica-Bold",
                                fontSize=7.5, textColor=NAVY, leading=9.5),
    }


def _T(lang, it, en):
    return en if lang == "en" else it


def build_conformity_dossier(feedstock_db: dict, *, lang: str = "it",
                             company: str = "", plant: str = "", cui: str = "",
                             date_str: str = "", manure_credit_declared: bool = False
                             ) -> bytes:
    s = _styles()
    date_str = date_str or date.today().isoformat()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=_T(lang, "Dossier di conformità — Metan.iQ",
                 "Conformity dossier — Metan.iQ"),
    )
    CONTENT_W = doc.width
    flow = []

    # ---- Header banner ----
    hdr = Table([[Paragraph(
        _T(lang, "// DOSSIER DI CONFORMITÀ · UNI/TS 11567:2024 · RED III",
           "// CONFORMITY DOSSIER · UNI/TS 11567:2024 · RED III"), s["eyebrow"])],
        [Paragraph(_T(lang, "Fattori emissivi e rese biomasse",
                      "Emission factors & feedstock yields"), s["title"])],
        [Paragraph(_T(lang,
            "Tracciabilità e difendibilità dei valori per audit Organismo di Certificazione",
            "Traceability and defendability of values for Certification Body audit"),
            s["sub"])]],
        colWidths=[CONTENT_W])
    hdr.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEABOVE", (0, 0), (-1, 0), 2, BRASS),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
    ]))
    flow.append(hdr)
    flow.append(Spacer(1, 6 * mm))

    # ---- Anagrafica ----
    anag = [
        [Paragraph(_T(lang, "Società", "Company"), s["cellb"]),
         Paragraph(company or "—", s["cell"]),
         Paragraph(_T(lang, "Impianto (CUI)", "Plant (CUI)"), s["cellb"]),
         Paragraph(f"{plant or '—'} ({cui or '—'})", s["cell"])],
        [Paragraph(_T(lang, "Data dossier", "Dossier date"), s["cellb"]),
         Paragraph(date_str, s["cell"]),
         Paragraph(_T(lang, "Manure credit", "Manure credit"), s["cellb"]),
         Paragraph(_T(lang,
            "ATTIVO (dichiarazioni baseline disponibili)" if manure_credit_declared
            else "DISATTIVO (valori standard conservativi)",
            "ENABLED (baseline declarations available)" if manure_credit_declared
            else "DISABLED (conservative standard values)"), s["cell"])],
    ]
    t_anag = Table(anag, colWidths=[CONTENT_W * 0.16, CONTENT_W * 0.34,
                                    CONTENT_W * 0.18, CONTENT_W * 0.32])
    t_anag.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (0, -1), SLATE_50),
        ("BACKGROUND", (2, 0), (2, -1), SLATE_50),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(t_anag)
    flow.append(Spacer(1, 5 * mm))

    # ---- Quadro normativo ----
    flow.append(Paragraph(_T(lang, "1. Quadro normativo applicato",
                             "1. Regulatory framework applied"), s["h2"]))
    flow.append(Paragraph(_T(lang,
        "Formula GHG (RED III All. V Parte C): "
        "<b>e_total = eec + e_l + e_td + e_p - e_sca - crediti</b> [gCO2eq/MJ]. "
        "Comparatori fossili (FFC): rete/calore <b>80</b>, trasporto <b>94</b>, "
        "CHP mix UE <b>183</b>. Soglie saving GHG: rete/calore <b>80%</b> "
        "(nuovi impianti), trasporto 65%, CHP 80%. GWP (Reg. UE 2022/996): "
        "CH4 28, N2O 265. Rese da UNI/TS Prosp. A.1/A.3; eec standard da Prosp. A.5.",
        "GHG formula (RED III Annex V Part C): "
        "<b>e_total = eec + e_l + e_td + e_p - e_sca - credits</b> [gCO2eq/MJ]. "
        "Fossil comparators (FFC): grid/heat <b>80</b>, transport <b>94</b>, "
        "EU-mix CHP <b>183</b>. GHG saving thresholds: grid/heat <b>80%</b> "
        "(new plants), transport 65%, CHP 80%. GWP (Reg. EU 2022/996): "
        "CH4 28, N2O 265. Yields from UNI/TS A.1/A.3; standard eec from A.5."),
        s["body"]))

    # ---- Legenda tier ----
    flow.append(Paragraph(_T(lang, "2. Legenda tier di difendibilità eec",
                             "2. eec defendability tier legend"), s["h2"]))
    legend_rows = [[
        Paragraph("Tier", s["cellb"]),
        Paragraph(_T(lang, "Significato", "Meaning"), s["cellb"]),
        Paragraph(_T(lang, "Difendibilità in audit", "Audit defendability"), s["cellb"]),
    ]]
    legend_data = [
        ("A", _T(lang, "Default normativo (UNI/TS A.5 / RED III All. V-VI)",
                 "Regulatory default (UNI/TS A.5 / RED III Annex V-VI)"),
         _T(lang, "È la norma: non contestabile.", "It is the rule: non-contestable.")),
        ("B", _T(lang, "Zero da regola: residuo/rifiuto Annex IX (eec=0 fino a raccolta)",
                 "Zero by rule: residue/waste Annex IX (eec=0 up to collection)"),
         _T(lang, "Regola RED III esplicita.", "Explicit RED III rule.")),
        ("C", _T(lang, "Stima conservativa da letteratura JEC v5/KTBL (eec>0)",
                 "Conservative literature estimate JEC v5/KTBL (eec>0)"),
         _T(lang, "A sfavore dell'operatore -> nessun motivo di contestazione.",
            "Against the operator -> no reason to contest.")),
        ("D", _T(lang, "Credito da stoccaggio (manure credit, eec<0)",
                 "Storage credit (manure credit, eec<0)"),
         _T(lang, "Richiede dichiarazione baseline del fornitore (RED III All. VI).",
            "Requires supplier baseline declaration (RED III Annex VI).")),
    ]
    for code, mean, defend in legend_data:
        legend_rows.append([
            Paragraph(code, s["cellb"]),
            Paragraph(mean, s["cell"]),
            Paragraph(defend, s["cell"]),
        ])
    t_leg = Table(legend_rows, colWidths=[CONTENT_W * 0.08, CONTENT_W * 0.50,
                                          CONTENT_W * 0.42])
    _leg_style = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, (code, _, _) in enumerate(legend_data, start=1):
        _leg_style.append(("BACKGROUND", (0, i), (0, i), TIER_BG.get(code, SLATE_50)))
    t_leg.setStyle(TableStyle(_leg_style))
    flow.append(t_leg)
    flow.append(Spacer(1, 5 * mm))

    # ---- Tabella completa biomasse ----
    flow.append(Paragraph(_T(lang, "3. Catalogo biomasse — valori e tracciabilità",
                             "3. Feedstock catalogue — values & traceability"), s["h2"]))
    head = [
        Paragraph(_T(lang, "Biomassa", "Feedstock"), s["cellb"]),
        Paragraph(_T(lang, "Categoria", "Category"), s["cellb"]),
        Paragraph("eec", s["cellb"]),
        Paragraph("Tier", s["cellb"]),
        Paragraph("Annex IX", s["cellb"]),
        Paragraph(_T(lang, "Resa", "Yield"), s["cellb"]),
        Paragraph("ST", s["cellb"]),
        Paragraph(_T(lang, "Fonte", "Source"), s["cellb"]),
    ]
    rows = [head]
    tier_rowidx = {}
    for i, (name, d) in enumerate(feedstock_db.items(), start=1):
        eec = float(d.get("eec", 0.0) or 0.0)
        # eec efficace: se gated (manure credit non dichiarato) -> 0
        eff_eec = eec
        if eec < 0 and not manure_credit_declared:
            eff_eec = 0.0
        code = eec_tier_code(d.get("src", ""), eff_eec)
        tier_rowidx[i] = code
        rows.append([
            Paragraph(name, s["cell"]),
            Paragraph(d.get("cat", "—"), s["cell"]),
            Paragraph(f"{eff_eec:+.1f}".replace(".", ","), s["cell"]),
            Paragraph(code, s["cellb"]),
            Paragraph(d.get("annex_ix") or "—", s["cell"]),
            Paragraph(f"{float(d.get('yield', 0.0)):.1f}".replace(".", ","), s["cell"]),
            Paragraph(f"{float(d.get('dry_matter_std', 0.0)) * 100:.0f}%", s["cell"]),
            Paragraph(d.get("src", "—"), s["small"]),
        ])
    tbl = Table(rows, colWidths=[
        CONTENT_W * 0.20, CONTENT_W * 0.14, CONTENT_W * 0.07, CONTENT_W * 0.06,
        CONTENT_W * 0.08, CONTENT_W * 0.07, CONTENT_W * 0.06, CONTENT_W * 0.32,
    ], repeatRows=1)
    tstyle = [
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (6, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for i, code in tier_rowidx.items():
        tstyle.append(("BACKGROUND", (3, i), (3, i), TIER_BG.get(code, SLATE_50)))
    tbl.setStyle(TableStyle(tstyle))
    flow.append(tbl)
    flow.append(Spacer(1, 4 * mm))

    # ---- Note ----
    flow.append(Paragraph(_T(lang, "4. Note metodologiche", "4. Methodological notes"), s["h2"]))
    notes = [
        _T(lang,
           "Manure credit (tier D): sui valori standard è applicato solo con "
           "dichiarazione di baseline di stoccaggio del fornitore; in assenza è "
           "azzerato (eec=0), posizione conservativa. Con valori certificati da "
           "relazione tecnica d'impianto il credito è coperto dalla certificazione.",
           "Manure credit (tier D): on standard values it is applied only with the "
           "supplier's storage baseline declaration; otherwise it is zeroed (eec=0), "
           "a conservative stance. With values certified by a plant technical report "
           "the credit is covered by the certification."),
        _T(lang,
           "Colture dedicate (food/feed): e_l (Land Use Change) = 0 richiede "
           "dichiarazione no-LUC NUTS-2 del fornitore (RED III All. V; Reg. UE 2022/996).",
           "Dedicated crops (food/feed): e_l (Land Use Change) = 0 requires the "
           "supplier's no-LUC NUTS-2 declaration (RED III Annex V; Reg. EU 2022/996)."),
        _T(lang,
           "Residui/sottoprodotti/rifiuti Annex IX: eec=0 fino alla raccolta "
           "(RED III All. V Parte C). Valori eec>0 indicati sono cautelativi.",
           "Residues/by-products/wastes Annex IX: eec=0 up to collection "
           "(RED III Annex V Part C). Any eec>0 shown is precautionary."),
        _T(lang,
           "I valori di letteratura (JEC WTT v5, KTBL) sono la base scientifica dei "
           "default RED; per l'audit possono essere sostituiti da valori reali "
           "documentati tramite la funzione «relazione tecnica» del software.",
           "Literature values (JEC WTT v5, KTBL) are the scientific basis of RED "
           "defaults; for audit they may be replaced by documented actual values via "
           "the software's «technical report» feature."),
    ]
    for n in notes:
        flow.append(Paragraph("• " + n, s["small"]))

    flow.append(Spacer(1, 5 * mm))
    flow.append(Paragraph(_T(lang,
        "Documento generato da Metan.iQ a supporto della verifica di sostenibilità. "
        "Non sostituisce la dichiarazione di sostenibilità né l'attività dell'OdC.",
        "Document generated by Metan.iQ to support sustainability verification. "
        "It does not replace the sustainability declaration nor the Certification Body's work."),
        s["small"]))

    doc.build(flow)
    return buf.getvalue()
