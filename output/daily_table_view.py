# -*- coding: utf-8 -*-
"""output/daily_table_view.py — Costruzione DataFrame giornaliero.

Trasforma una lista di `DailyEntry` + `DailyComputed` in un DataFrame
pronto per la visualizzazione in Streamlit (e per gli export CSV/Excel/PDF).

Espone anche `style_daily_dataframe()` che produce un Styler pandas con
highlighting rosso sulle celle che violano:
  - cap autorizzativo Sm³/h (colonna "Sm³/h netti")
  - soglia normativa GHG (colonna "Saving giornaliero (stima %)")
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from core.daily_model import DailyComputed, DailyEntry


def build_daily_dataframe(
    daily_entries: list[DailyEntry],
    daily_computed_list: list[DailyComputed],
    feed_columns: list[str] | None = None,
    hours_per_day: float = 24.0,
) -> pd.DataFrame:
    """Costruisce il DataFrame giornaliero per la UI/export.

    Colonne (ordine):
      Data,
      <colonne biomasse dinamiche>,
      Tot biomasse t,
      Sm3 netti, Sm³/h netti, MWh,
      eec, esca, etd, ep, e_total,
      Saving giornaliero (stima %),
      Cap OK,
      Cumulato Sm3, Cumulato MWh, Cumulato t.
    """
    by_date_entry = {e.date: e for e in (daily_entries or [])}
    by_date_comp = {c.date: c for c in (daily_computed_list or [])}

    if feed_columns is None:
        feed_set: set[str] = set()
        for e in (daily_entries or []):
            feed_set.update((e.feedstocks or {}).keys())
        feed_columns = sorted(feed_set)

    hpd = float(hours_per_day) if hours_per_day and float(hours_per_day) > 0 else 24.0

    rows: list[dict] = []
    cum_sm3 = 0.0
    cum_mwh = 0.0
    cum_t = 0.0

    all_dates = sorted(set(by_date_entry.keys()) | set(by_date_comp.keys()))
    for d in all_dates:
        e = by_date_entry.get(d)
        c = by_date_comp.get(d)
        row: dict = {"Data": d}
        for f in feed_columns:
            row[f] = float((e.feedstocks or {}).get(f, 0.0)) if e else 0.0
        if c is not None:
            cum_sm3 += c.sm3_netti
            cum_mwh += c.mwh
            cum_t += c.biomass_total_t
            sm3h_net = float(c.sm3_netti) / hpd if hpd > 0 else 0.0
            row.update({
                "Tot biomasse t":          c.biomass_total_t,
                "Sm3 netti":               c.sm3_netti,
                "Sm³/h netti":             sm3h_net,
                "MWh":                     c.mwh,
                "eec":                     c.eec,
                "esca":                    c.esca,
                "etd":                     c.etd,
                "ep":                      c.ep,
                "e_total":                 c.e_total,
                "Saving giornaliero (stima %)": c.daily_saving_estimate,
                "Cap OK":                  c.cap_ok,
                "Cumulato Sm3":            cum_sm3,
                "Cumulato MWh":            cum_mwh,
                "Cumulato t":              cum_t,
            })
        else:
            tot_t = sum(row.get(f, 0.0) for f in feed_columns) if feed_columns else 0.0
            cum_t += tot_t
            row.update({
                "Tot biomasse t":          tot_t,
                "Sm3 netti":               0.0,
                "Sm³/h netti":             0.0,
                "MWh":                     0.0,
                "eec":                     0.0,
                "esca":                    0.0,
                "etd":                     0.0,
                "ep":                      0.0,
                "e_total":                 0.0,
                "Saving giornaliero (stima %)": 0.0,
                "Cap OK":                  True,
                "Cumulato Sm3":            cum_sm3,
                "Cumulato MWh":            cum_mwh,
                "Cumulato t":              cum_t,
            })
        rows.append(row)

    if not rows:
        cols = (["Data"] + (feed_columns or []) + [
            "Tot biomasse t", "Sm3 netti", "Sm³/h netti", "MWh",
            "eec", "esca", "etd", "ep", "e_total",
            "Saving giornaliero (stima %)", "Cap OK",
            "Cumulato Sm3", "Cumulato MWh", "Cumulato t",
        ])
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Styler: highlight rosso per cap autorizzativo Sm³/h e soglia GHG
# ---------------------------------------------------------------------------

_RED_BG = "background-color: #ffd6d6; color: #b00020; font-weight: 600;"


def _style_smch_col(series: pd.Series, cap_smch: float) -> list[str]:
    """Rosso se Sm³/h netti supera (strettamente) la capacità autorizzata."""
    out: list[str] = []
    for v in series:
        try:
            val = float(v)
        except (TypeError, ValueError):
            out.append("")
            continue
        if cap_smch and val > float(cap_smch):
            out.append(_RED_BG)
        else:
            out.append("")
    return out


def _style_saving_col(series: pd.Series, threshold_pct: float) -> list[str]:
    """Rosso se saving giornaliero (in %) è inferiore alla soglia normativa.

    Le celle a 0.0 (giorni senza biomassa) restano non evidenziate.
    """
    out: list[str] = []
    for v in series:
        try:
            val = float(v)
        except (TypeError, ValueError):
            out.append("")
            continue
        if threshold_pct and 0.0 < val < float(threshold_pct):
            out.append(_RED_BG)
        else:
            out.append("")
    return out


def style_daily_dataframe(
    df: pd.DataFrame,
    cap_smch: float | None = None,
    ghg_threshold_pct: float | None = None,
):
    """Restituisce un Styler con highlight rossi su Sm³/h netti e Saving %.

    Args:
        df: DataFrame prodotto da `build_daily_dataframe`.
        cap_smch: capacità autorizzata Sm³/h netti (cap impianto). Se la cella
            "Sm³/h netti" supera questo valore → rosso.
        ghg_threshold_pct: soglia normativa saving GHG in PERCENTUALE
            (es. 80.0 per 80%). Se la cella "Saving giornaliero (stima %)"
            è > 0 e < soglia → rosso.

    Returns:
        Styler pandas. Se il DataFrame è vuoto ritorna comunque uno Styler valido.
    """
    if df is None or len(df) == 0:
        return df.style if hasattr(df, "style") else pd.DataFrame().style

    styler = df.style

    # Formattazione numerica leggibile
    fmt_map: dict = {}
    if "Sm³/h netti" in df.columns:
        fmt_map["Sm³/h netti"] = "{:,.2f}"
    if "Sm3 netti" in df.columns:
        fmt_map["Sm3 netti"] = "{:,.0f}"
    if "MWh" in df.columns:
        fmt_map["MWh"] = "{:,.2f}"
    if "Tot biomasse t" in df.columns:
        fmt_map["Tot biomasse t"] = "{:,.2f}"
    if "Saving giornaliero (stima %)" in df.columns:
        fmt_map["Saving giornaliero (stima %)"] = "{:,.2f}"
    for col in ("eec", "esca", "etd", "ep", "e_total"):
        if col in df.columns:
            fmt_map[col] = "{:,.3f}"
    for col in ("Cumulato Sm3", "Cumulato MWh", "Cumulato t"):
        if col in df.columns:
            fmt_map[col] = "{:,.1f}"
    try:
        styler = styler.format(fmt_map, na_rep="-")
    except Exception:
        pass

    # Highlight Sm³/h > cap
    if cap_smch and cap_smch > 0 and "Sm³/h netti" in df.columns:
        try:
            styler = styler.apply(
                lambda s: _style_smch_col(s, float(cap_smch)),
                subset=["Sm³/h netti"],
            )
        except Exception:
            pass

    # Highlight saving < soglia
    if ghg_threshold_pct and "Saving giornaliero (stima %)" in df.columns:
        try:
            styler = styler.apply(
                lambda s: _style_saving_col(s, float(ghg_threshold_pct)),
                subset=["Saving giornaliero (stima %)"],
            )
        except Exception:
            pass

    return styler


__all__ = ["build_daily_dataframe", "style_daily_dataframe"]
