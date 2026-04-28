"""Guardrail numerici per il parser italiano/anglosassone.

Questi test documentano il comportamento atteso del parser isolato
`metaniq_numeric.parse_it`.

Nota operativa:
- Il test `0.800 -> 0.8` è il caso critico emerso dall'audit.
- Se fallisce, il parser tratta un decimale anglosassone come migliaia.
"""

from __future__ import annotations

from metaniq_numeric import parse_it


def test_parse_it_decimal_zero_dot_three_digits():
    assert parse_it("0.800") == 0.8


def test_parse_it_italian_thousands_and_decimal():
    assert parse_it("1.234,56") == 1234.56


def test_parse_it_plain_english_decimal():
    assert parse_it("1234.56") == 1234.56


def test_parse_it_common_integer_thousands():
    assert parse_it("1.800") == 1800.0
    assert parse_it("26.303") == 26303.0


def test_parse_it_rejects_invalid_as_zero():
    assert parse_it("") == 0.0
    assert parse_it("-") == 0.0
    assert parse_it(None) == 0.0
