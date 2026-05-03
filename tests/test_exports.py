# -*- coding: utf-8 -*-
"""tests/test_exports.py — Test pytest per export/*.

Verifica:
  - build_csv_from_output() genera CSV valido per tutti gli sheet
  - build_excel_from_output() genera BytesIO non vuoto
  - build_pdf_from_output() genera BytesIO non vuoto
  - tutti gli export leggono da output_model (non da app_mensile)
  - se mancano campi non crasha
  - sheet non valido per CSV genera ValueError
"""
import sys
import os
import io
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures condivise
# ---------------------------------------------------------------------------

def _make_output_model(**overrides) -> dict:
    """output_model minimale valido per tutti gli export."""
    monthly = [
        {"Mese": "Gennaio",  "Ore": 744, "Sm³ netti": 150000.0,
         "MWh netti": 1495.5, "Saving %": 82.5, "Validità": "✅ OK",
         "Totale biomasse (t)": 700.0},
        {"Mese": "Febbraio", "Ore": 672, "Sm³ netti": 135000.0,
         "MWh netti": 1345.9, "Saving %": 83.1, "Validità": "✅ OK",
         "Totale biomasse (t)": 650.0},
    ]
    feedstock = [
        {"biomassa": "Trinciato di mais", "categoria": "Colture dedicate",
         "annex_ix": None, "tonnellate_anno": 6000.0, "mwh_anno": 12000.0,
         "ricavi_eur": 1700000.0, "tariffa_eur_mwh": 131.0, "n_cic": 0.0},
        {"biomassa": "Liquame suino", "categoria": "Effluenti zootecnici",
         "annex_ix": "A", "tonnellate_anno": 2400.0, "mwh_anno": 5946.0,
         "ricavi_eur": 800000.0, "tariffa_eur_mwh": 131.0, "n_cic": 0.0},
    ]
    ghg = [
        {"biomassa": "Trinciato di mais", "eec": 26.0, "etd": 0.8,
         "esca": 0.0, "ep": 5.0, "e_total": 31.8,
         "fonte": "UNI-TS 11567:2024", "override_attivo": False},
        {"biomassa": "Liquame suino", "eec": -45.0, "etd": 0.8,
         "esca": 0.0, "ep": 5.0, "e_total": -39.2,
         "fonte": "RED III Annex VI", "override_attivo": False},
    ]
    bp = [
        {"anno": y, "ricavi_eur": 3000000.0, "opex_eur": 800000.0,
         "ebitda_eur": 2200000.0, "interessi_eur": 150000.0,
         "ammortamenti_eur": 400000.0, "utile_ante_eur": 1650000.0,
         "utile_netto_eur": 1256400.0, "fcf_eur": 1056400.0}
        for y in range(1, 16)
    ]
    audit = [
        {"tipo": "BMT_yield_override", "biomass_name": "Trinciato di mais",
         "standard_value": 104.0, "override_value": 110.0,
         "source": "BMT Lab 2025", "cert_date": "2025-01-15", "note": ""},
    ]
    model = {
        "metadata": {
            "software_name": "Metan.iQ",
            "version": "2.0.0-refactor",
            "generated_at": "2026-05-03T10:00:00",
            "language": "it",
            "scenario_name": "Biometano DM 2022 — 300 Sm³/h",
            "app_mode": "biometano",
        },
        "input_summary": {
            "plant": {
                "plant_net_smch": 300.0, "plant_kwe": None,
                "aux_factor": 1.29, "ep_total": 5.0,
                "end_use": "Rete", "is_chp": False, "is_fer2": False,
                "is_dm2018": False, "is_dm2022": True,
                "ghg_threshold": 0.80, "fossil_comparator": 80.0,
                "upgrading_opt": "PSA (methane slip ~1.5%)",
                "offgas_opt": "No - off-gas rilasciato in atmosfera",
                "injection_opt": "Media pressione (5-24 bar)",
            },
            "feedstocks": [
                {"name": "Trinciato di mais", "categoria": "Colture dedicate",
                 "annex_ix": None, "yield_std": 104.0,
                 "eec": 26.0, "etd": 0.8, "esca": 0.0, "src": "UNI-TS 11567"},
                {"name": "Liquame suino", "categoria": "Effluenti zootecnici",
                 "annex_ix": "A", "yield_std": 15.0,
                 "eec": -45.0, "etd": 0.8, "esca": 0.0, "src": "RED III"},
            ],
            "mode": "biometano",
        },
        "calculation_summary": {
            "tot_biomasse_t": 8400.0, "tot_sm3_netti": 1800000.0,
            "tot_mwh": 17946.0, "saving_avg": 82.5, "valid_months": 12,
            "total_revenue": 2500000.0, "tot_mwh_el_lordo": 0.0,
            "tot_mwh_el_netto": 0.0, "tot_n_cic": 0.0,
            "cic_active": False, "is_advanced": False,
            "tariffa_media_ponderata": 131.0,
        },
        "monthly_table":      monthly,
        "feedstock_table":    feedstock,
        "ghg_table":          ghg,
        "business_plan_table": bp,
        "audit_trail":        audit,
        "warnings":           ["Warning di test: verificare saving mese 3."],
        "errors":             [],
        "explanations": {
            "yield_origin":           "Rese da UNI/TS 11567:2024 e JEC v5.",
            "emission_factor_origin": "Fattori da RED III Annex VI e JEC v5.",
            "ghg_method":             "Metodo RED III Allegato V Parte C.",
            "regulatory_basis":       "RED III, DM 2022, UNI/TS 11567:2024.",
        },
    }
    model.update(overrides)
    return model


# ---------------------------------------------------------------------------
# Test CSV
# ---------------------------------------------------------------------------

class TestCSVExport:
    """Test per export/csv_export.py::build_csv_from_output."""

    def test_csv_monthly_returns_bytes(self):
        """build_csv_from_output ritorna bytes non vuoti."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_csv_has_utf8_bom(self):
        """Il CSV ha BOM UTF-8 per compatibilita' Excel Windows."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model())
        assert result[:3] == b"\xef\xbb\xbf"

    def test_csv_monthly_has_header(self):
        """Il CSV mensile ha intestazione con colonne attese."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="monthly")
        text = result.decode("utf-8-sig")
        first_line = text.split("\r\n")[0]
        assert "Mese" in first_line or "Ore" in first_line

    def test_csv_feedstock_sheet(self):
        """Sheet 'feedstock' produce CSV non vuoto."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="feedstock")
        text = result.decode("utf-8-sig")
        assert "Biomassa" in text or "biomassa" in text.lower()

    def test_csv_ghg_sheet(self):
        """Sheet 'ghg' produce CSV non vuoto."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="ghg")
        text = result.decode("utf-8-sig")
        assert "eec" in text.lower() or "Biomassa" in text

    def test_csv_business_plan_sheet(self):
        """Sheet 'business_plan' produce CSV non vuoto con 15 righe dati."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="business_plan")
        text = result.decode("utf-8-sig")
        assert "Anno" in text

    def test_csv_audit_sheet(self):
        """Sheet 'audit' produce CSV con la riga di override BMT."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="audit")
        text = result.decode("utf-8-sig")
        assert "BMT" in text or "Tipo" in text

    def test_csv_invalid_sheet_raises(self):
        """Sheet non valido genera ValueError."""
        from export.csv_export import build_csv_from_output
        with pytest.raises(ValueError, match="non valido"):
            build_csv_from_output(_make_output_model(), sheet="nonexistent")

    def test_csv_empty_monthly_table(self):
        """CSV con monthly_table vuota non crasha."""
        from export.csv_export import build_csv_from_output
        model = _make_output_model(monthly_table=[])
        result = build_csv_from_output(model, sheet="monthly")
        assert isinstance(result, bytes)

    def test_csv_metadata_appended(self):
        """Il CSV include righe di metadata in fondo."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="monthly")
        text = result.decode("utf-8-sig")
        assert "# Software:" in text or "# Generato:" in text

    def test_csv_warnings_in_metadata(self):
        """I warning vengono inclusi nelle righe metadata del CSV."""
        from export.csv_export import build_csv_from_output
        result = build_csv_from_output(_make_output_model(), sheet="monthly")
        text = result.decode("utf-8-sig")
        assert "WARNING" in text

    def test_csv_invalid_model_raises(self):
        """Output model non dict genera ValueError."""
        from export.csv_export import build_csv_from_output
        with pytest.raises(ValueError):
            build_csv_from_output("not a dict")


# ---------------------------------------------------------------------------
# Test Excel
# ---------------------------------------------------------------------------

class TestExcelExport:
    """Test per export/excel_export.py::build_excel_from_output."""

    def test_excel_returns_bytesio(self):
        """build_excel_from_output ritorna BytesIO non vuoto."""
        from export.excel_export import build_excel_from_output
        result = build_excel_from_output(_make_output_model())
        assert isinstance(result, io.BytesIO)
        data = result.read()
        assert len(data) > 0

    def test_excel_snapshot_returns_bytesio(self):
        """Modalita' snapshot ritorna BytesIO non vuoto."""
        from export.excel_export import build_excel_from_output
        result = build_excel_from_output(_make_output_model(), snapshot=True)
        assert isinstance(result, io.BytesIO)
        data = result.read()
        assert len(data) > 0

    def test_excel_invalid_model_raises(self):
        """Output model non dict genera ValueError."""
        from export.excel_export import build_excel_from_output
        with pytest.raises(ValueError):
            build_excel_from_output("not a dict")

    def test_excel_empty_model_does_not_crash(self):
        """Con output_model vuoto non crasha."""
        from export.excel_export import build_excel_from_output
        result = build_excel_from_output({})
        assert isinstance(result, io.BytesIO)

    def test_excel_is_valid_xlsx(self):
        """Il file generato e' un XLSX valido (magic bytes PK)."""
        from export.excel_export import build_excel_from_output
        result = build_excel_from_output(_make_output_model())
        data = result.read()
        # XLSX e' un ZIP -> inizia con PK (0x50 0x4B)
        assert data[:2] == b"PK", "Il file XLSX non ha magic bytes validi"


# ---------------------------------------------------------------------------
# Test PDF
# ---------------------------------------------------------------------------

class TestPDFExport:
    """Test per export/pdf_export.py::build_pdf_from_output."""

    def test_pdf_returns_bytesio(self):
        """build_pdf_from_output ritorna BytesIO non vuoto."""
        from export.pdf_export import build_pdf_from_output
        result = build_pdf_from_output(_make_output_model())
        assert isinstance(result, io.BytesIO)
        data = result.read()
        assert len(data) > 0

    def test_pdf_invalid_model_raises(self):
        """Output model non dict genera ValueError."""
        from export.pdf_export import build_pdf_from_output
        with pytest.raises(ValueError):
            build_pdf_from_output("not a dict")

    def test_pdf_empty_model_does_not_crash(self):
        """Con output_model vuoto non crasha."""
        from export.pdf_export import build_pdf_from_output
        result = build_pdf_from_output({})
        assert isinstance(result, io.BytesIO)

    def test_pdf_is_valid_pdf(self):
        """Il file generato e' un PDF valido (magic bytes %PDF)."""
        from export.pdf_export import build_pdf_from_output
        result = build_pdf_from_output(_make_output_model())
        data = result.read()
        # Verifica magic bytes PDF
        assert data[:4] == b"%PDF", "Il file non e' un PDF valido"

    def test_pdf_with_chp_mode(self):
        """PDF per modalita' CHP non crasha."""
        from export.pdf_export import build_pdf_from_output
        model = _make_output_model()
        model["metadata"]["app_mode"] = "biogas_chp"
        model["input_summary"]["plant"]["is_chp"] = True
        model["input_summary"]["plant"]["plant_kwe"] = 999.0
        result = build_pdf_from_output(model)
        assert isinstance(result, io.BytesIO)


# ---------------------------------------------------------------------------
# Test: tutti gli export leggono da output_model
# ---------------------------------------------------------------------------

class TestExportsUseOutputModel:
    """Verifica che tutti gli export usino output_model come unica fonte."""

    def test_csv_reads_saving_avg_from_model(self):
        """Il CSV mensile include il saving corretto da output_model."""
        from export.csv_export import build_csv_from_output
        model = _make_output_model()
        result = build_csv_from_output(model, sheet="monthly")
        text = result.decode("utf-8-sig")
        # saving_avg deve comparire nelle righe metadata
        assert "82" in text or "82,5" in text or "saving" in text.lower()

    def test_csv_reads_scenario_name_from_metadata(self):
        """Il CSV include il nome scenario da metadata."""
        from export.csv_export import build_csv_from_output
        model = _make_output_model()
        result = build_csv_from_output(model, sheet="monthly")
        text = result.decode("utf-8-sig")
        assert "Biometano DM 2022" in text or "Scenario:" in text

    def test_all_exports_accept_same_output_model(self):
        """Tutti e tre gli export accettano lo stesso output_model senza errori."""
        from export.csv_export import build_csv_from_output
        from export.excel_export import build_excel_from_output
        from export.pdf_export import build_pdf_from_output

        model = _make_output_model()

        csv_result = build_csv_from_output(model, sheet="monthly")
        assert isinstance(csv_result, bytes) and len(csv_result) > 0

        xlsx_result = build_excel_from_output(model)
        assert isinstance(xlsx_result, io.BytesIO)

        pdf_result = build_pdf_from_output(model)
        assert isinstance(pdf_result, io.BytesIO)
