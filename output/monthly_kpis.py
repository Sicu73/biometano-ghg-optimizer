# -*- coding: utf-8 -*-
"""output/monthly_kpis.py — KPI mensili per la sezione Gestione Giornaliera.

Costruisce un dict pronto per la UI Streamlit con KPI principali del mese
e l'esito di sostenibilita' ufficiale.
"""
from __future__ import annotations

from typing import Any

from core.monthly_aggregate import MonthlyAggregate


def build_monthly_kpis(
    monthly_agg: MonthlyAggregate,
    sustainability_eval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restituisce un dict piatto di KPI mensili."""
    se = sustainability_eval or {}
    feed_totals = getattr(monthly_agg, "feedstock_totals_t", {}) or {}

    return {
        "year":                int(getattr(monthly_agg, "year", 0)),
        "month":               int(getattr(monthly_agg, "month", 0)),
        "biomass_total_t":     float(getattr(monthly_agg, "biomass_total_t", 0.0)),
        "feedstock_totals":    dict(feed_totals),
        "sm3_gross":           float(getattr(monthly_agg, "sm3_gross", 0.0)),
        "sm3_netti":           float(getattr(monthly_agg, "sm3_netti", 0.0)),
        "mwh":                 float(getattr(monthly_agg, "mwh", 0.0)),
        "mwh_gross":           float(getattr(monthly_agg, "mwh_gross", 0.0)),
        "saving_pct":          float(getattr(monthly_agg, "saving_pct", 0.0)),
        "saving_pct_net":      float(getattr(monthly_agg, "saving_pct_net",
                                              getattr(monthly_agg, "saving_pct", 0.0))),
        "sustainability_basis":str(getattr(monthly_agg, "sustainability_basis", "LORDO")),
        "e_total":             float(getattr(monthly_agg, "e_total", 0.0)),
        "eec":                 float(getattr(monthly_agg, "eec_w", 0.0)),
        "esca":                float(getattr(monthly_agg, "esca_w", 0.0)),
        "etd":                 float(getattr(monthly_agg, "etd_w", 0.0)),
        "ep":                  float(getattr(monthly_agg, "ep_w", 0.0)),
        "n_days_with_data":    int(getattr(monthly_agg, "n_days_with_data", 0)),
        "compliant":           bool(se.get("compliant", False)),
        "threshold":           float(se.get("threshold", 0.0)),
        "margin":              float(se.get("margin", 0.0)),
        "constraints_status":  list(se.get("constraints_status", [])),
        "regime":              str(se.get("regime", "")),
        "cap_violation_days":  list(getattr(monthly_agg, "cap_violation_days", []) or []),
        # REMI consolidated KPIs
        "remi_vb_total":       float(getattr(monthly_agg, "remi_vb_total", 0.0)),
        "remi_e_total":        float(getattr(monthly_agg, "remi_e_total", 0.0)),
        "remi_e_estimated":    bool(getattr(monthly_agg, "remi_e_estimated", False)),
        "remi_qb_max_month":   float(getattr(monthly_agg, "remi_qb_max_month", 0.0)),
        "remi_pci_avg":        float(getattr(monthly_agg, "remi_pci_avg", 0.0)),
        "remi_rho_avg":        float(getattr(monthly_agg, "remi_rho_avg", 0.0)),
        "remi_portata_media_smch": float(getattr(monthly_agg, "remi_portata_media_smch", 0.0)),
        "remi_potenza_media_mw":   float(getattr(monthly_agg, "remi_potenza_media_mw", 0.0)),
        "remi_energia_specifica_kwh_smc": float(getattr(monthly_agg, "remi_energia_specifica_kwh_smc", 0.0)),
    }


__all__ = ["build_monthly_kpis"]
