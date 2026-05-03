# -*- coding: utf-8 -*-
"""export/daily_csv.py — Esportazione CSV giornaliero."""
from __future__ import annotations

import io

import pandas as pd


def build_daily_csv(daily_df: pd.DataFrame, sep: str = ";",
                    decimal: str = ",") -> bytes:
    """Serializza il DataFrame giornaliero in CSV (bytes UTF-8 BOM)."""
    buf = io.StringIO()
    df = daily_df.copy()
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")
    df.to_csv(buf, sep=sep, decimal=decimal, index=False)
    return ("﻿" + buf.getvalue()).encode("utf-8")


__all__ = ["build_daily_csv"]
