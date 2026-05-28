# -*- coding: utf-8 -*-
"""Tests per core/ls_identifier.py — generatore ID Lotto di Sostenibilità."""
import pytest

from core.ls_identifier import build_ls_id, validate_ls_id


class TestBuildLsId:
    def test_format_canonico(self):
        ls = build_ls_id(year=2026, month=5, plant_cui="IT01X-2024-1234")
        assert ls.startswith("LS-2026-05-")
        assert len(ls) == 17  # LS-YYYY-MM-XXXXXX
        assert validate_ls_id(ls)

    def test_idempotente_su_stesso_cui(self):
        a = build_ls_id(year=2026, month=5, plant_cui="IT01X-2024-1234")
        b = build_ls_id(year=2026, month=5, plant_cui="IT01X-2024-1234")
        assert a == b

    def test_cui_diversi_producono_id_diversi(self):
        a = build_ls_id(year=2026, month=5, plant_cui="IT-A")
        b = build_ls_id(year=2026, month=5, plant_cui="IT-B")
        assert a != b

    def test_fallback_plant_name_se_cui_vuoto(self):
        ls = build_ls_id(year=2026, month=5, plant_cui="", plant_name="Impianto Foo")
        assert ls.startswith("LS-2026-05-")
        assert validate_ls_id(ls)

    def test_fallback_no_cui_no_name(self):
        ls = build_ls_id(year=2026, month=5)
        assert ls.startswith("LS-2026-05-")
        assert validate_ls_id(ls)

    def test_year_fuori_range(self):
        with pytest.raises(ValueError):
            build_ls_id(year=1999, month=5)
        with pytest.raises(ValueError):
            build_ls_id(year=2100, month=5)

    def test_month_fuori_range(self):
        with pytest.raises(ValueError):
            build_ls_id(year=2026, month=0)
        with pytest.raises(ValueError):
            build_ls_id(year=2026, month=13)

    def test_mese_zero_padded(self):
        ls = build_ls_id(year=2026, month=3, plant_cui="X")
        assert "-03-" in ls


class TestValidateLsId:
    def test_valido(self):
        assert validate_ls_id("LS-2026-05-ABC123")
        assert validate_ls_id("LS-2026-12-000000")
        assert validate_ls_id("LS-2026-01-FFFFFF")

    def test_invalido(self):
        assert not validate_ls_id("LS-2026-13-ABC123")  # mese 13
        assert not validate_ls_id("LS-2026-00-ABC123")  # mese 0
        assert not validate_ls_id("LS-2026-5-ABC123")   # mese senza zero-pad
        assert not validate_ls_id("LS-2026-05-ABC12")   # 5 char invece di 6
        assert not validate_ls_id("LS-2026-05-XYZ123")  # non-hex
        assert not validate_ls_id("LS-26-05-ABC123")    # anno 2 cifre
        assert not validate_ls_id("")
        assert not validate_ls_id(None)
