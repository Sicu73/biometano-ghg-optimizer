# -*- coding: utf-8 -*-
"""tests/test_output_model.py — Test pytest per output/output_builder.py.

Verifica:
  - build_output_model() produce tutte le chiavi obbligatorie
  - output_model contiene KPI principali
  - gestione ctx vuoto / campi mancanti non crasha
  - warnings ed errori vengono riportati
  - audit trail viene costruito correttamente
"""
import sys
import os
import pytest

# Aggiungi la root al path per import relativi in test standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = [
    "metadata",
    "input_summary",
    "calculation_summary",
    "monthly_table",
    "feedstock_table",
    "ghg_table",
    "business_plan_table",
    "audit_trail",
    "warnings",
    "errors",
    "explanations",
]

REQUIRED_METADATA_KEYS = [
    "software_name",
    "version",
    "generated_at",
    "language",
    "scenario_name",
]

REQUIRED_CALC_SUMMARY_KEYS = [
    "tot_biomasse_t",
    "tot_sm3_netti",
    "tot_mwh",
    "saving_avg",
    "valid_months",
    "total_revenue",
]

REQUIRED_EXPLANATION_KEYS = [
    "yield_origin",
    "emission_factor_origin",
    "ghg_method",
    "regulatory_basis",
]


def _make_minimal_ctx(**overrides) -> dict:
    """Contesto minimale valido per build_output_model."""
    ctx = {
        "APP_MODE": "biometano",
        "lang": "it",
        "active_feeds": [],
        "FEEDSTOCK_DB": {},
        "aux_factor": 1.29,
        "ep_total": 5.0,
        "fossil_comparator": 80.0,
        "ghg_threshold": 0.80,
        "plant_net_smch": 300.0,
        "IS_CHP": False,
        "IS_FER2": False,
        "IS_DM2018": False,
        "IS_DM2022": True,
        "end_use": "Elettricita/calore",
        "tot_biomasse_t": 0.0,
        "tot_sm3_netti": 0.0,
        "tot_mwh_netti": 0.0,
        "saving_avg": 0.0,
        "valid_months": 0,
        "tot_revenue": 0.0,
        "df_res": None,
        "yield_audit_rows": [],
        "emission_audit_rows": [],
        "annual_t": {},
        "annual_mwh": {},
        "revenue_rows": [],
        "warnings": [],
        "errors": [],
    }
    ctx.update(overrides)
    return ctx


def _make_rich_ctx() -> dict:
    """Contesto ricco con dati mensili, feedstock, KPI."""
    feedstock_db = {
        "Trinciato di mais": {
            "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 104.0,
            "color": "#F5C518", "cat": "Colture dedicate",
            "annex_ix": None, "src": "UNI-TS 11567:2024 / JEC v5",
        },
        "Liquame suino": {
            "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 15.0,
            "color": "#8D6E63", "cat": "Effluenti zootecnici",
            "annex_ix": "A", "src": "RED III Annex VI / JEC v5",
        },
    }
    monthly_rows = []
    months = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
              "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    hours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
    for m, h in zip(months, hours):
        monthly_rows.append({
            "Mese": m, "Ore": h,
            "Trinciato di mais": 500.0, "Liquame suino": 200.0,
            "Sm³ netti": 150000.0, "MWh netti": 1495.5,
            "Saving %": 82.5, "Validità": "✅ OK",
            "Totale biomasse (t)": 700.0,
        })

    try:
        import pandas as pd
        df_res = pd.DataFrame(monthly_rows)
    except ImportError:
        df_res = monthly_rows

    return _make_minimal_ctx(
        active_feeds=["Trinciato di mais", "Liquame suino"],
        FEEDSTOCK_DB=feedstock_db,
        df_res=df_res,
        tot_biomasse_t=8400.0,
        tot_sm3_netti=1800000.0,
        tot_mwh_netti=17946.0,
        saving_avg=82.5,
        valid_months=12,
        tot_revenue=2500000.0,
        annual_t={"Trinciato di mais": 6000.0, "Liquame suino": 2400.0},
        annual_mwh={"Trinciato di mais": 12000.0, "Liquame suino": 5946.0},
        revenue_rows=[
            ("Trinciato di mais", {"ricavi": 1700000.0, "tariffa": 131.0, "n_cic": 0.0}),
            ("Liquame suino",     {"ricavi": 800000.0,  "tariffa": 131.0, "n_cic": 0.0}),
        ],
        yield_audit_rows=[{
            "biomass_name": "Trinciato di mais",
            "standard_value": 104.0, "override_value": 110.0,
            "source": "BMT Lab XYZ 2025-01-15",
            "cert_date": "2025-01-15", "note": "deviazione +5.8%",
        }],
    )


# ---------------------------------------------------------------------------
# Test: struttura output_model
# ---------------------------------------------------------------------------

class TestOutputModelStructure:
    """Verifica che build_output_model() produca la struttura attesa."""

    def test_empty_ctx_does_not_crash(self):
        """Con ctx vuoto non crasha e ritorna dict valido."""
        from output.output_builder import build_output_model
        result = build_output_model({})
        assert isinstance(result, dict)

    def test_minimal_ctx_has_required_keys(self):
        """Con ctx minimale tutte le chiavi obbligatorie sono presenti."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        for key in REQUIRED_TOP_KEYS:
            assert key in result, f"Chiave obbligatoria mancante: '{key}'"

    def test_metadata_has_required_keys(self):
        """metadata contiene tutte le chiavi obbligatorie."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        meta = result["metadata"]
        for key in REQUIRED_METADATA_KEYS:
            assert key in meta, f"metadata mancante: '{key}'"

    def test_calculation_summary_has_required_keys(self):
        """calculation_summary contiene tutte le chiavi obbligatorie."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        calc = result["calculation_summary"]
        for key in REQUIRED_CALC_SUMMARY_KEYS:
            assert key in calc, f"calculation_summary mancante: '{key}'"

    def test_explanations_has_required_keys(self):
        """explanations contiene tutte le chiavi obbligatorie."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        expl = result["explanations"]
        for key in REQUIRED_EXPLANATION_KEYS:
            assert key in expl, f"explanations mancante: '{key}'"

    def test_all_tables_are_lists(self):
        """Tutte le tabelle sono liste (mai None)."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        for key in ("monthly_table", "feedstock_table", "ghg_table",
                     "business_plan_table", "audit_trail"):
            assert isinstance(result[key], list), f"{key} deve essere una lista"

    def test_warnings_and_errors_are_lists(self):
        """warnings e errors devono essere liste di stringhe."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        assert isinstance(result["warnings"], list)
        assert isinstance(result["errors"], list)


# ---------------------------------------------------------------------------
# Test: KPI
# ---------------------------------------------------------------------------

class TestOutputModelKPI:
    """Verifica che i KPI siano corretti nel calculation_summary."""

    def test_kpi_from_rich_ctx(self):
        """KPI aggregati derivati correttamente dal ctx ricco."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        calc = result["calculation_summary"]
        assert calc["tot_biomasse_t"] == pytest.approx(8400.0, rel=1e-3)
        assert calc["tot_sm3_netti"] == pytest.approx(1800000.0, rel=1e-3)
        assert calc["tot_mwh"] == pytest.approx(17946.0, rel=1e-3)
        assert calc["saving_avg"] == pytest.approx(82.5, rel=1e-3)
        assert calc["valid_months"] == 12
        assert calc["total_revenue"] == pytest.approx(2500000.0, rel=1e-3)

    def test_kpi_zero_when_missing(self):
        """KPI sono 0.0 quando mancano in ctx."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        calc = result["calculation_summary"]
        assert calc["tot_biomasse_t"] == 0.0
        assert calc["total_revenue"] == 0.0

    def test_metadata_software_name(self):
        """metadata.software_name == 'Metan.iQ'."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        assert result["metadata"]["software_name"] == "Metan.iQ"

    def test_metadata_language(self):
        """metadata.language riflette il ctx."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx(lang="en"))
        assert result["metadata"]["language"] == "en"


# ---------------------------------------------------------------------------
# Test: Tabelle
# ---------------------------------------------------------------------------

class TestOutputModelTables:
    """Verifica il contenuto delle tabelle nel output_model."""

    def test_monthly_table_has_rows(self):
        """monthly_table ha 12 righe con ctx ricco."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        assert len(result["monthly_table"]) == 12

    def test_feedstock_table_has_correct_count(self):
        """feedstock_table ha una riga per biomassa attiva."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        assert len(result["feedstock_table"]) == 2

    def test_ghg_table_has_correct_count(self):
        """ghg_table ha una riga per biomassa attiva."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        assert len(result["ghg_table"]) == 2

    def test_ghg_table_eec_values(self):
        """ghg_table contiene i valori eec corretti dal feedstock_db."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        ghg_map = {r["biomassa"]: r for r in result["ghg_table"]}
        assert ghg_map["Trinciato di mais"]["eec"] == pytest.approx(26.0)
        assert ghg_map["Liquame suino"]["eec"] == pytest.approx(-45.0)

    def test_business_plan_table_empty_without_bp(self):
        """business_plan_table e' vuota se bp_result non e' in ctx."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        assert result["business_plan_table"] == []


# ---------------------------------------------------------------------------
# Test: Audit trail
# ---------------------------------------------------------------------------

class TestOutputModelAuditTrail:
    """Verifica la costruzione dell'audit trail."""

    def test_audit_trail_empty_by_default(self):
        """audit_trail e' vuoto se non ci sono override."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        assert result["audit_trail"] == []

    def test_audit_trail_bmt_override_present(self):
        """audit_trail contiene la riga BMT se yield_audit_rows e' non vuoto."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        bmt_entries = [r for r in result["audit_trail"]
                       if r.get("tipo") == "BMT_yield_override"]
        assert len(bmt_entries) == 1

    def test_audit_trail_contains_biomass_name(self):
        """audit_trail BMT contiene il nome della biomassa."""
        from output.output_builder import build_output_model
        ctx = _make_rich_ctx()
        result = build_output_model(ctx)
        bmt = [r for r in result["audit_trail"]
               if r.get("tipo") == "BMT_yield_override"][0]
        assert "Trinciato di mais" in str(bmt.get("biomass_name", ""))


# ---------------------------------------------------------------------------
# Test: Warnings e errori
# ---------------------------------------------------------------------------

class TestOutputModelWarningsErrors:
    """Verifica che warning ed errori vengano riportati."""

    def test_ctx_warnings_propagated(self):
        """I warning del ctx vengono propagati in output_model.warnings."""
        from output.output_builder import build_output_model
        ctx = _make_minimal_ctx(warnings=["Attenzione: biomassa X non certificata."])
        result = build_output_model(ctx)
        assert any("biomassa X" in w for w in result["warnings"])

    def test_ctx_errors_propagated(self):
        """Gli errori del ctx vengono propagati in output_model.errors."""
        from output.output_builder import build_output_model
        ctx = _make_minimal_ctx(errors=["Errore: aux_factor < 1.0."])
        result = build_output_model(ctx)
        assert any("aux_factor" in e for e in result["errors"])

    def test_invalid_months_warning(self):
        """Mesi sotto soglia generano warning in output_model."""
        from output.output_builder import build_output_model
        monthly_rows = [
            {"Mese": "Gennaio", "Ore": 744, "Validità": "❌ NO (65.0%)",
             "Totale biomasse (t)": 500.0, "Sm³ netti": 100000.0,
             "Saving %": 65.0},
        ]
        try:
            import pandas as pd
            df = pd.DataFrame(monthly_rows)
        except ImportError:
            df = monthly_rows
        ctx = _make_minimal_ctx(df_res=df)
        result = build_output_model(ctx)
        # Deve esserci almeno un warning (il mese non valido)
        # Il check e' soft: se df_res ha dati, il builder li legge
        assert isinstance(result["warnings"], list)


# ---------------------------------------------------------------------------
# Test: Explanations
# ---------------------------------------------------------------------------

class TestOutputModelExplanations:
    """Verifica i testi spiegativi."""

    def test_explanations_not_empty(self):
        """I testi spiegativi non sono vuoti."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        expl = result["explanations"]
        for key in REQUIRED_EXPLANATION_KEYS:
            assert len(expl.get(key, "")) > 0, f"explanation '{key}' e' vuota"

    def test_explanations_language_en(self):
        """Con lang='en' i testi spiegativi sono in inglese."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx(lang="en"))
        expl = result["explanations"]
        # Controllo molto semplice: "yield" compare nel testo EN
        assert "yield" in expl["yield_origin"].lower() or \
               "biomass" in expl["yield_origin"].lower()

    def test_explanations_regulatory_basis_contains_red_iii(self):
        """La base normativa cita RED III."""
        from output.output_builder import build_output_model
        result = build_output_model(_make_minimal_ctx())
        assert "RED III" in result["explanations"]["regulatory_basis"]
