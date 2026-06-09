# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""export/ — Moduli di esportazione dati per Metan.iQ.

Moduli:
  csv_export        — build_csv_from_output(output_model) -> bytes
  daily_csv         — CSV piano giornaliero
  daily_excel       — Excel mensile multi-foglio
  daily_pdf         — Report PDF mensile brand
  business_plan_pdf — PDF Business Plan 15 anni
  pptx_export       — Presentazione PPTX

I moduli model-based leggono esclusivamente dall'output_model (dict
strutturato prodotto da output/output_builder.py). Non accedono
direttamente a app_mensile.py ne' a Streamlit session_state.
"""
from .csv_export import build_csv_from_output  # noqa: F401
