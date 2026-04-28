"""Guardrail numerici per il parser italiano/anglosassone.

Questi test documentano il comportamento atteso prima del refactoring
profondo di `parse_it()` fuori da app_mensile.py.

Nota operativa:
- Il test `0.800 -> 0.8` è il caso critico emerso dall'audit.
- Se fallisce, il parser tratta un decimale anglosassone come migliaia.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_parse_it():
    """Carica parse_it senza avviare Streamlit come applicazione."""
    module_path = Path(__file__).resolve().parents[1] / "app_mensile.py"
    spec = importlib.util.spec_from_file_location("app_mensile_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.parse_it


def test_parse_it_decimal_zero_dot_three_digits():
    parse_it = _load_parse_it()
    assert parse_it("0.800") == 0.8


def test_parse_it_italian_thousands_and_decimal():
    parse_it = _load_parse_it()
    assert parse_it("1.234,56") == 1234.56


def test_parse_it_plain_english_decimal():
    parse_it = _load_parse_it()
    assert parse_it("1234.56") == 1234.56


def test_parse_it_common_integer_thousands():
    parse_it = _load_parse_it()
    assert parse_it("1.800") == 1800.0
    assert parse_it("26.303") == 26303.0
