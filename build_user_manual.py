"""
Generatore del Manuale Utente PDF per Metan.iQ.
Uso: python build_user_manual.py
Output: C:/Users/CarloSicurini/Downloads/Metan.iQ_Manuale_Utente.pdf
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, ListFlowable, ListItem
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from datetime import date

# Brand colors Metan.iQ
NAVY = colors.HexColor("#0B1E3A")
NAVY_DARK = colors.HexColor("#061327")
AMBER = colors.HexColor("#F5B100")
CREAM = colors.HexColor("#F8F4EC")
GREY = colors.HexColor("#666666")
GREY_LIGHT = colors.HexColor("#CCCCCC")
TINT = colors.HexColor("#F2F4F8")
WHITE = colors.white

OUTPUT_PATH = r"C:\Users\CarloSicurini\Downloads\Metan.iQ_Manuale_Utente.pdf"

# Styles
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=20, textColor=NAVY, spaceAfter=14, spaceBefore=4,
                    leading=24)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=14, textColor=NAVY, spaceAfter=8, spaceBefore=12,
                    leading=18, borderPadding=0)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                    fontSize=11, textColor=NAVY_DARK, spaceAfter=4, spaceBefore=8,
                    leading=14)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=9.5, textColor=NAVY_DARK, leading=13,
                      alignment=TA_JUSTIFY, spaceAfter=4)
BODY_TIGHT = ParagraphStyle("BodyTight", parent=BODY, spaceAfter=2)
CODE = ParagraphStyle("Code", parent=styles["Code"], fontName="Courier",
                      fontSize=8.5, textColor=NAVY_DARK, leading=11,
                      leftIndent=10, backColor=TINT)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=8.5, textColor=GREY,
                      leftIndent=8, leading=11, alignment=TA_LEFT)
COVER_TITLE = ParagraphStyle("CoverTitle", parent=H1, fontSize=42,
                             leading=46, alignment=TA_LEFT, textColor=WHITE,
                             spaceAfter=8)
COVER_SUB = ParagraphStyle("CoverSub", parent=BODY, fontSize=14,
                           leading=18, alignment=TA_LEFT, textColor=AMBER,
                           spaceAfter=20)
COVER_META = ParagraphStyle("CoverMeta", parent=BODY, fontSize=10,
                            leading=13, alignment=TA_LEFT, textColor=CREAM)

# ============================================================
# PAGE TEMPLATES
# ============================================================

def cover_page(canvas, doc):
    canvas.saveState()
    # Sfondo navy
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    # Banda amber bottom
    canvas.setFillColor(AMBER)
    canvas.rect(0, 0, A4[0], 8*mm, fill=1, stroke=0)
    canvas.setFillColor(AMBER)
    canvas.rect(0, A4[1]-4*mm, A4[0], 4*mm, fill=1, stroke=0)
    # Logo testo
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 56)
    canvas.drawString(25*mm, A4[1]-80*mm, "Metan.")
    canvas.setFillColor(AMBER)
    canvas.drawString(25*mm + canvas.stringWidth("Metan.", "Helvetica-Bold", 56),
                      A4[1]-80*mm, "iQ")
    # Sottotitolo
    canvas.setFillColor(CREAM)
    canvas.setFont("Helvetica", 14)
    canvas.drawString(25*mm, A4[1]-92*mm, "Decision Intelligence Platform")
    canvas.drawString(25*mm, A4[1]-99*mm, "per biometano DM 2022 / RED III")
    # Box titolo manuale
    canvas.setStrokeColor(AMBER)
    canvas.setLineWidth(2)
    canvas.line(25*mm, A4[1]-115*mm, A4[0]-25*mm, A4[1]-115*mm)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 28)
    canvas.drawString(25*mm, A4[1]-135*mm, "MANUALE UTENTE")
    canvas.setFillColor(AMBER)
    canvas.setFont("Helvetica", 12)
    canvas.drawString(25*mm, A4[1]-145*mm,
                      "Guida operativa completa - funzioni, calcoli, workflow")
    # Footer cover
    canvas.setFillColor(CREAM)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(25*mm, 20*mm, "Versione documento: 1.0")
    canvas.drawString(25*mm, 16*mm,
                      f"Data emissione: {date.today().strftime('%d/%m/%Y')}")
    canvas.drawString(25*mm, 12*mm,
                      "Software: Metan.iQ v0.5.0 - branch dm2022-only")
    canvas.drawRightString(A4[0]-25*mm, 12*mm,
                           "(c) Carlo Sicurini - Tutti i diritti riservati")
    canvas.restoreState()


def std_page(canvas, doc):
    canvas.saveState()
    # Header
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1]-18*mm, A4[0], 18*mm, fill=1, stroke=0)
    canvas.setFillColor(AMBER)
    canvas.rect(0, A4[1]-19*mm, A4[0], 1*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(20*mm, A4[1]-12*mm, "Metan.iQ")
    canvas.setFillColor(AMBER)
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(A4[0]-20*mm, A4[1]-12*mm, "Manuale Utente")
    # Footer
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20*mm, 12*mm,
                      "(c) Metan.iQ - Decision Intelligence Platform per biometano DM 2022 / RED III")
    canvas.drawRightString(A4[0]-20*mm, 12*mm, f"Pag. {doc.page}")
    # Banda amber bottom
    canvas.setFillColor(AMBER)
    canvas.rect(0, 6*mm, A4[0], 1*mm, fill=1, stroke=0)
    canvas.restoreState()


# ============================================================
# HELPERS
# ============================================================

def p(text, style=BODY):
    return Paragraph(text, style)


def section(title):
    return [PageBreak(), Paragraph(title, H1)]


def subsec(title):
    return Paragraph(title, H2)


def subsub(title):
    return Paragraph(title, H3)


def bullet_list(items):
    return ListFlowable(
        [ListItem(p(t), leftIndent=0) for t in items],
        bulletType="bullet", start="-", leftIndent=14,
        bulletFontName="Helvetica-Bold", bulletFontSize=9,
    )


def kv_table(rows, col_widths=(70*mm, 100*mm)):
    data = [[p(f"<b>{k}</b>", BODY_TIGHT), p(v, BODY_TIGHT)] for k, v in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), TINT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, GREY_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def data_table(header, rows, col_widths=None):
    if col_widths is None:
        col_widths = [170*mm / (len(header))] * len(header)
    data = [[p(f"<b>{c}</b>", BODY_TIGHT) for c in header]] + \
           [[p(str(c), BODY_TIGHT) for c in r] for r in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TINT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, GREY_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def callout(text, kind="info"):
    bg = TINT if kind == "info" else colors.HexColor("#FFF4E0")
    border = AMBER if kind == "warn" else GREY_LIGHT
    t = Table([[p(text)]], colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ============================================================
# BUILD DOCUMENT
# ============================================================

def build():
    doc = BaseDocTemplate(
        OUTPUT_PATH, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=24*mm, bottomMargin=22*mm,
        title="Metan.iQ - Manuale Utente",
        author="Carlo Sicurini",
        subject="Manuale operativo software Metan.iQ",
    )
    frame_cover = Frame(0, 0, A4[0], A4[1], leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0, id="cover")
    frame_std = Frame(20*mm, 22*mm, A4[0]-40*mm, A4[1]-46*mm,
                      leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, id="std")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame_cover], onPage=cover_page),
        PageTemplate(id="std", frames=[frame_std], onPage=std_page),
    ])

    story = []

    # ---------------- COVER ----------------
    story.append(Spacer(1, 1))
    story.append(PageBreak())  # apre la pagina cover, poi passa a std

    # Forziamo passaggio al template std
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.insert(0, NextPageTemplate("cover"))
    story.insert(2, NextPageTemplate("std"))

    # ---------------- INDICE ----------------
    story.append(p("Indice", H1))
    toc_rows = [
        ("1.", "Scopo del software e contesto normativo"),
        ("2.", "Architettura e tecnologie"),
        ("3.", "Avvio dell'app: prima schermata e sidebar"),
        ("4.", "Tab 1 - Conduzione Giornaliera Standard (UNI-TS / RED III)"),
        ("5.", "Tab 2 - Conduzione Giornaliera Analisi (BMT / Override EF)"),
        ("6.", "Tab 3 - Risultati, Incentivi e Business Plan"),
        ("7.", "Logica di calcolo GHG (RED III All.V Parte C)"),
        ("8.", "Calcolo aux_factor e bilancio energetico"),
        ("9.", "Vincoli normativi e verifica compliance mensile"),
        ("10.", "Export: PDF, Excel, CSV"),
        ("11.", "Anagrafica impianto e audit trail"),
        ("12.", "FAQ e troubleshooting"),
        ("A.", "Appendice - Formule normative complete"),
        ("B.", "Appendice - Costanti fisiche e fattori emissivi"),
        ("C.", "Appendice - Database biomasse (estratto)"),
    ]
    toc_table = Table(
        [[p(f"<b>{n}</b>", BODY_TIGHT), p(t, BODY_TIGHT)] for n, t in toc_rows],
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

    # ---------------- CAP 1 ----------------
    story.extend(section("1. Scopo del software e contesto normativo"))
    story.append(p(
        "<b>Metan.iQ</b> e' una <b>Decision Intelligence Platform</b> "
        "(piattaforma di intelligenza decisionale) progettata per gli "
        "operatori di impianti di biometano e biogas cogenerativo "
        "che operano sotto il regime <b>DM 15 settembre 2022</b> "
        "(incentivazione del biometano immesso in rete) e le direttive "
        "europee <b>RED II (2018/2001)</b> e <b>RED III (2023/2413)</b>."
    ))
    story.append(p(
        "Lo strumento copre l'intero ciclo operativo dell'impianto a livello "
        "<b>mensile</b>, dalla pianificazione del mix biomasse alla "
        "verifica della sostenibilita' GHG, dalla conformita' ai vincoli "
        "autorizzativi alla generazione dei report ufficiali per audit "
        "RINA / SGS / ISCC e dossier conformita' verso GSE / MASE."
    ))

    story.append(subsec("1.1 Obiettivi principali"))
    story.append(bullet_list([
        "<b>Tracciare</b> giorno per giorno biomasse caricate e Sm3 netti "
        "immessi in rete (letti dalla cabina REMI).",
        "<b>Calcolare</b> il risparmio GHG (saving %) secondo la "
        "metodologia RED III Allegato V Parte C e UNI/TS 11567:2024.",
        "<b>Verificare</b> il rispetto della soglia normativa di saving "
        "(80% per impianti nuovi rete/calore, 65% trasporti) sul lotto "
        "di sostenibilita' MENSILE.",
        "<b>Verificare</b> il rispetto del cap autorizzativo (es. 300 Sm3/h "
        "medi mensili).",
        "<b>Ottimizzare</b> il mix biomasse via solver LP per massimizzare "
        "saving GHG o ricavi tariffari rispettando i vincoli.",
        "<b>Pianificare</b> il business plan a 15 anni con tariffe DM 2022, "
        "premi matrice, PNRR conto capitale, OPEX, finance.",
        "<b>Esportare</b> dossier audit-ready (PDF brand, Excel 4 fogli, "
        "CSV separato ;) per consulenti tecnici, OdC, GSE.",
    ]))

    story.append(subsec("1.2 Riferimenti normativi applicati"))
    story.append(data_table(
        ["Norma", "Ambito di applicazione"],
        [
            ["DM 15/09/2022", "Tariffe biometano in rete (TR per taglia, 15 anni)"],
            ["RED III (Dir. UE 2023/2413)", "Soglie saving GHG, metodologia Allegato V Parte C"],
            ["RED II (Dir. UE 2018/2001)", "Quadro normativo precedente, ancora applicabile per impianti pre-2021"],
            ["D.Lgs. 199/2021", "Recepimento italiano RED II"],
            ["D.Lgs. 5/2026 (atteso)", "Recepimento italiano RED III"],
            ["UNI/TS 11567:2024", "Calcolo emissioni GHG biocombustibili, rese standard, fattori emissivi"],
            ["GSE Linee Guida 2024", "Modalita' operative attuative DM 2022, Lotti di Sostenibilita'"],
            ["JEC WTT v5", "Joint Research Centre Well-to-Tank, fattori emissivi default"],
            ["Reg. UE 2022/996", "GWP aggiornati (CH4 = 28, N2O = 265)"],
            ["UNI EN 16723-1", "Specifiche biometano per immissione in rete (LHV, % CH4)"],
        ],
        col_widths=[55*mm, 115*mm]
    ))

    story.append(subsec("1.3 Regola fondamentale di compliance"))
    story.append(callout(
        "<b>La sostenibilita' GHG si verifica sul LOTTO MENSILE, non sul "
        "singolo giorno.</b> Il saving giornaliero mostrato in tabella e' "
        "solo informativo. Il verdetto ufficiale <b>Compliant / Non "
        "Compliant</b> e' calcolato sull'aggregato mensile, secondo la "
        "regola dei <b>Lotti di Sostenibilita' (LS)</b> della UNI/TS "
        "11567:2024 (durata max 6 mesi, mensile per prassi GSE).",
        kind="warn"
    ))
    story.append(p(
        "Conseguenza pratica: un mese puo' essere <b>Compliant</b> anche se "
        "alcuni giorni isolati hanno saving giornaliero sotto soglia, "
        "purche' la media pesata sull'energia dell'intero mese rispetti "
        "il limite normativo. Questo permette di compensare giorni 'cattivi' "
        "(mais puro, alto eec) con giorni 'buoni' (reflui, manure credit)."
    ))

    # ---------------- CAP 2 ----------------
    story.extend(section("2. Architettura e tecnologie"))
    story.append(p(
        "Metan.iQ e' un'applicazione web monolitica costruita su <b>Streamlit</b> "
        "(framework Python per data app). L'utente interagisce tramite browser; "
        "tutti i calcoli avvengono server-side in Python."
    ))

    story.append(subsec("2.1 Stack tecnico"))
    story.append(kv_table([
        ("Frontend / runtime", "Streamlit 1.57+ (Python 3.11+)"),
        ("Motore di calcolo", "NumPy, SciPy (solver LP linprog), pandas"),
        ("Visualizzazione", "Plotly (grafici), HTML/CSS Material 3 custom"),
        ("Export PDF", "ReportLab (template brand Metan.iQ)"),
        ("Export Excel", "openpyxl (4-6 fogli, formattazione condizionale)"),
        ("Export PPTX", "python-pptx (8 slide annuali)"),
        ("Persistenza locale", "SQLite (data/metaniq_daily.db)"),
        ("i18n", "Dizionari IT/EN con substring replacement"),
        ("Theme", "Light / Dark switcher (palette navy + amber, font Outfit)"),
        ("Hosting di riferimento", "Streamlit Cloud (privato, branch dm2022-only)"),
    ]))

    story.append(subsec("2.2 Struttura logica del codice"))
    story.append(data_table(
        ["Modulo", "Responsabilita'"],
        [
            ["app_mensile.py", "Entry point Streamlit, UI principale, calcoli, FEEDSTOCK_DB"],
            ["core/daily_model.py", "DailyEntry, compute_daily() - calcolo giornaliero"],
            ["core/monthly_aggregate.py", "aggregate_month() - aggregato mensile GHG"],
            ["core/sustainability.py", "evaluate_monthly_sustainability() - verdetto"],
            ["core/constants.py", "LHV biometano, NM3_TO_MWH, FFC, GWP, soglie"],
            ["core/calculation_engine.py", "ghg_summary(), e_total_feedstock()"],
            ["core/persistence.py", "Salvataggio / caricamento SQLite"],
            ["output/monthly_kpis.py", "KPI builder, calcoli di sintesi"],
            ["output/output_builder.py", "Builder dati tabellari per UI ed export"],
            ["export/daily_pdf.py", "Generatore report PDF brand Metan.iQ"],
            ["export/daily_excel.py", "Generatore Excel 4-6 fogli"],
            ["bmt_override.py", "Override rese da BMT (lab analysis)"],
            ["emission_factors_override.py", "Override fattori emissivi (relazione tecnica)"],
            ["dossier_conformita.py", "PDF dossier conformita' OdC"],
            ["theme_editorial.py", "Override CSS estetico iniettato post design system"],
        ],
        col_widths=[60*mm, 110*mm]
    ))

    # ---------------- CAP 3 ----------------
    story.extend(section("3. Avvio dell'app: prima schermata e sidebar"))
    story.append(p(
        "Aprendo l'URL dell'app (es. https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/) "
        "si presenta una schermata divisa in:"
    ))
    story.append(bullet_list([
        "<b>Sidebar a sinistra:</b> selettori globali (lingua, regime, mese di "
        "lavoro, biomasse attive, parametri tecnici impianto).",
        "<b>Area principale a destra:</b> tre macro-tab di lavoro "
        "(Standard / Analisi / Risultati).",
        "<b>Header in alto:</b> brand Metan.iQ con badge versione e regime "
        "attivo (DM 2022 / RED III).",
        "<b>Footer:</b> link legali (Privacy, Terms), versione software.",
    ]))

    story.append(subsec("3.1 Sidebar: pannello di controllo globale"))
    story.append(p("La sidebar contiene i seguenti gruppi di controlli:"))
    story.append(data_table(
        ["Sezione", "Controllo", "Funzione"],
        [
            ["Lingua", "Selettore IT / EN",
             "Cambia tutte le label dell'app, formato numeri e date"],
            ["Tema", "Toggle Light / Dark",
             "Switcher palette colori, mantiene leggibilita' WCAG AA"],
            ["Anno / Mese", "Number input / Select",
             "Periodo di lavoro per cui caricare/salvare dati"],
            ["ID impianto", "Text input",
             "Discriminante per gestire piu' impianti nello stesso DB"],
            ["Regime", "Radio DM 2022 / DM 2018 / FER2",
             "Cambia soglia GHG e cap autorizzativo"],
            ["Biomasse attive", "Multiselect su FEEDSTOCK_DB",
             "Definisce le colonne disponibili nella tabella giornaliera"],
            ["Plant net Sm3/h", "Number input (default 300)",
             "Cap autorizzativo Sm3/h immessi in rete"],
            ["Aux factor", "Auto (Config Tecnica) o manuale",
             "Rapporto Sm3 lordi / Sm3 netti, default 1.29 (JRC-CONCAWE)"],
            ["ep totale", "Auto da config upgrading o manuale",
             "Emissioni processing impianto (gCO2eq/MJ)"],
            ["Manure credit", "Checkbox per biomassa (default ON)",
             "Attiva/disattiva eec negativo per reflui zootecnici"],
        ],
        col_widths=[30*mm, 50*mm, 90*mm]
    ))
    story.append(callout(
        "<b>Importante:</b> qualunque modifica in sidebar ricalcola "
        "<b>immediatamente</b> tutta l'app. Se modifichi un parametro tecnico "
        "(es. aux_factor) durante l'analisi, i KPI mensili e il PDF tengono "
        "conto del nuovo valore senza dover salvare."
    ))

    # ---------------- CAP 4 ----------------
    story.extend(section("4. Tab 1 - Conduzione Giornaliera Standard"))
    story.append(p(
        "Tab di lavoro principale per la <b>gestione operativa quotidiana</b>. "
        "Usa rese e fattori emissivi <b>standard</b> della UNI/TS 11567:2024 "
        "(Prospetto A.5). Indicato per uso routinario senza analisi di laboratorio."
    ))

    story.append(subsec("4.1 Tabella biomasse giornaliere"))
    story.append(p(
        "E' la tabella centrale del software. Una riga per ogni giorno del mese "
        "(28-31 a seconda del mese, anno bisestile gestito). Colonne dinamiche "
        "in base alle biomasse selezionate in sidebar."
    ))
    story.append(p("<b>Colonne tipiche:</b>"))
    story.append(bullet_list([
        "<b>Data</b> - generata automaticamente.",
        "<b>Trinciato di mais, Liquame suino, ...</b> - una colonna per ogni "
        "biomassa attiva. Input in <b>tonnellate / giorno</b>.",
        "<b>Tot biomasse t</b> - somma riga (calcolata).",
        "<b>Sm3 lordi</b> - calcolato da (sum massa x resa biomassa).",
        "<b>Sm3 netti</b> - <b>INSERITO DALL'OPERATORE</b> il giorno dopo "
        "leggendo la cabina REMI. Senza questo valore i KPI di portata e "
        "produzione netta sono 0.",
        "<b>Sm3/h netti</b> - calcolato come Sm3 netti / ore funzionamento.",
        "<b>MWh</b> - calcolato come Sm3 netti x NM3_TO_MWH (0.00979).",
        "<b>eec</b> - emissioni colture pesate sull'energia del giorno.",
        "<b>esca / etd / ep</b> - emissioni altre componenti.",
        "<b>e_total</b> - somma componenti, in gCO2eq/MJ.",
        "<b>Saving giornaliero (stima %)</b> - (80 - e_total) / 80 x 100. "
        "Solo informativo, non vincolante.",
        "<b>Cap OK</b> - True se Sm3/h netti <= 300 (o cap autorizzativo).",
        "<b>Cumulato Sm3 / MWh / t</b> - progressivi mese.",
    ]))

    story.append(subsec("4.2 Workflow giornaliero passo-passo"))
    story.append(data_table(
        ["Step", "Azione operatore", "Effetto nel software"],
        [
            ["1", "Apri il mese di lavoro in sidebar",
             "Carica dati salvati o crea mese vuoto"],
            ["2", "Inserisci massa biomasse del giorno (t)",
             "Calcola in tempo reale Sm3 lordi attesi, eec, e_total"],
            ["3", "Il giorno successivo, leggi cabina REMI",
             "Inserisci Sm3 netti immessi nella colonna 'Sm3 netti'"],
            ["4", "Verifica saving giornaliero (informativo)",
             "Vedi se sei sopra/sotto soglia per il giorno"],
            ["5", "Verifica Cap OK (Sm3/h)",
             "Verifica non superi cap autorizzativo"],
            ["6", "Salva il mese (pulsante in basso)",
             "Scrive su SQLite locale"],
            ["7", "A fine mese, controlla KPI aggregato",
             "Saving GHG mese vs soglia 80% - esito Compliant/Non Compliant"],
            ["8", "Esporta report PDF / Excel / CSV",
             "Dossier per archivio aziendale, OdC, GSE"],
        ],
        col_widths=[12*mm, 75*mm, 83*mm]
    ))

    story.append(subsec("4.3 KPI mensili"))
    story.append(p("Sotto la tabella appaiono 4 metriche principali:"))
    story.append(bullet_list([
        "<b>Biomassa mese (t)</b> - totale tonnellate caricate.",
        "<b>Sm3 netti mese</b> - totale REMI immesso in rete.",
        "<b>MWh netti mese</b> - energia netta (= Sm3 netti x 0.00979).",
        "<b>Saving GHG (%)</b> - calcolato sull'aggregato mensile, "
        "con badge <b>COMPLIANT</b> (verde) o <b>NON COMPLIANT</b> (rosso) "
        "e indicazione del margine vs soglia.",
    ]))

    story.append(subsec("4.4 Pulsanti operativi"))
    story.append(data_table(
        ["Pulsante", "Effetto"],
        [
            ["Ricarica da DB", "Riporta i dati dal SQLite (scarta modifiche non salvate)"],
            ["Nuovo mese (vuoto)", "Azzera la tabella (cura: perde dati non salvati)"],
            ["Salva mese", "Persiste dati su data/metaniq_daily.db"],
            ["Esporta PDF", "Genera report mensile brand Metan.iQ (7 pagine)"],
            ["Esporta Excel", "Genera workbook 4 fogli (Riepilogo, Giornaliera, Anagrafica, Vincoli)"],
            ["Esporta CSV", "Genera CSV (sep ;, dec ,, UTF-8) per import Excel italiano"],
            ["Genera dossier conformita'", "PDF audit-ready per OdC (RINA/SGS/ISCC)"],
            ["Risolvi 1 incognita", "Solver LP per quantita' ottimale di 1 biomassa"],
            ["Risolvi 2 incognite", "Solver LP dual (saving + produzione target)"],
        ],
        col_widths=[55*mm, 115*mm]
    ))

    # ---------------- CAP 5 ----------------
    story.extend(section("5. Tab 2 - Conduzione Giornaliera Analisi (BMT / Override EF)"))
    story.append(p(
        "Variante <b>avanzata</b> del Tab 1, destinata a operatori che dispongono "
        "di <b>BMT</b> (Biological Methane Potential, test di laboratorio sulla "
        "resa metanogena specifica delle proprie biomasse) e/o di una "
        "<b>Relazione Tecnica</b> con fattori emissivi su misura validati "
        "dal proprio OdC."
    ))

    story.append(subsec("5.1 Override BMT (rese)"))
    story.append(p(
        "Permette di sostituire le rese standard del Prospetto A.3 UNI/TS "
        "11567:2024 con valori da analisi laboratorio. Tipicamente:"
    ))
    story.append(bullet_list([
        "Rese reali pesate (umide) o normalizzate su ST (Sostanza Totale) / SV "
        "(Sostanza Volatile).",
        "Conversione Nm3 biogas -> Nm3 CH4 tramite %CH4 medio misurato.",
        "Riconciliazione con il dato di campo (Sm3 netti REMI) tramite scarto "
        "% atteso (deve essere <= +/- 15% per validita' LS).",
    ]))
    story.append(callout(
        "Quando attivi un override BMT, l'audit trail del PDF lo riporta "
        "esplicitamente come <b>'Origine rese: BMT override'</b>. Questa "
        "informazione e' obbligatoria per audit OdC."
    ))

    story.append(subsec("5.2 Override fattori emissivi"))
    story.append(p(
        "Sostituisce i valori standard di <b>eec, esca, etd, ep</b> con valori "
        "da Relazione Tecnica certificata. Tipicamente:"
    ))
    story.append(bullet_list([
        "<b>eec</b> custom per biomasse non tabulate o per dichiarazioni "
        "specifiche del fornitore (es. manure credit con vasca aperta documentata).",
        "<b>ep</b> custom da bilancio energetico reale dell'impianto "
        "(consumi elettrici, termici, slip CH4 misurato).",
        "<b>etd</b> custom da rilievo logistico (km, mezzo, ritorno a vuoto).",
    ]))

    # ---------------- CAP 6 ----------------
    story.extend(section("6. Tab 3 - Risultati, Incentivi e Business Plan"))
    story.append(p(
        "Tab di sintesi annuale / strategica. Aggrega 12 mesi e calcola "
        "ricavi, OPEX, CAPEX, business plan a 15 anni."
    ))

    story.append(subsec("6.1 Configurazione impianto (ep)"))
    story.append(p(
        "Sezione tecnica per definire il bilancio energetico dell'impianto, "
        "che determina automaticamente:"
    ))
    story.append(bullet_list([
        "<b>aux_factor</b> = Sm3 lordi / Sm3 netti, dipende da tecnologia "
        "upgrading (ammine, PSA, membrane), gestione off-gas (RTO, flare), "
        "fonti calore (autoconsumo biometano, biogas, esterno) ed elettricita' "
        "(rete, FV, cogen).",
        "<b>ep_total</b> = somma EP_UPGRADING + EP_OFFGAS + EP_HEAT + EP_ELEC, "
        "in gCO2eq/MJ. Vincolato a <b>>= 0</b> per RED III All.V Parte C "
        "(off-gas RTO non puo' rendere ep negativo).",
    ]))

    story.append(subsec("6.2 DM 2022 - Tariffe e premi"))
    story.append(p(
        "Configurazione lato incentivo. L'utente seleziona:"
    ))
    story.append(bullet_list([
        "<b>Taglia impianto</b> (scaglione Sm3/h) - determina la tariffa di "
        "riferimento (TR).",
        "<b>Ribasso d'asta</b> applicato in gara GSE.",
        "<b>Premi matrice</b> cumulabili (Annex IX, kWh recuperato, lavoro "
        "agricolo, premio cogenerazione).",
        "<b>PNRR conto capitale</b> - aliquota di contributo (max 40%) e "
        "massimale di spesa eleggibile (euro/Sm3h).",
    ]))

    story.append(subsec("6.3 Business plan 15 anni"))
    story.append(p(
        "Costruisce un piano economico-finanziario completo:"
    ))
    story.append(bullet_list([
        "<b>CAPEX</b> per voce (movimenti terra, civili, tecnologico, "
        "upgrading, varie) scalato con plant_size.",
        "<b>OPEX</b> annuale per voce (O&M, gestore, service, assicurazioni).",
        "<b>Finanziamento</b> a leva (default 70% leverage, 5% tasso, 15 anni).",
        "<b>Conto economico</b> con ricavi tariffari, OPEX, ammortamenti, "
        "imposte (IRES + IRAP semplificato 24%).",
        "<b>Free Cash Flow</b> e indicatori (NPV, IRR, payback).",
    ]))

    # ---------------- CAP 7 ----------------
    story.extend(section("7. Logica di calcolo GHG (RED III All.V Parte C)"))
    story.append(p(
        "Questa sezione descrive analiticamente la formula applicata dal "
        "software per calcolare il risparmio GHG. E' il cuore tecnico-normativo "
        "del prodotto e ogni numero in output deriva da queste relazioni."
    ))

    story.append(subsec("7.1 Formula generale RED III"))
    story.append(p("Per ogni Lotto di Sostenibilita' (LS = mese aggregato):"))
    story.append(callout(
        "<b>E = eec + el + ep + etd + eu - esca - eccs - eccr</b><br/>"
        "[gCO2eq / MJ biometano]<br/><br/>"
        "Risparmio (%) = (FFC - E) / FFC x 100"
    ))
    story.append(data_table(
        ["Termine", "Significato", "Tipico biometano"],
        [
            ["eec", "Estrazione/coltivazione materie prime", "0 (rifiuti) a 29 (mais)"],
            ["el", "Lavorazione (digestione)", "incluso in ep nel modello"],
            ["ep", "Processing (upgrading, calore, elettricita')", "0 a 10 (cap >= 0)"],
            ["etd", "Trasporto e distribuzione", "0.8 (default standard)"],
            ["eu", "Uso del carburante", "0 (biometano ad uso rete)"],
            ["esca", "Credito accumulo C nel suolo", "0 (default)"],
            ["eccs/eccr", "Credito cattura CO2", "0 (default)"],
            ["FFC", "Fossil Fuel Comparator", "80 rete/calore, 94 trasporti, 183 elettr."],
        ],
        col_widths=[20*mm, 90*mm, 60*mm]
    ))

    story.append(subsec("7.2 Calcolo aggregato sul lotto mensile"))
    story.append(p(
        "Il punto critico - <b>NON e' una media aritmetica dei saving "
        "giornalieri</b>. Per UNI/TS 11567:2024 e RED III All.V Parte C, "
        "l'aggregazione avviene sull'energia totale del lotto:"
    ))
    story.append(callout(
        "<b>e_w_lotto = SOMMA (e_biomassa_i x Energia_biomassa_i) / "
        "SOMMA (Energia_biomassa_i)</b><br/><br/>"
        "dove Energia_i = massa_i x resa_CH4_i x LHV<br/>"
        "e e_biomassa_i = eec_i + esca_i + etd_i + ep<br/><br/>"
        "Saving_lotto = (FFC - e_w_lotto) / FFC x 100"
    ))
    story.append(p(
        "<b>Implicazione operativa:</b> giorni con saving giornaliero <80% "
        "non rendono automaticamente il mese non conforme. Vengono 'diluiti' "
        "da giorni a saving alto grazie alla pesatura sull'energia. Il "
        "verdetto finale e' sul totale mese."
    ))

    story.append(subsec("7.3 Sistema tier difendibilita' eec (A/B/C/D)"))
    story.append(p(
        "Ogni biomassa nel software e' classificata per <b>livello di "
        "difendibilita' del valore eec in audit</b>:"
    ))
    story.append(data_table(
        ["Tier", "Significato", "eec tipico"],
        [
            ["A - Default normativo", "Tabellato Prospetto A.5 UNI/TS",
             "Mais 29, Sorgo 26, rifiuti 0"],
            ["B - Zero da regola", "Residuo Annex IX non tabulato",
             "0 (regola residui)"],
            ["C - Stima conservativa", "Letteratura JEC/KTBL a sfavore",
             "positivo, non contestabile"],
            ["D - Manure credit", "Credito reflui zootecnici",
             "negativo (-45 std), richiede baseline fornitore"],
        ],
        col_widths=[40*mm, 70*mm, 60*mm]
    ))

    story.append(subsec("7.4 Manure credit (Tier D)"))
    story.append(p(
        "Per reflui zootecnici (liquame suino/bovino, pollina, etc.) il "
        "software applica per default un eec <b>-45 gCO2eq/MJ</b> (RED III "
        "All.V/VI). Questo credito riflette le emissioni di metano <b>evitate</b> "
        "rispetto allo stoccaggio in vasca/lagone aperto (decomposizione "
        "anaerobica spontanea)."
    ))
    story.append(callout(
        "Il manure credit richiede <b>dichiarazione baseline del fornitore</b> "
        "in audit OdC. Se il fornitore stocca in vasca COPERTA con captazione "
        "o N-stripping, il credit va ridotto o annullato. Il software emette "
        "warning specifico per ogni biomassa con credit attivo.",
        kind="warn"
    ))

    # ---------------- CAP 8 ----------------
    story.extend(section("8. Calcolo aux_factor e bilancio energetico"))
    story.append(p(
        "L'<b>aux_factor</b> (fattore servizi ausiliari) e' il rapporto tra "
        "Sm3 di biometano <b>lordi</b> prodotti dal fermentatore e Sm3 <b>netti</b> "
        "effettivamente immessi in rete. Tiene conto degli autoconsumi "
        "energetici dell'impianto."
    ))

    story.append(subsec("8.1 Formula"))
    story.append(callout(
        "<b>aux_factor = 1 / (1 - f_calore - f_elettrico - f_slip - f_margine)</b><br/><br/>"
        "Sm3_netti = Sm3_lordi / aux_factor"
    ))
    story.append(p("Le frazioni di autoconsumo dipendono dalla configurazione:"))
    story.append(bullet_list([
        "<b>f_calore</b> - frazione di biometano destinata alla caldaia "
        "per riscaldare il fermentatore (0 se calore esterno o cogenerazione).",
        "<b>f_elettrico</b> - frazione bruciata in CHP interno per "
        "produrre elettricita' di autoconsumo (0 se rete o FV).",
        "<b>f_slip</b> - perdite metano in upgrading (PSA, ammine, membrane). "
        "Tipicamente 0.5% - 2%.",
        "<b>f_margine</b> - margine prudenziale (3% default).",
    ]))

    story.append(subsec("8.2 Valore default e range"))
    story.append(kv_table([
        ("Default DEFAULT_AUX_FACTOR", "1.29 (JRC-CONCAWE)"),
        ("Range tipico ammine + autoconsumo termico", "1.20 - 1.32"),
        ("Range tipico PSA + elettricita' rete", "1.10 - 1.18"),
        ("Range tipico membrane + cogen", "1.15 - 1.25"),
        ("Override manuale", "Disponibile in 'Config Tecnica & GHG'"),
    ]))

    # ---------------- CAP 9 ----------------
    story.extend(section("9. Vincoli normativi e verifica compliance mensile"))
    story.append(p(
        "Il software verifica automaticamente DUE vincoli a fine mese:"
    ))

    story.append(subsec("9.1 Vincolo A - Soglia saving GHG"))
    story.append(p(
        "Confronta saving_mese aggregato con la soglia del regime selezionato:"
    ))
    story.append(data_table(
        ["Entrata in servizio impianto", "Uso", "Soglia"],
        [
            ["Prima 5 ott 2015", "Trasporti", "50%"],
            ["5 ott 2015 - 31 dic 2020", "Trasporti", "60%"],
            ["Dal 1 gen 2021", "Trasporti", "65%"],
            ["Dal 1 gen 2021", "Elettricita' / calore (>1 MW)", "70%"],
            ["Dal 1 gen 2026 (impianti nuovi)", "Elettricita' / calore", "80%"],
        ],
        col_widths=[60*mm, 60*mm, 50*mm]
    ))
    story.append(callout(
        "La data rilevante e' quella di <b>entrata in servizio dell'impianto "
        "di biogas originario</b>, NON dell'upgrading. Riconfigurabile in "
        "sidebar."
    ))

    story.append(subsec("9.2 Vincolo B - Cap autorizzativo Sm3/h"))
    story.append(p(
        "Verifica che la portata media mensile non superi il cap "
        "dell'autorizzazione AUA / VIA. Default 300 Sm3/h, modificabile "
        "in sidebar 'plant_net Sm3/h'."
    ))

    story.append(subsec("9.3 Esito finale"))
    story.append(p(
        "Il mese e' <b>COMPLIANT</b> se ENTRAMBI i vincoli sono soddisfatti. "
        "Il PDF mensile mostra il verdetto in copertina con badge colorato "
        "(verde = OK, rosso = KO) e dettaglia il margine in punti percentuali."
    ))

    # ---------------- CAP 10 ----------------
    story.extend(section("10. Export: PDF, Excel, CSV"))
    story.append(subsec("10.1 PDF mensile (7 pagine)"))
    story.append(p("Struttura del PDF brand Metan.iQ generato:"))
    story.append(data_table(
        ["Pag.", "Contenuto"],
        [
            ["1", "Copertina - Esito ufficiale, KPI principali (Biomasse, Sm3, MWh, Saving)"],
            ["2", "Riepilogo KPI mensili + Vincoli normativi con esito"],
            ["3", "Indicazioni operative (azioni correttive fine mese)"],
            ["4-5", "Tabella giornaliera dettagliata (26 colonne)"],
            ["6", "Anagrafica simulazione & Audit Trail"],
            ["7", "Riferimenti normativi & Validazione"],
        ],
        col_widths=[15*mm, 155*mm]
    ))

    story.append(subsec("10.2 Excel (4 fogli)"))
    story.append(bullet_list([
        "<b>Riepilogo Mensile</b> - intestazione, esito, KPI principali, totali biomasse.",
        "<b>Operativita' Giornaliera</b> - tabella 26 colonne, 28-31 righe.",
        "<b>Anagrafica & Parametri</b> - voci tracciabilita' per audit.",
        "<b>Vincoli</b> - esito per ogni vincolo regime.",
    ]))

    story.append(subsec("10.3 CSV"))
    story.append(p(
        "Separatore <b>;</b>, decimale <b>,</b>, encoding UTF-8 con BOM. "
        "Apertura diretta in Excel italiano senza wizard import. "
        "Contiene la tabella giornaliera completa."
    ))

    story.append(subsec("10.4 Dossier Conformita' OdC"))
    story.append(p(
        "PDF specifico per audit RINA / SGS / ISCC. Include:"
    ))
    story.append(bullet_list([
        "Tutti i parametri di calcolo (eec, etd, ep, esca, FFC) con fonte normativa.",
        "Mass balance del lotto: scarto biomassa vs biometano (<= +/- 15%).",
        "Origine rese (standard / BMT) per ciascuna biomassa.",
        "Origine fattori emissivi (standard / Relazione Tecnica).",
        "Lista DDT di ingresso e fornitori (se anagrafati).",
        "Dichiarazioni di sostenibilita' fornitori (link).",
        "Firma elettronica responsabile filiera (placeholder).",
    ]))

    # ---------------- CAP 11 ----------------
    story.extend(section("11. Anagrafica impianto e audit trail"))
    story.append(p(
        "Sezione obbligatoria per la tracciabilita' GSE / OdC. Tutti i valori "
        "vengono riportati in copertina dei report e nel foglio "
        "<b>Anagrafica & Parametri</b> dell'Excel."
    ))
    story.append(data_table(
        ["Voce", "Note"],
        [
            ["Nome azienda", "Ragione sociale completa"],
            ["Sede legale", "Indirizzo sede legale"],
            ["Nome impianto", "Denominazione operativa"],
            ["Sede operativa", "Indirizzo impianto"],
            ["Regime applicato", "DM 2022 / DM 2018 / FER2"],
            ["Soglia normativa (%)", "80 / 70 / 65 / 60 / 50 a seconda regime"],
            ["Comparatore fossile", "80 / 94 / 183 a seconda uso finale"],
            ["Aux factor", "Da Config Tecnica oppure override"],
            ["EP totale", "Da Config Tecnica oppure override"],
            ["Plant net (Sm3/h)", "Cap autorizzativo"],
            ["Origine rese", "BMT override se attivo, altrimenti standard"],
            ["Origine fattori emissivi", "Override RT se attivo, altrimenti UNI-TS"],
            ["Giorni con dati", "Conteggio giorni compilati"],
            ["Giorni cap violato", "Conteggio giorni con Sm3/h > cap"],
        ],
        col_widths=[55*mm, 115*mm]
    ))

    # ---------------- CAP 12 ----------------
    story.extend(section("12. FAQ e troubleshooting"))
    story.append(subsec("12.1 Domande frequenti"))

    faq = [
        ("Perche' il saving mensile non e' la media dei saving giornalieri?",
         "Perche' UNI/TS 11567:2024 e RED III prescrivono l'aggregazione "
         "sull'energia del lotto. Vedi cap. 7.2 per la formula completa."),
        ("Posso avere giorni con saving < 80% senza essere Non Compliant?",
         "Si', purche' il saving mensile aggregato sia >= 80%. La "
         "compensazione tra giorni a alto e basso saving e' una "
         "caratteristica della metodologia LS."),
        ("Cosa succede se non inserisco i Sm3 netti REMI?",
         "I KPI di portata, MWh netti e ricavi vengono mostrati come 0 (o "
         "auto-derivati da PCI standard, con warning). Il saving GHG e' "
         "comunque calcolabile dalla biomassa (basato sul lordo)."),
        ("Il manure credit -45 si applica sempre?",
         "Si' per default, ma solo se il fornitore stocca i reflui in vasca "
         "APERTA. Con vasca coperta + captazione, il credit va annullato. "
         "Richiede dichiarazione baseline fornitore in audit."),
        ("ep_total puo' essere negativo (es. credito RTO off-gas)?",
         "No. Per RED III All.V Parte C, ep e' >= 0. Il software applica un "
         "floor automatico se la configurazione produrrebbe ep negativo "
         "(es. ammine + RTO con credito -8)."),
        ("Quale LHV biometano usa il software?",
         "9.79 kWh/Sm3 = 35.24 MJ/Sm3, conforme a UNI EN 16723-1 "
         "(biometano spec rete, ~98% CH4). E' il valore commercialmente "
         "difendibile in audit GSE."),
        ("I dati sono persistenti su Streamlit Cloud?",
         "Il filesystem Streamlit Cloud e' EFFIMERO: i dati salvati in "
         "sessione possono perdersi al redeploy. Si raccomanda export "
         "regolare PDF/Excel come backup, e uso locale per persistenza "
         "affidabile."),
        ("Come gestisco un fornitore non certificato?",
         "Va escluso dal LS, oppure va avviato iter certificazione. La "
         "biomassa non certificata non puo' contribuire al saving GHG "
         "dichiarato in audit."),
    ]
    for q, a in faq:
        story.append(p(f"<b>D:</b> {q}", BODY_TIGHT))
        story.append(p(f"<b>R:</b> {a}", BODY))
        story.append(Spacer(1, 4))

    story.append(subsec("12.2 Troubleshooting"))
    story.append(data_table(
        ["Problema", "Causa probabile / Azione"],
        [
            ["KPI tutti a 0 dopo apertura app",
             "Sidebar: nessuna biomassa selezionata. Aggiungi almeno una."],
            ["Saving mensile basso inatteso",
             "Verifica mix biomasse: troppo mais (eec +29) abbatte il saving. Aumenta reflui."],
            ["MWh netti != cumulato giornaliero",
             "Probabile incoerenza LHV - aggiornare a v0.5.0+ (fix UNI EN 16723-1)."],
            ["ep_total mostrato 0 ma config dice diverso",
             "Verifica floor ep >= 0: configurazione produrrebbe ep negativo (RTO off-gas)."],
            ["Tabella non aggiornabile",
             "Mese gia' chiuso (saved_at presente). Usa 'Nuovo mese' o riapri esplicitamente."],
            ["Export PDF in errore",
             "Spesso caratteri non-ASCII in anagrafica. Usa font Helvetica safe."],
            ["Solver LP nessuna soluzione",
             "Vincoli incompatibili (saving + produzione + cap). Rilassa uno dei tre."],
        ],
        col_widths=[60*mm, 110*mm]
    ))

    # ---------------- APPENDICE A ----------------
    story.extend(section("Appendice A - Formule normative complete"))
    story.append(subsec("A.1 GHG per singola biomassa"))
    story.append(callout(
        "e_biomassa = eec + esca + etd + ep<br/><br/>"
        "Tutti in gCO2eq / MJ biometano. Manure credit applicato su eec con "
        "segno negativo (es. -45 per liquame)."
    ))

    story.append(subsec("A.2 Energia biomassa (denominatore aggregato)"))
    story.append(callout(
        "Energia_i [MJ] = massa_i [t] x resa_CH4_i [Nm3/t] x LHV [MJ/Nm3]<br/><br/>"
        "LHV = 35.24 MJ/Nm3 (UNI EN 16723-1, biometano spec rete)"
    ))

    story.append(subsec("A.3 Aggregato lotto"))
    story.append(callout(
        "e_w_lotto = SOMMA(e_biomassa_i x Energia_i) / SOMMA(Energia_i)<br/><br/>"
        "Saving = (FFC - e_w_lotto) / FFC x 100<br/><br/>"
        "FFC = 80 (rete/calore) | 94 (trasporti) | 183 (elettricita')"
    ))

    story.append(subsec("A.4 Mass balance LS"))
    story.append(callout(
        "Tolleranza mass balance LS UNI/TS 11567 sec. 6:<br/>"
        "| (biometano_atteso - biometano_REMI) | / biometano_atteso <= 15%<br/><br/>"
        "Durata massima LS: 6 mesi (prassi GSE: mensile)."
    ))

    # ---------------- APPENDICE B ----------------
    story.extend(section("Appendice B - Costanti fisiche e fattori emissivi"))
    story.append(data_table(
        ["Costante", "Valore", "Fonte"],
        [
            ["LHV biometano", "35.24 MJ/Nm3 = 9.79 kWh/Sm3", "UNI EN 16723-1"],
            ["NM3_TO_MWH", "0.00979", "derivato LHV"],
            ["Purezza CH4 default", "98.0 %", "spec rete UNI EN 16723-1"],
            ["FFC rete / calore", "80 gCO2eq/MJ", "RED III All. VI"],
            ["FFC trasporti", "94 gCO2eq/MJ", "RED III All. VI"],
            ["FFC elettricita'", "183 gCO2eq/MJ", "RED III All. VI"],
            ["GWP CH4", "28", "Reg. UE 2022/996"],
            ["GWP N2O", "265", "Reg. UE 2022/996"],
            ["GWP CO2", "1", "Reg. UE 2022/996"],
            ["DEFAULT_AUX_FACTOR", "1.29", "JRC-CONCAWE"],
            ["Soglia GHG nuova rete/calore 2026+", "80 %", "RED III"],
            ["Soglia GHG trasporti 2021+", "65 %", "RED III"],
            ["Tolleranza mass balance LS", "+/- 15 %", "UNI/TS 11567:2024 sec.6"],
            ["Durata massima LS", "6 mesi", "UNI/TS 11567:2024 sec.6"],
            ["Conservazione documenti", "5 anni", "UNI/TS 11567:2024"],
        ],
        col_widths=[55*mm, 55*mm, 60*mm]
    ))

    # ---------------- APPENDICE C ----------------
    story.extend(section("Appendice C - Database biomasse (estratto)"))
    story.append(p(
        "Estratto del FEEDSTOCK_DB del software (42 biomasse totali). "
        "Mostriamo le piu' comuni; il DB completo e' in app_mensile.py."
    ))
    story.append(data_table(
        ["Biomassa", "Categoria", "eec", "etd", "Resa Nm3CH4/t", "Tier"],
        [
            ["Trinciato di mais", "Colture dedicate", "29.0", "0.8", "116.1", "A"],
            ["Trinciato di sorgo da foraggio", "Colture dedicate", "26.0", "0.8", "81.4", "A"],
            ["Triticale insilato", "Colture dedicate", "29.0", "0.8", "100", "A"],
            ["FORSU", "Rifiuto", "0.0", "0.8", "64.8", "A"],
            ["Fanghi depurazione", "Rifiuto", "0.0", "0.8", "13.0", "A"],
            ["Liquame suino", "Reflui zootecnici", "-45.0", "0.8", "14.0", "D"],
            ["Liquame bovino", "Reflui zootecnici", "-45.0", "0.8", "14.0", "D"],
            ["Liquame bufalino", "Reflui zootecnici", "-45.0", "0.8", "13.0", "D"],
            ["Letame bovino palabile", "Reflui zootecnici", "-45.0", "0.8", "35.0", "D"],
            ["Pollina broiler (lettiera)", "Reflui zootecnici", "-15.0", "0.8", "105.0", "D"],
            ["Pollina ovaiole (aerobico)", "Reflui zootecnici", "+5.0", "0.8", "84.0", "C"],
            ["Pollina tacchini", "Reflui zootecnici", "-15.0", "0.8", "95.0", "D"],
            ["Paglia cereali", "Residuo colturale", "0.0", "0.8", "60.0", "A"],
            ["Polpe sorpressate bietola", "Sottoprodotto industria", "0.0", "0.8", "57.0", "A"],
            ["Sansa olive umida", "Sottoprodotto industria", "0.0", "0.8", "44.0", "A"],
        ],
        col_widths=[50*mm, 35*mm, 15*mm, 14*mm, 32*mm, 14*mm]
    ))
    story.append(callout(
        "<b>Legenda Tier:</b><br/>"
        "<b>A</b> = Default normativo (Prospetto A.5 UNI/TS 11567:2024)<br/>"
        "<b>B</b> = Zero da regola (Annex IX non tabulato)<br/>"
        "<b>C</b> = Stima conservativa (no manure credit, es. pollina aerobica)<br/>"
        "<b>D</b> = Manure credit (richiede dichiarazione baseline fornitore)"
    ))

    story.append(Spacer(1, 20))
    story.append(p(
        "<i>Fine del manuale. Per supporto contatta carlo.sicurini@gmail.com.</i>",
        NOTE
    ))

    # Genera
    doc.build(story)
    print(f"PDF generato: {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
