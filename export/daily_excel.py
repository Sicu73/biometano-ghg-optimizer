# -*- coding: utf-8 -*-
"""export/daily_excel.py — Esportazione Excel giornaliero (3 fogli)."""
from __future__ import annotations

import io
from typing import Any

import pandas as pd


def build_daily_excel(daily_df: pd.DataFrame, monthly_kpis: dict[str, Any],
                      audit_trail: dict[str, Any] | None = None) -> bytes:
    """Crea un .xlsx con 3 fogli: Giornaliero / Mensile KPI / Audit Trail."""
    buf = io.BytesIO()
    audit_trail = audit_trail or {}

    # Foglio Giornaliero
    df_day = daily_df.copy()
    if "Data" in df_day.columns:
        df_day["Data"] = pd.to_datetime(df_day["Data"], errors="coerce")

    # Foglio Mensile KPI
    kpi_rows = []
    for k, v in (monthly_kpis or {}).items():
        if k in ("constraints_status", "feedstock_totals", "cap_violation_days"):
            continue
        kpi_rows.append({"KPI": k, "Valore": v})
    # Espansione feedstock_totals
    for fname, qty in (monthly_kpis.get("feedstock_totals") or {}).items():
        kpi_rows.append({"KPI": f"Biomassa: {fname} (t)", "Valore": qty})
    df_kpi = pd.DataFrame(kpi_rows)

    # Foglio Vincoli (constraints_status come tabella)
    constraints = monthly_kpis.get("constraints_status") or []
    df_con = pd.DataFrame(constraints) if constraints else pd.DataFrame(
        columns=["name", "ok", "value", "limit", "msg"]
    )

    # Foglio Audit Trail
    audit_rows = []
    for k, v in audit_trail.items():
        if isinstance(v, (list, tuple)):
            v = " | ".join(str(x) for x in v)
        audit_rows.append({"Voce": k, "Valore": v})
    df_audit = pd.DataFrame(audit_rows) if audit_rows else pd.DataFrame(
        columns=["Voce", "Valore"]
    )

    # Try openpyxl first (preferred for .xlsx)
    engine = None
    try:
        import openpyxl  # noqa: F401
        engine = "openpyxl"
    except ImportError:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except ImportError:
            engine = None

    if engine is None:
        # Fallback: produce CSV-like with separator info (graceful degradation)
        return df_day.to_csv(sep=";", index=False).encode("utf-8")

    with pd.ExcelWriter(buf, engine=engine) as writer:
        df_day.to_excel(writer, sheet_name="Giornaliero", index=False)
        df_kpi.to_excel(writer, sheet_name="Mensile KPI", index=False)
        df_con.to_excel(writer, sheet_name="Vincoli", index=False)
        df_audit.to_excel(writer, sheet_name="Audit Trail", index=False)

    return buf.getvalue()


__all__ = ["build_daily_excel"]
