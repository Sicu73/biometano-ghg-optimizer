"""
Genera carosello LinkedIn per Metan.iQ.
Formato 4:5 verticale (ottimale mobile feed LinkedIn).
8 slide impattanti, brand navy/amber, testo grosso, contrasto AA+.

Uso: python build_linkedin_carousel.py
Output: C:/Users/CarloSicurini/Downloads/Metan.iQ_LinkedIn.pdf
"""
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

OUTPUT = r"C:\Users\CarloSicurini\Downloads\Metan.iQ_LinkedIn.pdf"

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
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 20, "L'80% di saving GHG.")
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 60, "Garantito.")
    # Sub
    c.setFillColor(AMBER)
    c.setFont("Helvetica", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 120,
                        "Software di compliance per biometano")
    c.setFillColor(GREY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 150,
                        "DM 2022 / RED III / UNI-TS 11567:2024")
    # Footer cover
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, 60, "Carlo Sicurini  -  carlo.sicurini@gmail.com")
    c.drawCentredString(PAGE_W / 2, 40, "carosello LinkedIn -- swipe per scoprire ->")


def slide_2_problem(c):
    """Slide 2: il problema."""
    draw_white_bg(c)
    draw_section_chip(c, "IL PROBLEMA", PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 44)
    c.drawString(40, PAGE_H - 230,
                 "1.000+ impianti biometano")
    c.drawString(40, PAGE_H - 280, "in Italia.")
    c.setFillColor(NAVY_2)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 360,
                 "Tutti devono dimostrare")
    c.setFillColor(AMBER_DARK)
    c.drawString(40, PAGE_H - 405, "GHG saving >= 80%")
    c.setFillColor(NAVY_2)
    c.drawString(40, PAGE_H - 450, "per non perdere l'incentivo.")
    # 3 bullet pain points
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, PAGE_H - 560, "Calcoli a mano. Excel sparsi.")
    c.drawString(40, PAGE_H - 600, "Errori in audit RINA / SGS.")
    c.drawString(40, PAGE_H - 640, "Soglia 80% sforata = -150k EUR/anno.")
    # Quote
    c.setStrokeColor(AMBER)
    c.setLineWidth(4)
    c.line(40, PAGE_H - 700, 80, PAGE_H - 700)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 16)
    c.drawString(40, PAGE_H - 730,
                 "L'80% di saving GHG e' la differenza tra")
    c.drawString(40, PAGE_H - 755, "incentivo e nulla. Servirebbe certezza.")
    draw_footer(c, 2, 8)


def slide_3_solution(c):
    """Slide 3: la soluzione."""
    draw_navy_bg(c)
    draw_section_chip(c, "LA SOLUZIONE", PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 56)
    c.drawString(40, PAGE_H - 240, "Metan.")
    c.setFillColor(AMBER)
    c.drawString(40 + c.stringWidth("Metan.", "Helvetica-Bold", 56),
                 PAGE_H - 240, "iQ")
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 22)
    c.drawString(40, PAGE_H - 290,
                 "Una sola piattaforma. Zero Excel.")
    # 3 funzioni chiave
    items = [
        ("Inserisci biomasse", "ogni giorno -- come un diario"),
        ("Inserisci Sm3 netti", "dalla cabina REMI"),
        ("Compliance certa", "saving GHG calcolato in real-time"),
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
    draw_section_chip(c, "IL CUORE NORMATIVO", PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(40, PAGE_H - 220, "RED III All. V Parte C")
    c.setFillColor(GREY)
    c.setFont("Helvetica", 16)
    c.drawString(40, PAGE_H - 250, "UNI-TS 11567:2024  -  GSE Linee Guida 2024")
    # Formula box
    c.setFillColor(CREAM)
    c.rect(40, PAGE_H - 460, PAGE_W - 80, 180, fill=1, stroke=0)
    c.setStrokeColor(AMBER)
    c.setLineWidth(4)
    c.line(40, PAGE_H - 460, PAGE_W - 40, PAGE_H - 460)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(60, PAGE_H - 305, "Saving GHG mensile =")
    c.setFillColor(AMBER_DARK)
    c.setFont("Courier-Bold", 22)
    c.drawString(60, PAGE_H - 350, "(80 - e_w) / 80 x 100")
    c.setFillColor(NAVY_2)
    c.setFont("Helvetica", 14)
    c.drawString(60, PAGE_H - 390,
                 "e_w = SOMMA(e_i x Energia_i) / SOMMA(Energia_i)")
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(60, PAGE_H - 420,
                 "Aggregato sul LOTTO MENSILE. Non media giornaliera.")
    c.drawString(60, PAGE_H - 440,
                 "I giorni 'cattivi' si compensano con i giorni 'buoni'.")
    # Caratteristiche
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, PAGE_H - 520, "42 biomasse")
    c.drawString(40, PAGE_H - 555, "Manure credit (-45 gCO2/MJ)")
    c.drawString(40, PAGE_H - 590, "Override BMT da analisi laboratorio")
    c.drawString(40, PAGE_H - 625, "ep totale floor >= 0 (RED III All.V)")
    c.drawString(40, PAGE_H - 660, "LHV 9.79 kWh/Sm3 (UNI EN 16723-1)")
    draw_footer(c, 4, 8)


def slide_5_kpis(c):
    """Slide 5: KPI numerici."""
    draw_navy_bg(c)
    draw_section_chip(c, "NUMERI", PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 220, "Compliance audit-ready.")
    c.drawString(40, PAGE_H - 265, "In 3 click.")
    # KPI grid 2x2
    kpis = [
        ("322", "test automatizzati"),
        ("42", "biomasse nel DB"),
        ("9", "norme integrate"),
        ("15", "anni business plan"),
    ]
    col_w = (PAGE_W - 80) / 2
    row_h = 160
    for idx, (num, label) in enumerate(kpis):
        col = idx % 2
        row = idx // 2
        x = 40 + col * col_w
        y = PAGE_H - 360 - row * row_h
        # Box
        c.setFillColor(NAVY_2)
        c.rect(x, y - row_h + 20, col_w - 15, row_h - 20, fill=1, stroke=0)
        # Stripe amber sinistra
        c.setFillColor(AMBER)
        c.rect(x, y - row_h + 20, 6, row_h - 20, fill=1, stroke=0)
        # Numero gigante
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 70)
        c.drawString(x + 30, y - 70, num)
        # Label
        c.setFillColor(CREAM)
        c.setFont("Helvetica", 14)
        c.drawString(x + 30, y - 110, label)
    draw_footer(c, 5, 8)


def slide_6_deliverables(c):
    """Slide 6: deliverables."""
    draw_white_bg(c)
    draw_section_chip(c, "COSA CONSEGNI AL CLIENTE", PAGE_H - 140)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(40, PAGE_H - 220, "Report ufficiali brand.")
    c.drawString(40, PAGE_H - 265, "Audit-ready dal giorno 1.")
    deliverables = [
        ("PDF mensile",  "7 pagine brand: esito, KPI, vincoli, audit trail."),
        ("Excel 4 fogli", "Riepilogo, giornaliera, anagrafica, vincoli."),
        ("CSV",          "Sep ; - dec , - UTF-8. Apre direttamente in Excel IT."),
        ("Dossier OdC",  "Mass balance, fonti normative, dichiarazioni fornitori."),
        ("Business Plan", "15 anni: CAPEX, OPEX, PNRR, NPV, IRR, FCF."),
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
    draw_section_chip(c, "STACK NORMATIVO", PAGE_H - 140, color=AMBER)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, PAGE_H - 220, "9 norme integrate.")
    c.drawString(40, PAGE_H - 265, "Zero interpretazioni.")
    norme = [
        "DM 15/09/2022   -  Tariffe biometano in rete",
        "RED III  (Dir. UE 2023/2413)  -  Soglie GHG All.V Parte C",
        "RED II   (Dir. UE 2018/2001)  -  Quadro precedente",
        "D.Lgs. 199/2021  -  Recepimento italiano RED II",
        "UNI/TS 11567:2024  -  Calcolo GHG, rese standard, LS",
        "GSE Linee Guida 2024  -  Decreto attuativo 248/2024",
        "JEC WTT v5  -  Fattori emissivi default",
        "Reg. UE 2022/996  -  GWP CH4=28, N2O=265",
        "UNI EN 16723-1  -  Specifiche biometano in rete",
    ]
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
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 30, "Vuoi smettere di")
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 15, "calcolare GHG a mano?")
    c.setStrokeColor(AMBER)
    c.setLineWidth(3)
    c.line(PAGE_W * 0.25, PAGE_H / 2 - 50, PAGE_W * 0.75, PAGE_H / 2 - 50)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 100, "Scrivimi in DM.")
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 140,
                        "Demo gratuita sul tuo impianto.")
    # CTA box
    c.setFillColor(AMBER)
    c.rect(PAGE_W / 2 - 220, 180, 440, 80, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(PAGE_W / 2, 225, "carlo.sicurini@gmail.com")
    c.setFont("Helvetica", 13)
    c.drawCentredString(PAGE_W / 2, 200, "Risposta entro 24h")
    # Footer minimal
    c.setFillColor(GREY)
    c.setFont("Helvetica", 10)
    c.drawCentredString(PAGE_W / 2, 60,
                        f"(c) {date.today().year} Carlo Sicurini  -  Tutti i diritti riservati")
    c.drawCentredString(PAGE_W / 2, 42,
                        "Decision Intelligence Platform per biometano DM 2022 / RED III")


def build():
    c = canvas.Canvas(OUTPUT, pagesize=PAGE_SIZE)
    c.setTitle("Metan.iQ - Carosello LinkedIn")
    c.setAuthor("Carlo Sicurini")
    c.setSubject("Compliance GHG biometano DM 2022 RED III")
    c.setKeywords("biometano biogas GHG RED III compliance audit")
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
    print(f"Carosello LinkedIn generato: {OUTPUT}")


if __name__ == "__main__":
    build()
