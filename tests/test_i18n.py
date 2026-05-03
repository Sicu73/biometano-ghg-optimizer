# -*- coding: utf-8 -*-
"""tests/test_i18n.py — Verifica integrita' del modulo core.i18n."""
from __future__ import annotations

import pytest

from core import i18n
from core.i18n import (
    DEFAULT_LANG,
    SUPPORTED_LANGS,
    TRANSLATIONS,
    get_language,
    set_language,
    t,
)


# ---------------------------------------------------------------------------
# Struttura del dizionario
# ---------------------------------------------------------------------------

def test_supported_langs_has_it_en():
    assert "it" in SUPPORTED_LANGS
    assert "en" in SUPPORTED_LANGS


def test_default_lang_is_it():
    assert DEFAULT_LANG == "it"


def test_translations_has_both_buckets():
    assert "it" in TRANSLATIONS
    assert "en" in TRANSLATIONS
    assert isinstance(TRANSLATIONS["it"], dict)
    assert isinstance(TRANSLATIONS["en"], dict)


def test_translations_buckets_not_empty():
    assert len(TRANSLATIONS["it"]) > 0
    assert len(TRANSLATIONS["en"]) > 0


def test_translations_it_keys_are_in_en():
    """Ogni chiave IT deve esistere anche in EN."""
    missing = [k for k in TRANSLATIONS["it"] if k not in TRANSLATIONS["en"]]
    assert not missing, f"Chiavi IT mancanti in EN: {missing}"


def test_translations_en_keys_are_in_it():
    """Ogni chiave EN deve esistere anche in IT (parita' totale)."""
    missing = [k for k in TRANSLATIONS["en"] if k not in TRANSLATIONS["it"]]
    assert not missing, f"Chiavi EN mancanti in IT: {missing}"


def test_translations_en_values_not_empty():
    """Tutte le traduzioni EN devono essere non-vuote."""
    empty = [k for k, v in TRANSLATIONS["en"].items() if not str(v).strip()]
    assert not empty, f"Traduzioni EN vuote: {empty}"


def test_translations_it_values_not_empty():
    """Tutte le traduzioni IT devono essere non-vuote."""
    empty = [k for k, v in TRANSLATIONS["it"].items() if not str(v).strip()]
    assert not empty, f"Traduzioni IT vuote: {empty}"


# ---------------------------------------------------------------------------
# Funzione t()
# ---------------------------------------------------------------------------

def test_t_returns_it_translation():
    # Prendiamo una chiave nota
    sample_key = next(iter(TRANSLATIONS["it"].keys()))
    expected = TRANSLATIONS["it"][sample_key]
    assert t(sample_key, "it") == expected


def test_t_returns_en_translation():
    sample_key = next(iter(TRANSLATIONS["en"].keys()))
    expected = TRANSLATIONS["en"][sample_key]
    assert t(sample_key, "en") == expected


def test_t_unknown_key_does_not_crash():
    """t() su chiave inesistente deve restituire la chiave stessa, non sollevare."""
    result = t("inesistente.chiave.xyz", "it")
    assert result == "inesistente.chiave.xyz"


def test_t_unknown_key_does_not_crash_en():
    result = t("non.existing.key", "en")
    assert result == "non.existing.key"


def test_t_unknown_lang_falls_back_to_default():
    # Se passiamo una lingua non supportata, fallback su default (it)
    sample_key = next(iter(TRANSLATIONS["it"].keys()))
    expected = TRANSLATIONS["it"][sample_key]
    assert t(sample_key, "fr") == expected


def test_t_none_key_does_not_crash():
    # Passare None come key non deve crashare
    result = t(None, "it")  # type: ignore[arg-type]
    assert isinstance(result, str)


def test_t_with_no_lang_uses_get_language():
    # Senza streamlit, get_language() ritorna DEFAULT_LANG
    sample_key = next(iter(TRANSLATIONS["it"].keys()))
    expected = TRANSLATIONS["it"][sample_key]
    assert t(sample_key) == expected


# ---------------------------------------------------------------------------
# get_language / set_language (no streamlit -> no-op)
# ---------------------------------------------------------------------------

def test_get_language_default_no_streamlit():
    # In assenza di streamlit attivo (test runner) deve restituire DEFAULT_LANG
    assert get_language() == DEFAULT_LANG


def test_set_language_does_not_crash_without_streamlit():
    # set_language deve essere no-op silenzioso senza streamlit
    set_language("en")  # non solleva
    set_language("it")
    set_language("xx")  # lingua non supportata: no-op


# ---------------------------------------------------------------------------
# Chiavi-sentinella per la sezione Daily Operations
# ---------------------------------------------------------------------------

DAILY_REQUIRED_KEYS = [
    "daily.title",
    "daily.subtitle",
    "daily.input.day",
    "daily.input.feedstock",
    "daily.input.mass_t",
    "daily.summary.title",
    "daily.summary.month",
    "daily.summary.compliant",
    "daily.summary.non_compliant",
]


@pytest.mark.parametrize("key", DAILY_REQUIRED_KEYS)
def test_daily_section_keys_present_it(key):
    assert key in TRANSLATIONS["it"], f"Chiave Daily mancante in IT: {key}"


@pytest.mark.parametrize("key", DAILY_REQUIRED_KEYS)
def test_daily_section_keys_present_en(key):
    assert key in TRANSLATIONS["en"], f"Chiave Daily mancante in EN: {key}"
