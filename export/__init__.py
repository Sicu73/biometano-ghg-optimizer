# -*- coding: utf-8 -*-
"""export/ — Moduli di esportazione dati per Metan.iQ.

Moduli:
  csv_export    — build_csv_from_output(output_model) -> bytes
  excel_export  — build_excel_from_output(output_model) -> BytesIO
  pdf_export    — build_pdf_from_output(output_model) -> BytesIO

Tutti i moduli leggono esclusivamente dall'output_model (dict strutturato
prodotto da output/output_builder.py). Non accedono direttamente a
app_mensile.py ne' a Streamlit session_state.
"""
from .csv_export import build_csv_from_output  # noqa: F401
from .excel_export import build_excel_from_output  # noqa: F401
from .pdf_export import build_pdf_from_output  # noqa: F401
