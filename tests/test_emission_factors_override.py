# -*- coding: utf-8 -*-
"""Test pytest per il modulo emission_factors_override.py.

Copre i 10 scenari richiesti dalla specifica:
  1. senza relazione tecnica caricata → no fattori reali
  2. con relazione tecnica caricata + override attivo → fattori reali
  3. senza override → valori standard
  4. valori reali si applicano SOLO alla biomassa corretta
  5. calcolo e_total usa i valori corretti
  6. crediti emissivi NON sottratti due volte
  7. warning se scostamento > ±30%
  8. CSV/Excel/PDF audit row include origine del dato
  9. report spiega formula e fonte (audit_row chiavi descrittive)
 10. valori standard NON sovrascritti permanentemente
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from emission_factors_override import (
    ALLOWED_REPORT_EXTS,
    EMISSION_DEVIATION_WARN_THRESHOLD,
    EMISSION_UNIT,
    EmissionFactorReport,
    PLAUSIBILITY_RANGES,
    SOURCE_REAL,
    SOURCE_STD,
    build_emission_factor_audit_row,
    calculate_emission_total,
    is_valid_report_filename,
    resolve_emission_factors,
    validate_real_emission_factor_override,
)


# Fixture: standard factors realistici (Liquame suino, Trinciato di mais)
STD_LIQUAME = {"eec": -45.0, "esca": 0.0, "etd": 0.8, "ep": 5.0}
STD_MAIS    = {"eec":  26.0, "esca": 0.0, "etd": 0.8, "ep": 5.0}


def _make_valid_report(name="Liquame suino",
                       eec=-40.0, esca=0.0, etd=1.0, ep=6.0,
                       extra=0.0):
    return EmissionFactorReport(
        biomass_name=name,
        eec_real=eec, esca_real=esca, etd_real=etd, ep_real=ep,
        extra_credits_real=extra,
        report_title="Studio LCA impianto Pinco",
        author_name="Ing. M. Rossi",
        company_name="Studio LCA SRL",
        report_date="2025-09-15",
        plant_reference="Impianto Verde 300 Sm3/h",
        sample_lot_ref="LOT-2025-001",
        report_filename="relazione.pdf",
        methodology_notes="Metodo RED III All. V Parte C",
        report_size_bytes=12345,
    )


# ============================================================
# 1) is_valid_report_filename
# ============================================================
class TestReportFilename:
    @pytest.mark.parametrize("name", [
        "rel.pdf", "rel.PDF", "doc.docx", "data.xlsx",
        "data.csv", "scan.jpg", "scan.JPG", "scan.jpeg",
        "img.png", "REL_OK.PdF",
    ])
    def test_valid_extensions(self, name):
        assert is_valid_report_filename(name) is True

    @pytest.mark.parametrize("name", [
        "", None, "malware.exe", "archive.zip",
        "doc_no_ext", "report.txt", "scan.tiff",
    ])
    def test_invalid_extensions(self, name):
        assert is_valid_report_filename(name) is False


# ============================================================
# 2) calculate_emission_total
# ============================================================
class TestEmissionTotal:
    def test_basic_formula(self):
        # eec=20, etd=1, ep=5, esca=2, no extra
        # e_total = 20 + 1 + 5 - 2 = 24
        assert calculate_emission_total(20, 2, 1, 5, 0) == 24.0

    def test_with_extra_credits(self):
        # eec=20, etd=1, ep=5, esca=2, extra=3
        # e_total = 20 + 1 + 5 - 2 - 3 = 21
        assert calculate_emission_total(20, 2, 1, 5, 3) == 21.0

    def test_negative_eec_manure_credit(self):
        # Manure credit gia' incorporato in eec negativo
        # eec=-45, etd=0.8, ep=5, esca=0
        # e_total = -45 + 0.8 + 5 = -39.2
        result = calculate_emission_total(-45, 0, 0.8, 5, 0)
        assert abs(result - (-39.2)) < 1e-9

    def test_no_double_counting_credits(self):
        """REQ-6: i crediti non vengono sottratti due volte.

        Se l'utente dichiara esca=10 E extra=5, vengono sottratti
        ENTRAMBI ma in slot DIVERSI (esca e' la voce normale,
        extra sono crediti AGGIUNTIVI). NON e' doppia sottrazione
        della stessa voce.
        """
        # esca=10, extra=0 → e_total - 10
        v1 = calculate_emission_total(20, 10, 0, 0, 0)
        # esca=0, extra=10 → e_total - 10
        v2 = calculate_emission_total(20, 0, 0, 0, 10)
        # esca=10, extra=10 → e_total - 20 (sono voci diverse)
        v3 = calculate_emission_total(20, 10, 0, 0, 10)
        assert v1 == v2 == 10.0
        assert v3 == 0.0  # 20 - 10 - 10

    def test_string_input_coerced(self):
        assert calculate_emission_total("10", "2", "1", "3", "0") == 12.0


# ============================================================
# 3) validate_real_emission_factor_override — REGOLE BLOCCANTI
# ============================================================
class TestValidationBlocking:
    def _kw(self, **overrides):
        base = dict(
            biomass_name="Liquame suino",
            eec_real=-40.0, esca_real=0.0, etd_real=1.0,
            ep_real=6.0, extra_credits_real=0.0,
            standard_factors=STD_LIQUAME,
            report_uploaded=True,
            report_filename="rel.pdf",
            report_title="Studio LCA",
            author_name="Ing. Rossi",
            company_name="LCA SRL",
            report_date="2025-09-15",
            plant_reference="Impianto X",
            sample_lot_ref="LOT-001",
            methodology_notes="m",
        )
        base.update(overrides)
        return base

    def test_no_report_blocks_override(self):
        """REQ-1: senza relazione tecnica caricata → override blocked."""
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(report_uploaded=False)
        )
        assert is_valid is False
        assert any("relazione tecnica" in e.lower() for e in errors)

    def test_complete_data_passes(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw()
        )
        assert is_valid is True, f"errori inattesi: {errors}"

    def test_non_numeric_eec_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(eec_real="abc")
        )
        assert is_valid is False
        assert any("non numerico" in e for e in errors)

    def test_nan_eec_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(eec_real=float("nan"))
        )
        assert is_valid is False

    def test_negative_esca_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(esca_real=-5.0)
        )
        assert is_valid is False
        assert any("esca" in e.lower() for e in errors)

    def test_negative_etd_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(etd_real=-1.0)
        )
        assert is_valid is False

    def test_negative_ep_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(ep_real=-1.0)
        )
        assert is_valid is False

    def test_negative_extra_credits_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(extra_credits_real=-3.0)
        )
        assert is_valid is False

    def test_invalid_extension_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(report_filename="malware.exe")
        )
        assert is_valid is False
        assert any("estensione" in e.lower() for e in errors)

    def test_missing_title_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(report_title="")
        )
        assert is_valid is False

    def test_missing_author_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(author_name="")
        )
        assert is_valid is False

    def test_missing_company_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(company_name="")
        )
        assert is_valid is False

    def test_missing_date_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(report_date="")
        )
        assert is_valid is False

    def test_missing_plant_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(plant_reference="")
        )
        assert is_valid is False

    def test_missing_sample_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(sample_lot_ref="")
        )
        assert is_valid is False

    def test_missing_biomass_name_blocked(self):
        is_valid, errors, _ = validate_real_emission_factor_override(
            **self._kw(biomass_name="")
        )
        assert is_valid is False
        assert any("biomassa" in e.lower() for e in errors)


# ============================================================
# 4) validate_real_emission_factor_override — WARNINGS
# ============================================================
class TestValidationWarnings:
    def _kw(self, **overrides):
        base = dict(
            biomass_name="Trinciato di mais",
            eec_real=26.0, esca_real=0.0, etd_real=0.8,
            ep_real=5.0, extra_credits_real=0.0,
            standard_factors=STD_MAIS,
            report_uploaded=True,
            report_filename="r.pdf",
            report_title="t", author_name="a",
            company_name="c", report_date="d",
            plant_reference="p", sample_lot_ref="s",
        )
        base.update(overrides)
        return base

    def test_warning_eec_above_30pct(self):
        """REQ-7: warning se scostamento > +30%."""
        # standard eec=26, real=40 → +53.8% > +30%
        _, _, warnings = validate_real_emission_factor_override(
            **self._kw(eec_real=40.0)
        )
        assert any("differisce" in w.lower() for w in warnings)
        # warning composito contiene la dicitura "30%"
        assert any("30%" in w for w in warnings)

    def test_warning_eec_below_30pct(self):
        # std eec=26, real=15 → -42% > -30%
        _, _, warnings = validate_real_emission_factor_override(
            **self._kw(eec_real=15.0)
        )
        assert any("inferiore" in w for w in warnings)

    def test_no_warning_within_threshold(self):
        # std eec=26, real=30 (~+15%): nessun warning di scostamento
        _, _, warnings = validate_real_emission_factor_override(
            **self._kw(eec_real=30.0)
        )
        # non deve esserci warning di scostamento (puo' esserci warning di range)
        deviation_w = [w for w in warnings if "differisce" in w.lower()]
        assert deviation_w == []

    def test_out_of_range_warning(self):
        """eec out of range → warning sanity-check."""
        _, _, warnings = validate_real_emission_factor_override(
            **self._kw(eec_real=500.0)  # fuori range plausible 200
        )
        # almeno un warning relativo al range
        assert any("range" in w.lower() for w in warnings)

    def test_warning_does_not_block(self):
        """Warning NON blocca la validita'."""
        is_valid, errors, warnings = validate_real_emission_factor_override(
            **self._kw(eec_real=50.0)  # dentro range, ma >+30% scost.
        )
        assert is_valid is True
        assert errors == []
        assert len(warnings) >= 1


# ============================================================
# 5) resolve_emission_factors
# ============================================================
class TestResolveFactors:
    def test_no_overrides_returns_standard(self):
        """REQ-3: senza override → valori standard."""
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0, {})
        assert res["eec_used"] == -45.0
        assert res["esca_used"] == 0.0
        assert res["etd_used"] == 0.8
        assert res["ep_used"] == 5.0
        assert res["extra_credits_used"] == 0.0
        assert res["source"] == SOURCE_STD
        assert res["override_active"] is False
        assert res["report"] is None

    def test_none_overrides_returns_standard(self):
        res = resolve_emission_factors("X", {"eec": 10}, 0.0, None)
        assert res["source"] == SOURCE_STD

    def test_inactive_override_returns_standard(self):
        report = _make_valid_report()
        overrides = {"Liquame suino": {"active": False, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        assert res["source"] == SOURCE_STD
        assert res["eec_used"] == -45.0  # standard

    def test_active_override_returns_real(self):
        """REQ-2: con override attivo + relazione → valori reali."""
        report = _make_valid_report(eec=-40.0, etd=1.0, ep=6.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        assert res["source"] == SOURCE_REAL
        assert res["eec_used"] == -40.0
        assert res["etd_used"] == 1.0
        assert res["ep_used"] == 6.0
        assert res["override_active"] is True
        assert res["report"] is report

    def test_active_override_invalid_filename_returns_standard(self):
        """Cert con estensione invalida → fallback a standard."""
        report = _make_valid_report()
        report.report_filename = "corrupt.exe"
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        assert res["source"] == SOURCE_STD

    def test_override_isolated_to_specific_biomass(self):
        """REQ-4: i valori reali si applicano SOLO alla biomassa corretta."""
        report = _make_valid_report(name="Liquame suino", eec=-40.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}

        res_a = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                           overrides)
        res_b = resolve_emission_factors("Trinciato di mais", STD_MAIS, 5.0,
                                           overrides)
        res_c = resolve_emission_factors("Pollina ovaiole",
                                           {"eec": 5, "esca": 0, "etd": 0.8},
                                           5.0, overrides)

        assert res_a["eec_used"] == -40.0
        assert res_a["source"] == SOURCE_REAL

        assert res_b["eec_used"] == 26.0  # standard mais
        assert res_b["source"] == SOURCE_STD
        assert res_b["report"] is None

        assert res_c["eec_used"] == 5.0  # standard pollina
        assert res_c["source"] == SOURCE_STD

    def test_e_total_uses_real_values(self):
        """REQ-5: e_total calcolato con i valori corretti (real se override)."""
        report = _make_valid_report(
            name="X", eec=10.0, esca=2.0, etd=1.0, ep=5.0, extra=0.0,
        )
        overrides = {"X": {"active": True, "report": report}}
        res = resolve_emission_factors("X",
                                         {"eec": 100, "esca": 0, "etd": 0, "ep": 0},
                                         50.0, overrides)
        # e_total = 10 + 1 + 5 - 2 - 0 = 14 (real values)
        assert res["e_total"] == 14.0
        # NON 100 + 0.8 + 50 = 150.8 (standard)

    def test_e_total_with_extra_credits(self):
        report = _make_valid_report(eec=20, esca=5, etd=1, ep=4, extra=3)
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        # e_total = 20 + 1 + 4 - 5 - 3 = 17
        assert res["e_total"] == 17.0


# ============================================================
# 6) build_emission_factor_audit_row
# ============================================================
class TestAuditRow:
    def test_audit_row_with_real(self):
        report = _make_valid_report(eec=-40.0, ep=6.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                         overrides)
        row = build_emission_factor_audit_row(res)
        assert row["Biomassa"] == "Liquame suino"
        assert row["Origine fattori"] == SOURCE_REAL
        assert row["eec usato"] == -40.0
        assert row["eec standard"] == -45.0
        assert row["ep usato"] == 6.0
        assert row["ep standard"] == 5.0
        assert row["Relazione tecnica"] == "relazione.pdf"
        assert row["Autore"] == "Ing. M. Rossi"
        assert row["Societa'"] == "Studio LCA SRL"
        assert row["Data relazione"] == "2025-09-15"
        assert row["Impianto rif."] == "Impianto Verde 300 Sm3/h"
        assert row["Riferimento campione"] == "LOT-2025-001"
        assert row["Note metodologiche"] == "Metodo RED III All. V Parte C"
        # scostamento eec: real=-40, std=-45 → ((-40)-(-45))/45 = +11.1%
        assert row["eec scost. %"].startswith("+")

    def test_audit_row_without_real(self):
        res = resolve_emission_factors("Trinciato di mais", STD_MAIS, 5.0, {})
        row = build_emission_factor_audit_row(res)
        assert row["Origine fattori"] == SOURCE_STD
        assert row["Relazione tecnica"] == "—"
        assert row["Autore"] == "—"
        # scostamento 0 quando real == standard
        assert row["eec scost. %"] in ("0.0%", "+0.0%", "-0.0%")

    def test_audit_row_complete_keys(self):
        """REQ-8/9: audit row contiene TUTTI i campi richiesti per export."""
        res = resolve_emission_factors("X", {"eec": 0, "esca": 0, "etd": 0}, 0.0, {})
        row = build_emission_factor_audit_row(res)
        required = {
            "Biomassa", "Origine fattori", "Unita'",
            "eec standard", "eec usato", "eec scost. %",
            "esca standard", "esca usato", "esca scost. %",
            "etd standard", "etd usato", "etd scost. %",
            "ep standard", "ep usato", "ep scost. %",
            "Crediti extra", "e_total",
            "Relazione tecnica", "Titolo relazione", "Autore",
            "Societa'", "Data relazione", "Impianto rif.",
            "Riferimento campione", "Note metodologiche",
        }
        assert required.issubset(row.keys())


# ============================================================
# 7) REQ-10: i valori standard NON vengono sovrascritti
# ============================================================
class TestStandardImmutability:
    def test_standard_factors_dict_not_mutated(self):
        """REQ-10: dict standard rimane invariato dopo resolve."""
        std = deepcopy(STD_LIQUAME)
        report = _make_valid_report(eec=999.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}

        _ = resolve_emission_factors("Liquame suino", std, 5.0, overrides)
        # Standard dict deve essere invariato
        assert std == STD_LIQUAME
        assert std["eec"] == -45.0  # NOT 999

    def test_standard_factors_carried_in_resolved(self):
        report = _make_valid_report(eec=999.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        # Il resolved dict deve contenere il riferimento agli standard
        assert res["standard_factors"]["eec"] == -45.0
        assert res["standard_factors"]["esca"] == 0.0


# ============================================================
# 8) Integrazione end-to-end (validation → resolve → audit → calc)
# ============================================================
class TestIntegration:
    def test_e2e_invalid_override_keeps_standard(self):
        """REQ-1+REQ-3: validazione blocca, calcoli usano standard."""
        is_valid, errors, _ = validate_real_emission_factor_override(
            biomass_name="Liquame suino",
            eec_real=-40.0, esca_real=0.0, etd_real=1.0,
            ep_real=6.0, extra_credits_real=0.0,
            standard_factors=STD_LIQUAME,
            report_uploaded=False,  # <-- mancante
            report_title="t", author_name="a",
            company_name="c", report_date="d",
            plant_reference="p", sample_lot_ref="s",
        )
        assert is_valid is False
        # Simula UI: nessun override salvato
        overrides = {}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        assert res["source"] == SOURCE_STD
        assert res["eec_used"] == -45.0
        # e_total con valori standard
        # = -45 + 0.8 + 5 - 0 - 0 = -39.2
        assert abs(res["e_total"] - (-39.2)) < 1e-9

    def test_e2e_valid_override_applies_to_calculations(self):
        """REQ-2+REQ-5: con relazione + override valido → calcoli reali."""
        is_valid, _, _ = validate_real_emission_factor_override(
            biomass_name="Liquame suino",
            eec_real=-40.0, esca_real=0.0, etd_real=1.0,
            ep_real=6.0, extra_credits_real=0.0,
            standard_factors=STD_LIQUAME,
            report_uploaded=True,
            report_filename="r.pdf",
            report_title="t", author_name="a",
            company_name="c", report_date="2025-09-15",
            plant_reference="p", sample_lot_ref="s",
        )
        assert is_valid is True

        report = _make_valid_report(eec=-40.0, etd=1.0, ep=6.0)
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                        overrides)
        assert res["source"] == SOURCE_REAL
        # e_total = -40 + 1 + 6 - 0 - 0 = -33
        assert res["e_total"] == -33.0

    def test_e2e_isolated_biomass_correct_e_total(self):
        """Override su A non altera e_total di B."""
        report = _make_valid_report(name="Liquame suino",
                                      eec=999.0, esca=0, etd=0, ep=0)
        overrides = {"Liquame suino": {"active": True, "report": report}}

        res_b = resolve_emission_factors("Trinciato di mais", STD_MAIS, 5.0,
                                          overrides)
        # mais resta sui valori standard
        # e_total = 26 + 0.8 + 5 - 0 - 0 = 31.8
        assert abs(res_b["e_total"] - 31.8) < 1e-9
        assert res_b["source"] == SOURCE_STD

    def test_e2e_audit_row_traces_origin(self):
        """REQ-8: audit_row identifica origine in modo univoco per export."""
        # Caso reale
        report = _make_valid_report()
        overrides = {"Liquame suino": {"active": True, "report": report}}
        res_real = resolve_emission_factors("Liquame suino", STD_LIQUAME, 5.0,
                                              overrides)
        row_real = build_emission_factor_audit_row(res_real)
        assert "Relazione tecnica" in row_real["Origine fattori"]

        # Caso standard
        res_std = resolve_emission_factors("Trinciato di mais", STD_MAIS, 5.0,
                                             overrides)
        row_std = build_emission_factor_audit_row(res_std)
        assert "standard" in row_std["Origine fattori"].lower() or \
               "default" in row_std["Origine fattori"].lower()
        assert row_real["Origine fattori"] != row_std["Origine fattori"]


# ============================================================
# 9) Costanti pubbliche
# ============================================================
class TestPublicConstants:
    def test_threshold_is_30pct(self):
        assert EMISSION_DEVIATION_WARN_THRESHOLD == 0.30

    def test_unit_is_gco2eq_mj(self):
        assert "gCO2eq" in EMISSION_UNIT.replace(" ", "")
        assert "MJ" in EMISSION_UNIT

    def test_allowed_extensions_complete(self):
        # tutti i formati richiesti dalla spec
        for ext in (".pdf", ".docx", ".xlsx", ".csv", ".jpg", ".png"):
            assert ext in ALLOWED_REPORT_EXTS

    def test_source_labels_distinct(self):
        assert SOURCE_REAL != SOURCE_STD
        assert "Relazione" in SOURCE_REAL
        assert "standard" in SOURCE_STD.lower()

    def test_plausibility_ranges_complete(self):
        for k in ("eec", "esca", "etd", "ep", "crediti_extra"):
            assert k in PLAUSIBILITY_RANGES
            lo, hi = PLAUSIBILITY_RANGES[k]
            assert lo < hi
