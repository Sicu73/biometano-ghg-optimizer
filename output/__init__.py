# -*- coding: utf-8 -*-
"""output/ — Costruttori di output strutturato per Metan.iQ.

Moduli:
  output_builder   — build_output_model(ctx) -> output_model dict
  tables           — funzioni per costruire DataFrame dalle tabelle output
  explanations     — testi spiegativi origine dati e metodo di calcolo
"""
from .output_builder import build_output_model  # noqa: F401
from .tables import (  # noqa: F401
    build_monthly_table,
    build_feedstock_table,
    build_ghg_table,
    build_business_plan_table,
    build_audit_table,
)
from .explanations import (  # noqa: F401
    explain_yield_origin,
    explain_emission_factor_origin,
    explain_ghg_method,
    explain_regulatory_basis,
    build_all_explanations,
)
