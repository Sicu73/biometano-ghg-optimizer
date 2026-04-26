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
def build_metaniq_xlsx(ctx: dict) -> BytesIO:
    """Costruisce il workbook XLSX completo.

    ctx contiene: active_feeds, FEEDSTOCK_DB, aux_factor, ep_total,
    fossil_comparator, ghg_threshold, plant_net_smch, MONTHS,
    MONTH_HOURS, NM3_TO_MWH, initial_data (opt), APP_MODE, end_use.
    """
    wb = Workbook()

    # === Sheet 1: Database (creata per prima per nome reference) ===
    ws_db = wb.create_sheet("Database feedstock")
    _build_database(ws_db, ctx)

    # === Sheet 2: Piano (main, attiva di default) ===
    ws_piano = wb.active
    ws_piano.title = "Piano mensile"
    _build_piano(ws_piano, ctx, ws_db.title)

    # === Sheet 3: Sintesi ===
    ws_sum = wb.create_sheet("Sintesi annuale")
    _build_summary(ws_sum, ctx, ws_piano.title)

    # Imposta Piano come sheet attiva di default
    wb.active = wb.sheetnames.index(ws_piano.title)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ============================================================
# Sheet 1 — Database feedstock
# ============================================================
def _build_database(ws, ctx):
    feeds   = ctx["active_feeds"]
    fdb     = ctx["FEEDSTOCK_DB"]
    ep_t    = ctx["ep_total"]

    # Header
    headers = ["Biomassa", "Resa Nm3/t", "eec", "esca", "etd", "ep", "e_total"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=h)
        _style_header(c)
    ws.row_dimensions[1].height = 28

    # Righe
    for i, name in enumerate(feeds):
        d = fdb[name]
        r = i + 2
        ws.cell(row=r, column=1, value=name).font = Font(bold=True)
        ws.cell(row=r, column=2, value=float(d["yield"])).number_format = "0"
        ws.cell(row=r, column=3, value=float(d["eec"])).number_format = "0.00"
        ws.cell(row=r, column=4, value=float(d["esca"])).number_format = "0.00"
        ws.cell(row=r, column=5, value=float(d["etd"])).number_format = "0.00"
        # ep: linkato al Piano!B9 cosi' modifichi una volta sola
        ws.cell(row=r, column=6, value="='Piano mensile'!$B$9").number_format = "0.00"
        # e_total = eec - esca + etd + ep
        ws.cell(row=r, column=7,
                value=f"=C{r}-D{r}+E{r}+F{r}").number_format = "0.00"
        for c in range(1, 8):
            cell = ws.cell(row=r, column=c)
            cell.border = _border_thin()
            if c == 1:
                cell.fill = PatternFill("solid", fgColor=SLATE_50)
            elif c == 7:
                cell.fill = PatternFill("solid", fgColor=AMBER_BG)
                cell.font = Font(bold=True, color=AMBER_DK)

    # Caption finale
    last_r = len(feeds) + 3
    ws.cell(row=last_r, column=1,
            value=("Read-only. e_total = eec - esca + etd + ep. "
                   "Modifica «ep» in «Piano mensile» cella B9 per "
                   "ricalcolare automaticamente la sostenibilita'.")
            ).font = Font(italic=True, size=9, color=SLATE_500)
    ws.merge_cells(start_row=last_r, start_column=1,
                   end_row=last_r, end_column=7)

    # Larghezze colonne
    ws.column_dimensions["A"].width = 32
    for col_letter in "BCDEFG":
        ws.column_dimensions[col_letter].width = 12


# ============================================================
# Sheet 2 — Piano mensile (main)
# ============================================================
def _build_piano(ws, ctx, db_sheet_name):
    feeds   = ctx["active_feeds"]
    n_feed  = len(feeds)

    # Layout columns:
    #  A: Mese (read-only)
    #  B: Ore (editable)
    #  C..C+n-1: biomasse (editable)
    #  poi: Sm3 lordi, Sm3 netti, MWh netti, e_w, Saving %, Sm3/h netti, Validita
    bio_col_start = 3
    bio_col_end   = 2 + n_feed
    sm3_lordi_col = bio_col_end + 1
    sm3_netti_col = sm3_lordi_col + 1
    mwh_netti_col = sm3_netti_col + 1
    e_w_col       = mwh_netti_col + 1
    saving_col    = e_w_col + 1
    smch_col      = saving_col + 1
    valid_col     = smch_col + 1

    L = get_column_letter
    last_col_letter = L(valid_col)

    # === Title (row 1) ===
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=valid_col)
    c = ws.cell(row=1, column=1,
                value="Metan.iQ — Piano mensile editabile")
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
    c = ws.cell(row=3, column=1,
                value=("✏️ Modifica le celle GIALLE (Ore + Biomasse). "
                       "Tutti i calcoli si aggiornano automaticamente."))
    c.font = Font(bold=True, size=10, color=AMBER_DK)
    c.fill = PatternFill("solid", fgColor=AMBER_BG)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    c.border = _border_thin()
    ws.row_dimensions[3].height = 22

    # === Parametri impianto (rows 4-10) ===
    aux_factor       = float(ctx.get("aux_factor", 1.29))
    comparator       = float(ctx.get("fossil_comparator", 80.0))
    ghg_threshold    = float(ctx.get("ghg_threshold", 0.65)) * 100
    plant_max_smch   = float(ctx.get("plant_net_smch", 300.0))
    ep_total         = float(ctx.get("ep_total", 0.0))
    nm3_to_mwh       = float(ctx.get("NM3_TO_MWH", 0.00997))

    params = [
        ("PARAMETRI IMPIANTO (read-only)", None, None, True),
        ("aux_factor (netto -> lordo)",   aux_factor,    "0.000", False),
        ("Comparator fossile (gCO2/MJ)",  comparator,    "0",     False),
        ("Soglia saving GHG (%)",         ghg_threshold, "0.0",   False),
        ("Produzione netta max (Sm3/h)",  plant_max_smch,"0.0",   False),
        ("ep totale (gCO2/MJ)",           ep_total,      "0.00",  False),
        ("PCI biometano (MWh/Sm3)",       nm3_to_mwh,    "0.00000", False),
    ]
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
            # Editable for the user (es. ep totale per simulare scenari ep)
            c_val.fill = PatternFill("solid", fgColor=AMBER_BG)
            c_val.font = Font(bold=True, color=NAVY)
            c_val.alignment = Alignment(horizontal="right")
            c_val.border = _border_thin()

    # === Empty row 11 ===

    # === Header tabella (row 12) ===
    header_row = 12
    headers = ["Mese", "Ore"] + feeds + [
        "Sm3 lordi", "Sm3 netti", "MWh netti",
        "e_w", "Saving %", "Sm3/h netti", "Validita",
    ]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=col, value=h)
        _style_header(c)
    ws.row_dimensions[header_row].height = 42

    # === Riferimenti per formule ===
    aux_cell        = "$B$5"
    comparator_cell = "$B$6"
    threshold_cell  = "$B$7"
    max_prod_cell   = "$B$8"
    pci_cell        = "$B$10"

    db_yield_range = f"'{db_sheet_name}'!$B$2:$B${1 + n_feed}"
    db_etot_range  = f"'{db_sheet_name}'!$G$2:$G${1 + n_feed}"

    bio_start_letter = L(bio_col_start)
    bio_end_letter   = L(bio_col_end)

    # === Dati 12 mesi (rows 13-24) ===
    months = ctx.get("MONTHS", [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ])
    month_hours = ctx.get("MONTH_HOURS", [
        744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744,
    ])
    initial_data = ctx.get("initial_data", {}) or {}

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

        # B: Ore (editable)
        ore_default = h
        if m in initial_data:
            ore_default = initial_data[m].get("Ore", h)
        c_ore = ws.cell(row=r, column=2, value=int(ore_default))
        _style_editable(c_ore)
        c_ore.number_format = "0"

        # C..N: biomasse (editable)
        for j, name in enumerate(feeds):
            col = bio_col_start + j
            default = 0.0
            if m in initial_data:
                default = initial_data[m].get(name, 0.0)
            c_b = ws.cell(row=r, column=col, value=float(default))
            _style_editable(c_b)
            c_b.number_format = "#,##0.0"

        bio_range = f"{bio_start_letter}{r}:{bio_end_letter}{r}"

        # Sm3 lordi
        c = ws.cell(row=r, column=sm3_lordi_col,
                    value=f"=SUMPRODUCT({bio_range},{db_yield_range})")
        c.number_format = "#,##0"
        _style_readonly(c)

        # Sm3 netti = lordi / aux
        sm3_lordi_letter = L(sm3_lordi_col)
        c = ws.cell(row=r, column=sm3_netti_col,
                    value=f"=IFERROR({sm3_lordi_letter}{r}/{aux_cell},0)")
        c.number_format = "#,##0"
        _style_readonly(c)

        # MWh netti = netti * PCI
        sm3_netti_letter = L(sm3_netti_col)
        c = ws.cell(row=r, column=mwh_netti_col,
                    value=f"={sm3_netti_letter}{r}*{pci_cell}")
        c.number_format = "#,##0.0"
        _style_readonly(c)

        # e_w (gCO2/MJ): SUMPRODUCT(bio*yield*etot)/SUMPRODUCT(bio*yield)
        c = ws.cell(row=r, column=e_w_col,
                    value=(f"=IFERROR(SUMPRODUCT({bio_range},"
                           f"{db_yield_range},{db_etot_range})"
                           f"/SUMPRODUCT({bio_range},{db_yield_range}),0)"))
        c.number_format = "0.00"
        _style_readonly(c)

        # Saving %
        e_w_letter = L(e_w_col)
        c = ws.cell(row=r, column=saving_col,
                    value=(f"=IFERROR(({comparator_cell}-{e_w_letter}{r})"
                           f"/{comparator_cell}*100,0)"))
        c.number_format = "0.0\"%\""
        _style_readonly(c)

        # Sm3/h netti
        c = ws.cell(row=r, column=smch_col,
                    value=f"=IFERROR({sm3_netti_letter}{r}/B{r},0)")
        c.number_format = "0.0"
        _style_readonly(c)

        # Validita
        saving_letter = L(saving_col)
        smch_letter   = L(smch_col)
        c = ws.cell(row=r, column=valid_col,
                    value=(f'=IF(AND({saving_letter}{r}>={threshold_cell},'
                           f'{smch_letter}{r}<={max_prod_cell}),"OK","KO")'))
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _border_thin()
        # background applied via conditional formatting

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
    for col in (sm3_lordi_col, sm3_netti_col, mwh_netti_col):
        cl = L(col)
        c = ws.cell(row=tot_row, column=col,
                    value=f"=SUM({cl}{first_data_row}:{cl}{last_data_row})")
        _style_total(c)
        c.number_format = "#,##0" if col != mwh_netti_col else "#,##0.0"

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

    # Sm3/h netti medio
    cl_smch = L(smch_col)
    c = ws.cell(row=tot_row, column=smch_col,
                value=(f"=IFERROR(AVERAGE("
                       f"{cl_smch}{first_data_row}:{cl_smch}{last_data_row}),0)"))
    _style_total(c); c.number_format = "0.0"

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

    # Sm3/h netti: rosso se > max
    smch_range = f"{cl_smch}{first_data_row}:{cl_smch}{last_data_row}"
    rule_smch_ko = CellIsRule(
        operator="greaterThan", formula=[max_prod_cell],
        fill=PatternFill("solid", fgColor=RED_BG),
        font=Font(color=RED_FG),
    )
    ws.conditional_formatting.add(smch_range, rule_smch_ko)

    # === Larghezze colonne ===
    ws.column_dimensions["A"].width = 14   # Mese
    ws.column_dimensions["B"].width = 8    # Ore
    for j in range(n_feed):
        ws.column_dimensions[L(bio_col_start + j)].width = 14
    ws.column_dimensions[L(sm3_lordi_col)].width = 12
    ws.column_dimensions[L(sm3_netti_col)].width = 12
    ws.column_dimensions[L(mwh_netti_col)].width = 12
    ws.column_dimensions[L(e_w_col)].width      = 11
    ws.column_dimensions[L(saving_col)].width   = 11
    ws.column_dimensions[L(smch_col)].width     = 12
    ws.column_dimensions[L(valid_col)].width    = 11

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
# Sheet 3 — Sintesi annuale
# ============================================================
def _build_summary(ws, ctx, piano_sheet_name):
    feeds  = ctx["active_feeds"]
    n_feed = len(feeds)

    bio_col_start = 3
    bio_col_end   = 2 + n_feed
    sm3_lordi_col = bio_col_end + 1
    sm3_netti_col = sm3_lordi_col + 1
    mwh_netti_col = sm3_netti_col + 1
    saving_col    = sm3_netti_col + 3   # +3 = Sm3 netti, MWh netti, e_w
    valid_col     = saving_col + 2      # +2 dopo saving = Sm3/h, Validita
    L = get_column_letter

    first_data_row = 13
    last_data_row  = 24
    tot_row        = 25

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

    # === KPI block ===
    cl_smnett = L(sm3_netti_col)
    cl_mwh    = L(mwh_netti_col)
    cl_sav    = L(saving_col)
    cl_val    = L(valid_col)

    kpi = [
        ("Tot. biomasse (t/anno)",
         f"=SUMPRODUCT(('{p}'!{L(bio_col_start)}{first_data_row}:"
         f"{L(bio_col_end)}{last_data_row}))",
         "#,##0"),
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
        ("Soglia RED III (%)",
         f"='{p}'!$B$7",
         "0.0\"%\""),
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
        c = ws.cell(row=r, column=4,
                    value=f"=B{r}*'Database feedstock'!$B${j+2}*"
                          f"'{p}'!$B$10/'{p}'!$B$5")
        c.number_format = "#,##0.0"; _style_readonly(c)

    # Larghezze
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 18
