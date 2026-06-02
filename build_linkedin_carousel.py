"""
Genera carosello LinkedIn per Metan.iQ in IT e EN.
Formato 4:5 verticale (ottimale mobile feed LinkedIn).
8 slide impattanti, brand navy/amber, testo grosso.

Uso:
    python build_linkedin_carousel.py           # entrambi IT + EN
    python build_linkedin_carousel.py it        # solo IT
    python build_linkedin_carousel.py en        # solo EN

Output:
    C:/Users/CarloSicurini/Downloads/Metan.iQ_LinkedIn_IT.pdf
    C:/Users/CarloSicurini/Downloads/Metan.iQ_LinkedIn_EN.pdf
"""
import sys
from datetime import date
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import portrait
from reportlab.pdfgen import canvas

# --- Formato 4:5 verticale (ottimale LinkedIn mobile) -----------------------
# 1080x1350 px @ 96dpi -> 11.25" x 14.0625" -> 810x1012.5 pt
PAGE_W = 810
PAGE_H = 1012.5
PAGE_SIZE = (PAGE_W, PAGE_H)

OUTPUT_PATHS = {
    "it": r"C:\Users\CarloSicurini\Downloads\Metan.iQ_LinkedIn_IT.pdf",
    "en": r"C:\Users\CarloSicurini\Downloads\Metan.iQ_LinkedIn_EN.pdf",
}

# ============================================================
# STRINGHE per slide - IT / EN
# ============================================================
TXT = {
    # slide 1 cover
    "s1_chip":      {"it": "",                                  "en": ""},
    "s1_hero1":     {"it": "L'80% di saving GHG.",              "en": "80% GHG saving."},
    "s1_hero2":     {"it": "Garantito.",                        "en": "Guaranteed."},
    "s1_subtitle":  {"it": "Software di compliance per biometano",
                     "en": "Compliance software for biomethane"},
    "s1_norms":     {"it": "DM 2022 / RED III / UNI-TS 11567:2024",
                     "en": "DM 2022 / RED III / UNI-TS 11567:2024"},
    "s1_email":     {"it": "Carlo Sicurini  -  carlo.sicurini@gmail.com",
                     "en": "Carlo Sicurini  -  carlo.sicurini@gmail.com"},
    "s1_swipe":     {"it": "carosello LinkedIn -- swipe per scoprire ->",
                     "en": "LinkedIn carousel -- swipe to discover ->"},
    # slide 2 problema
    "s2_chip":      {"it": "IL PROBLEMA",                       "en": "THE PROBLEM"},
    "s2_h1":        {"it": "1.000+ impianti biometano",         "en": "1,000+ biomethane plants"},
    "s2_h2":        {"it": "in Italia.",                        "en": "in Italy."},
    "s2_h3":        {"it": "Tutti devono dimostrare",           "en": "All must prove"},
    "s2_target":    {"it": "GHG saving >= 80%",                 "en": "GHG saving >= 80%"},
    "s2_h4":        {"it": "per non perdere l'incentivo.",      "en": "or lose the incentive."},
    "s2_pain1":     {"it": "Calcoli a mano. Excel sparsi.",     "en": "Manual calcs. Scattered Excels."},
    "s2_pain2":     {"it": "Errori in audit RINA / SGS.",       "en": "Errors in RINA / SGS audits."},
    "s2_pain3":     {"it": "Soglia 80% sforata = -150k EUR/anno.",
                     "en": "80% threshold missed = -150k EUR/year."},
    "s2_quote1":    {"it": "L'80% di saving GHG e' la differenza tra",
                     "en": "80% GHG saving is the difference between"},
    "s2_quote2":    {"it": "incentivo e nulla. Servirebbe certezza.",
                     "en": "incentive and nothing. Certainty is needed."},
    # slide 3 soluzione
    "s3_chip":      {"it": "LA SOLUZIONE",                      "en": "THE SOLUTION"},
    "s3_sub":       {"it": "Una sola piattaforma. Zero Excel.",
                     "en": "One platform. Zero Excels."},
    "s3_step1_t":   {"it": "Inserisci biomasse",                "en": "Enter feedstocks"},
    "s3_step1_s":   {"it": "ogni giorno -- come un diario",     "en": "every day -- like a log"},
    "s3_step2_t":   {"it": "Inserisci Sm3 netti",               "en": "Enter net Sm3"},
    "s3_step2_s":   {"it": "dalla cabina REMI",                 "en": "from the REMI cabin"},
    "s3_step3_t":   {"it": "Compliance certa",                  "en": "Certain compliance"},
    "s3_step3_s":   {"it": "saving GHG calcolato in real-time",
                     "en": "GHG saving computed in real-time"},
    # slide 4 normativo
    "s4_chip":      {"it": "IL CUORE NORMATIVO",                "en": "THE REGULATORY CORE"},
    "s4_h1":        {"it": "RED III All. V Parte C",            "en": "RED III Annex V Part C"},
    "s4_sub":       {"it": "UNI-TS 11567:2024  -  GSE Linee Guida 2024",
                     "en": "UNI-TS 11567:2024  -  GSE Guidelines 2024"},
    "s4_label":     {"it": "Saving GHG mensile =",              "en": "Monthly GHG saving ="},
    "s4_formula":   {"it": "(80 - e_w) / 80 x 100",             "en": "(80 - e_w) / 80 x 100"},
    "s4_ew":        {"it": "e_w = SOMMA(e_i x Energia_i) / SOMMA(Energia_i)",
                     "en": "e_w = SUM(e_i x Energy_i) / SUM(Energy_i)"},
    "s4_note1":     {"it": "Aggregato sul LOTTO MENSILE. Non media giornaliera.",
                     "en": "Aggregated on the MONTHLY LOT. Not a daily average."},
    "s4_note2":     {"it": "I giorni 'cattivi' si compensano con i giorni 'buoni'.",
                     "en": "'Bad' days offset 'good' days."},
    "s4_feat1":     {"it": "42 biomasse",                        "en": "42 feedstocks"},
    "s4_feat2":     {"it": "Manure credit (-45 gCO2/MJ)",        "en": "Manure credit (-45 gCO2/MJ)"},
    "s4_feat3":     {"it": "Override BMT da analisi laboratorio","en": "BMT override from lab analysis"},
    "s4_feat4":     {"it": "ep totale floor >= 0 (RED III All.V)",
                     "en": "ep total floor >= 0 (RED III Ann.V)"},
    "s4_feat5":     {"it": "LHV 9.79 kWh/Sm3 (UNI EN 16723-1)",  "en": "LHV 9.79 kWh/Sm3 (UNI EN 16723-1)"},
    # slide 5 KPI
    "s5_chip":      {"it": "NUMERI",                            "en": "BY THE NUMBERS"},
    "s5_h1":        {"it": "Compliance audit-ready.",           "en": "Audit-ready compliance."},
    "s5_h2":        {"it": "In 3 click.",                       "en": "In 3 clicks."},
    "s5_k1":        {"it": "test automatizzati",                "en": "automated tests"},
    "s5_k2":        {"it": "biomasse nel DB",                   "en": "feedstocks in DB"},
    "s5_k3":        {"it": "norme integrate",                   "en": "regulations integrated"},
    "s5_k4":        {"it": "anni business plan",                "en": "years business plan"},
    # slide 6 deliverables
    "s6_chip":      {"it": "COSA CONSEGNI AL CLIENTE",          "en": "WHAT YOU DELIVER"},
    "s6_h1":        {"it": "Report ufficiali brand.",           "en": "Branded official reports."},
    "s6_h2":        {"it": "Audit-ready dal giorno 1.",         "en": "Audit-ready from day one."},
    "s6_d1_t":      {"it": "PDF mensile",                       "en": "Monthly PDF"},
    "s6_d1_s":      {"it": "7 pagine brand: esito, KPI, vincoli, audit trail.",
                     "en": "7 branded pages: outcome, KPIs, constraints, audit trail."},
    "s6_d2_t":      {"it": "Excel 4 fogli",                     "en": "Excel 4 sheets"},
    "s6_d2_s":      {"it": "Riepilogo, giornaliera, anagrafica, vincoli.",
                     "en": "Summary, daily, registry, constraints."},
    "s6_d3_t":      {"it": "CSV",                               "en": "CSV"},
    "s6_d3_s":      {"it": "Sep ; - dec , - UTF-8. Apre direttamente in Excel IT.",
                     "en": "Sep ; - dec , - UTF-8. Opens directly in Italian Excel."},
    "s6_d4_t":      {"it": "Dossier OdC",                       "en": "Certification body dossier"},
    "s6_d4_s":      {"it": "Mass balance, fonti normative, dichiarazioni fornitori.",
                     "en": "Mass balance, regulatory sources, supplier declarations."},
    "s6_d5_t":      {"it": "Business Plan",                     "en": "Business Plan"},
    "s6_d5_s":      {"it": "15 anni: CAPEX, OPEX, PNRR, NPV, IRR, FCF.",
                     "en": "15 years: CAPEX, OPEX, PNRR, NPV, IRR, FCF."},
    # slide 7 norme
    "s7_chip":      {"it": "STACK NORMATIVO",                   "en": "REGULATORY STACK"},
    "s7_h1":        {"it": "9 norme integrate.",                "en": "9 regulations integrated."},
    "s7_h2":        {"it": "Zero interpretazioni.",             "en": "Zero interpretations."},
    # slide 8 CTA
    "s8_h1":        {"it": "Vuoi smettere di",                  "en": "Tired of computing"},
    "s8_h2":        {"it": "calcolare GHG a mano?",             "en": "GHG by hand?"},
    "s8_cta":       {"it": "Scrivimi in DM.",                   "en": "DM me."},
    "s8_demo":      {"it": "Demo gratuita sul tuo impianto.",   "en": "Free demo on your plant."},
    "s8_email":     {"it": "carlo.sicurini@gmail.com",          "en": "carlo.sicurini@gmail.com"},
    "s8_reply":     {"it": "Risposta entro 24h",                "en": "Reply within 24h"},
    "s8_copy":      {"it": "Tutti i diritti riservati",         "en": "All rights reserved"},
    "s8_strap":     {"it": "Decision Intelligence Platform per biometano DM 2022 / RED III",
                     "en": "Decision Intelligence Platform for biomethane DM 2022 / RED III"},
}

NORME = {
    "it": [
        "DM 15/09/2022   -  Tariffe biometano in rete",
        "RED III  (Dir. UE 2023/2413)  -  Soglie GHG All.V Parte C",
        "RED II   (Dir. UE 2018/2001)  -  Quadro precedente",
        "D.Lgs. 199/2021  -  Recepimento italiano RED II",
        "UNI/TS 11567:2024  -  Calcolo GHG, rese standard, LS",
        "GSE Linee Guida 2024  -  Decreto attuativo 248/2024",
        "JEC WTT v5  -  Fattori emissivi default",
        "Reg. UE 2022/996  -  GWP CH4=28, N2O=265",
        "UNI EN 16723-1  -  Specifiche biometano in rete",
    ],
    "en": [
        "DM 15/09/2022   -  Italian biomethane grid tariffs",
        "RED III  (EU Dir. 2023/2413)  -  GHG thresholds Annex V Part C",
        "RED II   (EU Dir. 2018/2001)  -  Previous framework",
        "D.Lgs. 199/2021  -  Italian transposition of RED II",
        "UNI/TS 11567:2024  -  GHG calculation, standard yields, LS",
        "GSE Guidelines 2024  -  Decree 248/2024",
        "JEC WTT v5  -  Default emission factors",
        "EU Reg. 2022/996  -  GWP CH4=28, N2O=265",
        "UNI EN 16723-1  -  Grid biomethane specifications",
    ],
}

_LANG = "it"
def x(key):
    return TXT[key].get(_LANG, TXT[key]["it"])

# --- Brand colors -----------------------------------------------------------
NAVY = colors.HexColor("#0B1E3A")
NAVY_DARK = colors.HexColor("#061327")
NAVY_2 = colors.HexColor("#142A4F")
AMBER = colors.HexColor("#F5B100")
AMBER_DARK = colors.HexColor("#C68C00")
CREAM = colors.HexColor("#F8F4EC")
WHITE = colors.white
GREY = colors.HexColor("#94A3B8")


def draw_amber_bar(c, y, h=10):
    c.setFillColor(AMBER)
    c.rect(0, y, PAGE_W, h, fill=1, stroke=0)


def draw_footer(c, page_num, total):
    """Footer con paginazione + brand."""
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, 60, fill=1, stroke=0)
    draw_amber_bar(c, 60, 4)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 28, "Metan.")
    c.setFillColor(AMBER)
    c.drawString(40 + c.stringWidth("Metan.", "Helvetica-Bold", 14), 28, "iQ")
    c.setFillColor(GREY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, 28, "Decision Intelligence Platform")
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(PAGE_W - 40, 28, f"{page_num} / {total}")


def draw_navy_bg(c):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def draw_white_bg(c):
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def draw_section_chip(c, text, y, color=AMBER):
    """Chip di sezione (badge piccolo)."""
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 10)
    chip_w = c.stringWidth(text, "Helvetica-Bold", 10) + 20
    c.rect(40, y, chip_w, 22, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.drawString(50, y + 7, text)


def slide_1_cover(c):
    """Slide 1: COVER impattante."""
    draw_navy_bg(c)
    draw_amber_bar(c, 0, 12)
    draw_amber_bar(c, PAGE_H - 12, 12)
    # Logo gigante centrato
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 110)
    c.drawCentredString(PAGE_W / 2 - 30, PAGE_H / 2 + 90, "Metan.")
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 110)
    c.drawCentredString(PAGE_W / 2 + 175, PAGE_H / 2 + 90, "iQ")
    # Linea separatrice
    c.setStrokeColor(AMBER)
    c.setLineWidth(3)
    c.line(PAGE_W * 0.25, PAGE_H / 2 + 50, PAGE_W * 0.75, PAGE_H / 2 + 50)
    # Headline
    c.setFillColor(CREAM)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 20, x("s1_hero1"))
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 60, x("s1_hero2"))
    # Sub
    c.setFillColor(AMBER)
    c.setFont("Helvetica", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 120, x("s1_subtitle"))
    c.setFillColor(GREY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 150, x("s1_norms"))
    # Footer cover
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, 60, x("s1_email"))
    c.drawCentredString(PAGE_W / 2, 40, x("s1_swipe"))


def slide_2_problem(c):
    """Slide 2: il problema."""
    draw_white_bg(c)
    draw_section_chip(c, x("s2_chip"), PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 44)
    c.drawString(40, PAGE_H - 230, x("s2_h1"))
    c.drawString(40, PAGE_H - 280, x("s2_h2"))
    c.setFillColor(NAVY_2)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 360, x("s2_h3"))
    c.setFillColor(AMBER_DARK)
    c.drawString(40, PAGE_H - 405, x("s2_target"))
    c.setFillColor(NAVY_2)
    c.drawString(40, PAGE_H - 450, x("s2_h4"))
    # 3 bullet pain points
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, PAGE_H - 560, x("s2_pain1"))
    c.drawString(40, PAGE_H - 600, x("s2_pain2"))
    c.drawString(40, PAGE_H - 640, x("s2_pain3"))
    # Quote
    c.setStrokeColor(AMBER)
    c.setLineWidth(4)
    c.line(40, PAGE_H - 700, 80, PAGE_H - 700)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 16)
    c.drawString(40, PAGE_H - 730, x("s2_quote1"))
    c.drawString(40, PAGE_H - 755, x("s2_quote2"))
    draw_footer(c, 2, 8)


def slide_3_solution(c):
    """Slide 3: la soluzione."""
    draw_navy_bg(c)
    draw_section_chip(c, x("s3_chip"), PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 56)
    c.drawString(40, PAGE_H - 240, "Metan.")
    c.setFillColor(AMBER)
    c.drawString(40 + c.stringWidth("Metan.", "Helvetica-Bold", 56),
                 PAGE_H - 240, "iQ")
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 22)
    c.drawString(40, PAGE_H - 290, x("s3_sub"))
    # 3 funzioni chiave
    items = [
        (x("s3_step1_t"), x("s3_step1_s")),
        (x("s3_step2_t"), x("s3_step2_s")),
        (x("s3_step3_t"), x("s3_step3_s")),
    ]
    y = PAGE_H - 400
    for title, sub in items:
        # Number badge
        c.setFillColor(AMBER)
        c.circle(70, y + 10, 24, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(70, y + 3, str(items.index((title, sub)) + 1))
        # Title + subtitle
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(110, y + 10, title)
        c.setFillColor(GREY)
        c.setFont("Helvetica", 16)
        c.drawString(110, y - 16, sub)
        y -= 90
    draw_footer(c, 3, 8)


def slide_4_compliance(c):
    """Slide 4: il calcolo GHG."""
    draw_white_bg(c)
    draw_section_chip(c, x("s4_chip"), PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(40, PAGE_H - 220, x("s4_h1"))
    c.setFillColor(GREY)
    c.setFont("Helvetica", 16)
    c.drawString(40, PAGE_H - 250, x("s4_sub"))
    # Formula box
    c.setFillColor(CREAM)
    c.rect(40, PAGE_H - 460, PAGE_W - 80, 180, fill=1, stroke=0)
    c.setStrokeColor(AMBER)
    c.setLineWidth(4)
    c.line(40, PAGE_H - 460, PAGE_W - 40, PAGE_H - 460)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(60, PAGE_H - 305, x("s4_label"))
    c.setFillColor(AMBER_DARK)
    c.setFont("Courier-Bold", 22)
    c.drawString(60, PAGE_H - 350, x("s4_formula"))
    c.setFillColor(NAVY_2)
    c.setFont("Helvetica", 14)
    c.drawString(60, PAGE_H - 390, x("s4_ew"))
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(60, PAGE_H - 420, x("s4_note1"))
    c.drawString(60, PAGE_H - 440, x("s4_note2"))
    # Caratteristiche
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, PAGE_H - 520, x("s4_feat1"))
    c.drawString(40, PAGE_H - 555, x("s4_feat2"))
    c.drawString(40, PAGE_H - 590, x("s4_feat3"))
    c.drawString(40, PAGE_H - 625, x("s4_feat4"))
    c.drawString(40, PAGE_H - 660, x("s4_feat5"))
    draw_footer(c, 4, 8)


def slide_5_kpis(c):
    """Slide 5: KPI numerici."""
    draw_navy_bg(c)
    draw_section_chip(c, x("s5_chip"), PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 220, x("s5_h1"))
    c.drawString(40, PAGE_H - 265, x("s5_h2"))
    # KPI grid 2x2
    kpis = [
        ("322", x("s5_k1")),
        ("42",  x("s5_k2")),
        ("9",   x("s5_k3")),
        ("15",  x("s5_k4")),
    ]
    col_w = (PAGE_W - 80) / 2
    row_h = 160
    for idx, (num, label) in enumerate(kpis):
        col = idx % 2
        row = idx // 2
        xpos = 40 + col * col_w
        y = PAGE_H - 360 - row * row_h
        # Box
        c.setFillColor(NAVY_2)
        c.rect(xpos, y - row_h + 20, col_w - 15, row_h - 20, fill=1, stroke=0)
        # Stripe amber sinistra
        c.setFillColor(AMBER)
        c.rect(xpos, y - row_h + 20, 6, row_h - 20, fill=1, stroke=0)
        # Numero gigante
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 70)
        c.drawString(xpos + 30, y - 70, num)
        # Label
        c.setFillColor(CREAM)
        c.setFont("Helvetica", 14)
        c.drawString(xpos + 30, y - 110, label)
    draw_footer(c, 5, 8)


def slide_6_deliverables(c):
    """Slide 6: deliverables."""
    draw_white_bg(c)
    draw_section_chip(c, x("s6_chip"), PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(40, PAGE_H - 220, x("s6_h1"))
    c.drawString(40, PAGE_H - 265, x("s6_h2"))
    deliverables = [
        (x("s6_d1_t"), x("s6_d1_s")),
        (x("s6_d2_t"), x("s6_d2_s")),
        (x("s6_d3_t"), x("s6_d3_s")),
        (x("s6_d4_t"), x("s6_d4_s")),
        (x("s6_d5_t"), x("s6_d5_s")),
    ]
    y = PAGE_H - 380
    for title, desc in deliverables:
        c.setFillColor(AMBER)
        c.rect(40, y - 4, 6, 36, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(60, y + 14, title)
        c.setFillColor(GREY)
        c.setFont("Helvetica", 14)
        c.drawString(60, y - 8, desc)
        y -= 75
    draw_footer(c, 6, 8)


def slide_7_normative(c):
    """Slide 7: stack normativo."""
    draw_navy_bg(c)
    draw_section_chip(c, x("s7_chip"), PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 220, x("s7_h1"))
    c.drawString(40, PAGE_H - 265, x("s7_h2"))
    norme = NORME[_LANG]
    y = PAGE_H - 350
    c.setFont("Helvetica", 17)
    for n in norme:
        c.setFillColor(AMBER)
        c.circle(50, y + 5, 4, fill=1, stroke=0)
        c.setFillColor(CREAM)
        c.drawString(70, y, n)
        y -= 35
    draw_footer(c, 7, 8)


def slide_8_cta(c):
    """Slide 8: call to action."""
    draw_navy_bg(c)
    draw_amber_bar(c, 0, 12)
    draw_amber_bar(c, PAGE_H - 12, 12)
    # Big logo top
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 72)
    c.drawCentredString(PAGE_W / 2 - 20, PAGE_H - 250, "Metan.")
    c.setFillColor(AMBER)
    c.drawCentredString(PAGE_W / 2 + 110, PAGE_H - 250, "iQ")
    # Hero text
    c.setFillColor(CREAM)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 30, x("s8_h1"))
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 15, x("s8_h2"))
    c.setStrokeColor(AMBER)
    c.setLineWidth(3)
    c.line(PAGE_W * 0.25, PAGE_H / 2 - 50, PAGE_W * 0.75, PAGE_H / 2 - 50)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 100, x("s8_cta"))
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 140, x("s8_demo"))
    # CTA box
    c.setFillColor(AMBER)
    c.rect(PAGE_W / 2 - 220, 180, 440, 80, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(PAGE_W / 2, 225, x("s8_email"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(PAGE_W / 2, 200, x("s8_reply"))
    # Footer minimal
    c.setFillColor(GREY)
    c.setFont("Helvetica", 10)
    c.drawCentredString(PAGE_W / 2, 60,
                        f"(c) {date.today().year} Carlo Sicurini  -  " + x("s8_copy"))
    c.drawCentredString(PAGE_W / 2, 42, x("s8_strap"))


def build(lang):
    global _LANG
    _LANG = lang
    out = OUTPUT_PATHS[lang]
    c = canvas.Canvas(out, pagesize=PAGE_SIZE)
    c.setTitle(f"Metan.iQ - LinkedIn carousel ({lang.upper()})")
    c.setAuthor("Carlo Sicurini")
    c.setSubject("Compliance GHG biometano DM 2022 RED III")
    c.setKeywords("biometano biogas biomethane GHG RED III compliance audit")
    slides = [
        slide_1_cover,
        slide_2_problem,
        slide_3_solution,
        slide_4_compliance,
        slide_5_kpis,
        slide_6_deliverables,
        slide_7_normative,
        slide_8_cta,
    ]
    for s in slides:
        s(c)
        c.showPage()
    c.save()
    print(f"Carosello LinkedIn [{lang.upper()}] generato: {out}")


if __name__ == "__main__":
    lang_arg = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    if lang_arg in ("it", "en"):
        build(lang_arg)
    else:
        build("it")
        build("en")
