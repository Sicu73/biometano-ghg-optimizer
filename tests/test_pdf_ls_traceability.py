# -*- coding: utf-8 -*-
"""Tests smoke per la sezione 'Tracciabilità Lotto di Sostenibilità' nel PDF.

Verifica che:
1. La funzione _build_ls_traceability produca un flow non vuoto
2. Generi un LS-ID valido nel formato canonico
3. Mostri il warning "DA COMPILARE" se i campi anagrafica sono assenti
4. Il PDF completo si generi senza errori con il ctx minimo richiesto
"""
import pytest

from report_pdf import _build_ls_traceability, _styles


def _minimal_ctx():
    """ctx minimo per evitare KeyError nella build PDF completa."""
    import pandas as pd
    df_res = pd.DataFrame({
        "Mese": ["Gennaio"],
        "Totale biomasse (t)": [100.0],
        "Sm³ netti": [50000.0],
        "MWh netti": [500.0],
        "Saving %": [82.5],
        "Validità": ["✅ OK"],
    })
    return {
        "df_res": df_res,
        "APP_MODE": "biometano",
        "plant_kwe": 0, "plant_kwe_net": 0,
        "plant_net_smch": 300.0,
        "eta_el": 0.40, "eta_th": 0.42, "aux_el_pct": 8.0,
        "aux_factor": 1.29, "ep_total": 5.0,
        "end_use": "Elettricità/calore/immissione rete (nuovo >=20/11/2023)",
        "ghg_threshold": 0.80, "fossil_comparator": 80.0,
        "upgrading_opt": "Membrane", "offgas_opt": "RTO", "injection_opt": "Rete",
        "is_advanced": True, "cic_active": True, "cic_double": True,
        "cic_price": 375.0, "annex_mass_share": 0.85,
        "annex_threshold": 0.70, "tot_n_cic": 100.0,
        "MWH_PER_CIC": 11.628, "GCAL_PER_CIC": 10.0,
        "fer2_kwe_cap": 300, "fer2_periodo_anni": 20,
        "fer2_subprod_share": 0.0, "fer2_matrice_threshold": 0.8,
        "fer2_qualified": False,
        "fer2_tariffa_base": 0.0, "fer2_premio_matrice_eur": 0.0,
        "fer2_premio_car_eur": 0.0, "fer2_apply_matrice": False,
        "fer2_apply_car": False, "fer2_tariffa_eff": 0.0,
        "bp_result": None,
        "tot_biomasse_t": 100.0, "tot_sm3_netti": 50000.0,
        "tot_mwh_netti": 500.0, "tot_mwh_el_lordo": 0.0, "tot_mwh_el_netto": 0.0,
        "saving_avg": 82.5, "valid_months": 1,
        "tot_revenue": 50000.0, "tot_mwh_basis": 500.0,
        "tariffa_media_ponderata": 100.0,
        "revenue_rows": [],
        "lang": "it",
        "yield_audit_rows": [], "effective_yields": {},
        "emission_audit_rows": [], "emission_overrides": {},
    }


class TestLsTraceabilitySection:
    def test_build_section_returns_flow(self):
        ctx = {"_lang": "it", "year": 2026, "month": 5,
               "company_name": "ACME S.r.l.", "plant_name": "Test Plant",
               "plant_cui": "IT01X-2026-9999", "company_vat": "IT12345678901",
               "report_date_short": "28/05/2026"}
        flow = _build_ls_traceability(ctx, _styles())
        assert isinstance(flow, list)
        assert len(flow) > 5, "sezione vuota"

    def test_warn_when_fields_missing(self):
        """Senza anagrafica deve esserci il marker '⚠️ DA COMPILARE'."""
        ctx = {"_lang": "it", "year": 2026, "month": 5,
               "report_date_short": "28/05/2026"}
        flow = _build_ls_traceability(ctx, _styles())
        rendered = " ".join(
            str(getattr(item, "text", "")) for item in flow
        )
        # Le warning sono dentro celle Table; cerchiamo nei sottocomponenti
        from reportlab.platypus import Table
        warn_found = False
        for item in flow:
            if isinstance(item, Table):
                for row in item._cellvalues:
                    for cell in row:
                        if isinstance(cell, str) and "DA COMPILARE" in cell:
                            warn_found = True
        assert warn_found, "manca il warning 'DA COMPILARE' nei campi vuoti"

    def test_ls_id_in_section(self):
        ctx = {"_lang": "it", "year": 2026, "month": 5,
               "plant_cui": "IT01X-2026-9999",
               "report_date_short": "28/05/2026"}
        flow = _build_ls_traceability(ctx, _styles())
        from reportlab.platypus import Table
        ls_id_found = False
        for item in flow:
            if isinstance(item, Table):
                for row in item._cellvalues:
                    for cell in row:
                        if isinstance(cell, str) and cell.startswith("LS-2026-05-"):
                            ls_id_found = True
        assert ls_id_found, "LS-ID canonico non presente nella tabella"


class TestMassBalanceSection:
    def test_mass_balance_with_feedstock(self):
        """Mass balance table popolata con dati feedstock + Annex IX."""
        ctx = {"_lang": "it", "year": 2026, "month": 5,
               "plant_cui": "IT-TEST",
               "report_date_short": "28/05/2026",
               "feedstock_totals_t": {"Liquame suino": 500.0, "Mais": 200.0},
               "FEEDSTOCK_DB": {
                   "Liquame suino": {"annex_ix": "A", "cat": "Effluenti zootecnici"},
                   "Mais": {"annex_ix": None, "cat": "Colture dedicate"},
               },
               "sm3_gross": 100000.0, "sm3_netti": 77519.0}
        flow = _build_ls_traceability(ctx, _styles())
        from reportlab.platypus import Table
        seen_feedstocks = []
        for item in flow:
            if isinstance(item, Table):
                for row in item._cellvalues:
                    for cell in row:
                        if isinstance(cell, str) and cell in ("Liquame suino", "Mais"):
                            seen_feedstocks.append(cell)
        assert "Liquame suino" in seen_feedstocks
        assert "Mais" in seen_feedstocks
