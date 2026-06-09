"""
Generatore Manuale Utente PDF per Metan.iQ — versione bilingue IT / EN.

Uso:
    python build_user_manual.py            # genera entrambi IT + EN
    python build_user_manual.py it         # solo IT
    python build_user_manual.py en         # solo EN

Output:
    C:/Users/CarloSicurini/Downloads/Metan.iQ_Manuale_Utente_IT.pdf
    C:/Users/CarloSicurini/Downloads/Metan.iQ_Manuale_Utente_EN.pdf
"""
import sys
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, ListFlowable, ListItem
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, NextPageTemplate
from reportlab.platypus.frames import Frame

# --- Brand colors -----------------------------------------------------------
NAVY = colors.HexColor("#0B1E3A")
NAVY_DARK = colors.HexColor("#061327")
AMBER = colors.HexColor("#F5B100")
CREAM = colors.HexColor("#F8F4EC")
GREY = colors.HexColor("#666666")
GREY_LIGHT = colors.HexColor("#CCCCCC")
TINT = colors.HexColor("#F2F4F8")
WHITE = colors.white

# --- Output paths -----------------------------------------------------------
OUTPUT_PATHS = {
    "it": r"C:\Users\CarloSicurini\Downloads\Metan.iQ_Manuale_Utente_IT.pdf",
    "en": r"C:\Users\CarloSicurini\Downloads\Metan.iQ_Manuale_Utente_EN.pdf",
}

# ============================================================
# STRINGHE TESTUALI - IT / EN
# ============================================================
S = {
    # Cover
    "doc_title_pdf":    {"it": "Metan.iQ - Manuale Utente",
                         "en": "Metan.iQ - User Manual"},
    "doc_subject":      {"it": "Manuale operativo software Metan.iQ",
                         "en": "Metan.iQ software operating manual"},
    "cover_subtitle1":  {"it": "Decision Intelligence Platform",
                         "en": "Decision Intelligence Platform"},
    "cover_subtitle2":  {"it": "per biometano DM 2022 / RED III",
                         "en": "for biomethane DM 2022 / RED III"},
    "cover_title":      {"it": "MANUALE UTENTE",
                         "en": "USER MANUAL"},
    "cover_tagline":    {"it": "Guida operativa completa - funzioni, calcoli, workflow",
                         "en": "Complete operating guide - features, calculations, workflow"},
    "cover_version":    {"it": "Versione documento: 1.1",
                         "en": "Document version: 1.1"},
    "cover_date":       {"it": "Data emissione: ",
                         "en": "Issue date: "},
    "cover_software":   {"it": "Software: Metan.iQ v0.5.0 - branch dm2022-only",
                         "en": "Software: Metan.iQ v0.5.0 - branch dm2022-only"},
    "cover_copyright":  {"it": "(c) Carlo Sicurini - Tutti i diritti riservati",
                         "en": "(c) Carlo Sicurini - All rights reserved"},
    # Header / footer
    "header_doc":       {"it": "Manuale Utente",
                         "en": "User Manual"},
    "footer_company":   {"it": "(c) Metan.iQ - Decision Intelligence Platform per biometano DM 2022 / RED III",
                         "en": "(c) Metan.iQ - Decision Intelligence Platform for biomethane DM 2022 / RED III"},
    "footer_page":      {"it": "Pag. ",
                         "en": "Page "},
    # TOC
    "toc_title":        {"it": "Indice",
                         "en": "Table of contents"},
    # Sezioni capitoli
    "ch1":   {"it": "1. Scopo del software e contesto normativo",
              "en": "1. Software scope and regulatory context"},
    "ch2":   {"it": "2. Architettura e tecnologie",
              "en": "2. Architecture and technologies"},
    "ch3":   {"it": "3. Avvio dell'app: prima schermata e sidebar",
              "en": "3. Launching the app: first screen and sidebar"},
    "ch4":   {"it": "4. Tab 1 - Conduzione Giornaliera Standard (UNI-TS / RED III)",
              "en": "4. Tab 1 - Daily Operations Standard (UNI-TS / RED III)"},
    "ch5":   {"it": "5. Tab 2 - Conduzione Giornaliera Analisi (BMT / Override EF)",
              "en": "5. Tab 2 - Daily Operations Analysis (BMT / EF Override)"},
    "ch6":   {"it": "6. Tab 3-4 - Risultati Annuali e Pianificazione & BP",
              "en": "6. Tab 3-4 - Annual Results and Planning & BP"},
    "ch7":   {"it": "7. Logica di calcolo GHG (RED III All.V Parte C)",
              "en": "7. GHG calculation logic (RED III Annex V Part C)"},
    "ch8":   {"it": "8. Calcolo aux_factor e bilancio energetico",
              "en": "8. aux_factor calculation and energy balance"},
    "ch9":   {"it": "9. Vincoli normativi e verifica compliance mensile",
              "en": "9. Regulatory constraints and monthly compliance check"},
    "ch10":  {"it": "10. Export: PDF, Excel, CSV",
              "en": "10. Export: PDF, Excel, CSV"},
    "ch11":  {"it": "11. Anagrafica impianto e audit trail",
              "en": "11. Plant registry and audit trail"},
    "ch12":  {"it": "12. FAQ e troubleshooting",
              "en": "12. FAQ and troubleshooting"},
    "appA":  {"it": "Appendice A - Formule normative complete",
              "en": "Appendix A - Complete regulatory formulas"},
    "appB":  {"it": "Appendice B - Costanti fisiche e fattori emissivi",
              "en": "Appendix B - Physical constants and emission factors"},
    "appC":  {"it": "Appendice C - Database biomasse completo (42 voci)",
              "en": "Appendix C - Complete feedstock database (42 entries)"},
}


def t(key, lang):
    """Restituisce la stringa nel linguaggio richiesto, fallback IT."""
    if key not in S:
        return f"[{key}]"
    return S[key].get(lang) or S[key].get("it") or f"[{key}]"


# ============================================================
# STYLES
# ============================================================
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=20, textColor=NAVY, spaceAfter=16, spaceBefore=0,
                    leading=24, keepWithNext=1)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=14, textColor=NAVY, spaceAfter=8, spaceBefore=18,
                    leading=18, borderPadding=0, keepWithNext=1)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=11, textColor=NAVY_DARK, spaceAfter=4, spaceBefore=10,
                    leading=14, keepWithNext=1)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=9.5, textColor=NAVY_DARK, leading=13,
                      alignment=TA_JUSTIFY, spaceAfter=6)
BODY_TIGHT = ParagraphStyle("BodyTight", parent=BODY, spaceAfter=2)
HEADER_CELL = ParagraphStyle("HeaderCell", parent=BODY_TIGHT, fontName="Helvetica-Bold",
                              textColor=WHITE, fontSize=9.5, leading=12,
                              alignment=TA_LEFT)
CODE = ParagraphStyle("Code", parent=styles["Code"], fontName="Courier",
                      fontSize=8.5, textColor=NAVY_DARK, leading=11,
                      leftIndent=10, backColor=TINT)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=8.5, textColor=GREY,
                      leftIndent=8, leading=11, alignment=TA_LEFT)

# ============================================================
# COVER + PAGE TEMPLATES (bilingue via closure)
# ============================================================

def make_cover_page(lang):
    def cover_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(AMBER)
        canvas.rect(0, 0, A4[0], 8*mm, fill=1, stroke=0)
        canvas.rect(0, A4[1]-4*mm, A4[0], 4*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 56)
        canvas.drawString(25*mm, A4[1]-80*mm, "Metan.")
        canvas.setFillColor(AMBER)
        canvas.drawString(25*mm + canvas.stringWidth("Metan.", "Helvetica-Bold", 56),
                          A4[1]-80*mm, "iQ")
        canvas.setFillColor(CREAM)
        canvas.setFont("Helvetica", 14)
        canvas.drawString(25*mm, A4[1]-92*mm, t("cover_subtitle1", lang))
        canvas.drawString(25*mm, A4[1]-99*mm, t("cover_subtitle2", lang))
        canvas.setStrokeColor(AMBER)
        canvas.setLineWidth(2)
        canvas.line(25*mm, A4[1]-115*mm, A4[0]-25*mm, A4[1]-115*mm)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 28)
        canvas.drawString(25*mm, A4[1]-135*mm, t("cover_title", lang))
        canvas.setFillColor(AMBER)
        canvas.setFont("Helvetica", 12)
        canvas.drawString(25*mm, A4[1]-145*mm, t("cover_tagline", lang))
        canvas.setFillColor(CREAM)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(25*mm, 20*mm, t("cover_version", lang))
        canvas.drawString(25*mm, 16*mm,
                          t("cover_date", lang) + date.today().strftime("%d/%m/%Y"))
        canvas.drawString(25*mm, 12*mm, t("cover_software", lang))
        canvas.drawRightString(A4[0]-25*mm, 12*mm, t("cover_copyright", lang))
        canvas.restoreState()
    return cover_page


def make_std_page(lang):
    def std_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1]-18*mm, A4[0], 18*mm, fill=1, stroke=0)
        canvas.setFillColor(AMBER)
        canvas.rect(0, A4[1]-19*mm, A4[0], 1*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(20*mm, A4[1]-12*mm, "Metan.iQ")
        canvas.setFillColor(AMBER)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0]-20*mm, A4[1]-12*mm, t("header_doc", lang))
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(20*mm, 12*mm, t("footer_company", lang))
        canvas.drawRightString(A4[0]-20*mm, 12*mm, f"{t('footer_page', lang)}{doc.page}")
        canvas.setFillColor(AMBER)
        canvas.rect(0, 6*mm, A4[0], 1*mm, fill=1, stroke=0)
        canvas.restoreState()
    return std_page


# ============================================================
# HELPERS
# ============================================================

def p(text, style=BODY):
    return Paragraph(text, style)


def section(title):
    return [PageBreak(), Paragraph(title, H1)]


def subsec(title):
    return Paragraph(title, H2)


def bullet_list(items):
    return ListFlowable(
        [ListItem(p(i), leftIndent=0) for i in items],
        bulletType="bullet", start="-", leftIndent=14,
        bulletFontName="Helvetica-Bold", bulletFontSize=9,
    )


def intro_list(intro_text, items, h2_title=None):
    blocks = []
    if h2_title:
        blocks.append(subsec(h2_title))
    blocks.append(p(intro_text))
    blocks.append(bullet_list(items))
    return KeepTogether(blocks)


def kv_table(rows, col_widths=(70*mm, 100*mm)):
    data = [[p(f"<b>{k}</b>", BODY_TIGHT), p(v, BODY_TIGHT)] for k, v in rows]
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), TINT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, GREY_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def data_table(header, rows, col_widths=None):
    if col_widths is None:
        col_widths = [170*mm / len(header)] * len(header)
    data = [[p(str(c), HEADER_CELL) for c in header]] + \
           [[p(str(c), BODY_TIGHT) for c in r] for r in rows]
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TINT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, GREY_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def intro_table(intro_text, header, rows, col_widths=None, h2_title=None):
    blocks = []
    if h2_title:
        blocks.append(subsec(h2_title))
    blocks.append(p(intro_text))
    blocks.append(data_table(header, rows, col_widths))
    return KeepTogether(blocks)


def callout(text, kind="info"):
    bg = TINT if kind == "info" else colors.HexColor("#FFF4E0")
    border = AMBER if kind == "warn" else GREY_LIGHT
    tbl = Table([[p(text)]], colWidths=[170*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


# ============================================================
# BIOMASSE 42 (estratte da FEEDSTOCK_DB con ast.literal_eval)
# Etichette categoria tradotte. Nomi biomasse mantenuti in IT (sono i nomi
# tecnici-commerciali italiani di filiera, usati in audit RINA/SGS/ISCC e GSE).
# ============================================================

def categoria(lang, key):
    cats = {
        "colture":  {"it": "Colture dedicate",
                     "en": "Energy crops"},
        "effluenti": {"it": "Effluenti zootecnici",
                      "en": "Animal manure"},
        "sottop":   {"it": "Sottoprod. agroindustriali",
                     "en": "Agro-industrial by-products"},
        "forsu":    {"it": "FORSU / Rifiuti",
                     "en": "OFMSW / Waste"},
    }
    return cats[key][lang]


def make_biomasse_42(lang):
    C = lambda k: categoria(lang, k)
    return [
        ["Trinciato di mais",                  C("colture"),  "+29", "0.8", "116.1", "A"],
        ["Trinciato di sorgo da foraggio",     C("colture"),  "+26", "0.8",  "81.4", "A"],
        ["Trinciato di sorgo (energetico)",    C("colture"),  "+26", "0.8",  "90.5", "A"],
        ["Triticale insilato",                 C("colture"),  "+20", "0.8", "106.1", "A"],
        ["Segale insilata",                    C("colture"),  "+22", "0.8",  "80.0", "A"],
        ["Orzo insilato",                      C("colture"),  "+22", "0.8",  "82.0", "A"],
        ["Loietto insilato (ryegrass)",        C("colture"),  "+18", "0.8",  "93.7", "A"],
        ["Erba medica insilata",               C("colture"),  "+15", "0.8",  "70.0", "A"],
        ["Doppia coltura (2° raccolto)",       C("colture"),  "+15", "0.8",  "95.0", "A"],
        ["Erbaio misto insilato",              C("colture"),  "+16", "0.8",  "64.0", "A"],
        ["Barbabietola da zucchero",           C("colture"),  "+12", "0.8", "105.0", "A"],
        ["Liquame suino",                      C("effluenti"), "-45", "0.8",  "14.0", "D"],
        ["Liquame bovino",                     C("effluenti"), "-45", "0.8",  "14.0", "D"],
        ["Liquame bufalino",                   C("effluenti"), "-45", "0.8",  "14.0", "D"],
        ["Letame bovino palabile",             C("effluenti"), "-30", "0.8",  "35.0", "D"],
        ["Letame equino",                      C("effluenti"), "-20", "0.8",  "42.0", "D"],
        ["Pollina ovaiole (aerobico)",         C("effluenti"), "+5",  "0.8",  "84.0", "C"],
        ["Pollina broiler (lettiera)",         C("effluenti"), "-15", "0.8", "105.0", "D"],
        ["Pollina tacchini",                   C("effluenti"), "-10", "0.8", "100.0", "D"],
        ["Deiezioni conigli",                  C("effluenti"), "+5",  "0.8",  "75.0", "C"],
        ["Sansa di olive umida",               C("sottop"),    "+3",  "0.8", "120.0", "C"],
        ["Sansa vergine",                      C("sottop"),    "+2",  "0.8", "140.0", "C"],
        ["Pastazzo di agrumi",                 C("sottop"),    "+6",  "0.8", "100.0", "C"],
        ["Vinaccia (con raspi)",               C("sottop"),    "+5",  "0.8", "130.0", "C"],
        ["Raspi d'uva",                        C("sottop"),    "+3",  "0.8",  "70.0", "C"],
        ["Feccia vinicola",                    C("sottop"),    "+3",  "0.8", "180.0", "C"],
        ["Siero di latte",                     C("sottop"),    "+3",  "0.8",  "30.0", "C"],
        ["Scotta (siero residuo)",             C("sottop"),    "+2",  "0.8",  "22.0", "C"],
        ["Trebbie di birra",                   C("sottop"),    "+4",  "0.8", "140.0", "C"],
        ["Lolla/pula di riso",                 C("sottop"),    "+2",  "0.8",  "50.0", "C"],
        ["Melasso",                            C("sottop"),    "+8",  "0.8", "180.0", "A"],
        ["Scarti panificazione/pasticceria",   C("sottop"),    "+5",  "0.8", "280.0", "C"],
        ["Grassi esausti / UCO",               C("sottop"),    "+2",  "0.8", "700.0", "C"],
        ["Scarti macellazione (cat. 3)",       C("sottop"),    "+5",  "0.8", "180.0", "C"],
        ["Sottoprodotti ortofrutticoli",       C("sottop"),    "+7",  "0.8", "100.0", "A"],
        ["Scarti caseari vari",                C("sottop"),    "+4",  "0.8",  "40.0", "C"],
        ["Fanghi agro-industriali",            C("sottop"),    "+3",  "0.8",  "55.0", "C"],
        ["Polpe di barbabietola fresche",      C("sottop"),     "0",  "2.0",  "50.0", "A/B"],
        ["Polpe di barbabietola insilate",     C("sottop"),     "0",  "2.5",  "75.0", "A/B"],
        ["Melasso di barbabietola",            C("sottop"),     "0",  "1.5", "280.0", "A/B"],
        ["FORSU selezionata",                  C("forsu"),      "0",  "0.8",  "64.8", "A/B"],
        ["Fanghi depurazione",                 C("forsu"),      "0",  "0.8",  "13.0", "A/B"],
    ]


# ============================================================
# CONTENUTI CAPITOLI - lingua selezionata via lang
# Per snellezza: contenuti lunghi in funzioni dedicate
# ============================================================

def build_chapter_1(story, lang):
    story.extend(section(t("ch1", lang)))
    if lang == "it":
        story.append(p(
            "<b>Metan.iQ</b> e' una <b>Decision Intelligence Platform</b> "
            "(piattaforma di intelligenza decisionale) progettata per gli "
            "operatori di <b>impianti di biometano da digestione anaerobica "
            "con immissione in rete</b>, regolati dal <b>DM 15 settembre 2022</b> "
            "(incentivazione del biometano immesso in rete) e dalle direttive "
            "europee <b>RED II (2018/2001)</b> e <b>RED III (2023/2413)</b>."
        ))
        story.append(p(
            "Il software opera in modalita' <b>biometano-only</b> "
            "(APP_MODE = 'biometano' hardcoded nel runtime). Eventuali sezioni "
            "di autoconsumo CHP modellate dall'app si riferiscono al "
            "<b>recupero termico/elettrico interno dall'autoconsumo di una "
            "quota di biometano prodotto</b>, non a un impianto biogas-CHP "
            "standalone che produce direttamente elettricita' in rete."
        ))
        story.append(subsec("1.1 Obiettivi principali"))
        story.append(bullet_list([
            "<b>Tracciare</b> giorno per giorno biomasse caricate e Sm3 netti immessi in rete (letti dalla cabina REMI).",
            "<b>Calcolare</b> il risparmio GHG (saving %) secondo RED III Allegato V Parte C e UNI/TS 11567:2024.",
            "<b>Verificare</b> il rispetto della soglia normativa di saving sul lotto di sostenibilita' MENSILE.",
            "<b>Verificare</b> il rispetto del cap autorizzativo (es. 300 Sm3/h medi mensili).",
            "<b>Ottimizzare</b> il mix biomasse via solver LP per massimizzare saving GHG o ricavi tariffari.",
            "<b>Pianificare</b> il business plan a 15 anni con tariffe DM 2022, premi matrice, PNRR conto capitale.",
            "<b>Esportare</b> dossier audit-ready (PDF, Excel, CSV) per consulenti, OdC, GSE.",
        ]))
        story.append(subsec("1.2 Riferimenti normativi applicati"))
    else:
        story.append(p(
            "<b>Metan.iQ</b> is a <b>Decision Intelligence Platform</b> designed "
            "for operators of <b>biomethane plants from anaerobic digestion with "
            "grid injection</b>, regulated by the Italian <b>Ministerial Decree "
            "15 September 2022</b> (biomethane grid injection incentives) and the "
            "European directives <b>RED II (2018/2001)</b> and <b>RED III (2023/2413)</b>."
        ))
        story.append(p(
            "The software operates in <b>biomethane-only</b> mode "
            "(APP_MODE = 'biometano' hardcoded in the runtime). Any CHP self-consumption "
            "sections refer to <b>internal thermal/electrical recovery from "
            "self-consumption of a fraction of produced biomethane</b>, not to a "
            "standalone biogas-CHP plant injecting electricity into the grid."
        ))
        story.append(subsec("1.1 Main objectives"))
        story.append(bullet_list([
            "<b>Track</b> daily feedstock loaded and net Sm3 injected (REMI cabin readings).",
            "<b>Compute</b> GHG saving (%) per RED III Annex V Part C and UNI/TS 11567:2024.",
            "<b>Verify</b> the saving threshold on the MONTHLY sustainability lot.",
            "<b>Verify</b> the authorisation cap (e.g. 300 Sm3/h monthly average).",
            "<b>Optimise</b> the feedstock mix via LP solver to maximise GHG saving or tariff revenue.",
            "<b>Plan</b> the 15-year business plan with DM 2022 tariffs, matrix premiums, PNRR capital grants.",
            "<b>Export</b> audit-ready dossiers (PDF, Excel, CSV) for consultants, certification bodies, GSE.",
        ]))
        story.append(subsec("1.2 Applied regulatory references"))

    story.append(data_table(
        ["DM 15/09/2022" if lang == "it" else "DM 15/09/2022", "RED III (Dir. UE 2023/2413)",
         "D.Lgs. 199/2021", "D.Lgs. 5/2026", "UNI/TS 11567:2024",
         "GSE Linee Guida 2024", "JEC WTT v5", "Reg. UE 2022/996", "UNI EN 16723-1"][:1] + [{
            "it": "Ambito di applicazione", "en": "Scope of application"
        }[lang]],
        [
            ["DM 15/09/2022", {"it": "Tariffe biometano in rete (TR per taglia, 15 anni)",
                              "en": "Biomethane grid tariffs (size-based, 15 years)"}[lang]],
            ["RED III (Dir. UE 2023/2413)", {"it": "Soglie saving GHG, metodologia Allegato V Parte C",
                                            "en": "GHG saving thresholds, methodology Annex V Part C"}[lang]],
            ["D.Lgs. 199/2021", {"it": "Recepimento italiano RED II",
                                "en": "Italian transposition of RED II"}[lang]],
            ["UNI/TS 11567:2024", {"it": "Calcolo emissioni GHG biocombustibili, rese standard",
                                  "en": "GHG emissions calculation for biofuels, standard yields"}[lang]],
            ["GSE Linee Guida 2024", {"it": "Modalita' operative attuative DM 2022 (Decreto 248/2024)",
                                     "en": "Operating procedures for DM 2022 (Decree 248/2024)"}[lang]],
            ["JEC WTT v5", {"it": "Joint Research Centre Well-to-Tank, fattori emissivi default",
                           "en": "Joint Research Centre Well-to-Tank, default emission factors"}[lang]],
            ["Reg. UE 2022/996", {"it": "GWP aggiornati (CH4 = 28, N2O = 265)",
                                 "en": "Updated GWP values (CH4 = 28, N2O = 265)"}[lang]],
            ["UNI EN 16723-1", {"it": "Specifiche biometano per immissione in rete (LHV, % CH4)",
                               "en": "Biomethane specifications for grid injection (LHV, %CH4)"}[lang]],
        ],
        col_widths=[55*mm, 115*mm]
    ))

    if lang == "it":
        story.append(subsec("1.3 Regola fondamentale di compliance"))
        story.append(callout(
            "<b>La sostenibilita' GHG si verifica sul LOTTO MENSILE, non sul "
            "singolo giorno.</b> Il saving giornaliero in tabella e' solo "
            "informativo. Il verdetto ufficiale <b>Compliant / Non Compliant</b> "
            "e' calcolato sull'aggregato mensile, regola dei <b>Lotti di "
            "Sostenibilita' (LS)</b> della UNI/TS 11567:2024 (durata max 6 mesi, "
            "mensile per prassi GSE).",
            kind="warn"
        ))
        story.append(p(
            "Un mese puo' essere <b>Compliant</b> anche se alcuni giorni isolati "
            "hanno saving giornaliero sotto soglia, purche' la media pesata "
            "sull'energia dell'intero mese rispetti il limite. Questo permette "
            "di compensare giorni 'cattivi' (mais puro) con giorni 'buoni' "
            "(reflui, manure credit)."
        ))
    else:
        story.append(subsec("1.3 Fundamental compliance rule"))
        story.append(callout(
            "<b>GHG sustainability is verified on the MONTHLY LOT, not on the "
            "individual day.</b> Daily saving in the table is purely informative. "
            "The official <b>Compliant / Non Compliant</b> verdict is computed on "
            "the monthly aggregate, following the <b>Sustainability Lots (LS)</b> "
            "rule of UNI/TS 11567:2024 (max duration 6 months, monthly by GSE "
            "practice).",
            kind="warn"
        ))
        story.append(p(
            "A month can be <b>Compliant</b> even when some isolated days fall "
            "below threshold, provided the energy-weighted monthly average "
            "respects the limit. This allows offsetting 'bad' days (pure maize) "
            "with 'good' days (manure, manure credit)."
        ))


def build_chapter_2(story, lang):
    story.extend(section(t("ch2", lang)))
    if lang == "it":
        story.append(p(
            "Metan.iQ e' un'applicazione web su <b>Streamlit</b>. L'utente "
            "interagisce tramite browser, i calcoli avvengono server-side in Python."
        ))
        story.append(subsec("2.1 Stack tecnico"))
    else:
        story.append(p(
            "Metan.iQ is a web application built on <b>Streamlit</b>. The user "
            "interacts through the browser, calculations run server-side in Python."
        ))
        story.append(subsec("2.1 Technical stack"))
    L = lang == "it"
    story.append(kv_table([
        ("Frontend / runtime" if L else "Frontend / runtime", "Streamlit 1.57+ (Python 3.11+)"),
        ("Motore di calcolo" if L else "Calculation engine", "NumPy, SciPy (LP solver), pandas"),
        ("Visualizzazione" if L else "Visualisation", "Plotly, HTML/CSS Material 3 custom"),
        ("Export PDF", "ReportLab (Metan.iQ brand template)"),
        ("Export Excel", "openpyxl (4-6 sheets, conditional formatting)"),
        ("Export PPTX", "python-pptx (8 yearly slides)"),
        ("Persistenza locale" if L else "Local persistence", "SQLite (data/metaniq_daily.db)"),
        ("i18n", "IT/EN dictionary substring replacement"),
        ("Theme", "Light / Dark switcher (navy + amber, Outfit font)"),
        ("Hosting", "Streamlit Cloud (private, branch dm2022-only)"),
    ]))


def build_chapter_3(story, lang):
    story.extend(section(t("ch3", lang)))
    if lang == "it":
        story.append(p(
            "All'apertura dell'URL dell'app si presenta una schermata divisa in:"
        ))
        story.append(bullet_list([
            "<b>Sidebar a sinistra</b>: identita' prodotto, lingua, tema, anagrafica, biomasse e parametri impianto.",
            "<b>Area principale a destra</b>: quattro modalita' di lavoro a step numerato (1 Standard / 2 Analisi / 3 Risultati Annuali / 4 Pianificazione &amp; BP).",
            "<b>Header in alto</b>: brand Metan.iQ con versione e regime attivo.",
            "<b>Footer</b>: versione software; Privacy, Termini e Licenza nell'expander legale a fondo sidebar.",
        ]))
        story.append(subsec("3.1 Sidebar: pannello di controllo globale"))
        intro = "La sidebar contiene, dall'alto in basso, i seguenti gruppi di controlli:"
        rows = [
            ["Lingua", "Selettore IT / EN", "Cambia label, formato numeri e date"],
            ["Tema", "Toggle Light / Dark", "Switcher palette chiaro/scuro"],
            ["Anagrafica simulazione", "Expander: azienda, sede, impianto, P.IVA/CF, CUI/GSE, responsabile sostenibilita'",
             "Tracciabilita' GSE/OdC in report ed export"],
            ["Normative applicate", "Expander informativo", "Registro delle norme cablate nel calcolo"],
            ["Taglia Impianto", "Radio NETTI/LORDI + number input (default 300)",
             "Cap autorizzativo Sm3/h; sincronizzazione lordo/netto via aux"],
            ["Config. Tecnica &amp; GHG", "Expander: digestato, upgrading, off-gas, iniezione, calore, elettricita'",
             "Determina ep_total e aux_factor (default 1.29, override manuale)"],
            ["Biomasse attive", "Ricerca + multiselect per categoria", "Colonne disponibili in tabella giornaliera"],
            ["Manure credit", "Checkbox (default ON)", "Attiva eec negativo per reflui"],
            ["Manuale / Demo / Legali", "Expander a fondo sidebar", "Download manuale PDF, richiesta demo, Privacy/Termini/Licenza"],
        ]
        story.append(intro_table(intro, ["Sezione", "Controllo", "Funzione"], rows,
                                 col_widths=[30*mm, 50*mm, 90*mm]))
        story.append(callout(
            "Anno, mese e ID impianto <b>non</b> stanno in sidebar: si "
            "selezionano in testa al pannello Operativita' Giornaliera "
            "(modalita' 1 e 2), cosi' ogni combinazione impianto+anno+mese "
            "ha il suo set di dati isolato nel database.", "info"
        ))
        story.append(subsec("3.2 Le quattro modalita' di configurazione"))
        story.append(p(
            "L'area principale presenta le quattro tab come un <b>selettore a "
            "step numerato (1 - 2 - 3 - 4)</b>, raggruppate in due famiglie: "
            "<b>operativa</b> (1-2, conduzione mensile sui dati reali) e "
            "<b>strategica</b> (3-4, sintesi annuale ed economia), separate da "
            "uno stacco visivo. Ogni modalita' e' una scheda con titolo e "
            "sottotitolo; la scheda attiva e' evidenziata in navy con barra "
            "d'accento ottone. Su schermo stretto le schede si impilano in "
            "verticale."
        ))
        story.append(intro_table(
            "Le quattro modalita' a confronto:",
            ["#", "Modalita'", "Cosa configura", "Quando usarla"],
            [
                ["1", "Standard",
                 "Solo valori standard (UNI-TS / RED III)",
                 "Conduzione quotidiana di routine, senza analisi di laboratorio."],
                ["2", "Analisi",
                 "Standard + valori personalizzati (BMT &amp; EF)",
                 "Quando hai rese BMT da laboratorio o fattori emissivi su misura."],
                ["3", "Risultati Annuali",
                 "Consuntivo reale 12 mesi (dati DB)",
                 "Vedere produzione, saving e grafici sui dati realmente immessi."],
                ["4", "Pianificazione &amp; BP",
                 "Incentivi DM 2022, scenario what-if, pro forma 15 anni",
                 "Configurare tariffe, simulare e costruire il business plan."],
            ],
            col_widths=[8*mm, 38*mm, 60*mm, 64*mm]
        ))
        story.append(callout(
            "Distinzione chiave: la modalita' 3 mostra il <b>consuntivo REALE</b> "
            "(forward, dai dati salvati), la 4 lavora su uno <b>scenario di "
            "pianificazione</b> (solver inverso). Tutte condividono mese, biomasse "
            "e parametri della sidebar.", "info"
        ))
    else:
        story.append(p(
            "Opening the app URL presents a screen split into:"
        ))
        story.append(bullet_list([
            "<b>Left sidebar</b>: product identity, language, theme, registry, feedstocks and plant parameters.",
            "<b>Main area on the right</b>: four working modes as a numbered step selector (1 Standard / 2 Analysis / 3 Annual Results / 4 Planning &amp; BP).",
            "<b>Top header</b>: Metan.iQ brand with version and active regime.",
            "<b>Footer</b>: software version; Privacy, Terms and License in the legal expander at the bottom of the sidebar.",
        ]))
        story.append(subsec("3.1 Sidebar: global control panel"))
        intro = "From top to bottom, the sidebar contains the following control groups:"
        rows = [
            ["Language", "Selector IT / EN", "Switches labels, number and date format"],
            ["Theme", "Light / Dark toggle", "Light/dark palette switcher"],
            ["Simulation registry", "Expander: company, address, plant, VAT, GSE code, sustainability officer",
             "GSE/CB traceability in reports and exports"],
            ["Applied regulations", "Informative expander", "Registry of the norms wired into the engine"],
            ["Plant Size", "NET/GROSS radio + number input (default 300)",
             "Authorisation cap Sm3/h; gross/net sync via aux"],
            ["Technical &amp; GHG Config", "Expander: digestate, upgrading, off-gas, injection, heat, electricity",
             "Determines ep_total and aux_factor (default 1.29, manual override)"],
            ["Active feedstocks", "Search + multiselect by category", "Available columns in the daily table"],
            ["Manure credit", "Checkbox (default ON)", "Enables negative eec for manure"],
            ["Manual / Demo / Legal", "Expander at sidebar bottom", "Manual PDF download, demo request, Privacy/Terms/License"],
        ]
        story.append(intro_table(intro, ["Section", "Control", "Function"], rows,
                                 col_widths=[30*mm, 50*mm, 90*mm]))
        story.append(callout(
            "Year, month and plant ID are <b>not</b> in the sidebar: they are "
            "selected at the top of the Daily Operations panel (modes 1 and 2), "
            "so each plant+year+month combination has its own isolated data set "
            "in the database.", "info"
        ))
        story.append(subsec("3.2 The four configuration modes"))
        story.append(p(
            "The main area presents the four tabs as a <b>numbered step "
            "selector (1 - 2 - 3 - 4)</b>, grouped into two families: "
            "<b>operational</b> (1-2, monthly operation on real data) and "
            "<b>strategic</b> (3-4, annual summary and economics), separated by a "
            "visual gap. Each mode is a card with a title and subtitle; the "
            "active card is highlighted in navy with a brass accent bar. On a "
            "narrow screen the cards stack vertically."
        ))
        story.append(intro_table(
            "The four modes compared:",
            ["#", "Mode", "What it configures", "When to use it"],
            [
                ["1", "Standard",
                 "Standard values only (UNI-TS / RED III)",
                 "Routine daily operation, without lab analysis."],
                ["2", "Analysis",
                 "Standard + custom values (BMT &amp; EF)",
                 "When you have BMT lab yields or custom emission factors."],
                ["3", "Annual Results",
                 "Real 12-month actuals (DB data)",
                 "See production, saving and charts on actually injected data."],
                ["4", "Planning &amp; BP",
                 "DM 2022 incentives, what-if scenario, 15-year pro forma",
                 "Configure tariffs, simulate and build the business plan."],
            ],
            col_widths=[8*mm, 38*mm, 60*mm, 64*mm]
        ))
        story.append(callout(
            "Key distinction: mode 3 shows the <b>REAL actuals</b> (forward, from "
            "saved data), mode 4 works on a <b>planning scenario</b> (inverse "
            "solver). All share the month, feedstocks and sidebar parameters.",
            "info"
        ))


def build_chapter_workflow(story, lang):
    """Capitoli 4-6: Tabs."""
    story.extend(section(t("ch4", lang)))
    L = lang == "it"
    if L:
        story.append(p(
            "<b>Modalita' 1 - Standard</b> (sottotitolo: <i>Solo valori standard - "
            "UNI-TS / RED III</i>). Tab di lavoro principale per la "
            "<b>gestione quotidiana</b>. "
            "Usa rese e fattori emissivi <b>standard</b> UNI/TS 11567:2024 "
            "(Prospetto A.5). Indicato per uso routinario senza analisi BMT."
        ))
        story.append(subsec("4.1 Tabella biomasse giornaliere"))
        story.append(p(
            "Tabella centrale: una riga per ogni giorno del mese, colonne "
            "dinamiche in base alle biomasse selezionate in sidebar."
        ))
        story.append(intro_list(
            "<b>Colonne tipiche:</b>",
            [
                "<b>Data</b> - generata automaticamente.",
                "<b>Biomassa 1, 2, ...</b> - una colonna per biomassa attiva, input in t/giorno.",
                "<b>Sm3 lordi</b> - calcolato (massa x resa).",
                "<b>Sm3 netti</b> - <b>INSERITO DALL'OPERATORE</b> il giorno dopo (lettura REMI).",
                "<b>Sm3/h netti</b> - Sm3 netti / ore funzionamento.",
                "<b>MWh</b> - Sm3 netti x NM3_TO_MWH (0.00979).",
                "<b>eec/esca/etd/ep</b> - emissioni componenti.",
                "<b>e_total</b> - somma in gCO2eq/MJ.",
                "<b>Saving giornaliero</b> - (80 - e_total) / 80 x 100, solo informativo.",
                "<b>Cap OK</b> - True se Sm3/h netti <= cap.",
                "<b>Cumulato Sm3/MWh/t</b> - progressivi mese.",
            ]
        ))
        story.append(subsec("4.2 Selezione periodo e salvataggio automatico"))
        story.append(p(
            "In testa al pannello si scelgono <b>Anno</b>, <b>Periodo di "
            "rendicontazione</b> (mese) e <b>ID impianto</b>: ogni combinazione "
            "impianto+anno+mese ha un set di dati isolato nel database. Le "
            "modifiche alla tabella sono <b>salvate automaticamente</b> (nessun "
            "bottone Salva): a ogni modifica valida compare la conferma "
            "<i>Auto-salvato HH:MM:SS</i>. Nell'expander <b>Operazioni mese</b> "
            "sono disponibili <b>Ricarica da DB</b> (ripristina l'ultimo "
            "salvataggio) e <b>Azzera mese</b> (riparte da tabella vuota)."
        ))
        story.append(intro_list(
            "Sotto la tabella appaiono 4 metriche principali:",
            [
                "<b>Biomassa mese (t)</b>",
                "<b>Sm3 netti mese</b>",
                "<b>MWh netti mese</b>",
                "<b>Saving GHG (%)</b> con badge <b>COMPLIANT</b> / <b>NON COMPLIANT</b>",
            ],
            h2_title="4.3 KPI mensili"
        ))
        story.append(subsec("4.4 Consolidato REMI mese"))
        story.append(p(
            "Se sono presenti letture del contatore fiscale, il pannello "
            "<b>Consolidato REMI</b> riepiloga i dati di cabina: volume Vb, "
            "energia E (kWh), portata massima Qb, PCI medio, portata e potenza "
            "media, energia specifica. L'energia specifica E/Vb deve "
            "avvicinarsi a ~9.79 kWh/Sm3 (UNI EN 16723-1): scostamenti ampi "
            "indicano biometano fuori specifica o errore di lettura."
        ))
    else:
        story.append(p(
            "<b>Mode 1 - Standard</b> (subtitle: <i>Standard values only - "
            "UNI-TS / RED III</i>). Main working tab for <b>daily management</b>. "
            "Uses <b>standard</b> "
            "yields and emission factors from UNI/TS 11567:2024 (Schedule A.5). "
            "Recommended for routine use without BMT analysis."
        ))
        story.append(subsec("4.1 Daily feedstock table"))
        story.append(p(
            "Central table: one row per day of the month, dynamic columns based "
            "on the feedstocks selected in the sidebar."
        ))
        story.append(intro_list(
            "<b>Typical columns:</b>",
            [
                "<b>Date</b> - auto-generated.",
                "<b>Feedstock 1, 2, ...</b> - one column per active feedstock, input in t/day.",
                "<b>Gross Sm3</b> - computed (mass x yield).",
                "<b>Net Sm3</b> - <b>ENTERED BY OPERATOR</b> next day (REMI reading).",
                "<b>Net Sm3/h</b> - Net Sm3 / operating hours.",
                "<b>MWh</b> - Net Sm3 x NM3_TO_MWH (0.00979).",
                "<b>eec/esca/etd/ep</b> - component emissions.",
                "<b>e_total</b> - sum in gCO2eq/MJ.",
                "<b>Daily saving</b> - (80 - e_total) / 80 x 100, informative only.",
                "<b>Cap OK</b> - True if Net Sm3/h <= cap.",
                "<b>Cumulative Sm3/MWh/t</b> - month-to-date progressives.",
            ]
        ))
        story.append(subsec("4.2 Period selection and auto-save"))
        story.append(p(
            "At the top of the panel you select <b>Year</b>, <b>Reporting "
            "period</b> (month) and <b>Plant ID</b>: each plant+year+month "
            "combination has an isolated data set in the database. Table "
            "edits are <b>saved automatically</b> (no Save button): on every "
            "valid change the confirmation <i>Auto-saved HH:MM:SS</i> appears. "
            "The <b>Month operations</b> expander offers <b>Reload from DB</b> "
            "(restores the last save) and <b>Reset month</b> (starts from an "
            "empty table)."
        ))
        story.append(intro_list(
            "Below the table, 4 main metrics are displayed:",
            [
                "<b>Monthly feedstock (t)</b>",
                "<b>Net Sm3 month</b>",
                "<b>Net MWh month</b>",
                "<b>GHG Saving (%)</b> with <b>COMPLIANT</b> / <b>NON COMPLIANT</b> badge",
            ],
            h2_title="4.3 Monthly KPIs"
        ))
        story.append(subsec("4.4 Monthly REMI consolidation"))
        story.append(p(
            "If fiscal-meter readings are present, the <b>REMI "
            "consolidation</b> panel summarises the metering-station data: "
            "volume Vb, energy E (kWh), max flow Qb, average HHV/LHV, average "
            "flow and power, specific energy. The specific energy E/Vb should "
            "approach ~9.79 kWh/Sm3 (UNI EN 16723-1): large deviations "
            "indicate off-spec biomethane or a reading error."
        ))

    # Cap 5 - Tab 2
    story.extend(section(t("ch5", lang)))
    if L:
        story.append(p(
            "<b>Modalita' 2 - Analisi</b> (sottotitolo: <i>Standard + valori "
            "personalizzati - BMT &amp; EF</i>). "
            "Variante avanzata del Tab 1, per operatori con BMT (Biological "
            "Methane Potential, test laboratorio) e/o Relazione Tecnica con "
            "fattori emissivi su misura. I valori personalizzati si "
            "<b>sovrappongono</b> ai tabellari, biomassa per biomassa; senza "
            "override la modalita' calcola identica alla Standard."
        ))
        story.append(subsec("5.1 Override BMT (rese)"))
        story.append(p(
            "Sostituisce le rese standard A.3 UNI/TS 11567:2024 con valori "
            "da analisi lab. Riconciliazione mass balance <= +/-15% per LS valido."
        ))
        story.append(subsec("5.2 Override fattori emissivi"))
        story.append(bullet_list([
            "<b>eec</b> custom per biomasse non tabulate o dichiarazioni fornitore.",
            "<b>ep</b> custom da bilancio energetico reale impianto.",
            "<b>etd</b> custom da rilievo logistico.",
        ]))
        story.append(subsec("5.3 Ponderazione Umidita' / Sostanza Secca"))
        story.append(p(
            "Per ogni biomassa si puo' dichiarare la <b>sostanza secca reale "
            "(%)</b> misurata sul carico: la resa standard viene riponderata "
            "sul tenore di secco effettivo (UNI/TS 11567:2024), allineando il "
            "calcolo alla qualita' reale della biomassa senza richiedere un "
            "BMT di laboratorio."
        ))
    else:
        story.append(p(
            "<b>Mode 2 - Analysis</b> (subtitle: <i>Standard + custom values - "
            "BMT &amp; EF</i>). "
            "Advanced variant of Tab 1, for operators with BMT (Biological "
            "Methane Potential lab test) and/or Technical Report with custom "
            "emission factors. Custom values <b>override</b> the tabular ones "
            "feedstock by feedstock; with no override the mode computes "
            "identically to Standard."
        ))
        story.append(subsec("5.1 BMT override (yields)"))
        story.append(p(
            "Replaces standard yields A.3 UNI/TS 11567:2024 with lab values. "
            "Mass balance reconciliation must stay within +/-15% for valid LS."
        ))
        story.append(subsec("5.2 Emission factors override"))
        story.append(bullet_list([
            "<b>eec</b> custom for non-tabulated feedstocks or supplier declarations.",
            "<b>ep</b> custom from real plant energy balance.",
            "<b>etd</b> custom from logistic survey.",
        ]))
        story.append(subsec("5.3 Moisture / Dry Matter weighting"))
        story.append(p(
            "For each feedstock you can declare the <b>actual dry matter "
            "(%)</b> measured on the load: the standard yield is re-weighted "
            "on the effective dry content (UNI/TS 11567:2024), aligning the "
            "calculation with the real feedstock quality without requiring a "
            "lab BMT."
        ))

    # Cap 6 - Tab 3
    story.extend(section(t("ch6", lang)))
    if L:
        story.append(p(
            "<b>Famiglia strategica</b> — due tab distinti. <b>3 Risultati "
            "Annuali</b>: consuntivo REALE dei 12 mesi salvati (produzione, "
            "saving, grafici sui dati effettivamente immessi). <b>4 "
            "Pianificazione &amp; Business Plan</b>: incentivi DM 2022, scenario "
            "what-if con solver inverso, pro forma 15 anni. Le sezioni che "
            "seguono descrivono i contenuti, distribuiti tra i due tab."
        ))
        story.append(subsec("6.1 Configurazione impianto (ep)"))
        story.append(p(
            "Definisce il bilancio energetico, da cui derivano <b>aux_factor</b> "
            "(tecnologia upgrading, gestione off-gas, fonti calore/elettricita') "
            "e <b>ep_total</b> (somma EP_UPGRADING + EP_OFFGAS + EP_HEAT + EP_ELEC). "
            "ep_total e' vincolato a <b>>= 0</b> per RED III All.V Parte C."
        ))
        story.append(subsec("6.2 DM 2022 - Tariffe e premi"))
        story.append(bullet_list([
            "Taglia impianto (scaglione Sm3/h) determina la TR.",
            "Ribasso d'asta applicato in gara GSE.",
            "Premi matrice cumulabili (Annex IX, kWh recuperato, lavoro agricolo, cogen).",
            "PNRR conto capitale (max 40% contributo).",
        ]))
        story.append(subsec("6.3 Business plan 15 anni"))
        story.append(bullet_list([
            "CAPEX per voce, scalato con plant_size.",
            "OPEX annuale per voce (O&M, gestore, service, assicurazioni).",
            "Finanziamento a leva (default 70% leverage, 5% tasso, 15 anni).",
            "Conto economico con ricavi tariffari, OPEX, ammortamenti, imposte.",
            "Free Cash Flow + NPV, IRR, payback.",
        ]))
    else:
        story.append(p(
            "<b>Strategic family</b> — two distinct tabs. <b>3 Annual Results</b>: "
            "REAL 12-month actuals (production, saving, charts on actually "
            "injected data). <b>4 Planning &amp; Business Plan</b>: DM 2022 "
            "incentives, what-if scenario with inverse solver, 15-year pro forma. "
            "The sections below describe the contents, split across the two tabs."
        ))
        story.append(subsec("6.1 Plant configuration (ep)"))
        story.append(p(
            "Defines the energy balance, which determines <b>aux_factor</b> "
            "(upgrading technology, off-gas handling, heat/electricity sources) "
            "and <b>ep_total</b> (sum of EP_UPGRADING + EP_OFFGAS + EP_HEAT + "
            "EP_ELEC). ep_total is constrained to <b>>= 0</b> per RED III "
            "Annex V Part C."
        ))
        story.append(subsec("6.2 DM 2022 - Tariffs and premiums"))
        story.append(bullet_list([
            "Plant size (Sm3/h bracket) determines the reference tariff (TR).",
            "Auction discount applied in GSE tender.",
            "Cumulative matrix premiums (Annex IX, recovered kWh, farm labour, cogen).",
            "PNRR capital grant (max 40% contribution).",
        ]))
        story.append(subsec("6.3 15-year business plan"))
        story.append(bullet_list([
            "CAPEX by line item, scaled with plant_size.",
            "Annual OPEX by line item (O&M, manager, service, insurance).",
            "Leveraged financing (default 70% leverage, 5% rate, 15 years).",
            "Income statement: tariff revenue, OPEX, depreciation, taxes.",
            "Free Cash Flow + NPV, IRR, payback.",
        ]))


def build_chapter_7(story, lang):
    story.extend(section(t("ch7", lang)))
    L = lang == "it"
    if L:
        story.append(p(
            "Questa sezione descrive analiticamente la formula GHG. E' il cuore "
            "tecnico-normativo del prodotto e ogni numero in output deriva da queste relazioni."
        ))
        story.append(subsec("7.1 Formula generale RED III"))
        story.append(p("Per ogni Lotto di Sostenibilita' (LS = mese aggregato):"))
        story.append(callout(
            "<b>E = eec + el + ep + etd + eu - esca - eccs - eccr</b><br/>"
            "[gCO2eq / MJ biometano]<br/><br/>"
            "Risparmio (%) = (FFC - E) / FFC x 100"
        ))
        rows = [
            ["eec", "Estrazione/coltivazione materie prime", "0 (rifiuti) a +29 (mais)"],
            ["el", "Lavorazione (digestione)", "incluso in ep nel modello"],
            ["ep", "Processing (upgrading, calore, elettr.)", "0-10, cap >= 0"],
            ["etd", "Trasporto e distribuzione", "0.8 (default standard)"],
            ["eu", "Uso del carburante", "0 (biometano rete)"],
            ["esca", "Credito C nel suolo", "0 (default)"],
            ["eccs/eccr", "Credito cattura CO2", "0 (default)"],
            ["FFC", "Comparatore fossile", "80 rete/calore, 94 trasporti, 183 elettricita'"],
        ]
        story.append(data_table(["Termine", "Significato", "Tipico biometano"], rows,
                                col_widths=[20*mm, 90*mm, 60*mm]))
        story.append(subsec("7.2 Calcolo aggregato sul lotto mensile"))
        story.append(p(
            "<b>NON e' una media aritmetica dei saving giornalieri</b>. Per "
            "UNI/TS 11567:2024 e RED III All.V Parte C, l'aggregazione avviene "
            "sull'energia totale del lotto:"
        ))
        story.append(callout(
            "<b>e_w_lotto = SOMMA (e_biomassa_i x Energia_biomassa_i) / "
            "SOMMA (Energia_biomassa_i)</b><br/><br/>"
            "Energia_i = massa_i x resa_CH4_i x LHV<br/>"
            "e_biomassa_i = eec_i + esca_i + etd_i + ep<br/><br/>"
            "Saving_lotto = (FFC - e_w_lotto) / FFC x 100"
        ))
        story.append(p(
            "Giorni con saving giornaliero <80% non rendono il mese non conforme: "
            "vengono diluiti da giorni a saving alto grazie alla pesatura sull'energia."
        ))
        story.append(subsec("7.3 Sistema tier difendibilita' eec (A/B/C/D)"))
        tier_rows = [
            ["A - Default normativo", "Tabellato Prospetto A.5 UNI/TS", "Mais 29, Sorgo 26, rifiuti 0"],
            ["B - Zero da regola", "Residuo Annex IX non tabulato", "0 (regola residui)"],
            ["C - Stima conservativa", "Letteratura JEC/KTBL a sfavore", "positivo, non contestabile"],
            ["D - Manure credit", "Credito reflui zootecnici", "negativo (-45 std), baseline fornitore"],
        ]
        story.append(data_table(["Tier", "Significato", "eec tipico"], tier_rows,
                                col_widths=[40*mm, 70*mm, 60*mm]))
        story.append(subsec("7.4 Manure credit (Tier D)"))
        story.append(p(
            "Per reflui zootecnici il software applica per default eec <b>-45 "
            "gCO2eq/MJ</b> (RED III All.V/VI). Riflette le emissioni metano "
            "<b>evitate</b> rispetto a stoccaggio in vasca/lagone aperto."
        ))
        story.append(callout(
            "Il manure credit richiede <b>dichiarazione baseline fornitore</b> "
            "in audit OdC. Se fornitore stocca in vasca COPERTA con captazione "
            "o N-stripping, il credit va ridotto o annullato.",
            kind="warn"
        ))
    else:
        story.append(p(
            "This chapter analytically describes the GHG formula. It is the "
            "regulatory-technical core of the product: every output number derives from these relations."
        ))
        story.append(subsec("7.1 RED III general formula"))
        story.append(p("For each Sustainability Lot (LS = monthly aggregate):"))
        story.append(callout(
            "<b>E = eec + el + ep + etd + eu - esca - eccs - eccr</b><br/>"
            "[gCO2eq / MJ biomethane]<br/><br/>"
            "Saving (%) = (FFC - E) / FFC x 100"
        ))
        rows = [
            ["eec", "Feedstock extraction/cultivation", "0 (waste) to +29 (maize)"],
            ["el", "Processing (digestion)", "included in ep in this model"],
            ["ep", "Processing (upgrading, heat, electr.)", "0-10, cap >= 0"],
            ["etd", "Transport and distribution", "0.8 (standard default)"],
            ["eu", "Fuel use", "0 (grid biomethane)"],
            ["esca", "Soil C accumulation credit", "0 (default)"],
            ["eccs/eccr", "CO2 capture credit", "0 (default)"],
            ["FFC", "Fossil fuel comparator", "80 grid/heat, 94 transport, 183 electricity"],
        ]
        story.append(data_table(["Term", "Meaning", "Typical biomethane"], rows,
                                col_widths=[20*mm, 90*mm, 60*mm]))
        story.append(subsec("7.2 Aggregation on the monthly lot"))
        story.append(p(
            "<b>It is NOT an arithmetic mean of daily savings</b>. Per UNI/TS "
            "11567:2024 and RED III Annex V Part C, aggregation is energy-weighted on the total lot:"
        ))
        story.append(callout(
            "<b>e_w_lot = SUM (e_feedstock_i x Energy_feedstock_i) / "
            "SUM (Energy_feedstock_i)</b><br/><br/>"
            "Energy_i = mass_i x CH4_yield_i x LHV<br/>"
            "e_feedstock_i = eec_i + esca_i + etd_i + ep<br/><br/>"
            "Saving_lot = (FFC - e_w_lot) / FFC x 100"
        ))
        story.append(p(
            "Days with daily saving <80% do not make the month non-compliant: "
            "they are diluted by high-saving days through energy weighting."
        ))
        story.append(subsec("7.3 eec defensibility tiers (A/B/C/D)"))
        tier_rows = [
            ["A - Regulatory default", "Tabulated Schedule A.5 UNI/TS", "Maize 29, Sorghum 26, waste 0"],
            ["B - Zero by rule", "Non-tabulated Annex IX residue", "0 (residue rule)"],
            ["C - Conservative estimate", "JEC/KTBL literature against operator", "positive, non-contestable"],
            ["D - Manure credit", "Animal manure credit", "negative (-45 std), supplier baseline required"],
        ]
        story.append(data_table(["Tier", "Meaning", "Typical eec"], tier_rows,
                                col_widths=[40*mm, 70*mm, 60*mm]))
        story.append(subsec("7.4 Manure credit (Tier D)"))
        story.append(p(
            "For animal manure the software applies by default eec <b>-45 "
            "gCO2eq/MJ</b> (RED III Annex V/VI). It reflects methane emissions "
            "<b>avoided</b> compared to open tank/lagoon storage."
        ))
        story.append(callout(
            "The manure credit requires a <b>supplier baseline declaration</b> "
            "during certification body audit. If the supplier uses a COVERED "
            "tank with capture or N-stripping, the credit must be reduced or removed.",
            kind="warn"
        ))


def build_chapter_8(story, lang):
    story.extend(section(t("ch8", lang)))
    L = lang == "it"
    if L:
        story.append(p(
            "L'<b>aux_factor</b> e' il rapporto Sm3 biometano lordi / Sm3 netti "
            "immessi in rete. Tiene conto degli autoconsumi energetici."
        ))
        story.append(subsec("8.1 Formula"))
        story.append(callout(
            "<b>aux_factor = 1 / (1 - f_calore - f_elettr - f_slip - f_margine)</b><br/><br/>"
            "Sm3_netti = Sm3_lordi / aux_factor"
        ))
        story.append(bullet_list([
            "<b>f_calore</b> - frazione biometano per caldaia digestore (0 se calore esterno).",
            "<b>f_elettrico</b> - frazione bruciata in CHP interno (0 se elettricita' da rete o FV).",
            "<b>f_slip</b> - perdite CH4 in upgrading (0.5%-2%).",
            "<b>f_margine</b> - margine prudenziale (3% default).",
        ]))
        story.append(subsec("8.2 Default e range tipici"))
    else:
        story.append(p(
            "The <b>aux_factor</b> is the ratio of gross biomethane Sm3 to net "
            "Sm3 injected. It accounts for the plant's energy self-consumption."
        ))
        story.append(subsec("8.1 Formula"))
        story.append(callout(
            "<b>aux_factor = 1 / (1 - f_heat - f_elec - f_slip - f_margin)</b><br/><br/>"
            "Net_Sm3 = Gross_Sm3 / aux_factor"
        ))
        story.append(bullet_list([
            "<b>f_heat</b> - biomethane fraction for digester boiler (0 if external heat).",
            "<b>f_elec</b> - fraction burned in internal CHP (0 if grid or PV).",
            "<b>f_slip</b> - CH4 losses in upgrading (0.5%-2%).",
            "<b>f_margin</b> - prudential margin (3% default).",
        ]))
        story.append(subsec("8.2 Default and typical ranges"))
    story.append(kv_table([
        ("DEFAULT_AUX_FACTOR", "1.29 (JRC-CONCAWE)"),
        ("Amine + thermal self-consumption", "1.20 - 1.32"),
        ("PSA + grid electricity", "1.10 - 1.18"),
        ("Membranes + cogen", "1.15 - 1.25"),
        ("Manual override", "Available in 'Config Tecnica & GHG'"),
    ]))


def build_chapter_9(story, lang):
    story.extend(section(t("ch9", lang)))
    L = lang == "it"
    if L:
        story.append(p("Il software verifica automaticamente DUE vincoli a fine mese:"))
        story.append(subsec("9.1 Vincolo A - Soglia saving GHG"))
        rows = [
            ["Prima 5 ott 2015", "Trasporti", "50%"],
            ["5 ott 2015 - 31 dic 2020", "Trasporti", "60%"],
            ["Dal 1 gen 2021", "Trasporti", "65%"],
            ["Dal 1 gen 2021", "Elettricita' / calore (>1 MW)", "70%"],
            ["Dal 1 gen 2026 (impianti nuovi)", "Elettricita' / calore", "80%"],
        ]
        story.append(data_table(["Entrata in servizio impianto", "Uso", "Soglia"], rows,
                                col_widths=[60*mm, 60*mm, 50*mm]))
        story.append(callout(
            "La data rilevante e' quella di <b>entrata in servizio dell'impianto "
            "di biogas originario</b>, NON dell'upgrading."
        ))
        story.append(subsec("9.2 Vincolo B - Cap autorizzativo Sm3/h"))
        story.append(p(
            "Verifica che la portata media mensile non superi il cap dell'AUA / "
            "AIA. Default 300 Sm3/h, modificabile in sidebar."
        ))
        story.append(subsec("9.3 Esito finale"))
        story.append(p(
            "Il mese e' <b>COMPLIANT</b> se ENTRAMBI i vincoli sono soddisfatti. "
            "Il PDF mensile mostra badge verde/rosso e margine in punti percentuali."
        ))
    else:
        story.append(p("The software automatically verifies TWO month-end constraints:"))
        story.append(subsec("9.1 Constraint A - GHG saving threshold"))
        rows = [
            ["Before 5 Oct 2015", "Transport", "50%"],
            ["5 Oct 2015 - 31 Dec 2020", "Transport", "60%"],
            ["From 1 Jan 2021", "Transport", "65%"],
            ["From 1 Jan 2021", "Electricity / heat (>1 MW)", "70%"],
            ["From 1 Jan 2026 (new plants)", "Electricity / heat", "80%"],
        ]
        story.append(data_table(["Plant commissioning date", "End use", "Threshold"], rows,
                                col_widths=[60*mm, 60*mm, 50*mm]))
        story.append(callout(
            "The relevant date is the <b>commissioning date of the ORIGINAL "
            "biogas plant</b>, NOT of the upgrading."
        ))
        story.append(subsec("9.2 Constraint B - Authorisation cap Sm3/h"))
        story.append(p(
            "Verifies that the monthly average flow rate does not exceed the "
            "AUA / AIA cap. Default 300 Sm3/h, configurable in the sidebar."
        ))
        story.append(subsec("9.3 Final outcome"))
        story.append(p(
            "The month is <b>COMPLIANT</b> if BOTH constraints are met. The "
            "monthly PDF shows a green/red badge and margin in percentage points."
        ))


def build_chapter_10(story, lang):
    story.extend(section(t("ch10", lang)))
    L = lang == "it"
    if L:
        story.append(subsec("10.1 PDF mensile (7 pagine)"))
        rows = [
            ["1", "Copertina - Esito ufficiale, KPI principali"],
            ["2", "Riepilogo KPI mensili + Vincoli normativi"],
            ["3", "Indicazioni operative (azioni correttive fine mese)"],
            ["4-5", "Tabella giornaliera dettagliata (26 colonne)"],
            ["6", "Anagrafica simulazione & Audit Trail"],
            ["7", "Riferimenti normativi & Validazione"],
        ]
        story.append(data_table(["Pag.", "Contenuto"], rows, col_widths=[15*mm, 155*mm]))
        story.append(subsec("10.2 Excel mensile (6 fogli)"))
        story.append(bullet_list([
            "<b>Riepilogo Mensile</b> - esito, KPI principali, totali biomasse.",
            "<b>Operativita' Giornaliera</b> - tabella 26 colonne, 28-31 righe.",
            "<b>Confronto Standard vs Analisi</b> - delta tra le due modalita'.",
            "<b>Override Attivi</b> - BMT, sostanza secca e fattori emissivi in uso.",
            "<b>Anagrafica & Parametri</b> - voci tracciabilita' per audit.",
            "<b>Vincoli</b> - esito per ogni vincolo regime.",
        ]))
        story.append(subsec("10.3 CSV"))
        story.append(p(
            "Separatore <b>;</b>, decimale <b>,</b>, UTF-8 con BOM. Apertura "
            "diretta in Excel italiano. Contiene tabella giornaliera completa."
        ))
        story.append(subsec("10.4 Dossier Conformita' OdC"))
        story.append(bullet_list([
            "Tutti i parametri di calcolo con fonte normativa.",
            "Mass balance del lotto: scarto biomassa vs biometano (<= +/- 15%).",
            "Origine rese (standard / BMT).",
            "Origine fattori emissivi (standard / Relazione Tecnica).",
            "Lista DDT di ingresso e fornitori.",
            "Dichiarazioni di sostenibilita' fornitori.",
        ]))
        story.append(subsec("10.5 Export annuali e di pianificazione"))
        story.append(p(
            "Oltre agli export mensili, le modalita' 3 e 4 offrono:"
        ))
        story.append(bullet_list([
            "<b>Excel consolidato annuale</b> e <b>Report PDF annuale</b> - sintesi 12 mesi (tab Risultati Annuali).",
            "<b>Presentazione PPTX</b> - 8 slide annuali pronte per il management (python-pptx).",
            "<b>Excel modificabile</b> - piano mensile riapribile e ricaricabile per iterare lo scenario.",
            "<b>Excel snapshot</b> - fotografia immutabile dello scenario corrente.",
            "<b>CSV piano mensile</b> - tabella di pianificazione per integrazione con altri sistemi.",
            "<b>PDF Business Plan (15 anni)</b> - landscape brand Metan.iQ: parametri di input, KPI "
            "CAPEX/IRR/NPV/payback, conto economico e flussi di cassa anno per anno, grafico cash flow equity.",
        ]))
    else:
        story.append(subsec("10.1 Monthly PDF (7 pages)"))
        rows = [
            ["1", "Cover - Official outcome, main KPIs"],
            ["2", "Monthly KPI summary + regulatory constraints"],
            ["3", "Operational guidance (month-end corrective actions)"],
            ["4-5", "Detailed daily table (26 columns)"],
            ["6", "Simulation registry & Audit Trail"],
            ["7", "Regulatory references & Validation"],
        ]
        story.append(data_table(["Page", "Content"], rows, col_widths=[15*mm, 155*mm]))
        story.append(subsec("10.2 Monthly Excel (6 sheets)"))
        story.append(bullet_list([
            "<b>Monthly Summary</b> - outcome, main KPIs, feedstock totals.",
            "<b>Daily Operations</b> - 26-column table, 28-31 rows.",
            "<b>Standard vs Analysis Comparison</b> - delta between the two modes.",
            "<b>Active Overrides</b> - BMT, dry matter and emission factors in use.",
            "<b>Registry & Parameters</b> - traceability entries for audit.",
            "<b>Constraints</b> - outcome for each regime constraint.",
        ]))
        story.append(subsec("10.3 CSV"))
        story.append(p(
            "Separator <b>;</b>, decimal <b>,</b>, UTF-8 with BOM. Opens "
            "directly in Italian Excel. Contains the complete daily table."
        ))
        story.append(subsec("10.4 Certification Body Conformity Dossier"))
        story.append(bullet_list([
            "All calculation parameters with regulatory source.",
            "Lot mass balance: feedstock vs biomethane deviation (<= +/- 15%).",
            "Yield origin (standard / BMT).",
            "Emission factors origin (standard / Technical Report).",
            "Incoming DDTs and supplier list.",
            "Supplier sustainability declarations.",
        ]))
        story.append(subsec("10.5 Annual and planning exports"))
        story.append(p(
            "Besides the monthly exports, modes 3 and 4 offer:"
        ))
        story.append(bullet_list([
            "<b>Annual consolidated Excel</b> and <b>annual PDF report</b> - 12-month summary (Annual Results tab).",
            "<b>PPTX presentation</b> - 8 yearly slides ready for management (python-pptx).",
            "<b>Editable Excel</b> - monthly plan that can be re-opened and re-loaded to iterate the scenario.",
            "<b>Excel snapshot</b> - immutable picture of the current scenario.",
            "<b>Monthly plan CSV</b> - planning table for integration with other systems.",
            "<b>Business Plan PDF (15 years)</b> - landscape Metan.iQ brand: input parameters, "
            "CAPEX/IRR/NPV/payback KPIs, P&amp;L and cash flows year by year, equity cash-flow chart.",
        ]))


def build_chapter_11(story, lang):
    story.extend(section(t("ch11", lang)))
    L = lang == "it"
    rows_it = [
        ["Nome azienda", "Ragione sociale completa"],
        ["Sede legale", "Indirizzo sede legale"],
        ["Nome impianto", "Denominazione operativa"],
        ["Sede operativa", "Indirizzo impianto"],
        ["Regime applicato", "Biometano DM 2022 (app mono-regime)"],
        ["Soglia normativa (%)", "80 / 70 / 65 secondo destinazione d'uso"],
        ["Comparatore fossile", "80 / 94 / 183 secondo uso finale"],
        ["Aux factor", "Da Config Tecnica o override"],
        ["EP totale", "Da Config Tecnica o override"],
        ["Plant net (Sm3/h)", "Cap autorizzativo"],
        ["Origine rese", "BMT override se attivo, altrimenti standard"],
        ["Origine fattori emissivi", "Override RT se attivo, altrimenti UNI-TS"],
        ["Giorni con dati", "Conteggio giorni compilati"],
        ["Giorni cap violato", "Conteggio giorni con Sm3/h > cap"],
    ]
    rows_en = [
        ["Company name", "Full registered name"],
        ["Registered office", "Registered office address"],
        ["Plant name", "Operating name"],
        ["Operating site", "Plant address"],
        ["Applied regime", "Biomethane DM 2022 (single-regime app)"],
        ["Regulatory threshold (%)", "80 / 70 / 65 depending on end use"],
        ["Fossil comparator", "80 / 94 / 183 based on end use"],
        ["Aux factor", "From Tech Config or override"],
        ["EP total", "From Tech Config or override"],
        ["Plant net (Sm3/h)", "Authorisation cap"],
        ["Yield origin", "BMT override if active, else standard"],
        ["Emission factors origin", "Tech Report override if active, else UNI-TS"],
        ["Days with data", "Count of filled days"],
        ["Days cap violated", "Count of days with Sm3/h > cap"],
    ]
    if L:
        story.append(p(
            "Sezione obbligatoria per la tracciabilita' GSE / OdC. Tutti i "
            "valori vengono riportati in copertina dei report e nell'Excel."
        ))
        story.append(data_table(["Voce", "Note"], rows_it, col_widths=[55*mm, 115*mm]))
    else:
        story.append(p(
            "Mandatory section for GSE / certification body traceability. All "
            "values appear on the cover of reports and in the Excel."
        ))
        story.append(data_table(["Item", "Notes"], rows_en, col_widths=[55*mm, 115*mm]))


def build_chapter_12(story, lang):
    story.extend(section(t("ch12", lang)))
    L = lang == "it"
    if L:
        story.append(subsec("12.1 Domande frequenti"))
        faq = [
            ("Perche' il saving mensile non e' la media dei saving giornalieri?",
             "Perche' UNI/TS 11567:2024 e RED III prescrivono l'aggregazione sull'energia del lotto. Vedi cap. 7.2."),
            ("Posso avere giorni con saving < 80% senza essere Non Compliant?",
             "Si', purche' il saving mensile aggregato sia >= 80%. La compensazione tra giorni alto/basso saving e' caratteristica del LS."),
            ("Cosa succede se non inserisco i Sm3 netti REMI?",
             "I KPI di portata, MWh netti e ricavi vengono mostrati come 0. Il saving GHG e' comunque calcolabile dalla biomassa."),
            ("Il manure credit -45 si applica sempre?",
             "Si' per default, ma solo se il fornitore stocca i reflui in vasca APERTA. Vasca coperta + captazione annulla il credit."),
            ("ep_total puo' essere negativo?",
             "No. Per RED III All.V Parte C, ep e' >= 0. Il software applica un floor automatico."),
            ("Quale LHV biometano usa il software?",
             "9.79 kWh/Sm3 = 35.24 MJ/Sm3, conforme UNI EN 16723-1 (biometano spec rete, ~98% CH4)."),
            ("I dati sono persistenti su Streamlit Cloud?",
             "Il filesystem Streamlit Cloud e' EFFIMERO. Esporta PDF/Excel regolarmente come backup."),
            ("Come gestisco un fornitore non certificato?",
             "Va escluso dal LS o avviato iter certificazione."),
        ]
    else:
        story.append(subsec("12.1 Frequently asked questions"))
        faq = [
            ("Why is monthly saving not the average of daily savings?",
             "Because UNI/TS 11567:2024 and RED III mandate aggregation on the lot energy. See ch. 7.2."),
            ("Can I have days with saving < 80% without being Non Compliant?",
             "Yes, provided the aggregate monthly saving is >= 80%. Offsetting high/low days is a feature of LS."),
            ("What if I don't enter the net Sm3 REMI?",
             "Flow, net MWh and revenue KPIs are shown as 0. GHG saving can still be computed from feedstock."),
            ("Does the manure credit -45 always apply?",
             "Yes by default, only if the supplier stores manure in an OPEN tank. Covered tank + capture cancels the credit."),
            ("Can ep_total be negative?",
             "No. Per RED III Annex V Part C, ep >= 0. The software applies an automatic floor."),
            ("Which biomethane LHV does the software use?",
             "9.79 kWh/Sm3 = 35.24 MJ/Sm3, compliant with UNI EN 16723-1 (grid spec biomethane, ~98% CH4)."),
            ("Is data persistent on Streamlit Cloud?",
             "The Streamlit Cloud filesystem is EPHEMERAL. Export PDF/Excel regularly as backup."),
            ("How do I handle a non-certified supplier?",
             "It must be excluded from the LS or a certification process must be started."),
        ]
    for q, a in faq:
        story.append(p(f"<b>{'D' if L else 'Q'}:</b> {q}", BODY_TIGHT))
        story.append(p(f"<b>{'R' if L else 'A'}:</b> {a}", BODY))
        story.append(Spacer(1, 4))

    if L:
        story.append(subsec("12.2 Troubleshooting"))
        rows = [
            ["KPI tutti a 0 dopo apertura", "Sidebar: nessuna biomassa selezionata. Aggiungerne almeno una."],
            ["Saving mensile basso inatteso", "Troppo mais (eec +29). Aumenta reflui."],
            ["MWh netti != cumulato giornaliero", "Aggiorna a v0.5.0+ (fix UNI EN 16723-1)."],
            ["ep_total mostrato 0 ma config dice diverso", "Floor ep >= 0: config produrrebbe ep negativo (RTO off-gas)."],
            ["Tabella non aggiornabile", "Mese gia' chiuso. Usa 'Nuovo mese' o riapri."],
            ["Solver LP nessuna soluzione", "Vincoli incompatibili. Rilassa uno dei tre."],
        ]
        story.append(data_table(["Problema", "Causa probabile / Azione"], rows, col_widths=[60*mm, 110*mm]))
    else:
        story.append(subsec("12.2 Troubleshooting"))
        rows = [
            ["All KPIs at 0 after opening", "Sidebar: no feedstock selected. Add at least one."],
            ["Unexpectedly low monthly saving", "Too much maize (eec +29). Increase manure."],
            ["Net MWh != daily cumulative", "Upgrade to v0.5.0+ (UNI EN 16723-1 fix)."],
            ["ep_total shows 0 but config says otherwise", "Floor ep >= 0: config would produce negative ep (RTO off-gas)."],
            ["Table not editable", "Month already closed. Use 'New month' or reopen."],
            ["LP solver no solution", "Incompatible constraints. Relax one of the three."],
        ]
        story.append(data_table(["Problem", "Probable cause / Action"], rows, col_widths=[60*mm, 110*mm]))


def build_appendices(story, lang):
    L = lang == "it"
    # Appendice A
    story.extend(section(t("appA", lang)))
    if L:
        story.append(subsec("A.1 GHG per singola biomassa"))
        story.append(callout("e_biomassa = eec + esca + etd + ep<br/><br/>Tutti in gCO2eq/MJ. Manure credit su eec con segno negativo (es. -45 liquame)."))
        story.append(subsec("A.2 Energia biomassa"))
        story.append(callout("Energia_i [MJ] = massa_i [t] x resa_CH4_i [Nm3/t] x LHV [MJ/Nm3]<br/><br/>LHV = 35.24 MJ/Nm3 (UNI EN 16723-1)"))
        story.append(subsec("A.3 Aggregato lotto"))
        story.append(callout("e_w_lotto = SOMMA(e_biomassa_i x Energia_i) / SOMMA(Energia_i)<br/>Saving = (FFC - e_w_lotto) / FFC x 100<br/>FFC = 80 (rete/calore) | 94 (trasporti) | 183 (elettricita')"))
        story.append(subsec("A.4 Mass balance LS"))
        story.append(callout("Tolleranza UNI/TS 11567 sec. 6:<br/>| biometano_atteso - biometano_REMI | / biometano_atteso <= 15%<br/>Durata massima LS: 6 mesi (prassi GSE: mensile)."))
    else:
        story.append(subsec("A.1 GHG per single feedstock"))
        story.append(callout("e_feedstock = eec + esca + etd + ep<br/><br/>All in gCO2eq/MJ. Manure credit on eec with negative sign (e.g. -45 for slurry)."))
        story.append(subsec("A.2 Feedstock energy"))
        story.append(callout("Energy_i [MJ] = mass_i [t] x CH4_yield_i [Nm3/t] x LHV [MJ/Nm3]<br/><br/>LHV = 35.24 MJ/Nm3 (UNI EN 16723-1)"))
        story.append(subsec("A.3 Lot aggregate"))
        story.append(callout("e_w_lot = SUM(e_feedstock_i x Energy_i) / SUM(Energy_i)<br/>Saving = (FFC - e_w_lot) / FFC x 100<br/>FFC = 80 (grid/heat) | 94 (transport) | 183 (electricity)"))
        story.append(subsec("A.4 LS mass balance"))
        story.append(callout("UNI/TS 11567 sec. 6 tolerance:<br/>| expected_biomethane - REMI_biomethane | / expected_biomethane <= 15%<br/>Maximum LS duration: 6 months (GSE practice: monthly)."))

    # Appendice B
    story.extend(section(t("appB", lang)))
    rows_const = [
        ["LHV biometano" if L else "Biomethane LHV", "35.24 MJ/Nm3 = 9.79 kWh/Sm3", "UNI EN 16723-1"],
        ["NM3_TO_MWH", "0.00979", "derivato LHV" if L else "LHV-derived"],
        ["Purezza CH4 default" if L else "Default CH4 purity", "98.0 %", "UNI EN 16723-1"],
        ["FFC rete / calore" if L else "FFC grid / heat", "80 gCO2eq/MJ", "RED III All. VI"],
        ["FFC trasporti" if L else "FFC transport", "94 gCO2eq/MJ", "RED III All. VI"],
        ["FFC elettricita'" if L else "FFC electricity", "183 gCO2eq/MJ", "RED III All. VI"],
        ["GWP CH4", "28", "Reg. UE 2022/996"],
        ["GWP N2O", "265", "Reg. UE 2022/996"],
        ["GWP CO2", "1", "Reg. UE 2022/996"],
        ["DEFAULT_AUX_FACTOR", "1.29", "JRC-CONCAWE"],
        ["Soglia GHG nuova rete/calore 2026+" if L else "GHG threshold new grid/heat 2026+", "80 %", "RED III"],
        ["Soglia GHG trasporti 2021+" if L else "GHG threshold transport 2021+", "65 %", "RED III"],
        ["Tolleranza mass balance LS" if L else "LS mass balance tolerance", "+/- 15 %", "UNI/TS 11567:2024 sec.6"],
        ["Durata massima LS" if L else "Maximum LS duration", "6 " + ("mesi" if L else "months"), "UNI/TS 11567:2024 sec.6"],
        ["Conservazione documenti" if L else "Document retention", "5 " + ("anni" if L else "years"), "UNI/TS 11567:2024"],
    ]
    story.append(data_table(
        ["Costante" if L else "Constant", "Valore" if L else "Value", "Fonte" if L else "Source"],
        rows_const, col_widths=[55*mm, 55*mm, 60*mm]
    ))

    # Appendice C - 42 biomasse
    story.extend(section(t("appC", lang)))
    if L:
        story.append(p(
            "Elenco completo delle <b>42 biomasse</b> nel FEEDSTOCK_DB del "
            "software, estratto direttamente da <i>app_mensile.py</i>. Valori "
            "normativi UNI/TS 11567:2024 Prospetto A.5 salvo override BMT / Relazione Tecnica."
        ))
    else:
        story.append(p(
            "Complete list of the <b>42 feedstocks</b> in the software's "
            "FEEDSTOCK_DB, extracted directly from <i>app_mensile.py</i>. "
            "Regulatory values from UNI/TS 11567:2024 Schedule A.5 unless "
            "overridden by BMT / Technical Report. Feedstock names are kept in "
            "Italian as they are the official commercial designations used in "
            "Italian audits (RINA / SGS / ISCC) and GSE filings."
        ))
    biomasse = make_biomasse_42(lang)
    story.append(data_table(
        ["#",
         "Biomassa" if L else "Feedstock (IT)",
         "Categoria" if L else "Category",
         "eec", "etd",
         "Resa Nm3CH4/t" if L else "Yield Nm3CH4/t",
         "Tier"],
        [[str(i)] + row for i, row in enumerate(biomasse, 1)],
        col_widths=[8*mm, 55*mm, 45*mm, 14*mm, 12*mm, 24*mm, 12*mm]
    ))
    if L:
        story.append(callout(
            "<b>Legenda Tier (livello difendibilita' eec in audit OdC):</b><br/>"
            "<b>A</b> = Default normativo tabulato (Prospetto A.5 UNI/TS 11567:2024).<br/>"
            "<b>A/B</b> = eec = 0 da regola (rifiuti, sottoprodotti, residui).<br/>"
            "<b>C</b> = Stima conservativa positiva (no manure credit). A sfavore dell'operatore, non contestabile in audit.<br/>"
            "<b>D</b> = Manure credit (eec negativo). Richiede <b>dichiarazione baseline fornitore</b> (stoccaggio in vasca/lagone aperto)."
        ))
        story.append(Spacer(1, 6))
        story.append(p(
            "<b>Distribuzione delle 42 voci:</b> Colture dedicate 11 | Effluenti zootecnici 9 "
            "| Sottoprodotti agroindustriali 20 | FORSU/Rifiuti 2.",
            NOTE
        ))
        story.append(Spacer(1, 20))
        story.append(p("<i>Fine del manuale. Per supporto: carlo.sicurini@gmail.com.</i>", NOTE))
    else:
        story.append(callout(
            "<b>Tier legend (eec defensibility level in certification body audit):</b><br/>"
            "<b>A</b> = Tabulated regulatory default (Schedule A.5 UNI/TS 11567:2024).<br/>"
            "<b>A/B</b> = eec = 0 by rule (waste, by-products, residues).<br/>"
            "<b>C</b> = Conservative positive estimate (no manure credit). Against operator interest, non-contestable in audit.<br/>"
            "<b>D</b> = Manure credit (negative eec). Requires <b>supplier baseline declaration</b> (open tank/lagoon storage)."
        ))
        story.append(Spacer(1, 6))
        story.append(p(
            "<b>Distribution of the 42 entries:</b> Energy crops 11 | Animal manure 9 "
            "| Agro-industrial by-products 20 | OFMSW/Waste 2.",
            NOTE
        ))
        story.append(Spacer(1, 20))
        story.append(p("<i>End of manual. Support: carlo.sicurini@gmail.com.</i>", NOTE))


# ============================================================
# TOC
# ============================================================

def build_toc(story, lang):
    L = lang == "it"
    story.append(p(t("toc_title", lang), H1))
    if L:
        toc_rows = [
            ("1.", "Scopo del software e contesto normativo"),
            ("2.", "Architettura e tecnologie"),
            ("3.", "Avvio dell'app: prima schermata e sidebar"),
            ("4.", "Tab 1 - Conduzione Giornaliera Standard (UNI-TS / RED III)"),
            ("5.", "Tab 2 - Conduzione Giornaliera Analisi (BMT / Override EF)"),
            ("6.", "Tab 3-4 - Risultati Annuali e Pianificazione & BP"),
            ("7.", "Logica di calcolo GHG (RED III All.V Parte C)"),
            ("8.", "Calcolo aux_factor e bilancio energetico"),
            ("9.", "Vincoli normativi e verifica compliance mensile"),
            ("10.", "Export: PDF, Excel, CSV"),
            ("11.", "Anagrafica impianto e audit trail"),
            ("12.", "FAQ e troubleshooting"),
            ("A.", "Appendice - Formule normative complete"),
            ("B.", "Appendice - Costanti fisiche e fattori emissivi"),
            ("C.", "Appendice - Database biomasse completo (42 voci)"),
        ]
    else:
        toc_rows = [
            ("1.", "Software scope and regulatory context"),
            ("2.", "Architecture and technologies"),
            ("3.", "Launching the app: first screen and sidebar"),
            ("4.", "Tab 1 - Daily Operations Standard (UNI-TS / RED III)"),
            ("5.", "Tab 2 - Daily Operations Analysis (BMT / EF Override)"),
            ("6.", "Tab 3-4 - Annual Results and Planning & BP"),
            ("7.", "GHG calculation logic (RED III Annex V Part C)"),
            ("8.", "aux_factor calculation and energy balance"),
            ("9.", "Regulatory constraints and monthly compliance check"),
            ("10.", "Export: PDF, Excel, CSV"),
            ("11.", "Plant registry and audit trail"),
            ("12.", "FAQ and troubleshooting"),
            ("A.", "Appendix - Complete regulatory formulas"),
            ("B.", "Appendix - Physical constants and emission factors"),
            ("C.", "Appendix - Complete feedstock database (42 entries)"),
        ]
    toc_table = Table(
        [[p(f"<b>{n}</b>", BODY_TIGHT), p(tt, BODY_TIGHT)] for n, tt in toc_rows],
        colWidths=[12*mm, 158*mm], hAlign="LEFT"
    )
    toc_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.2, GREY_LIGHT),
    ]))
    story.append(toc_table)


# ============================================================
# BUILD
# ============================================================

def build(lang):
    out = OUTPUT_PATHS[lang]
    doc = BaseDocTemplate(
        out, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=24*mm, bottomMargin=22*mm,
        title=t("doc_title_pdf", lang),
        author="Carlo Sicurini",
        subject=t("doc_subject", lang),
    )
    frame_cover = Frame(0, 0, A4[0], A4[1], leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0, id="cover")
    frame_std = Frame(20*mm, 22*mm, A4[0]-40*mm, A4[1]-46*mm,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, id="std")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame_cover], onPage=make_cover_page(lang)),
        PageTemplate(id="std", frames=[frame_std], onPage=make_std_page(lang)),
    ])

    story = [
        NextPageTemplate("cover"),
        Spacer(1, 1),
        NextPageTemplate("std"),
        PageBreak(),
    ]

    build_toc(story, lang)
    build_chapter_1(story, lang)
    build_chapter_2(story, lang)
    build_chapter_3(story, lang)
    build_chapter_workflow(story, lang)  # cap 4, 5, 6
    build_chapter_7(story, lang)
    build_chapter_8(story, lang)
    build_chapter_9(story, lang)
    build_chapter_10(story, lang)
    build_chapter_11(story, lang)
    build_chapter_12(story, lang)
    build_appendices(story, lang)

    doc.build(story)
    print(f"PDF [{lang.upper()}] generato: {out}")


if __name__ == "__main__":
    lang_arg = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    if lang_arg in ("it", "en"):
        build(lang_arg)
    else:
        build("it")
        build("en")
