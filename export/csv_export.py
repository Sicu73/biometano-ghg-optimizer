# -*- coding: utf-8 -*-
"""export/csv_export.py — Esportazione CSV da output_model.

Funzione pubblica:
  build_csv_from_output(output_model, sheet="monthly") -> bytes

`sheet` puo' essere:
  "monthly"       -> tabella piano mensile (df_res)
  "feedstock"     -> tabella feedstock con quantita' annuali e ricavi
  "ghg"           -> tabella fattori emissivi GHG
  "business_plan" -> tabella CE multi-anno (solo DM 2022)
  "audit"         -> audit trail BMT + fattori emissivi

Il CSV usa separatore ';' e decimale ',' (formato italiano / RFC 4180 IT).
Encoding: UTF-8 BOM (compatibile Excel Windows).
"""
from __future__ import annotations

import csv
import io
from typing import Any


def build_csv_from_output(
    output_model: dict,
    sheet: str = "monthly",
) -> bytes:
    """Genera CSV da output_model.

    Args:
        output_model:   Dict prodotto da build_output_model().
        sheet:          Quale tabella esportare (default: 'monthly').

    Returns:
        Bytes UTF-8 BOM del file CSV, pronti per st.download_button.

    Raises:
        KeyError:   Se il sheet richiesto non esiste in output_model.
        ValueError: Se output_model non e' un dict valido.
    """
    if not isinstance(output_model, dict):
        raise ValueError(f"output_model deve essere un dict, ricevuto: {type(output_model)}")

    # Seleziona la tabella corretta
    table_map = {
        "monthly":       ("monthly_table",       _build_monthly_rows),
        "feedstock":     ("feedstock_table",      _build_feedstock_rows),
        "ghg":           ("ghg_table",            _build_ghg_rows),
        "business_plan": ("business_plan_table",  _build_bp_rows),
        "audit":         ("audit_trail",          _build_audit_rows),
    }
    if sheet not in table_map:
        raise ValueError(
            f"sheet '{sheet}' non valido. "
            f"Valori ammessi: {list(table_map.keys())}"
        )

    key, builder = table_map[sheet]
    raw_rows: list[dict[str, Any]] = output_model.get(key, [])
    display_rows = builder(raw_rows)

    if not display_rows:
        # CSV vuoto con intestazione metadata
        return _empty_csv(output_model, sheet)

    # Scrivi CSV
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=list(display_rows[0].keys()),
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writeheader()
    for row in display_rows:
        # Converti float in formato italiano (virgola decimale)
        formatted = {k: _fmt_csv(v) for k, v in row.items()}
        writer.writerow(formatted)

    # Aggiungi metadata in fondo (righe commento con #)
    _append_metadata(buf, output_model, sheet)

    return ("﻿" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------------------
# Builder tabelle
# ---------------------------------------------------------------------------

def _build_monthly_rows(raw: list[dict]) -> list[dict]:
    """Ritorna le righe della tabella mensile as-is (gia' pronte da df_res)."""
    return raw


def _build_feedstock_rows(raw: list[dict]) -> list[dict]:
    return [
        {
            "Biomassa":        r.get("biomassa", ""),
            "Categoria":       r.get("categoria", ""),
            "Annex IX":        "Si" if r.get("annex_ix") else "No",
            "Tonnellate/anno": r.get("tonnellate_anno", 0.0),
            "MWh netti/anno":  r.get("mwh_anno", 0.0),
            "Ricavi EUR/anno": r.get("ricavi_eur", 0.0),
            "Tariffa EUR/MWh": r.get("tariffa_eur_mwh", 0.0),
            "N° CIC/anno":     r.get("n_cic", 0.0),
        }
        for r in raw
    ]


def _build_ghg_rows(raw: list[dict]) -> list[dict]:
    return [
        {
            "Biomassa":          r.get("biomassa", ""),
            "eec (gCO2/MJ)":     r.get("eec", 0.0),
            "etd (gCO2/MJ)":     r.get("etd", 0.0),
            "esca (gCO2/MJ)":    r.get("esca", 0.0),
            "ep (gCO2/MJ)":      r.get("ep", 0.0),
            "e_total (gCO2/MJ)": r.get("e_total", 0.0),
            "Fonte":             r.get("fonte", ""),
            "Override EF":       "Si" if r.get("override_attivo") else "No",
        }
        for r in raw
    ]


def _build_bp_rows(raw: list[dict]) -> list[dict]:
    return [
        {
            "Anno":                  r.get("anno", 0),
            "Ricavi (EUR)":          r.get("ricavi_eur", 0.0),
            "OPEX (EUR)":            r.get("opex_eur", 0.0),
            "EBITDA (EUR)":          r.get("ebitda_eur", 0.0),
            "Interessi (EUR)":       r.get("interessi_eur", 0.0),
            "Ammortamenti (EUR)":    r.get("ammortamenti_eur", 0.0),
            "Utile ante imp. (EUR)": r.get("utile_ante_eur", 0.0),
            "Utile netto (EUR)":     r.get("utile_netto_eur", 0.0),
            "FCF (EUR)":             r.get("fcf_eur", 0.0),
        }
        for r in raw
    ]


def _build_audit_rows(raw: list[dict]) -> list[dict]:
    return [
        {
            "Tipo":       r.get("tipo", ""),
            "Biomassa":   r.get("biomass_name", r.get("biomassa", r.get("raw", ""))),
            "Std":        r.get("standard_value", r.get("std", "")),
            "Override":   r.get("override_value", r.get("valore_reale", "")),
            "Fonte":      r.get("source", r.get("fonte", "")),
            "Data cert.": r.get("cert_date", r.get("data", "")),
            "Note":       r.get("note", ""),
        }
        for r in raw
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_csv(value: Any) -> str:
    """Formatta un valore per il CSV (float -> virgola decimale)."""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        return f"{value:,.4f}".replace(",", "§").replace(".", ",").replace("§", ".")
    if value is None:
        return ""
    return str(value)


def _empty_csv(output_model: dict, sheet: str) -> bytes:
    """CSV vuoto con info metadata + base sostenibilita' esplicita."""
    meta = output_model.get("metadata", {})
    calc = output_model.get("calculation_summary", {}) or {}
    lines = [
        f"# {meta.get('software_name', 'Metan.iQ')} - {meta.get('version', '')}",
        f"# Generato: {meta.get('generated_at', '')}",
        f"# Scenario: {meta.get('scenario_name', '')}",
        f"# Sheet: {sheet}",
        "# (nessun dato disponibile)",
    ]
    if sheet == "monthly":
        # Anche su sheet vuoto esponiamo i totali LORDO/NETTO + base
        lines.extend([
            f"# Sm3 LORDI (base sostenibilita'): {_fmt_csv(calc.get('tot_sm3_lordi', 0.0))}",
            f"# Sm3 NETTI (immesso in rete): {_fmt_csv(calc.get('tot_sm3_netti', 0.0))}",
            f"# MWh LORDI (base sostenibilita'): {_fmt_csv(calc.get('tot_mwh_lordi', 0.0))}",
            f"# MWh NETTI (immesso in rete): {_fmt_csv(calc.get('tot_mwh', 0.0))}",
            f"# Base sostenibilita': {calc.get('sustainability_basis', 'LORDO')}",
        ])
        _basis_note = str(calc.get("sustainability_basis_note", "")).replace("\r", " ").replace("\n", " ")
        if _basis_note:
            lines.append(f"# Nota base: {_basis_note}")
    return ("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8")


def _append_metadata(buf: io.StringIO, output_model: dict, sheet: str) -> None:
    """Aggiunge righe di metadata in fondo al CSV."""
    meta = output_model.get("metadata", {})
    calc = output_model.get("calculation_summary", {})
    buf.write("\r\n")
    buf.write(f"# Software: {meta.get('software_name', 'Metan.iQ')} {meta.get('version', '')}\r\n")
    buf.write(f"# Generato: {meta.get('generated_at', '')}\r\n")
    buf.write(f"# Scenario: {meta.get('scenario_name', '')}\r\n")
    buf.write(f"# Lingua: {meta.get('language', 'it')}\r\n")
    if sheet == "monthly":
        buf.write(f"# Mesi validi: {calc.get('valid_months', 0)}/12\r\n")
        buf.write(f"# Saving medio (%): {_fmt_csv(calc.get('saving_avg', 0.0))}\r\n")
        buf.write(f"# Totale ricavi (EUR): {_fmt_csv(calc.get('total_revenue', 0.0))}\r\n")
        # Doppia vista LORDO/NETTO + base sostenibilita' esplicita
        buf.write(f"# Sm3 LORDI (base sostenibilita'): {_fmt_csv(calc.get('tot_sm3_lordi', 0.0))}\r\n")
        buf.write(f"# Sm3 NETTI (immesso in rete): {_fmt_csv(calc.get('tot_sm3_netti', 0.0))}\r\n")
        buf.write(f"# MWh LORDI (base sostenibilita'): {_fmt_csv(calc.get('tot_mwh_lordi', 0.0))}\r\n")
        buf.write(f"# MWh NETTI (immesso in rete): {_fmt_csv(calc.get('tot_mwh', 0.0))}\r\n")
        buf.write(f"# Base sostenibilita': {calc.get('sustainability_basis', 'LORDO')}\r\n")
        _basis_note = str(calc.get("sustainability_basis_note", "")).replace("\r", " ").replace("\n", " ")
        if _basis_note:
            buf.write(f"# Nota base: {_basis_note}\r\n")
    warnings = output_model.get("warnings", [])
    errors = output_model.get("errors", [])
    for w in warnings:
        buf.write(f"# WARNING: {w}\r\n")
    for e in errors:
        buf.write(f"# ERROR: {e}\r\n")
