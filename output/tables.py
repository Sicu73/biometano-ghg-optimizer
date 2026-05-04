# -*- coding: utf-8 -*-
"""output/tables.py — Costruttori di tabelle da output_model.

Ogni funzione prende il output_model dict (prodotto da build_output_model)
e restituisce un oggetto compatibile con st.dataframe / pd.DataFrame.
Se pandas non e' disponibile, restituisce una lista di dict.

Funzioni pubbliche:
  build_monthly_table(output_model)       -> pd.DataFrame | list[dict]
  build_feedstock_table(output_model)     -> pd.DataFrame | list[dict]
  build_ghg_table(output_model)           -> pd.DataFrame | list[dict]
  build_business_plan_table(output_model) -> pd.DataFrame | list[dict]
  build_audit_table(output_model)         -> pd.DataFrame | list[dict]
"""
from __future__ import annotations

from typing import Any

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


def _to_df_or_list(rows: list[dict[str, Any]]) -> Any:
    """Ritorna DataFrame se pandas disponibile, altrimenti lista di dict."""
    if _HAS_PANDAS and rows:
        return pd.DataFrame(rows)
    return rows


def build_sustainability_basis_table(output_model: dict) -> Any:
    """Tabella riassuntiva della base sostenibilita' (LORDO vs NETTO).

    Espone in modo esplicito quale grandezza energetica e' usata per il
    saving GHG e quale e' la vista informativa NETTO (per biometano).
    Colonne: Voce, LORDO (base sostenibilita'), NETTO (immesso in rete),
             Note.
    """
    calc = output_model.get("calculation_summary", {}) or {}
    tot_sm3_lordi = float(calc.get("tot_sm3_lordi", 0.0) or 0.0)
    tot_sm3_netti = float(calc.get("tot_sm3_netti", 0.0) or 0.0)
    tot_mwh_lordi = float(calc.get("tot_mwh_lordi", 0.0) or 0.0)
    tot_mwh_netti = float(calc.get("tot_mwh", 0.0) or 0.0)
    saving_avg = float(calc.get("saving_avg", 0.0) or 0.0)
    basis = str(calc.get("sustainability_basis", "LORDO") or "LORDO")
    is_dual = bool(calc.get("biomethane_dual_view", False))

    rows: list[dict[str, Any]] = [
        {
            "Voce": "Sm³ biometano",
            "LORDO (base sostenibilita')": tot_sm3_lordi,
            "NETTO (immesso in rete)": tot_sm3_netti,
            "Note": "LORDO = resa biomasse · NETTO = LORDO/aux_factor",
        },
        {
            "Voce": "MWh biometano",
            "LORDO (base sostenibilita')": tot_mwh_lordi,
            "NETTO (immesso in rete)": tot_mwh_netti,
            "Note": "Conversione 1 Sm³ ≈ 0,00997 MWh (LHV)",
        },
        {
            "Voce": "Saving GHG (%)",
            "LORDO (base sostenibilita')": saving_avg,
            "NETTO (immesso in rete)": (saving_avg if is_dual else None),
            "Note": (
                "Intensita' gCO2eq/MJ riferita all'energia LORDA "
                "(base normativa RED III/DM 2022/DM 2018/DM 2012/FER 2)."
            ),
        },
        {
            "Voce": "Base normativa applicata",
            "LORDO (base sostenibilita')": basis,
            "NETTO (immesso in rete)": (
                "vista informativa" if is_dual else "non applicabile"
            ),
            "Note": calc.get("sustainability_basis_note", ""),
        },
    ]
    return _to_df_or_list(rows)


# ---------------------------------------------------------------------------
# Tabella mensile
# ---------------------------------------------------------------------------

def build_monthly_table(output_model: dict) -> Any:
    """Tabella mensile dal output_model.

    Ritorna le righe di `monthly_table` come DataFrame (o lista di dict).
    Le colonne sono quelle native di df_res (non viene fatto reshape qui:
    la tabella e' gia' pronta in output_model).
    """
    rows = output_model.get("monthly_table", [])
    return _to_df_or_list(rows)


# ---------------------------------------------------------------------------
# Tabella feedstock
# ---------------------------------------------------------------------------

def build_feedstock_table(output_model: dict) -> Any:
    """Tabella biomasse con quantita' annuali e ricavi.

    Colonne: biomassa, categoria, annex_ix, tonnellate_anno,
             mwh_anno, ricavi_eur, tariffa_eur_mwh, n_cic.
    """
    rows = output_model.get("feedstock_table", [])
    if not rows:
        return _to_df_or_list([])

    display_rows = []
    for r in rows:
        display_rows.append({
            "Biomassa":         r.get("biomassa", ""),
            "Categoria":        r.get("categoria", ""),
            "Annex IX":         "Si" if r.get("annex_ix") else "No",
            "Tonnellate/anno":  r.get("tonnellate_anno", 0.0),
            "MWh netti/anno":   r.get("mwh_anno", 0.0),
            "Ricavi EUR/anno":  r.get("ricavi_eur", 0.0),
            "Tariffa EUR/MWh":  r.get("tariffa_eur_mwh", 0.0),
            "N° CIC/anno":      r.get("n_cic", 0.0),
        })
    return _to_df_or_list(display_rows)


# ---------------------------------------------------------------------------
# Tabella GHG
# ---------------------------------------------------------------------------

def build_ghg_table(output_model: dict) -> Any:
    """Tabella fattori GHG per biomassa.

    Colonne: biomassa, eec, etd, esca, ep, e_total, fonte, override_attivo.
    """
    rows = output_model.get("ghg_table", [])
    if not rows:
        return _to_df_or_list([])

    display_rows = []
    for r in rows:
        override_flag = "Si (relazione tecnica)" if r.get("override_attivo") else "No (tabella std)"
        display_rows.append({
            "Biomassa":              r.get("biomassa", ""),
            "eec (gCO2/MJ)":         r.get("eec", 0.0),
            "etd (gCO2/MJ)":         r.get("etd", 0.0),
            "esca (gCO2/MJ)":        r.get("esca", 0.0),
            "ep (gCO2/MJ)":          r.get("ep", 0.0),
            "e_total (gCO2/MJ)":     r.get("e_total", 0.0),
            "Fonte":                 r.get("fonte", ""),
            "Override EF":           override_flag,
        })
    return _to_df_or_list(display_rows)


# ---------------------------------------------------------------------------
# Tabella Business Plan
# ---------------------------------------------------------------------------

def build_business_plan_table(output_model: dict) -> Any:
    """Tabella conto economico multi-anno (15 anni standard DM 2022).

    Colonne: anno, ricavi, opex, ebitda, interessi, ammortamenti,
             utile_ante, utile_netto, fcf.
    Valori in EUR (non k€).
    """
    rows = output_model.get("business_plan_table", [])
    if not rows:
        return _to_df_or_list([])

    display_rows = []
    for r in rows:
        display_rows.append({
            "Anno":                 r.get("anno", 0),
            "Ricavi (EUR)":         r.get("ricavi_eur", 0.0),
            "OPEX (EUR)":           r.get("opex_eur", 0.0),
            "EBITDA (EUR)":         r.get("ebitda_eur", 0.0),
            "Interessi (EUR)":      r.get("interessi_eur", 0.0),
            "Ammortamenti (EUR)":   r.get("ammortamenti_eur", 0.0),
            "Utile ante imp. (EUR)":r.get("utile_ante_eur", 0.0),
            "Utile netto (EUR)":    r.get("utile_netto_eur", 0.0),
            "FCF (EUR)":            r.get("fcf_eur", 0.0),
        })
    return _to_df_or_list(display_rows)


# ---------------------------------------------------------------------------
# Tabella Audit Trail
# ---------------------------------------------------------------------------

def build_audit_table(output_model: dict) -> Any:
    """Tabella audit trail unificata (override BMT + fattori emissivi).

    Colonne: tipo, biomassa/nome, valore std, valore override, fonte,
             data certificato, note.
    """
    rows = output_model.get("audit_trail", [])
    if not rows:
        return _to_df_or_list([])

    display_rows = []
    for r in rows:
        tipo = r.get("tipo", "")
        raw = r.get("raw", "")
        if raw:
            display_rows.append({
                "Tipo":           tipo,
                "Biomassa":       "",
                "Std":            "",
                "Override":       "",
                "Fonte":          raw,
                "Data cert.":     "",
                "Note":           "",
            })
        else:
            display_rows.append({
                "Tipo":           tipo,
                "Biomassa":       r.get("biomass_name", r.get("biomassa", "")),
                "Std":            r.get("standard_value", r.get("std", "")),
                "Override":       r.get("override_value", r.get("valore_reale", "")),
                "Fonte":          r.get("source", r.get("fonte", "")),
                "Data cert.":     r.get("cert_date", r.get("data", "")),
                "Note":           r.get("note", ""),
            })
    return _to_df_or_list(display_rows)
