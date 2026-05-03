# -*- coding: utf-8 -*-
"""Test pytest per il modulo bmt_override.py."""
from __future__ import annotations

import sys
from pathlib import Path

# Permette di importare bmt_override dal repo root anche se i test sono lanciati
# da una directory diversa.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from bmt_override import (
    ALLOWED_CERT_EXTS,
    BMT_DEVIATION_WARN_THRESHOLD,
    BMTCertificate,
    SOURCE_BMT,
    SOURCE_STD,
    YIELD_UNIT,
    build_yield_audit_row,
    is_valid_certificate_filename,
    resolve_biomass_yield,
    validate_bmt_override,
)


# ============================================================
# is_valid_certificate_filename
# ============================================================
class TestCertificateFilename:
    @pytest.mark.parametrize("name", [
        "cert.pdf", "cert.PDF", "scan.jpg", "scan.JPG", "img.png",
        "data.xlsx", "data.csv", "scan.jpeg", "MIX_OK.PdF",
    ])
    def test_valid_extensions(self, name):
        assert is_valid_certificate_filename(name) is True

    @pytest.mark.parametrize("name", [
        "", None, "malware.exe", "doc.docx", "archive.zip",
        "file_no_ext", "image.tiff", "report.txt",
    ])
    def test_invalid_extensions(self, name):
        assert is_valid_certificate_filename(name) is False


# ============================================================
# validate_bmt_override — regole BLOCCANTI
# ============================================================
class TestValidationBlocking:
    def _good_kwargs(self, **overrides):
        base = dict(
            bmt_value=18.0,
            standard_yield=15.0,
            certificate_uploaded=True,
            lab_name="Lab Esempio S.r.l.",
            cert_date="2025-09-15",
            sample_ref="RP-2025-0042",
            cert_filename="certificato.pdf",
        )
        base.update(overrides)
        return base

    def test_no_certificate_blocks_override(self):
        """Senza certificato caricato, l'override BMT NON deve essere valido."""
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(certificate_uploaded=False)
        )
        assert is_valid is False
        assert any("Certificato BMT obbligatorio" in e for e in errors)

    def test_certificate_with_complete_data_passes(self):
        """Con certificato e tutti i metadati validi → override valido."""
        is_valid, errors, _ = validate_bmt_override(**self._good_kwargs())
        assert is_valid is True, f"errori inattesi: {errors}"
        assert errors == []

    def test_zero_bmt_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(bmt_value=0.0)
        )
        assert is_valid is False
        assert any("> 0" in e for e in errors)

    def test_negative_bmt_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(bmt_value=-5.0)
        )
        assert is_valid is False
        assert any("> 0" in e for e in errors)

    def test_non_numeric_bmt_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(bmt_value="non-numero")
        )
        assert is_valid is False
        assert any("non numerico" in e for e in errors)

    def test_nan_bmt_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(bmt_value=float("nan"))
        )
        assert is_valid is False

    def test_inf_bmt_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(bmt_value=float("inf"))
        )
        assert is_valid is False

    def test_invalid_extension_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(cert_filename="cert.exe")
        )
        assert is_valid is False
        assert any("Estensione" in e for e in errors)

    def test_missing_lab_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(lab_name="")
        )
        assert is_valid is False
        assert any("laboratorio" in e.lower() for e in errors)

    def test_missing_date_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(cert_date="")
        )
        assert is_valid is False
        assert any("data" in e.lower() for e in errors)

    def test_missing_sample_ref_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(sample_ref="")
        )
        assert is_valid is False
        assert any("campione" in e.lower() for e in errors)

    def test_whitespace_only_lab_blocked(self):
        is_valid, errors, _ = validate_bmt_override(
            **self._good_kwargs(lab_name="   ")
        )
        assert is_valid is False


# ============================================================
# validate_bmt_override — regole NON BLOCCANTI (warning)
# ============================================================
class TestValidationWarnings:
    def _kwargs(self, bmt, std):
        return dict(
            bmt_value=bmt, standard_yield=std,
            certificate_uploaded=True,
            lab_name="L", cert_date="2025-01-01",
            sample_ref="X", cert_filename="c.pdf",
        )

    def test_warning_above_30pct(self):
        """BMT > standard di oltre 30% → warning."""
        _, _, warnings = validate_bmt_override(**self._kwargs(140.0, 100.0))
        assert len(warnings) == 1
        assert "30%" in warnings[0]
        assert "superiore" in warnings[0]

    def test_warning_below_30pct(self):
        """BMT < standard di oltre 30% → warning."""
        _, _, warnings = validate_bmt_override(**self._kwargs(60.0, 100.0))
        assert len(warnings) == 1
        assert "inferiore" in warnings[0]

    def test_no_warning_within_30pct_above(self):
        _, _, warnings = validate_bmt_override(**self._kwargs(125.0, 100.0))
        assert warnings == []

    def test_no_warning_within_30pct_below(self):
        _, _, warnings = validate_bmt_override(**self._kwargs(75.0, 100.0))
        assert warnings == []

    def test_no_warning_at_exactly_30pct(self):
        # +30% esatto: non oltre soglia → no warning
        _, _, warnings = validate_bmt_override(**self._kwargs(130.0, 100.0))
        assert warnings == []

    def test_warning_just_above_30pct(self):
        # 30.1% → warning
        _, _, warnings = validate_bmt_override(**self._kwargs(130.1, 100.0))
        assert len(warnings) == 1


# ============================================================
# resolve_biomass_yield
# ============================================================
class TestResolveYield:
    def test_no_overrides_returns_standard(self):
        """Senza override → resa standard."""
        res = resolve_biomass_yield("Liquame suino", 15.0, {})
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD
        assert res["override_active"] is False
        assert res["certificate"] is None
        assert res["unit"] == YIELD_UNIT

    def test_none_overrides_returns_standard(self):
        res = resolve_biomass_yield("Liquame suino", 15.0, None)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD

    def test_inactive_override_returns_standard(self):
        """Override presente ma active=False → resa standard."""
        cert = BMTCertificate(
            "Liquame suino", 22.0, "L", "2025-01-01", "X", "c.pdf",
        )
        overrides = {"Liquame suino": {"active": False, "certificate": cert}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD
        assert res["override_active"] is False

    def test_active_override_with_certificate_uses_bmt(self):
        """Override attivo + cert valido → usa la resa BMT."""
        cert = BMTCertificate(
            "Liquame suino", 22.0, "LabXYZ", "2025-09-15",
            "RP-001", "cert.pdf",
        )
        overrides = {"Liquame suino": {"active": True, "certificate": cert}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 22.0
        assert res["source"] == SOURCE_BMT
        assert res["certificate"] is cert
        assert res["override_active"] is True
        assert res["standard_yield"] == 15.0  # tabella standard intatta

    def test_active_override_without_certificate_returns_standard(self):
        """active=True ma certificate=None → fallback a standard."""
        overrides = {"Liquame suino": {"active": True, "certificate": None}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD

    def test_active_override_with_invalid_extension_returns_standard(self):
        """Cert con estensione non ammessa → fallback a standard."""
        cert = BMTCertificate(
            "Liquame suino", 22.0, "L", "2025-01-01", "X", "cert.exe",
        )
        overrides = {"Liquame suino": {"active": True, "certificate": cert}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD

    def test_active_override_with_zero_bmt_returns_standard(self):
        cert = BMTCertificate(
            "Liquame suino", 0.0, "L", "2025-01-01", "X", "c.pdf",
        )
        overrides = {"Liquame suino": {"active": True, "certificate": cert}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD

    def test_override_isolated_to_specific_biomass(self):
        """Override su una biomassa NON deve toccare le altre."""
        cert = BMTCertificate(
            "Liquame suino", 22.0, "L", "2025-01-01", "X", "c.pdf",
        )
        overrides = {"Liquame suino": {"active": True, "certificate": cert}}

        res_a = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        res_b = resolve_biomass_yield("Trinciato di mais", 104.0, overrides)
        res_c = resolve_biomass_yield("Pollina ovaiole", 90.0, overrides)

        assert res_a["yield_used"] == 22.0
        assert res_a["source"] == SOURCE_BMT

        assert res_b["yield_used"] == 104.0
        assert res_b["source"] == SOURCE_STD
        assert res_b["certificate"] is None

        assert res_c["yield_used"] == 90.0
        assert res_c["source"] == SOURCE_STD


# ============================================================
# build_yield_audit_row
# ============================================================
class TestAuditRow:
    def test_audit_row_with_bmt_certificate(self):
        cert = BMTCertificate(
            "Liquame suino", 22.0, "LabXYZ", "2025-09-15",
            "RP-001", "cert.pdf",
        )
        res = resolve_biomass_yield(
            "Liquame suino", 15.0,
            {"Liquame suino": {"active": True, "certificate": cert}},
        )
        row = build_yield_audit_row(res)

        assert row["Biomassa"] == "Liquame suino"
        assert row["Resa standard"] == 15.0
        assert row["Resa usata"] == 22.0
        assert row["Unità"] == YIELD_UNIT
        assert row["Origine resa"] == SOURCE_BMT
        assert row["Certificato"] == "cert.pdf"
        assert row["Laboratorio"] == "LabXYZ"
        assert row["Data certificato"] == "2025-09-15"
        assert row["Riferimento campione"] == "RP-001"

    def test_audit_row_without_bmt(self):
        res = resolve_biomass_yield("Trinciato di mais", 104.0, {})
        row = build_yield_audit_row(res)

        assert row["Resa usata"] == 104.0
        assert row["Resa standard"] == 104.0
        assert row["Origine resa"] == SOURCE_STD
        assert row["Certificato"] == "—"
        assert row["Laboratorio"] == "—"
        assert row["Data certificato"] == "—"
        assert row["Riferimento campione"] == "—"

    def test_audit_row_keys_complete(self):
        """L'audit row deve contenere TUTTI i campi richiesti."""
        res = resolve_biomass_yield("X", 100.0, {})
        row = build_yield_audit_row(res)
        required = {
            "Biomassa", "Resa standard", "Resa usata", "Unità",
            "Origine resa", "Certificato", "Laboratorio",
            "Data certificato", "Riferimento campione",
        }
        assert required.issubset(row.keys())


# ============================================================
# Integrazione — flusso end-to-end (validazione → risoluzione → audit)
# ============================================================
class TestIntegration:
    def test_e2e_invalid_override_does_not_apply(self):
        """Override non valido (no cert) → standard usato anche se BMT è inserito."""
        # 1) validazione: BMT inserito ma cert mancante
        is_valid, errors, _ = validate_bmt_override(
            bmt_value=22.0, standard_yield=15.0,
            certificate_uploaded=False,
            lab_name="L", cert_date="2025-01-01", sample_ref="X",
        )
        assert is_valid is False

        # 2) Per simulare la UI: non costruisco BMTCertificate se invalido
        overrides = {}  # nulla salvato

        # 3) risoluzione: standard
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 15.0
        assert res["source"] == SOURCE_STD

    def test_e2e_valid_override_applies_to_calculations(self):
        """Override valido → BMT usato nei calcoli simulati."""
        is_valid, errors, _ = validate_bmt_override(
            bmt_value=22.0, standard_yield=15.0,
            certificate_uploaded=True,
            lab_name="LabXYZ", cert_date="2025-09-15",
            sample_ref="RP-001", cert_filename="cert.pdf",
        )
        assert is_valid is True

        cert = BMTCertificate(
            "Liquame suino", 22.0, "LabXYZ", "2025-09-15",
            "RP-001", "cert.pdf",
        )
        overrides = {"Liquame suino": {"active": True, "certificate": cert}}
        res = resolve_biomass_yield("Liquame suino", 15.0, overrides)
        assert res["yield_used"] == 22.0

        # Simula calcolo Sm³: 100 t × resa_usata
        nm3 = 100.0 * res["yield_used"]
        assert nm3 == 2200.0  # con BMT
        # Senza override sarebbe 1500.0

    def test_e2e_export_row_traces_origin(self):
        """Una riga di export contiene sempre l'origine della resa."""
        # caso BMT
        cert = BMTCertificate("X", 50.0, "L", "2025-01-01", "S", "c.pdf")
        res_bmt = resolve_biomass_yield(
            "X", 30.0, {"X": {"active": True, "certificate": cert}}
        )
        row_bmt = build_yield_audit_row(res_bmt)
        assert row_bmt["Origine resa"] == SOURCE_BMT
        assert "BMT" in row_bmt["Origine resa"]

        # caso standard
        res_std = resolve_biomass_yield("Y", 80.0, {})
        row_std = build_yield_audit_row(res_std)
        assert row_std["Origine resa"] == SOURCE_STD
        assert "standard" in row_std["Origine resa"].lower()


# ============================================================
# Costanti pubbliche
# ============================================================
class TestPublicConstants:
    def test_threshold_is_30pct(self):
        assert BMT_DEVIATION_WARN_THRESHOLD == 0.30

    def test_yield_unit_string(self):
        assert "Sm" in YIELD_UNIT and "biometano/t" in YIELD_UNIT

    def test_allowed_extensions_set(self):
        assert ".pdf" in ALLOWED_CERT_EXTS
        assert ".jpg" in ALLOWED_CERT_EXTS
        assert ".png" in ALLOWED_CERT_EXTS
        assert ".xlsx" in ALLOWED_CERT_EXTS
        assert ".csv" in ALLOWED_CERT_EXTS

    def test_source_labels_distinct(self):
        assert SOURCE_BMT != SOURCE_STD
