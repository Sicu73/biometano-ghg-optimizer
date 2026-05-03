# -*- coding: utf-8 -*-
"""output/daily_table_view.py — Costruzione DataFrame giornaliero.

Trasforma una lista di `DailyEntry` + `DailyComputed` in un DataFrame
pronto per la visualizzazione in Streamlit (e per gli export CSV/Excel/PDF).
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from core.daily_model import DailyComputed, DailyEntry


def build_daily_dataframe(
    daily_entries: list[DailyEntry],
    daily_computed_list: list[DailyComputed],
    feed_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Costruisce il DataFrame giornaliero per la UI/export.

    Colonne (ordine):
      Data,
      <colonne biomasse dinamiche>,
      Tot biomasse t,
      Sm3 netti, MWh,
      eec, esca, etd, ep, e_total,
      Saving giornaliero (stima %),
      Cap OK,
      Cumulato Sm3, Cumulato MWh, Cumulato t.
    """
    # Prepara dict per accesso rapido
    by_date_entry = {e.date: e for e in (daily_entries or [])}
    by_date_comp = {c.date: c for c in (daily_computed_list or [])}

    # Determina elenco feed columns se non passato
    if feed_columns is None:
        feed_set: set[str] = set()
        for e in (daily_entries or []):
            feed_set.update((e.feedstocks or {}).keys())
        feed_columns = sorted(feed_set)

    rows: list[dict] = []
    cum_sm3 = 0.0
    cum_mwh = 0.0
    cum_t = 0.0

    # Iter su tutte le date (unione)
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
            row.update({
                "Tot biomasse t":          c.biomass_total_t,
                "Sm3 netti":               c.sm3_netti,
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
        # DataFrame vuoto ma ben tipizzato
        cols = (["Data"] + (feed_columns or []) + [
            "Tot biomasse t", "Sm3 netti", "MWh",
            "eec", "esca", "etd", "ep", "e_total",
            "Saving giornaliero (stima %)", "Cap OK",
            "Cumulato Sm3", "Cumulato MWh", "Cumulato t",
        ])
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    return df


__all__ = ["build_daily_dataframe"]
