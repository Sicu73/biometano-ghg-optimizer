"""Metan.iQ — Generatore XLSX editabile con formule live.

Crea un workbook Excel autocalcolante: l'utente modifica solo le celle
gialle (Ore + Biomasse) e tutti gli altri valori (produzione, saving GHG,
validita') si ricalcolano automaticamente IN EXCEL grazie alle formule.

Sheets:
- "Piano mensile": tabella editabile + formule
- "Database feedstock": tabella feedstock con yield, eec, etd, esca, e_total
- "Sintesi annuale": KPI aggregati con formule cross-sheet
"""
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.protection import SheetProtection


# ============================================================
# Design tokens (mirror dell'app)
# ============================================================
NAVY      = "0F172A"
NAVY_2    = "1E293B"
AMBER     = "F59E0B"
AMBER_DK  = "B45309"
AMBER_BG  = "FEF3C7"
SLATE_50  = "F8FAFC"
SLATE_100 = "F1F5F9"
SLATE_200 = "E2E8F0"
SLATE_400 = "94A3B8"
SLATE_500 = "64748B"
SLATE_700 = "334155"
EMERALD_BG = "D1FAE5"
EMERALD_FG = "065F46"
RED_BG     = "FECACA"
RED_FG     = "991B1B"
WHITE     = "FFFFFF"


def _border_thin():
    side = Side(style="thin", color=SLATE_200)
    return Border(left=side, right=side, top=side, bottom=side)


def _border_med():
    side = Side(style="medium", color=NAVY)
    return Border(left=side, right=side, top=side, bottom=side)


def _style_header(c):
    c.font = Font(bold=True, color=WHITE, size=10)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(
        horizontal="center", vertical="center", wrap_text=True,
    )
    c.border = _border_thin()


def _style_editable(c):
    c.fill = PatternFill("solid", fgColor=AMBER_BG)
    c.border = _border_thin()
    c.alignment = Alignment(horizontal="right", vertical="center")
    c.font = Font(color=NAVY)


def _style_readonly(c):
    c.fill = PatternFill("solid", fgColor=SLATE_50)
    c.border = _border_thin()
    c.alignment = Alignment(horizontal="right", vertical="center")
    c.font = Font(color=SLATE_700)


def _style_total(c):
    c.font = Font(bold=True, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="right", vertical="center")
    c.border = _border_thin()


# ============================================================
# Public API
# ============================================================
def build_metaniq_xlsx(ctx: dict, snapshot: bool = False) -> BytesIO:
    """Costruisce il workbook XLSX completo.

    Parametri:
      ctx: dict con active_feeds, FEEDSTOCK_DB, aux_factor, ep_total,
           fossil_comparator, ghg_threshold, plant_net_smch, MONTHS,
           MONTH_HOURS, NM3_TO_MWH, IS_CHP, plant_kwe (CHP), eta_el (CHP),
           eta_th (CHP), aux_el_pct (CHP), end_use, APP_MODE_LABEL,
           initial_data (per editabile) o df_res (per snapshot).

      snapshot: False (default) -> file EDITABILE con formule live.
                True -> file SNAPSHOT con valori statici (no formule).
    """
    wb = Workbook()

    # Forza ricalcolo completo all'apertura del file in Excel.
    try:
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.calcMode = "auto"
    except Exception:
        pass

    # === Sheet 1: Database (creata per prima per nome reference) ===
    ws_db = wb.create_sheet("Database feedstock")
    _build_database(ws_db, ctx)

    # === Sheet 2: Piano (main, attiva di default) ===
    ws_piano = wb.active
    ws_piano.title = "Piano mensile"
    _build_piano(ws_piano, ctx, ws_db.title, snapshot=snapshot)

    # === Sheet 3: Sintesi ===
    ws_sum = wb.create_sheet("Sintesi annuale")
    _build_summary(ws_sum, ctx, ws_piano.title)

    # === Sheet 4: Business Plan (sempre, anche per snapshot) ===
    # Pro forma 15 anni con formule live: CAPEX, OPEX, CE, cash flow, KPI.
    # Mode-aware: legge taglia + tariffa + autoconsumi dal ctx.
    ws_bp = wb.create_sheet("Business Plan")
    _build_business_plan(ws_bp, ctx, snapshot=snapshot)

    # Imposta Piano come sheet attiva di default
    wb.active = wb.sheetnames.index(ws_piano.title)

    # === SNAPSHOT: protezione sheet (read-only) ===
    # Tutte le celle sono "locked" di default in Excel; abilitando
    # protection.sheet=True diventano effettivamente non editabili.
    # L'utente puo' comunque selezionare/copiare/stampare.
    # Per riprendere editing: Revisione > Rimuovi protezione foglio
    # (no password).
    if snapshot:
        for sname in wb.sheetnames:
            ws = wb[sname]
            ws.protection.sheet = True
            ws.protection.formatCells     = False
            ws.protection.formatColumns   = False
            ws.protection.formatRows      = False
            ws.protection.insertColumns   = False
            ws.protection.insertRows      = False
            ws.protection.deleteColumns   = False
            ws.protection.deleteRows      = False
            ws.protection.sort            = False
            ws.protection.autoFilter      = False
            ws.protection.pivotTables     = False
            ws.protection.selectLockedCells   = False  # consente click
            ws.protection.selectUnlockedCells = False

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def build_metaniq_xlsx_snapshot(ctx: dict) -> BytesIO:
    """Comodita': snapshot XLSX (valori statici, no formule).

    Equivalente a build_metaniq_xlsx(ctx, snapshot=True).
    """
    return build_metaniq_xlsx(ctx, snapshot=True)


# ============================================================
# Sheet 1 — Database feedstock (LAYOUT ORIZZONTALE)
# ============================================================
# Layout:
#   A1: "Parametro" | B1..N1: nomi biomasse (header)
#   A2: "Resa Nm3/t" | B2..N2: yield
#   A3: "eec"        | B3..N3: eec
#   A4: "esca"       | B4..N4: esca
#   A5: "etd"        | B5..N5: etd
#   A6: "ep"         | B6..N6: ep (linkato a Piano!B9)
#   A7: "e_total"    | B7..N7: =Bi3-Bi4+Bi5+Bi6 (formula)
#
# Le formule del Piano usano range ORIZZONTALI omogenei al
# bio_range del Piano (anch'esso orizzontale, una riga per mese).
# Cosi' SUMPRODUCT(C13:F13, Database!$B$2:$E$2) ha entrambe le
# matrici 1xN -> dot product corretto, no #VALORE.
# ============================================================
def _build_database(ws, ctx):
    feeds = ctx["active_feeds"]
    fdb   = ctx["FEEDSTOCK_DB"]
    n     = len(feeds)

    # === Riga 1: header (Parametro + nomi biomasse) ===
    c = ws.cell(row=1, column=1, value="Parametro")
    _style_header(c)
    for j, name in enumerate(feeds):
        c = ws.cell(row=1, column=2 + j, value=name)
        _style_header(c)
    ws.row_dimensions[1].height = 36

    # === Righe parametri (label sx + valori a destra) ===
    rows_def = [
        # (row, label, getter, fmt, style_amber)
        (2, "Resa Nm3/t",  lambda d: float(d["yield"]), "0",     False),
        (3, "eec",         lambda d: float(d["eec"]),   "0.00",  False),
        (4, "esca",        lambda d: float(d["esca"]),  "0.00",  False),
        (5, "etd",         lambda d: float(d["etd"]),   "0.00",  False),
    ]
    for r, label, getter, fmt, _ in rows_def:
        # Label
        c_lbl = ws.cell(row=r, column=1, value=label)
        c_lbl.font = Font(bold=True, color=NAVY)
        c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
        c_lbl.alignment = Alignment(horizontal="left", indent=1)
        c_lbl.border = _border_thin()
        # Valori
        for j, name in enumerate(feeds):
            d = fdb[name]
            c_val = ws.cell(row=r, column=2 + j, value=getter(d))
            c_val.number_format = fmt
            c_val.fill = PatternFill("solid", fgColor=SLATE_50)
            c_val.alignment = Alignment(horizontal="right")
            c_val.border = _border_thin()

    # === Riga 6: ep linkato al Piano!B9 (master cell) ===
    c_lbl = ws.cell(row=6, column=1, value="ep (linkato Piano!B9)")
    c_lbl.font = Font(bold=True, color=NAVY)
    c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
    c_lbl.alignment = Alignment(horizontal="left", indent=1)
    c_lbl.border = _border_thin()
    for j in range(n):
        c_val = ws.cell(row=6, column=2 + j, value="='Piano mensile'!$B$9")
        c_val.number_format = "0.00"
        c_val.fill = PatternFill("solid", fgColor=SLATE_50)
        c_val.alignment = Alignment(horizontal="right")
        c_val.border = _border_thin()

    # === Riga 7: e_total = eec - esca + etd + ep ===
    c_lbl = ws.cell(row=7, column=1, value="e_total")
    c_lbl.font = Font(bold=True, color=AMBER_DK)
    c_lbl.fill = PatternFill("solid", fgColor=AMBER_BG)
    c_lbl.alignment = Alignment(horizontal="left", indent=1)
    c_lbl.border = _border_thin()
    for j in range(n):
        col = 2 + j
        cl = get_column_letter(col)
        c_val = ws.cell(row=7, column=col,
                        value=f"={cl}3-{cl}4+{cl}5+{cl}6")
        c_val.number_format = "0.00"
        c_val.fill = PatternFill("solid", fgColor=AMBER_BG)
        c_val.alignment = Alignment(horizontal="right")
        c_val.font = Font(bold=True, color=AMBER_DK)
        c_val.border = _border_thin()

    # === Caption finale ===
    last_r = 9
    end_col = 1 + n
    end_letter = get_column_letter(end_col)
    ws.merge_cells(start_row=last_r, start_column=1,
                   end_row=last_r, end_column=end_col)
    c = ws.cell(row=last_r, column=1,
                value=("Read-only · Layout orizzontale: ogni biomassa = una "
                       "colonna. e_total = eec - esca + etd + ep. "
                       "Modifica «ep» in «Piano mensile» cella B9 per "
                       "ricalcolare automaticamente la sostenibilita'."))
    c.font = Font(italic=True, size=9, color=SLATE_500)
    c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[last_r].height = 30

    # === Larghezze colonne ===
    ws.column_dimensions["A"].width = 26
    for j in range(n):
        ws.column_dimensions[get_column_letter(2 + j)].width = 16

    # Freeze pane: blocca header + colonna A
    ws.freeze_panes = ws["B2"]


# ============================================================
# Sheet 2 — Piano mensile (main, mode-aware + snapshot-aware)
# ============================================================
def _build_piano(ws, ctx, db_sheet_name, snapshot: bool = False):
    feeds   = ctx["active_feeds"]
    n_feed  = len(feeds)
    is_chp  = bool(ctx.get("IS_CHP", False))
    # In modalita' SNAPSHOT i valori sono statici (no formule). Le celle
    # input (Ore, Biomasse) NON sono editabili (no fill amber).
    cell_fill_input = SLATE_50 if snapshot else AMBER_BG

    # Layout columns:
    #  A: Mese (read-only)
    #  B: Ore (editable)
    #  C..C+n-1: biomasse (editable)
    #
    # BIOMETANO (DM 2022, DM 2018):
    #  Sm3 lordi | Sm3 netti | MWh netti | e_w | Saving % | Sm3/h netti | Validita
    #
    # BIOGAS CHP (DM 2012, FER 2):
    #  Sm3 lordi (CH4 eq) | Sm3 netti (CH4 motore) | MWh CH4 netti |
    #  MWh el lordi | MWh el netti rete | MWh termici |
    #  e_w | Saving % | kW lordi (medio) | Validita
    bio_col_start = 3
    bio_col_end   = 2 + n_feed
    sm3_lordi_col = bio_col_end + 1
    sm3_netti_col = sm3_lordi_col + 1
    mwh_netti_col = sm3_netti_col + 1

    if is_chp:
        # Colonne aggiuntive per CHP
        mwh_el_lordo_col = mwh_netti_col + 1
        mwh_el_netto_col = mwh_el_lordo_col + 1
        mwh_th_col       = mwh_el_netto_col + 1
        e_w_col          = mwh_th_col + 1
        saving_col       = e_w_col + 1
        kw_lordi_col     = saving_col + 1   # kW elettrici LORDI medi
        valid_col        = kw_lordi_col + 1
    else:
        # Biometano: layout originale
        e_w_col          = mwh_netti_col + 1
        saving_col       = e_w_col + 1
        smch_col         = saving_col + 1   # Sm3/h netti immissione
        valid_col        = smch_col + 1
        # Placeholder per evitare NameError nei branch successivi
        mwh_el_lordo_col = mwh_el_netto_col = mwh_th_col = kw_lordi_col = None

    L = get_column_letter
    last_col_letter = L(valid_col)

    # === Title (row 1) ===
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=valid_col)
    c = ws.cell(
        row=1, column=1,
        value=("Metan.iQ — Piano mensile (snapshot)" if snapshot
               else "Metan.iQ — Piano mensile editabile"),
    )
    c.font = Font(bold=True, size=16, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 32

    # === Subtitle (row 2) ===
    ws.merge_cells(start_row=2, start_column=1,
                   end_row=2, end_column=valid_col)
    end_use = ctx.get("end_use", "")
    app_mode_label = ctx.get("APP_MODE_LABEL", "DM 2022")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c = ws.cell(row=2, column=1,
                value=(
                    f"Modalita': {app_mode_label}  ·  "
                    f"Destinazione: {end_use}  ·  "
                    f"Generato il {now}"
                ))
    c.font = Font(italic=True, size=9, color=SLATE_500)
    c.alignment = Alignment(horizontal="left", indent=1)
    ws.row_dimensions[2].height = 18

    # === Helper banner (row 3) ===
    ws.merge_cells(start_row=3, start_column=1,
                   end_row=3, end_column=valid_col)
    if snapshot:
        banner_text = (
            "🔒 SNAPSHOT BLOCCATO — valori fotografati al download, "
            "celle in sola lettura. Per modificare e ricalcolare scarica "
            "il file «Excel modificabile» dall'app Metan.iQ."
        )
        banner_fg = SLATE_700
        banner_bg = SLATE_100
    else:
        banner_text = (
            "✏️ Modifica le celle GIALLE (Ore + Biomasse). "
            "Tutti i calcoli si aggiornano automaticamente."
        )
        banner_fg = AMBER_DK
        banner_bg = AMBER_BG
    c = ws.cell(row=3, column=1, value=banner_text)
    c.font = Font(bold=True, size=10, color=banner_fg)
    c.fill = PatternFill("solid", fgColor=banner_bg)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[3].height = 22

    # === Parametri impianto (rows 4-10 biometano, 4-13 CHP) ===
    aux_factor       = float(ctx.get("aux_factor", 1.29))
    comparator       = float(ctx.get("fossil_comparator", 80.0))
    ghg_threshold    = float(ctx.get("ghg_threshold", 0.65)) * 100
    plant_max_smch   = float(ctx.get("plant_net_smch", 300.0))
    ep_total         = float(ctx.get("ep_total", 0.0))
    nm3_to_mwh       = float(ctx.get("NM3_TO_MWH", 0.00997))
    # CHP-specific
    plant_kwe        = float(ctx.get("plant_kwe", 999.0))
    eta_el           = float(ctx.get("eta_el", 0.40))
    eta_th           = float(ctx.get("eta_th", 0.42))
    aux_el_pct       = float(ctx.get("aux_el_pct", 0.08)) * 100

    # Layout righe parametri (cell references in formulas):
    #   B5: aux_factor
    #   B6: comparator (CHP=183, biometano=80/94)
    #   B7: ghg_threshold (%)
    #   B8: plant_max  (CHP=plant_kwe in kWe LORDI; biometano=Sm3/h netti)
    #   B9: ep_total
    #   B10: PCI biometano (MWh/Sm3)
    #   --- CHP ONLY ---
    #   B11: eta_el
    #   B12: eta_th
    #   B13: aux_el_pct (%)
    common_max_label = (
        f"Potenza elettrica LORDA max (kWe targa)" if is_chp
        else f"Produzione netta max (Sm3/h)"
    )
    common_max_value = plant_kwe if is_chp else plant_max_smch
    common_max_fmt   = "0" if is_chp else "0.0"

    params = [
        ("PARAMETRI IMPIANTO (editabili)", None, None, True),
        ("aux_factor (netto -> lordo)",   aux_factor,    "0.000", False),
        ("Comparator fossile (gCO2/MJ)",  comparator,    "0",     False),
        ("Soglia saving GHG (%)",         ghg_threshold, "0.0",   False),
        (common_max_label,                common_max_value, common_max_fmt, False),
        ("ep totale (gCO2/MJ)",           ep_total,      "0.00",  False),
        ("PCI biometano (MWh/Sm3)",       nm3_to_mwh,    "0.00000", False),
    ]
    if is_chp:
        params.extend([
            ("Rendimento elettrico η_el", eta_el,    "0.000", False),
            ("Rendimento termico η_th",   eta_th,    "0.000", False),
            ("Autoconsumo ausiliari (% del lordo)", aux_el_pct, "0.0", False),
        ])
    for i, (label, value, fmt, is_header) in enumerate(params):
        r = 4 + i
        if is_header:
            ws.merge_cells(start_row=r, start_column=1,
                           end_row=r, end_column=2)
            c_lbl = ws.cell(row=r, column=1, value=label)
            c_lbl.font = Font(bold=True, color=WHITE, size=10)
            c_lbl.fill = PatternFill("solid", fgColor=NAVY_2)
            c_lbl.alignment = Alignment(horizontal="left", indent=1)
            c_lbl.border = _border_thin()
        else:
            c_lbl = ws.cell(row=r, column=1, value=label)
            c_lbl.font = Font(bold=True, color=SLATE_700)
            c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
            c_lbl.alignment = Alignment(horizontal="left", indent=1)
            c_lbl.border = _border_thin()

            c_val = ws.cell(row=r, column=2, value=value)
            c_val.number_format = fmt
            # Snapshot: read-only slate. Editable: amber (yellow).
            c_val.fill = PatternFill("solid", fgColor=cell_fill_input)
            c_val.font = Font(bold=True, color=NAVY)
            c_val.alignment = Alignment(horizontal="right")
            c_val.border = _border_thin()

    # === Empty row separatore ===
    # Per CHP la tabella inizia a row 15 (3 righe extra di params).
    # Per biometano resta a row 12 come prima.

    # === Header tabella (mode-aware row + columns) ===
    header_row = 15 if is_chp else 12
    if is_chp:
        # Etichette CHP (colonne aggiuntive: MWh el lordi/netti/termici, kW lordi)
        col_labels = ["Mese", "Ore"] + feeds + [
            "Sm3 CH4 lordi",      # CH4 equivalente totale (pre-perdite)
            "Sm3 CH4 al motore",  # post-aux_factor
            "MWh CH4 netti",      # energia CH4 al motore
            "MWh el LORDI",       # ai morsetti alternatore
            "MWh el netti rete",  # post-aux ausiliari (fatturati GSE)
            "MWh termici",        # recupero calore (uso interno/teleriscaldamento)
            "e_w",
            "Saving %",
            "kW lordi (medio)",   # potenza media oraria - check vs targa motore
            "Validita",
        ]
    else:
        col_labels = ["Mese", "Ore"] + feeds + [
            "Sm3 lordi", "Sm3 netti", "MWh netti",
            "e_w", "Saving %", "Sm3/h netti", "Validita",
        ]
    for col, h in enumerate(col_labels, start=1):
        c = ws.cell(row=header_row, column=col, value=h)
        _style_header(c)
    ws.row_dimensions[header_row].height = 42

    # === Riferimenti per formule (cell letters) ===
    aux_cell        = "$B$5"
    comparator_cell = "$B$6"
    threshold_cell  = "$B$7"
    max_prod_cell   = "$B$8"     # Sm3/h max biometano | kWe LORDI max CHP
    pci_cell        = "$B$10"
    # CHP-only cells
    eta_el_cell     = "$B$11"
    eta_th_cell     = "$B$12"
    aux_el_pct_cell = "$B$13"

    # Database layout ORIZZONTALE: yield in row 2, e_total in row 7
    # Per evitare problemi cross-version di SUMPRODUCT con range, usiamo
    # la forma ESPLICITA "somma di prodotti" - bulletproof in Excel,
    # LibreOffice, Numbers, Google Sheets, qualsiasi locale.
    # Esempio (4 biomasse):
    #   Sm3_lordi = C13*Database!$B$2 + D13*Database!$C$2 +
    #               E13*Database!$D$2 + F13*Database!$E$2
    bio_start_letter = L(bio_col_start)
    bio_end_letter   = L(bio_col_end)

    def _sum_of_products(row_idx: int, db_row_idx: int) -> str:
        """Costruisce somma di prodotti esplicita per N_feed biomasse."""
        terms = []
        for j in range(n_feed):
            piano_col = L(bio_col_start + j)
            db_col    = L(2 + j)  # B per j=0, C per j=1, ...
            terms.append(
                f"{piano_col}{row_idx}*'{db_sheet_name}'!${db_col}${db_row_idx}"
            )
        return "+".join(terms)

    # === Dati 12 mesi ===
    months = ctx.get("MONTHS", [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ])
    month_hours = ctx.get("MONTH_HOURS", [
        744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744,
    ])
    initial_data = ctx.get("initial_data", {}) or {}

    # Per SNAPSHOT: leggiamo i valori computati gia' pronti dal df_res.
    # Mappiamo per Mese -> dict di tutte le colonne computate.
    snap_data = {}
    if snapshot:
        df = ctx.get("df_res")
        if df is not None:
            for _, row in df.iterrows():
                m_key = row.get("Mese")
                if m_key:
                    snap_data[m_key] = dict(row)

    first_data_row = header_row + 1
    last_data_row  = first_data_row + 11

    for i, (m, h) in enumerate(zip(months, month_hours)):
        r = first_data_row + i

        # A: Mese (read-only, navy header look-alike)
        c_mese = ws.cell(row=r, column=1, value=m)
        c_mese.font = Font(bold=True, color=WHITE, size=10)
        c_mese.fill = PatternFill("solid", fgColor=NAVY_2)
        c_mese.alignment = Alignment(horizontal="left", indent=1)
        c_mese.border = _border_thin()

        # B: Ore (editable in modificabile, read-only in snapshot)
        ore_default = h
        if snapshot and m in snap_data:
            ore_default = snap_data[m].get("Ore", h)
        elif m in initial_data:
            ore_default = initial_data[m].get("Ore", h)
        c_ore = ws.cell(row=r, column=2, value=int(ore_default))
        if snapshot:
            _style_readonly(c_ore)
        else:
            _style_editable(c_ore)
        c_ore.number_format = "0"

        # C..N: biomasse (editable in modificabile, read-only in snapshot)
        for j, name in enumerate(feeds):
            col = bio_col_start + j
            default = 0.0
            if snapshot and m in snap_data:
                default = float(snap_data[m].get(name, 0.0) or 0.0)
            elif m in initial_data:
                default = initial_data[m].get(name, 0.0)
            c_b = ws.cell(row=r, column=col, value=float(default))
            if snapshot:
                _style_readonly(c_b)
            else:
                _style_editable(c_b)
            c_b.number_format = "#,##0.0"

        # =====================================================
        # FORMULE LIVE (modificabile) o VALORI STATICI (snapshot)
        # =====================================================
        # Sm3 lordi
        if snapshot:
            v = float(snap_data.get(m, {}).get("Sm³ lordi") or 0)
            c = ws.cell(row=r, column=sm3_lordi_col, value=v)
        else:
            sop_yield = _sum_of_products(row_idx=r, db_row_idx=2)
            c = ws.cell(row=r, column=sm3_lordi_col,
                        value=f"=IFERROR({sop_yield},0)")
        c.number_format = "#,##0"
        _style_readonly(c)

        # Sm3 netti
        sm3_lordi_letter = L(sm3_lordi_col)
        if snapshot:
            v = float(snap_data.get(m, {}).get("Sm³ netti") or 0)
            c = ws.cell(row=r, column=sm3_netti_col, value=v)
        else:
            c = ws.cell(row=r, column=sm3_netti_col,
                        value=f"=IFERROR({sm3_lordi_letter}{r}/{aux_cell},0)")
        c.number_format = "#,##0"
        _style_readonly(c)

        # MWh netti
        sm3_netti_letter = L(sm3_netti_col)
        if snapshot:
            v = float(snap_data.get(m, {}).get("MWh netti") or 0)
            c = ws.cell(row=r, column=mwh_netti_col, value=v)
        else:
            c = ws.cell(row=r, column=mwh_netti_col,
                        value=f"={sm3_netti_letter}{r}*{pci_cell}")
        c.number_format = "#,##0.0"
        _style_readonly(c)

        # e_w (gCO2/MJ)
        if snapshot:
            v = float(snap_data.get(m, {}).get("GHG (gCO₂/MJ)") or 0)
            c = ws.cell(row=r, column=e_w_col, value=v)
        else:
            num_terms = []
            for j in range(n_feed):
                piano_col = L(bio_col_start + j)
                db_col    = L(2 + j)
                num_terms.append(
                    f"{piano_col}{r}*'{db_sheet_name}'!${db_col}$2*"
                    f"'{db_sheet_name}'!${db_col}$7"
                )
            sop_num = "+".join(num_terms)
            sop_yield = _sum_of_products(row_idx=r, db_row_idx=2)
            c = ws.cell(row=r, column=e_w_col,
                        value=f"=IFERROR(({sop_num})/({sop_yield}),0)")
        c.number_format = "0.00"
        _style_readonly(c)

        # === CHP-only colonne energetiche ===
        if is_chp:
            mwh_netti_letter = L(mwh_netti_col)
            # MWh el LORDI = MWh CH4 × η_el
            if snapshot:
                v = float(snap_data.get(m, {}).get("MWh elettrici lordi") or 0)
                c = ws.cell(row=r, column=mwh_el_lordo_col, value=v)
            else:
                c = ws.cell(row=r, column=mwh_el_lordo_col,
                            value=f"={mwh_netti_letter}{r}*{eta_el_cell}")
            c.number_format = "#,##0.0"
            _style_readonly(c)

            # MWh el NETTI rete = lordi × (1 - aux%/100)
            mwh_el_lordo_letter = L(mwh_el_lordo_col)
            if snapshot:
                v = float(snap_data.get(m, {}).get("MWh elettrici netti") or 0)
                c = ws.cell(row=r, column=mwh_el_netto_col, value=v)
            else:
                c = ws.cell(row=r, column=mwh_el_netto_col,
                            value=(f"={mwh_el_lordo_letter}{r}*"
                                   f"(1-{aux_el_pct_cell}/100)"))
            c.number_format = "#,##0.0"
            _style_readonly(c)

            # MWh termici = MWh CH4 × η_th
            if snapshot:
                v = float(snap_data.get(m, {}).get("MWh termici") or 0)
                c = ws.cell(row=r, column=mwh_th_col, value=v)
            else:
                c = ws.cell(row=r, column=mwh_th_col,
                            value=f"={mwh_netti_letter}{r}*{eta_th_cell}")
            c.number_format = "#,##0.0"
            _style_readonly(c)

        # === Saving % ===
        e_w_letter = L(e_w_col)
        if snapshot:
            v = float(snap_data.get(m, {}).get("Saving %") or 0)
            c = ws.cell(row=r, column=saving_col, value=v)
        else:
            c = ws.cell(row=r, column=saving_col,
                        value=(f"=IFERROR(({comparator_cell}-{e_w_letter}{r})"
                               f"/{comparator_cell}*100,0)"))
        c.number_format = "0.0\"%\""
        _style_readonly(c)

        # === Production check column (mode-aware) ===
        if is_chp:
            # kW lordi medi sull'ora = MWh el lordi × 1000 / Ore
            mwh_el_lordo_letter = L(mwh_el_lordo_col)
            if snapshot:
                # Calcoliamo da MWh el lordi e Ore (gia' nel snap)
                _ml = float(snap_data.get(m, {}).get("MWh elettrici lordi") or 0)
                _ore = float(snap_data.get(m, {}).get("Ore") or h)
                v = (_ml * 1000.0 / _ore) if _ore > 0 else 0.0
                c = ws.cell(row=r, column=kw_lordi_col, value=v)
            else:
                c = ws.cell(row=r, column=kw_lordi_col,
                            value=(f"=IFERROR({mwh_el_lordo_letter}{r}*1000"
                                   f"/B{r},0)"))
            c.number_format = "#,##0"
            _style_readonly(c)
            prod_check_letter = L(kw_lordi_col)
        else:
            # Biometano: Sm3/h netti = Sm3 netti / Ore
            if snapshot:
                v = float(snap_data.get(m, {}).get("Sm³/h netti") or 0)
                c = ws.cell(row=r, column=smch_col, value=v)
            else:
                c = ws.cell(row=r, column=smch_col,
                            value=f"=IFERROR({sm3_netti_letter}{r}/B{r},0)")
            c.number_format = "0.0"
            _style_readonly(c)
            prod_check_letter = L(smch_col)

        # === Validita ===
        saving_letter = L(saving_col)
        if snapshot:
            # df_res ha "Validita" con emoji ✅/❌. Normalizziamo a OK/KO.
            v_str = str(snap_data.get(m, {}).get("Validità") or "")
            if "✅" in v_str:
                v_clean = "OK"
            elif "❌" in v_str:
                v_clean = "KO"
            elif v_str.upper().startswith("OK"):
                v_clean = "OK"
            else:
                v_clean = "KO"
            c = ws.cell(row=r, column=valid_col, value=v_clean)
        else:
            c = ws.cell(row=r, column=valid_col,
                        value=(f'=IF(AND({saving_letter}{r}>={threshold_cell},'
                               f'{prod_check_letter}{r}<={max_prod_cell}),"OK","KO")'))
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _border_thin()

    # === Riga TOTALE (row 25) ===
    tot_row = last_data_row + 1
    c_tot_label = ws.cell(row=tot_row, column=1, value="TOTALE/MEDIA")
    _style_total(c_tot_label)
    c_tot_label.alignment = Alignment(horizontal="left", indent=1)

    # Ore tot
    c = ws.cell(row=tot_row, column=2,
                value=f"=SUM(B{first_data_row}:B{last_data_row})")
    _style_total(c); c.number_format = "0"

    # Biomasse tot
    for j in range(n_feed):
        col = bio_col_start + j
        cl = L(col)
        c = ws.cell(row=tot_row, column=col,
                    value=f"=SUM({cl}{first_data_row}:{cl}{last_data_row})")
        _style_total(c); c.number_format = "#,##0"

    # Sm3 lordi/netti/MWh tot
    sum_cols = [sm3_lordi_col, sm3_netti_col, mwh_netti_col]
    if is_chp:
        sum_cols += [mwh_el_lordo_col, mwh_el_netto_col, mwh_th_col]
    for col in sum_cols:
        cl = L(col)
        c = ws.cell(row=tot_row, column=col,
                    value=f"=SUM({cl}{first_data_row}:{cl}{last_data_row})")
        _style_total(c)
        c.number_format = (
            "#,##0" if col in (sm3_lordi_col, sm3_netti_col)
            else "#,##0.0"
        )

    # e_w medio (weighted by Sm3 netti)
    cl_ew     = L(e_w_col)
    cl_smnett = L(sm3_netti_col)
    c = ws.cell(row=tot_row, column=e_w_col,
                value=(f"=IFERROR(SUMPRODUCT("
                       f"{cl_smnett}{first_data_row}:{cl_smnett}{last_data_row},"
                       f"{cl_ew}{first_data_row}:{cl_ew}{last_data_row})"
                       f"/SUM({cl_smnett}{first_data_row}:{cl_smnett}{last_data_row}),0)"))
    _style_total(c); c.number_format = "0.00"

    # Saving medio (weighted)
    cl_sav = L(saving_col)
    c = ws.cell(row=tot_row, column=saving_col,
                value=(f"=IFERROR(SUMPRODUCT("
                       f"{cl_smnett}{first_data_row}:{cl_smnett}{last_data_row},"
                       f"{cl_sav}{first_data_row}:{cl_sav}{last_data_row})"
                       f"/SUM({cl_smnett}{first_data_row}:{cl_smnett}{last_data_row}),0)"))
    _style_total(c); c.number_format = "0.0\"%\""

    # Production check medio (Sm3/h biometano | kW lordi CHP)
    if is_chp:
        cl_prod = L(kw_lordi_col)
        prod_fmt = "#,##0"
    else:
        cl_prod = L(smch_col)
        prod_fmt = "0.0"
    c = ws.cell(row=tot_row, column=(kw_lordi_col if is_chp else smch_col),
                value=(f"=IFERROR(AVERAGE("
                       f"{cl_prod}{first_data_row}:{cl_prod}{last_data_row}),0)"))
    _style_total(c); c.number_format = prod_fmt

    # Validita: count "OK" / 12
    cl_val = L(valid_col)
    c = ws.cell(row=tot_row, column=valid_col,
                value=(f'=COUNTIF({cl_val}{first_data_row}:{cl_val}{last_data_row},'
                       f'"OK")&"/12"'))
    _style_total(c); c.alignment = Alignment(horizontal="center")

    # === Conditional formatting ===
    # Saving %: rosso se < soglia, verde se >=
    sav_range = f"{cl_sav}{first_data_row}:{cl_sav}{last_data_row}"
    rule_red = CellIsRule(
        operator="lessThan", formula=[threshold_cell],
        fill=PatternFill("solid", fgColor=RED_BG),
        font=Font(color=RED_FG, bold=True),
    )
    rule_grn = CellIsRule(
        operator="greaterThanOrEqual", formula=[threshold_cell],
        fill=PatternFill("solid", fgColor=EMERALD_BG),
        font=Font(color=EMERALD_FG, bold=True),
    )
    ws.conditional_formatting.add(sav_range, rule_red)
    ws.conditional_formatting.add(sav_range, rule_grn)

    # Validita: OK = verde, KO = rosso
    val_range = f"{cl_val}{first_data_row}:{cl_val}{last_data_row}"
    rule_ok = CellIsRule(
        operator="equal", formula=['"OK"'],
        fill=PatternFill("solid", fgColor=EMERALD_BG),
        font=Font(color=EMERALD_FG, bold=True),
    )
    rule_ko = CellIsRule(
        operator="equal", formula=['"KO"'],
        fill=PatternFill("solid", fgColor=RED_BG),
        font=Font(color=RED_FG, bold=True),
    )
    ws.conditional_formatting.add(val_range, rule_ok)
    ws.conditional_formatting.add(val_range, rule_ko)

    # Production check rosso se > max (Sm3/h biometano | kW lordi CHP)
    prod_range = f"{cl_prod}{first_data_row}:{cl_prod}{last_data_row}"
    rule_prod_ko = CellIsRule(
        operator="greaterThan", formula=[max_prod_cell],
        fill=PatternFill("solid", fgColor=RED_BG),
        font=Font(color=RED_FG),
    )
    ws.conditional_formatting.add(prod_range, rule_prod_ko)

    # === Larghezze colonne ===
    ws.column_dimensions["A"].width = 14   # Mese
    ws.column_dimensions["B"].width = 8    # Ore
    for j in range(n_feed):
        ws.column_dimensions[L(bio_col_start + j)].width = 14
    ws.column_dimensions[L(sm3_lordi_col)].width = 13
    ws.column_dimensions[L(sm3_netti_col)].width = 13
    ws.column_dimensions[L(mwh_netti_col)].width = 12
    ws.column_dimensions[L(e_w_col)].width      = 9
    ws.column_dimensions[L(saving_col)].width   = 10
    ws.column_dimensions[L(valid_col)].width    = 10
    if is_chp:
        ws.column_dimensions[L(mwh_el_lordo_col)].width = 13
        ws.column_dimensions[L(mwh_el_netto_col)].width = 14
        ws.column_dimensions[L(mwh_th_col)].width       = 12
        ws.column_dimensions[L(kw_lordi_col)].width     = 13
    else:
        ws.column_dimensions[L(smch_col)].width = 12

    # === Freeze panes (header + Mese/Ore visibili) ===
    ws.freeze_panes = ws[f"C{first_data_row}"]

    # === Footer note ===
    note_row = tot_row + 2
    ws.merge_cells(start_row=note_row, start_column=1,
                   end_row=note_row, end_column=valid_col)
    note = (
        "Generato da Metan.iQ - Decision Intelligence Platform per "
        "biometano e biogas CHP. Modello GHG conforme RED III All. V/VI. "
        "Le celle gialle sono editabili: ogni modifica ricalcola "
        "in tempo reale produzione, sostenibilita' e validita'."
    )
    c = ws.cell(row=note_row, column=1, value=note)
    c.font = Font(italic=True, size=8, color=SLATE_500)
    c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[note_row].height = 30


# ============================================================
# Sheet 3 — Sintesi annuale (mode-aware)
# ============================================================
def _build_summary(ws, ctx, piano_sheet_name):
    feeds  = ctx["active_feeds"]
    n_feed = len(feeds)
    is_chp = bool(ctx.get("IS_CHP", False))

    L = get_column_letter
    bio_col_start = 3
    bio_col_end   = 2 + n_feed
    sm3_lordi_col = bio_col_end + 1
    sm3_netti_col = sm3_lordi_col + 1
    mwh_netti_col = sm3_netti_col + 1

    if is_chp:
        # Layout CHP: cols Sm3 lordi, Sm3 netti, MWh CH4, MWh el lordi,
        #             MWh el netti rete, MWh termici, e_w, Saving, kW lordi, Validita
        mwh_el_lordo_col = mwh_netti_col + 1
        mwh_el_netto_col = mwh_el_lordo_col + 1
        mwh_th_col       = mwh_el_netto_col + 1
        e_w_col          = mwh_th_col + 1
        saving_col       = e_w_col + 1
        kw_lordi_col     = saving_col + 1
        valid_col        = kw_lordi_col + 1
        first_data_row = 16  # CHP ha header a row 15
        last_data_row  = 27
    else:
        # Biometano: cols Sm3 lordi, Sm3 netti, MWh netti, e_w, Saving, Sm3/h, Validita
        e_w_col      = mwh_netti_col + 1
        saving_col   = e_w_col + 1
        smch_col     = saving_col + 1
        valid_col    = smch_col + 1
        first_data_row = 13
        last_data_row  = 24

    p = piano_sheet_name

    # === Title ===
    ws.merge_cells("A1:D1")
    c = ws.cell(row=1, column=1, value="Metan.iQ — Sintesi annuale")
    c.font = Font(bold=True, size=14, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:D2")
    c = ws.cell(row=2, column=1,
                value=("Aggiornata in tempo reale dalla sheet «Piano mensile». "
                       "Modifica ore/biomasse li' per vedere i KPI cambiare."))
    c.font = Font(italic=True, size=9, color=SLATE_500)
    c.alignment = Alignment(horizontal="left", indent=1)

    # === KPI block (mode-aware) ===
    cl_sav  = L(saving_col)
    cl_val  = L(valid_col)
    cl_mwh  = L(mwh_netti_col)
    # Threshold cell location nel Piano (CHP=$B$7, biometano=$B$7) - same
    threshold_ref = f"'{p}'!$B$7"

    kpi_common = [
        ("Tot. biomasse (t/anno)",
         f"=SUMPRODUCT(('{p}'!{L(bio_col_start)}{first_data_row}:"
         f"{L(bio_col_end)}{last_data_row}))",
         "#,##0"),
    ]

    if is_chp:
        cl_lordo = L(mwh_el_lordo_col)
        cl_netto = L(mwh_el_netto_col)
        cl_th    = L(mwh_th_col)
        cl_kw    = L(kw_lordi_col)
        kpi = kpi_common + [
            ("MWh CH4 al motore (anno)",
             f"=SUM('{p}'!{cl_mwh}{first_data_row}:{cl_mwh}{last_data_row})",
             "#,##0.0"),
            ("MWh el LORDI (anno)",
             f"=SUM('{p}'!{cl_lordo}{first_data_row}:{cl_lordo}{last_data_row})",
             "#,##0.0"),
            ("⚡ MWh el NETTI rete (anno)",
             f"=SUM('{p}'!{cl_netto}{first_data_row}:{cl_netto}{last_data_row})",
             "#,##0.0"),
            ("🔥 MWh termici (anno)",
             f"=SUM('{p}'!{cl_th}{first_data_row}:{cl_th}{last_data_row})",
             "#,##0.0"),
            ("kW lordi medi (anno)",
             f"=IFERROR(AVERAGE('{p}'!{cl_kw}{first_data_row}:"
             f"{cl_kw}{last_data_row}),0)",
             "#,##0"),
            ("Saving GHG medio (%)",
             f"=IFERROR(SUMPRODUCT('{p}'!{cl_mwh}{first_data_row}:"
             f"{cl_mwh}{last_data_row},"
             f"'{p}'!{cl_sav}{first_data_row}:{cl_sav}{last_data_row})"
             f"/SUM('{p}'!{cl_mwh}{first_data_row}:"
             f"{cl_mwh}{last_data_row}),0)",
             "0.0\"%\""),
            ("Soglia RED III (%)",       f"={threshold_ref}", "0.0\"%\""),
            ("Mesi validi (saving + kW lordi)",
             f'=COUNTIF(\'{p}\'!{cl_val}{first_data_row}:'
             f'{cl_val}{last_data_row},"OK")&"/12"',
             None),
        ]
    else:
        cl_smnett = L(sm3_netti_col)
        kpi = kpi_common + [
            ("Sm3 netti totali (anno)",
             f"=SUM('{p}'!{cl_smnett}{first_data_row}:"
             f"{cl_smnett}{last_data_row})",
             "#,##0"),
            ("MWh netti totali (anno)",
             f"=SUM('{p}'!{cl_mwh}{first_data_row}:{cl_mwh}{last_data_row})",
             "#,##0.0"),
            ("Saving GHG medio (%)",
             f"=IFERROR(SUMPRODUCT('{p}'!{cl_smnett}{first_data_row}:"
             f"{cl_smnett}{last_data_row},"
             f"'{p}'!{cl_sav}{first_data_row}:{cl_sav}{last_data_row})"
             f"/SUM('{p}'!{cl_smnett}{first_data_row}:"
             f"{cl_smnett}{last_data_row}),0)",
             "0.0\"%\""),
            ("Soglia RED III (%)",       f"={threshold_ref}", "0.0\"%\""),
            ("Mesi validi (saving + produzione)",
             f'=COUNTIF(\'{p}\'!{cl_val}{first_data_row}:'
             f'{cl_val}{last_data_row},"OK")&"/12"',
             None),
        ]
    for i, (lbl, formula, fmt) in enumerate(kpi):
        r = 4 + i
        c_lbl = ws.cell(row=r, column=1, value=lbl)
        c_lbl.font = Font(bold=True, color=SLATE_700)
        c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
        c_lbl.alignment = Alignment(horizontal="left", indent=1)
        c_lbl.border = _border_thin()
        ws.merge_cells(start_row=r, start_column=1,
                       end_row=r, end_column=2)

        c_val = ws.cell(row=r, column=3, value=formula)
        c_val.font = Font(bold=True, color=NAVY, size=12)
        c_val.fill = PatternFill("solid", fgColor=AMBER_BG)
        c_val.alignment = Alignment(horizontal="right", vertical="center")
        c_val.border = _border_thin()
        if fmt:
            c_val.number_format = fmt
        ws.merge_cells(start_row=r, start_column=3,
                       end_row=r, end_column=4)
        ws.row_dimensions[r].height = 24

    # === Mix biomasse (annuale) ===
    mix_row_hdr = 4 + len(kpi) + 2
    ws.merge_cells(start_row=mix_row_hdr, start_column=1,
                   end_row=mix_row_hdr, end_column=4)
    c = ws.cell(row=mix_row_hdr, column=1, value="MIX BIOMASSE ANNUALE")
    c.font = Font(bold=True, color=WHITE, size=11)
    c.fill = PatternFill("solid", fgColor=NAVY_2)
    c.alignment = Alignment(horizontal="left", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[mix_row_hdr].height = 22

    headers = ["Biomassa", "t/anno", "Quota %", "MWh CH4 equiv."]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=mix_row_hdr + 1, column=col, value=h)
        _style_header(c)

    for j, name in enumerate(feeds):
        r = mix_row_hdr + 2 + j
        col = bio_col_start + j
        cl = L(col)
        # Nome
        ws.cell(row=r, column=1, value=name).font = Font(bold=True)
        # t/anno
        c = ws.cell(row=r, column=2,
                    value=f"=SUM('{p}'!{cl}{first_data_row}:"
                          f"{cl}{last_data_row})")
        c.number_format = "#,##0"; _style_readonly(c)
        # Quota %
        tot_t_formula = (
            f"SUMPRODUCT('{p}'!{L(bio_col_start)}{first_data_row}:"
            f"{L(bio_col_end)}{last_data_row})"
        )
        c = ws.cell(row=r, column=3,
                    value=f"=IFERROR(B{r}/{tot_t_formula}*100,0)")
        c.number_format = "0.0\"%\""; _style_readonly(c)
        # MWh CH4 equiv = t × yield × PCI / aux_factor
        # NB Database orizzontale: yield in row 2, biomassa j -> col (2+j)
        db_yield_col_letter = get_column_letter(2 + j)
        c = ws.cell(row=r, column=4,
                    value=f"=B{r}*'Database feedstock'!${db_yield_col_letter}$2*"
                          f"'{p}'!$B$10/'{p}'!$B$5")
        c.number_format = "#,##0.0"; _style_readonly(c)

    # Larghezze
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 18


# ============================================================
# Sheet 4 — Business Plan (Pro Forma 15 anni, mode-aware)
# ============================================================
def _build_business_plan(ws, ctx, snapshot: bool = False):
    """Pro forma finanziario completo con formule LIVE.

    Inputs editabili (celle gialle): taglia impianto, ore, tariffa,
    CAPEX (8 voci), OPEX (12 voci), parametri finanziamento.
    Formule calcolano: ricavi, EBITDA, ammortamenti, oneri finanziari,
    utile netto, cash flow, ROI, payback, IRR, VAN.

    Mode-aware: il context fornisce energia_mwh_anno e tariffa_eur_mwh
    pre-calcolati per ciascun mode (biometano DM 2018/2022, biogas
    CHP DM 2012/FER 2). La sheet stessa e' agnostica alla mode.
    """
    is_chp = bool(ctx.get("IS_CHP", False))
    cell_input_fill = SLATE_50 if snapshot else AMBER_BG

    # ============================================================
    # INPUT VALUES (pre-calcolati dal contesto app)
    # ============================================================
    # Taglia (mode-aware label)
    if is_chp:
        plant_size_label = "Potenza elettrica LORDA (kWe targa)"
        plant_size = float(ctx.get("plant_kwe", 999.0))
        plant_size_unit = "kWe"
    else:
        plant_size_label = "Produzione netta (Sm3/h)"
        plant_size = float(ctx.get("plant_net_smch", 300.0))
        plant_size_unit = "Sm3/h"

    ore_anno      = float(ctx.get("bp_ore_anno", 8500.0))
    aux_el_pct    = float(ctx.get("aux_el_pct", 0.0))
    eta_el        = float(ctx.get("eta_el", 0.40))
    aux_factor    = float(ctx.get("aux_factor", 1.29))
    nm3_to_mwh    = float(ctx.get("NM3_TO_MWH", 0.00997))
    tariffa_eur_mwh = float(ctx.get("bp_tariffa_eff_mwh",
                                     ctx.get("bp_tariffa_eff", 131.0)))

    # CAPEX defaults (pre-scalati su taglia 250 Sm3/h o equivalenti)
    capex_def = ctx.get("bp_capex_breakdown", {}) or {}
    capex_forfait = ctx.get("bp_capex_forfait", {}) or {}
    if not capex_def:
        # Fallback se non passato (genera valori tipici per la taglia)
        # Per biometano: scala con plant_smch.
        # Per CHP: scala con plant_kwe.
        norm_size = plant_size if not is_chp else (plant_size / (eta_el * 9.97))
        # norm_size in Sm3/h equivalenti per scalare CAPEX intensity
        capex_def = {
            "Movimenti terra":     3105.0 * norm_size,
            "Opere civili":       10428.0 * norm_size,
            "Impianto tecnologico":15960.0 * norm_size,
            "Sezione upgrading":   9870.0 * norm_size if not is_chp else 0.0,
            "Sezione cogenerazione": 0.0 if not is_chp else 1500.0 * plant_size,
            "Varie (antincendio, ill., recinzione)": 1777.0 * norm_size,
        }
        capex_forfait = {
            "Connessione rete":         92000.0,
            "Acquisto terreno":        262000.0,
            "Progettazione/autorizz.":  65000.0,
            "Direzione lavori / CSE":   34000.0,
            "Altre spese":             105000.0,
        }
    else:
        # Se passato, le voci capex_breakdown sono €/(Smc/h) -> moltiplica
        norm_size = plant_size if not is_chp else (plant_size / (eta_el * 9.97))
        capex_def = {k: v * norm_size for k, v in capex_def.items()}
        # Aggiungi voce CHP-specifica se mode CHP
        if is_chp and "Sezione cogenerazione" not in capex_def:
            # Stima CHP: ~€1500/kWe per motore + accessori
            capex_def["Sezione cogenerazione"] = 1500.0 * plant_size
            # Rimuovi upgrading (non applicabile)
            capex_def.pop("Sezione upgrading", None)

    # OPEX defaults (€/anno scalati)
    opex_def = ctx.get("bp_opex_breakdown", {}) or {}
    opex_forfait = ctx.get("bp_opex_forfait", {}) or {}
    if not opex_def:
        norm_size = plant_size if not is_chp else (plant_size / (eta_el * 9.97))
        opex_def = {
            "O&M digestione":           210.0 * norm_size,
            "O&M upgrading/CHP":        428.0 * norm_size,
            "Service tecnico":          126.0 * norm_size,
            "Gestore d'impianto":       630.0 * norm_size,
            "Service amministrativo":    63.0 * norm_size,
            "Service gestionale":       147.0 * norm_size,
            "Adempimenti comune":       126.0 * norm_size,
            "Energia elettrica":         13.0 * norm_size,
            "Certificazioni / analisi":  34.0 * norm_size,
            "Varie operative":           63.0 * norm_size,
        }
        opex_forfait = {"Assicurazioni": 26000.0, "Tasse fisse": 10000.0}
    else:
        norm_size = plant_size if not is_chp else (plant_size / (eta_el * 9.97))
        opex_def = {k: v * norm_size for k, v in opex_def.items()}

    # Finance + economics defaults
    bp_lt_tasso       = float(ctx.get("bp_lt_tasso", 4.0))
    bp_lt_durata      = int(ctx.get("bp_lt_durata", 15))
    bp_lt_leva        = float(ctx.get("bp_lt_leva", 80.0))
    bp_inflazione     = float(ctx.get("bp_inflazione_pct", 2.5))
    bp_durata_tariffa = int(ctx.get("bp_durata_tariffa", 15))
    bp_pnrr_pct       = float(ctx.get("bp_pnrr_pct", 40.0))
    bp_ebitda_target  = float(ctx.get("bp_ebitda_target_pct", 24.5))
    bp_tax_rate       = float(ctx.get("bp_tax_rate_pct", 24.0))
    bp_ammort_anni    = int(ctx.get("bp_ammort_anni", 22))
    bp_npv_disc_rate  = float(ctx.get("bp_npv_disc_rate_pct", 6.0))
    bp_massimale_eur_per_smch = float(
        ctx.get("bp_massimale_eur_per_smch", 32817.23)
    )

    # Energia netta annua [MWh/anno] - mode-aware
    if is_chp:
        # CHP: kW_lordo × ore × (1-aux_el%) / 1000 = MWh netti rete
        mwh_anno = plant_size * ore_anno * (1 - aux_el_pct) / 1000.0
    else:
        # Biometano: Smc/h × ore × PCI = MWh
        mwh_anno = plant_size * ore_anno * nm3_to_mwh

    # ============================================================
    # SHEET LAYOUT
    # ============================================================
    L = get_column_letter

    # Title
    ws.merge_cells("A1:Q1")
    c = ws.cell(row=1, column=1,
                value="Metan.iQ — Business Plan & Pro Forma 15 anni")
    c.font = Font(bold=True, size=16, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 32

    ws.merge_cells("A2:Q2")
    mode_label = ctx.get("APP_MODE_LABEL", "DM 2022")
    end_use = ctx.get("end_use", "")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c = ws.cell(row=2, column=1,
                value=(f"Modalita': {mode_label}  ·  "
                       f"Destinazione: {end_use}  ·  "
                       f"Generato il {now}"))
    c.font = Font(italic=True, size=9, color=SLATE_500)
    c.alignment = Alignment(horizontal="left", indent=1)
    ws.row_dimensions[2].height = 18

    # Banner istruzioni
    ws.merge_cells("A3:Q3")
    if snapshot:
        banner = "🔒 SNAPSHOT BLOCCATO — valori fotografati al download."
        bf, bb = SLATE_700, SLATE_100
    else:
        banner = ("✏️ Modifica le celle GIALLE (taglia, ore, CAPEX, OPEX, "
                  "tariffa, finanziamento). Tutto il pro forma si aggiorna.")
        bf, bb = AMBER_DK, AMBER_BG
    c = ws.cell(row=3, column=1, value=banner)
    c.font = Font(bold=True, size=10, color=bf)
    c.fill = PatternFill("solid", fgColor=bb)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[3].height = 22

    # ============================================================
    # SEZIONE 1: PARAMETRI ENERGIA (rows 5-9)
    # ============================================================
    def _section_header(r, text, span=2):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=span)
        c = ws.cell(row=r, column=1, value=text)
        c.font = Font(bold=True, size=10, color=WHITE)
        c.fill = PatternFill("solid", fgColor=NAVY_2)
        c.alignment = Alignment(horizontal="left", indent=1)
        c.border = _border_thin()
        ws.row_dimensions[r].height = 22

    def _kv_row(r, label, value, fmt, editable=True, formula=False):
        c_lbl = ws.cell(row=r, column=1, value=label)
        c_lbl.font = Font(bold=True, color=SLATE_700)
        c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
        c_lbl.alignment = Alignment(horizontal="left", indent=1)
        c_lbl.border = _border_thin()

        c_val = ws.cell(row=r, column=2, value=value)
        c_val.number_format = fmt
        if formula:
            c_val.fill = PatternFill("solid", fgColor=SLATE_50)
            c_val.font = Font(bold=True, color=NAVY)
        else:
            c_val.fill = PatternFill("solid", fgColor=cell_input_fill if editable else SLATE_50)
            c_val.font = Font(bold=True, color=NAVY)
        c_val.alignment = Alignment(horizontal="right")
        c_val.border = _border_thin()

    # Sezione 1: PARAMETRI ENERGIA (rows 5-9)
    _section_header(5, "1) PARAMETRI ENERGIA & TARIFFA")
    _kv_row(6, plant_size_label, plant_size, "0.0")
    _kv_row(7, "Ore funzionamento [h/anno]", ore_anno, "0")
    if is_chp:
        _kv_row(8, "η_el (rendimento elettrico)", eta_el, "0.000")
        _kv_row(9, "Autoconsumo ausiliari [%]", aux_el_pct * 100, "0.0")
        # MWh el netti (formula)
        ws.cell(row=10, column=1, value="MWh el netti rete/anno [MWh]").font = Font(bold=True, color=SLATE_700)
        ws.cell(row=10, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
        ws.cell(row=10, column=1).alignment = Alignment(horizontal="left", indent=1)
        ws.cell(row=10, column=1).border = _border_thin()
        c_e = ws.cell(row=10, column=2,
                      value=f"=B6*B7*(1-B9/100)/1000")
        c_e.number_format = "#,##0.0"
        c_e.fill = PatternFill("solid", fgColor=AMBER_BG)
        c_e.font = Font(bold=True, color=AMBER_DK)
        c_e.alignment = Alignment(horizontal="right")
        c_e.border = _border_thin()
    else:
        _kv_row(8, "PCI biometano [MWh/Sm3]", nm3_to_mwh, "0.00000")
        _kv_row(9, "aux_factor (info)", aux_factor, "0.000", editable=False)
        # MWh netti (formula)
        ws.cell(row=10, column=1, value="MWh netti immissione/anno").font = Font(bold=True, color=SLATE_700)
        ws.cell(row=10, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
        ws.cell(row=10, column=1).alignment = Alignment(horizontal="left", indent=1)
        ws.cell(row=10, column=1).border = _border_thin()
        c_e = ws.cell(row=10, column=2, value=f"=B6*B7*B8")
        c_e.number_format = "#,##0.0"
        c_e.fill = PatternFill("solid", fgColor=AMBER_BG)
        c_e.font = Font(bold=True, color=AMBER_DK)
        c_e.alignment = Alignment(horizontal="right")
        c_e.border = _border_thin()

    _kv_row(11, "Tariffa effettiva [€/MWh]", tariffa_eur_mwh, "0.00")
    # Ricavi anno = MWh × tariffa
    ws.cell(row=12, column=1, value="Ricavi annui [€]").font = Font(bold=True, color=SLATE_700)
    ws.cell(row=12, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=12, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=12, column=1).border = _border_thin()
    c_r = ws.cell(row=12, column=2, value="=B10*B11")
    c_r.number_format = '#,##0" €"'
    c_r.fill = PatternFill("solid", fgColor=AMBER_BG)
    c_r.font = Font(bold=True, color=AMBER_DK, size=11)
    c_r.alignment = Alignment(horizontal="right")
    c_r.border = _border_thin()

    # ============================================================
    # SEZIONE 2: PARAMETRI ECONOMICI (rows 14-20)
    # ============================================================
    _section_header(14, "2) PARAMETRI ECONOMICI")
    _kv_row(15, "Inflazione OPEX [% annua]", bp_inflazione, "0.0")
    _kv_row(16, "Durata tariffa [anni]", bp_durata_tariffa, "0")
    _kv_row(17, "Aliquota imposte [%]", bp_tax_rate, "0.0")
    _kv_row(18, "Margine EBITDA target [%]", bp_ebitda_target, "0.0")
    _kv_row(19, "Vita utile ammortamento [anni]", bp_ammort_anni, "0")
    _kv_row(20, "Tasso sconto VAN [%]", bp_npv_disc_rate, "0.0")

    # ============================================================
    # SEZIONE 3: CAPEX (rows 22-...)
    # ============================================================
    _section_header(22, "3) CAPEX (€)")
    capex_start_row = 23
    capex_rows = []
    for i, (label, value) in enumerate(capex_def.items()):
        r = capex_start_row + i
        _kv_row(r, label, value, '#,##0" €"')
        capex_rows.append(r)
    # Forfait
    forfait_start = capex_start_row + len(capex_def)
    for i, (label, value) in enumerate(capex_forfait.items()):
        r = forfait_start + i
        _kv_row(r, label, value, '#,##0" €"')
        capex_rows.append(r)

    capex_tot_row = forfait_start + len(capex_forfait)
    capex_first = capex_rows[0]
    capex_last  = capex_rows[-1]

    # CAPEX TOTALE (formula)
    c_lbl = ws.cell(row=capex_tot_row, column=1, value="CAPEX TOTALE")
    c_lbl.font = Font(bold=True, color=WHITE)
    c_lbl.fill = PatternFill("solid", fgColor=NAVY)
    c_lbl.alignment = Alignment(horizontal="left", indent=1)
    c_lbl.border = _border_thin()
    c_val = ws.cell(row=capex_tot_row, column=2,
                    value=f"=SUM(B{capex_first}:B{capex_last})")
    c_val.number_format = '#,##0" €"'
    c_val.fill = PatternFill("solid", fgColor=NAVY)
    c_val.font = Font(bold=True, color=WHITE, size=11)
    c_val.alignment = Alignment(horizontal="right")
    c_val.border = _border_thin()

    # PNRR
    pnrr_pct_row = capex_tot_row + 1
    massimale_row = capex_tot_row + 2
    contributo_row = capex_tot_row + 3
    capex_netto_row = capex_tot_row + 4
    _kv_row(pnrr_pct_row, "Contributo PNRR [%]", bp_pnrr_pct, "0.0")
    _kv_row(massimale_row, f"Massimale spesa [€/{plant_size_unit}]",
            bp_massimale_eur_per_smch, "0.00")
    # Contributo = MIN(CAPEX, massimale * plant_size) * PNRR%
    # Per CHP: usiamo norm_size (Sm3/h equivalente) per applicare massimale GSE
    # Per biometano: usiamo plant_size direttamente
    if is_chp:
        massimale_basis_formula = f"$B$6/(B8*9.97)"  # plant_kwe / (eta_el * 9.97)
    else:
        massimale_basis_formula = f"$B$6"  # Sm3/h netti
    ws.cell(row=contributo_row, column=1, value="Contributo PNRR [€]")
    ws.cell(row=contributo_row, column=1).font = Font(bold=True, color=SLATE_700)
    ws.cell(row=contributo_row, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=contributo_row, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=contributo_row, column=1).border = _border_thin()
    c_contr = ws.cell(
        row=contributo_row, column=2,
        value=f"=MIN(B{capex_tot_row},B{massimale_row}*{massimale_basis_formula})"
              f"*B{pnrr_pct_row}/100"
    )
    c_contr.number_format = '#,##0" €"'
    c_contr.fill = PatternFill("solid", fgColor=AMBER_BG)
    c_contr.font = Font(bold=True, color=AMBER_DK)
    c_contr.alignment = Alignment(horizontal="right")
    c_contr.border = _border_thin()
    # CAPEX NETTO
    c_lbl = ws.cell(row=capex_netto_row, column=1, value="CAPEX NETTO (post-contributo)")
    c_lbl.font = Font(bold=True, color=WHITE)
    c_lbl.fill = PatternFill("solid", fgColor=NAVY)
    c_lbl.alignment = Alignment(horizontal="left", indent=1)
    c_lbl.border = _border_thin()
    c_netto = ws.cell(row=capex_netto_row, column=2,
                      value=f"=B{capex_tot_row}-B{contributo_row}")
    c_netto.number_format = '#,##0" €"'
    c_netto.fill = PatternFill("solid", fgColor=NAVY)
    c_netto.font = Font(bold=True, color=WHITE, size=11)
    c_netto.alignment = Alignment(horizontal="right")
    c_netto.border = _border_thin()

    # ============================================================
    # SEZIONE 4: FINANZIAMENTO (4 righe)
    # ============================================================
    fin_start = capex_netto_row + 2
    _section_header(fin_start, "4) FINANZIAMENTO")
    _kv_row(fin_start + 1, "Tasso LT [%]", bp_lt_tasso, "0.00")
    _kv_row(fin_start + 2, "Durata LT [anni]", bp_lt_durata, "0")
    _kv_row(fin_start + 3, "Leva LT [%] su CAPEX netto", bp_lt_leva, "0.0")
    # Debito LT
    debito_row = fin_start + 4
    ws.cell(row=debito_row, column=1, value="Debito LT [€]")
    ws.cell(row=debito_row, column=1).font = Font(bold=True, color=SLATE_700)
    ws.cell(row=debito_row, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=debito_row, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=debito_row, column=1).border = _border_thin()
    c_deb = ws.cell(row=debito_row, column=2,
                    value=f"=B{capex_netto_row}*B{fin_start+3}/100")
    c_deb.number_format = '#,##0" €"'
    c_deb.fill = PatternFill("solid", fgColor=SLATE_50)
    c_deb.font = Font(bold=True, color=NAVY)
    c_deb.alignment = Alignment(horizontal="right")
    c_deb.border = _border_thin()
    # Equity
    equity_row = debito_row + 1
    ws.cell(row=equity_row, column=1, value="Equity [€]")
    ws.cell(row=equity_row, column=1).font = Font(bold=True, color=SLATE_700)
    ws.cell(row=equity_row, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=equity_row, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=equity_row, column=1).border = _border_thin()
    c_eq = ws.cell(row=equity_row, column=2,
                   value=f"=B{capex_netto_row}-B{debito_row}")
    c_eq.number_format = '#,##0" €"'
    c_eq.fill = PatternFill("solid", fgColor=AMBER_BG)
    c_eq.font = Font(bold=True, color=AMBER_DK)
    c_eq.alignment = Alignment(horizontal="right")
    c_eq.border = _border_thin()
    # Rata LT
    rata_row = equity_row + 1
    ws.cell(row=rata_row, column=1, value="Rata LT/anno (PMT) [€]")
    ws.cell(row=rata_row, column=1).font = Font(bold=True, color=SLATE_700)
    ws.cell(row=rata_row, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=rata_row, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=rata_row, column=1).border = _border_thin()
    c_rata = ws.cell(
        row=rata_row, column=2,
        value=f"=IFERROR(-PMT(B{fin_start+1}/100,B{fin_start+2},B{debito_row}),0)"
    )
    c_rata.number_format = '#,##0" €"'
    c_rata.fill = PatternFill("solid", fgColor=SLATE_50)
    c_rata.font = Font(bold=True, color=NAVY)
    c_rata.alignment = Alignment(horizontal="right")
    c_rata.border = _border_thin()
    # Ammortamento annuo
    amm_row = rata_row + 1
    ws.cell(row=amm_row, column=1, value="Ammortamento annuo [€]")
    ws.cell(row=amm_row, column=1).font = Font(bold=True, color=SLATE_700)
    ws.cell(row=amm_row, column=1).fill = PatternFill("solid", fgColor=SLATE_50)
    ws.cell(row=amm_row, column=1).alignment = Alignment(horizontal="left", indent=1)
    ws.cell(row=amm_row, column=1).border = _border_thin()
    c_amm = ws.cell(row=amm_row, column=2,
                    value=f"=B{capex_tot_row}/B19")
    c_amm.number_format = '#,##0" €"'
    c_amm.fill = PatternFill("solid", fgColor=SLATE_50)
    c_amm.font = Font(bold=True, color=NAVY)
    c_amm.alignment = Alignment(horizontal="right")
    c_amm.border = _border_thin()

    # ============================================================
    # SEZIONE 5: OPEX
    # ============================================================
    opex_section_row = amm_row + 2
    _section_header(opex_section_row, "5) OPEX (€/anno)")
    opex_start_row = opex_section_row + 1
    opex_rows = []
    for i, (label, value) in enumerate(opex_def.items()):
        r = opex_start_row + i
        _kv_row(r, label, value, '#,##0" €"')
        opex_rows.append(r)
    forfait_opex_start = opex_start_row + len(opex_def)
    for i, (label, value) in enumerate(opex_forfait.items()):
        r = forfait_opex_start + i
        _kv_row(r, label, value, '#,##0" €"')
        opex_rows.append(r)
    opex_tot_row = forfait_opex_start + len(opex_forfait)
    opex_first = opex_rows[0]
    opex_last  = opex_rows[-1]
    c_lbl = ws.cell(row=opex_tot_row, column=1, value="OPEX TOTALE")
    c_lbl.font = Font(bold=True, color=WHITE)
    c_lbl.fill = PatternFill("solid", fgColor=NAVY)
    c_lbl.alignment = Alignment(horizontal="left", indent=1)
    c_lbl.border = _border_thin()
    c_val = ws.cell(row=opex_tot_row, column=2,
                    value=f"=SUM(B{opex_first}:B{opex_last})")
    c_val.number_format = '#,##0" €"'
    c_val.fill = PatternFill("solid", fgColor=NAVY)
    c_val.font = Font(bold=True, color=WHITE, size=11)
    c_val.alignment = Alignment(horizontal="right")
    c_val.border = _border_thin()

    # ============================================================
    # SEZIONE 6: CONTO ECONOMICO 15 ANNI (table)
    # ============================================================
    ce_section_row = opex_tot_row + 2
    ws.merge_cells(start_row=ce_section_row, start_column=1,
                   end_row=ce_section_row, end_column=16)  # cols A..P (15 anni + label)
    c = ws.cell(row=ce_section_row, column=1,
                value="6) CONTO ECONOMICO 15 ANNI (€)")
    c.font = Font(bold=True, size=11, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY_2)
    c.alignment = Alignment(horizontal="left", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[ce_section_row].height = 22

    # Header tabella CE: row ce_header_row
    ce_header_row = ce_section_row + 1
    ws.cell(row=ce_header_row, column=1, value="Voce")
    _style_header(ws.cell(row=ce_header_row, column=1))
    for y in range(1, 16):
        c = ws.cell(row=ce_header_row, column=1 + y, value=f"Anno {y}")
        _style_header(c)
    ws.row_dimensions[ce_header_row].height = 30

    # Riferimenti per formule (cell B di parametri)
    ricavi_ref = "$B$12"
    opex_tot_ref = f"$B${opex_tot_row}"
    inflaz_ref = "$B$15"
    ebitda_target_pct_ref = "$B$18"
    amm_ref = f"$B${amm_row}"
    rata_ref = f"$B${rata_row}"
    debito_ref = f"$B${debito_row}"
    tasso_ref = f"$B${fin_start+1}"
    durata_lt_ref = f"$B${fin_start+2}"
    tax_rate_ref = "$B$17"
    vita_amm_ref = "$B$19"

    # Righe CE (per anno)
    ce_row_ricavi = ce_header_row + 1
    ce_row_opex   = ce_header_row + 2
    ce_row_biom   = ce_header_row + 3
    ce_row_ebitda = ce_header_row + 4
    ce_row_amm    = ce_header_row + 5
    ce_row_int    = ce_header_row + 6
    ce_row_uante  = ce_header_row + 7
    ce_row_imp    = ce_header_row + 8
    ce_row_unetto = ce_header_row + 9
    ce_row_fcf    = ce_header_row + 10
    ce_row_fcf_cum = ce_header_row + 11

    ce_labels = [
        (ce_row_ricavi, "Ricavi"),
        (ce_row_opex,   "OPEX (inflazionato)"),
        (ce_row_biom,   "Costo biomasse"),
        (ce_row_ebitda, "EBITDA"),
        (ce_row_amm,    "Ammortamento"),
        (ce_row_int,    "Oneri finanziari"),
        (ce_row_uante,  "Utile ante imposte"),
        (ce_row_imp,    "Imposte"),
        (ce_row_unetto, "Utile netto"),
        (ce_row_fcf,    "Free Cash Flow"),
        (ce_row_fcf_cum,"FCF cumulato"),
    ]
    # Stile labels CE
    for r, lbl in ce_labels:
        c_lbl = ws.cell(row=r, column=1, value=lbl)
        c_lbl.font = Font(bold=True, color=SLATE_700)
        c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
        c_lbl.alignment = Alignment(horizontal="left", indent=1)
        c_lbl.border = _border_thin()
        # bold per EBITDA, FCF, FCF cum
        if r in (ce_row_ebitda, ce_row_fcf, ce_row_fcf_cum):
            c_lbl.font = Font(bold=True, color=NAVY)

    # Formule per ogni anno (col B..P)
    for y in range(1, 16):
        col = 1 + y
        cl = L(col)
        cl_prev = L(col - 1) if y > 1 else None

        # Ricavi (uniformi se DM 2022 nominale, altrimenti potresti mettere infla)
        ws.cell(row=ce_row_ricavi, column=col, value=f"={ricavi_ref}")
        # OPEX inflazionato: -opex × (1+infl/100)^(y-1)
        ws.cell(row=ce_row_opex, column=col,
                value=f"=-{opex_tot_ref}*(1+{inflaz_ref}/100)^({y-1})")
        # Costo biomasse = -(Ricavi + OPEX - EBITDA target)
        # EBITDA target = Ricavi × margine%
        ws.cell(row=ce_row_biom, column=col,
                value=(f"=-MAX({cl}{ce_row_ricavi}+{cl}{ce_row_opex}"
                       f"-{cl}{ce_row_ricavi}*{ebitda_target_pct_ref}/100,0)"))
        # EBITDA = Ricavi + OPEX + Costo biomasse
        ws.cell(row=ce_row_ebitda, column=col,
                value=(f"={cl}{ce_row_ricavi}+{cl}{ce_row_opex}"
                       f"+{cl}{ce_row_biom}"))
        # Ammortamento (solo entro vita utile)
        ws.cell(row=ce_row_amm, column=col,
                value=f"=IF({y}<={vita_amm_ref},-{amm_ref},0)")
        # Oneri finanziari (IPMT)
        ws.cell(row=ce_row_int, column=col,
                value=(f"=IF({y}<={durata_lt_ref},"
                       f"IPMT({tasso_ref}/100,{y},{durata_lt_ref},"
                       f"{debito_ref}),0)"))
        # Utile ante = EBITDA + Ammort + Interessi
        ws.cell(row=ce_row_uante, column=col,
                value=(f"={cl}{ce_row_ebitda}+{cl}{ce_row_amm}"
                       f"+{cl}{ce_row_int}"))
        # Imposte (solo se utile positivo)
        ws.cell(row=ce_row_imp, column=col,
                value=(f"=-MAX({cl}{ce_row_uante}*{tax_rate_ref}/100,0)"))
        # Utile netto
        ws.cell(row=ce_row_unetto, column=col,
                value=f"={cl}{ce_row_uante}+{cl}{ce_row_imp}")
        # FCF = EBITDA + Imposte - Rata LT (rata_ref e' positiva, sottraiamo)
        ws.cell(row=ce_row_fcf, column=col,
                value=(f"={cl}{ce_row_ebitda}+{cl}{ce_row_imp}"
                       f"-IF({y}<={durata_lt_ref},{rata_ref},0)"))
        # FCF cumulato
        if y == 1:
            # Anno 1: -equity + FCF1
            ws.cell(row=ce_row_fcf_cum, column=col,
                    value=f"=-${L(2)}${equity_row}+{cl}{ce_row_fcf}")
        else:
            ws.cell(row=ce_row_fcf_cum, column=col,
                    value=f"={cl_prev}{ce_row_fcf_cum}+{cl}{ce_row_fcf}")

        # Formato e stile per ogni cella della tabella CE
        for r, _ in ce_labels:
            cell = ws.cell(row=r, column=col)
            cell.number_format = '#,##0;-#,##0'
            cell.alignment = Alignment(horizontal="right")
            cell.border = _border_thin()
            cell.fill = PatternFill("solid", fgColor=SLATE_50)
            if r in (ce_row_ebitda, ce_row_fcf, ce_row_fcf_cum):
                cell.font = Font(bold=True, color=NAVY)
            else:
                cell.font = Font(color=SLATE_700)

    # ============================================================
    # SEZIONE 7: KPI FINANZIARI
    # ============================================================
    kpi_section_row = ce_row_fcf_cum + 2
    ws.merge_cells(start_row=kpi_section_row, start_column=1,
                   end_row=kpi_section_row, end_column=2)
    c = ws.cell(row=kpi_section_row, column=1,
                value="7) KPI FINANZIARI")
    c.font = Font(bold=True, size=11, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY_2)
    c.alignment = Alignment(horizontal="left", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[kpi_section_row].height = 22

    kpi_first_row = kpi_section_row + 1
    fcf_range = f"{L(2)}{ce_row_fcf}:{L(16)}{ce_row_fcf}"
    fcf_cum_range = f"{L(2)}{ce_row_fcf_cum}:{L(16)}{ce_row_fcf_cum}"
    ricavi_range = f"{L(2)}{ce_row_ricavi}:{L(16)}{ce_row_ricavi}"
    ebitda_range = f"{L(2)}{ce_row_ebitda}:{L(16)}{ce_row_ebitda}"
    unetto_range = f"{L(2)}{ce_row_unetto}:{L(16)}{ce_row_unetto}"

    # Helper per riga KPI con formula
    def _kpi_row(r, label, formula, fmt, accent=False):
        c_lbl = ws.cell(row=r, column=1, value=label)
        c_lbl.font = Font(bold=True, color=SLATE_700)
        c_lbl.fill = PatternFill("solid", fgColor=SLATE_50)
        c_lbl.alignment = Alignment(horizontal="left", indent=1)
        c_lbl.border = _border_thin()
        c_val = ws.cell(row=r, column=2, value=formula)
        c_val.number_format = fmt
        c_val.fill = PatternFill("solid", fgColor=AMBER_BG if accent else SLATE_50)
        c_val.font = Font(bold=True, color=AMBER_DK if accent else NAVY, size=11)
        c_val.alignment = Alignment(horizontal="right")
        c_val.border = _border_thin()

    _kpi_row(kpi_first_row + 0, "Ricavi totali 15 anni",
             f"=SUM({ricavi_range})", '#,##0" €"')
    _kpi_row(kpi_first_row + 1, "EBITDA medio annuo",
             f"=AVERAGE({ebitda_range})", '#,##0" €"')
    _kpi_row(kpi_first_row + 2, "Margine EBITDA medio",
             f"=IFERROR(AVERAGE({ebitda_range})/AVERAGE({ricavi_range})*100,0)",
             '0.0"%"')
    _kpi_row(kpi_first_row + 3, "Utile netto totale 15 anni",
             f"=SUM({unetto_range})", '#,##0" €"', accent=True)
    _kpi_row(kpi_first_row + 4, "FCF cumulato finale (anno 15)",
             f"={L(16)}{ce_row_fcf_cum}", '#,##0" €"', accent=True)
    _kpi_row(kpi_first_row + 5, "ROI = Utile netto / Equity",
             f"=IFERROR(SUM({unetto_range})/$B${equity_row}*100,0)",
             '0.0"%"', accent=True)
    # Payback: trova il primo anno in cui FCF cumulato >= 0
    _kpi_row(
        kpi_first_row + 6, "Payback (anni, primo FCF cum>=0)",
        (f'=IFERROR(MATCH(TRUE,{fcf_cum_range}>=0,0),'
         f'"oltre 15 anni")'),
        "0",
    )
    # IRR equity: array {-equity, FCF1..FCF15}
    # Trick: usa una helper row nascosta? Meglio: usa NPV+goal-seek non possibile.
    # Soluzione: costruisci IRR su un range esteso: -equity in cella separata + FCF range.
    # Workaround: aggiungiamo una RIGA con cash flow per IRR (Y0=-equity, Y1..15=FCF)
    # Subito sotto KPI block.
    irr_helper_row = kpi_first_row + 8
    # Year 0 (col B = -equity)
    ws.cell(row=irr_helper_row, column=1, value="(serie FCF per IRR/VAN)")
    ws.cell(row=irr_helper_row, column=1).font = Font(italic=True, size=8, color=SLATE_500)
    ws.cell(row=irr_helper_row, column=2, value=f"=-${L(2)}${equity_row}")
    ws.cell(row=irr_helper_row, column=2).number_format = '#,##0" €"'
    ws.cell(row=irr_helper_row, column=2).font = Font(size=8, color=SLATE_500)
    # Year 1..15 (cols C..Q): copia FCF
    for y in range(1, 16):
        col = 2 + y  # C, D, ..., Q
        cl_dst = L(col)
        cl_src = L(1 + y)  # B, C, ..., P (FCF originali)
        ws.cell(row=irr_helper_row, column=col,
                value=f"={cl_src}{ce_row_fcf}")
        ws.cell(row=irr_helper_row, column=col).number_format = '#,##0'
        ws.cell(row=irr_helper_row, column=col).font = Font(size=8, color=SLATE_500)

    irr_series_range = f"{L(2)}{irr_helper_row}:{L(17)}{irr_helper_row}"

    _kpi_row(kpi_first_row + 7, "IRR equity",
             f"=IFERROR(IRR({irr_series_range}),0)*100",
             '0.0"%"', accent=True)
    # VAN equity: NPV(rate, FCF1..15) - equity (NPV Excel sconta dal periodo 1)
    npv_disc_ref = "$B$20"
    fcf_only_range = f"{L(2)}{ce_row_fcf}:{L(16)}{ce_row_fcf}"
    _kpi_row(kpi_first_row + 9, "VAN equity (al tasso sconto)",
             f"=NPV({npv_disc_ref}/100,{fcf_only_range})-${L(2)}${equity_row}",
             '#,##0" €"', accent=True)

    # ============================================================
    # Larghezze colonne
    # ============================================================
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 18
    for y in range(1, 16):
        ws.column_dimensions[L(1 + y)].width = 13
    ws.column_dimensions["Q"].width = 13  # last col (irr helper)

    # Freeze: blocca header CE (label + B-K) durante scroll
    ws.freeze_panes = ws[f"C{ce_header_row + 1}"]
