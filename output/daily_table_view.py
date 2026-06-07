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
      remi_vb, remi_e, remi_qb_max, remi_pci, remi_rho,
      remi_portata_media_smch, remi_potenza_media_mw, remi_energia_specifica_kwh_smc,
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
                "remi_vb":                 c.remi_portata_media_smch * hpd if hpd > 0 else 0.0, # Placeholder if needed, but we have entry
                "remi_e":                  0.0, # Placeholder
                "Cumulato Sm3":            cum_sm3,
                "Cumulato MWh":            cum_mwh,
                "Cumulato t":              cum_t,
            })
            if e:
                row.update({
                    "remi_vb":             e.remi_vb,
                    "remi_e":              e.remi_e,
                    "remi_qb_max":         e.remi_qb_max,
                    "remi_pci":            e.remi_pci,
                    "remi_rho":            e.remi_rho,
                })
            row.update({
                "remi_portata_media_smch": c.remi_portata_media_smch,
                "remi_potenza_media_mw":   c.remi_potenza_media_mw,
                "remi_energia_specifica_kwh_smc": c.remi_energia_specifica_kwh_smc,
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
                "remi_vb":                 e.remi_vb if e else 0.0,
                "remi_e":                  e.remi_e if e else 0.0,
                "remi_qb_max":             e.remi_qb_max if e else 0.0,
                "remi_pci":                e.remi_pci if e else 0.0,
                "remi_rho":                e.remi_rho if e else 0.0,
                "remi_portata_media_smch": 0.0,
                "remi_potenza_media_mw":   0.0,
                "remi_energia_specifica_kwh_smc": 0.0,
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
            "remi_vb", "remi_e", "remi_qb_max", "remi_pci", "remi_rho",
            "remi_portata_media_smch", "remi_potenza_media_mw", "remi_energia_specifica_kwh_smc",
            "Cumulato Sm3", "Cumulato MWh", "Cumulato t",
        ])
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Append riga "TOTALE MESE" alla vista giornaliera
# ---------------------------------------------------------------------------

def append_monthly_total_row(
    df: pd.DataFrame,
    feed_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Aggiunge in fondo al DataFrame giornaliero una riga di totali mensili.

    Aggregazioni:
      - colonne biomasse (feed_columns)        -> SUM
      - "Tot biomasse t", "Sm3 netti", "MWh"   -> SUM
      - "Sm³/h netti"                          -> MAX (picco orario nel mese)
      - "Saving giornaliero (stima %)"         -> media pesata sui giorni con
                                                  biomassa > 0 (NaN se nessuno)
      - "Data"                                 -> stringa "TOTALE MESE"

    Le altre colonne (eec, esca, etd, ep, e_total, Cumulato*, Cap OK)
    restano vuote nella riga totale (sono concetti per-giorno).
    """
    if df is None or len(df) == 0:
        return df

    feed_cols = feed_columns or []

    # Per evitare ArrowTypeError nel rendering Streamlit (colonna Data mista
    # date + str), convertiamo l'intera colonna Data in stringa.
    out = df.copy()
    if "Data" in out.columns:
        out["Data"] = out["Data"].apply(
            lambda d: d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)
        )

    total: dict = {"Data": "TOTALE MESE"}

    # Somme biomasse per tipologia
    for c in feed_cols:
        if c in out.columns:
            total[c] = float(out[c].sum())

    # Aggregati standard
    for c in ("Tot biomasse t", "Sm3 netti", "MWh"):
        if c in out.columns:
            total[c] = float(out[c].sum())

    # Picco Sm³/h nel mese
    if "Sm³/h netti" in out.columns:
        try:
            total["Sm³/h netti"] = float(out["Sm³/h netti"].max())
        except (TypeError, ValueError):
            total["Sm³/h netti"] = 0.0

    # Aggregati REMI
    if "remi_vb" in out.columns:
        total["remi_vb"] = float(out["remi_vb"].sum())
    if "remi_e" in out.columns:
        total["remi_e"] = float(out["remi_e"].sum())
    if "remi_qb_max" in out.columns:
        total["remi_qb_max"] = float(out["remi_qb_max"].max())
    
    # KPI REMI medi mensili
    if "remi_vb" in total and total["remi_vb"] > 0:
        if "remi_e" in total:
            total["remi_energia_specifica_kwh_smc"] = total["remi_e"] / total["remi_vb"]
    
    # Per portata e potenza media mensile, servirebbe il totale ore del mese
    # Possiamo approssimare o calcolare se abbiamo accesso alle ore.
    # In questa vista, le ore non sono aggregate esplicitamente nella riga totale ancora.
    # Ma possiamo calcolare la media delle colonne se presenti.
    if "remi_portata_media_smch" in out.columns:
        mask = out["remi_portata_media_smch"] > 0
        if mask.any():
            total["remi_portata_media_smch"] = out.loc[mask, "remi_portata_media_smch"].mean()
    if "remi_potenza_media_mw" in out.columns:
        mask = out["remi_potenza_media_mw"] > 0
        if mask.any():
            total["remi_potenza_media_mw"] = out.loc[mask, "remi_potenza_media_mw"].mean()

    # Saving giornaliero medio pesato (su giorni con biomassa effettiva)
    if "Saving giornaliero (stima %)" in out.columns and "Tot biomasse t" in out.columns:
        try:
            mask = out["Tot biomasse t"].astype(float) > 0
            if mask.any():
                w = out.loc[mask, "Tot biomasse t"].astype(float)
                v = out.loc[mask, "Saving giornaliero (stima %)"].astype(float)
                total["Saving giornaliero (stima %)"] = float((v * w).sum() / w.sum())
            else:
                total["Saving giornaliero (stima %)"] = 0.0
        except Exception:  # noqa: BLE001
            pass

    # Riga totale: per le colonne non aggregate uso np.nan (verrà formattato
    # come "-" dallo styler con na_rep="-"), evitando ValueError sui formatter.
    import numpy as _np
    total_row = pd.DataFrame([total])
    for c in out.columns:
        if c not in total_row.columns:
            total_row[c] = _np.nan
    total_row = total_row[out.columns]

    return pd.concat([out, total_row], ignore_index=True)


# ---------------------------------------------------------------------------
# Styler: highlight rosso per cap autorizzativo Sm³/h e soglia GHG
# ---------------------------------------------------------------------------

_RED_BG = "background-color: #ffd6d6; color: #b00020; font-weight: 600;"
_TOTAL_ROW_STYLE = (
    "background-color: #fef3c7; color: #0F172A; font-weight: 700; "
    "border-top: 2px solid #F59E0B;"
)


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
    
    # Formattazione REMI
    for col in ("remi_vb", "remi_e", "remi_qb_max", "remi_portata_media_smch"):
        if col in df.columns:
            fmt_map[col] = "{:,.0f}"
    for col in ("remi_pci", "remi_rho", "remi_potenza_media_mw", "remi_energia_specifica_kwh_smc"):
        if col in df.columns:
            fmt_map[col] = "{:,.2f}"

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

    # Highlight saving < soglia (escludendo riga totale, che usa media pesata)
    if ghg_threshold_pct and "Saving giornaliero (stima %)" in df.columns:
        try:
            # NB: per la riga TOTALE non vogliamo highlight rosso anche se la
            # media pesata è sotto soglia: l'esito di compliance si vede nel
            # banner mensile, non nella tabella.
            _is_total = (
                df["Data"].astype(str).eq("TOTALE MESE")
                if "Data" in df.columns else None
            )
            if _is_total is not None and _is_total.any():
                _saving_subset = df.index[~_is_total]
                styler = styler.apply(
                    lambda s: _style_saving_col(s, float(ghg_threshold_pct)),
                    subset=(_saving_subset, ["Saving giornaliero (stima %)"]),
                )
            else:
                styler = styler.apply(
                    lambda s: _style_saving_col(s, float(ghg_threshold_pct)),
                    subset=["Saving giornaliero (stima %)"],
                )
        except Exception:
            pass

    # Riga "TOTALE MESE": evidenziazione amber, font bold, separatore in alto
    if "Data" in df.columns:
        try:
            _total_mask = df["Data"].astype(str).eq("TOTALE MESE")
            if _total_mask.any():
                _total_idx = df.index[_total_mask]
                styler = styler.apply(
                    lambda row: [_TOTAL_ROW_STYLE] * len(row),
                    axis=1,
                    subset=(_total_idx, df.columns),
                )
        except Exception:
            pass

    return styler


__all__ = [
    "build_daily_dataframe",
    "append_monthly_total_row",
    "style_daily_dataframe",
]
