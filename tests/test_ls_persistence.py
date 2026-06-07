# -*- coding: utf-8 -*-
"""Tests core/ls_persistence — backup/restore dossier UNI/TS 11567."""
import json

import pytest

from core.ls_persistence import (
    SCHEMA_VERSION,
    apply_dossier_to_session,
    build_dossier_from_session,
    default_dossier_path,
    dossier_to_json_bytes,
    json_bytes_to_dossier,
    load_dossier,
    save_dossier,
)


@pytest.fixture
def tmp_dossier(tmp_path):
    return tmp_path / "test_dossier.json"


@pytest.fixture
def sample_session():
    return {
        "company_name": "Bioenergia Test S.r.l.",
        "company_vat": "IT12345678901",
        "company_legal_address": "Via Roma 1, 20100 Milano (MI)",
        "plant_name": "Impianto Pilota",
        "plant_cui": "IT01X-2026-0001",
        "plant_operational_address": "Cascina San Giorgio, Pavia",
        "responsible_name": "Mario Rossi — Resp. Sostenibilita",
        "suppliers_registry": [
            {"name": "Az. Agr. Verdi", "vat": "IT00000000001",
             "feedstock": "Liquame suino", "tons_per_month": 500.0,
             "contract_ref": "CF-2026-007", "ddt_ref": "DDT 120-145",
             "baseline_storage": "lagone aperto"},
        ],
        "ls_history": [
            {"ls_id": "LS-2026-05-ABC123", "year": 2026, "month": 5,
             "biomass_total_t": 750.0, "saving_pct": 82.5, "compliant": True},
        ],
        "irrelevant_key": "should not be saved",
    }


class TestSaveLoadRoundtrip:
    def test_save_then_load_idempotente(self, tmp_dossier, sample_session):
        d = build_dossier_from_session(sample_session)
        save_dossier(d, tmp_dossier)
        loaded = load_dossier(tmp_dossier)
        assert loaded["company"]["name"] == "Bioenergia Test S.r.l."
        assert loaded["plant"]["cui"] == "IT01X-2026-0001"
        assert len(loaded["suppliers"]) == 1
        assert loaded["suppliers"][0]["feedstock"] == "Liquame suino"
        assert len(loaded["ls_history"]) == 1

    def test_load_inesistente_ritorna_dossier_vuoto(self, tmp_path):
        missing = tmp_path / "non_esiste.json"
        loaded = load_dossier(missing)
        assert loaded["schema_version"] == SCHEMA_VERSION
        assert loaded["company"]["name"] == ""
        assert loaded["suppliers"] == []
        assert loaded["ls_history"] == []

    def test_load_corrotto_ritorna_dossier_vuoto(self, tmp_dossier):
        tmp_dossier.write_text("not valid json {{{", encoding="utf-8")
        loaded = load_dossier(tmp_dossier)
        assert loaded["company"]["name"] == ""
        assert loaded["schema_version"] == SCHEMA_VERSION

    def test_save_aggiorna_saved_at(self, tmp_dossier, sample_session):
        d = build_dossier_from_session(sample_session)
        save_dossier(d, tmp_dossier)
        loaded = load_dossier(tmp_dossier)
        assert loaded["saved_at"]  # ISO timestamp non vuoto
        assert "T" in loaded["saved_at"]


class TestBuildAndApply:
    def test_irrelevant_keys_non_persistite(self, sample_session):
        d = build_dossier_from_session(sample_session)
        flat = json.dumps(d)
        assert "irrelevant_key" not in flat
        assert "should not be saved" not in flat

    def test_apply_roundtrip(self, sample_session):
        d = build_dossier_from_session(sample_session)
        flat = apply_dossier_to_session(d)
        assert flat["company_name"] == "Bioenergia Test S.r.l."
        assert flat["plant_cui"] == "IT01X-2026-0001"
        assert flat["responsible_name"] == "Mario Rossi — Resp. Sostenibilita"
        assert isinstance(flat["suppliers_registry"], list)
        assert flat["suppliers_registry"][0]["name"] == "Az. Agr. Verdi"

    def test_empty_session_no_crash(self):
        d = build_dossier_from_session({})
        assert d["company"]["name"] == ""
        assert d["suppliers"] == []
        flat = apply_dossier_to_session(d)
        assert flat["company_name"] == ""


class TestBytesSerialization:
    def test_to_bytes_then_back(self, sample_session):
        d = build_dossier_from_session(sample_session)
        b = dossier_to_json_bytes(d)
        assert isinstance(b, bytes)
        assert b.startswith(b"{")
        d2 = json_bytes_to_dossier(b)
        assert d2["company"]["name"] == d["company"]["name"]
        assert len(d2["suppliers"]) == 1

    def test_from_bytes_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            json_bytes_to_dossier(b"not json")

    def test_from_bytes_non_dict_raises(self):
        with pytest.raises(ValueError):
            json_bytes_to_dossier(b'["array", "not", "dict"]')


class TestDefaultPath:
    def test_default_path_uses_cui(self, monkeypatch, tmp_path):
        monkeypatch.setenv("METANIQ_LS_DATA_DIR", str(tmp_path))
        p = default_dossier_path(plant_cui="IT-AAA-001")
        assert "IT-AAA-001" in p.name
        assert p.suffix == ".json"

    def test_default_path_fallback_vat(self, monkeypatch, tmp_path):
        monkeypatch.setenv("METANIQ_LS_DATA_DIR", str(tmp_path))
        p = default_dossier_path(plant_cui="", company_vat="IT12345")
        assert "IT12345" in p.name

    def test_default_path_fallback_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("METANIQ_LS_DATA_DIR", str(tmp_path))
        p = default_dossier_path()
        assert "default" in p.name
