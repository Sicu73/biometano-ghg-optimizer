# -*- coding: utf-8 -*-
"""tests/test_dry_matter_normalization.py — Test per la normalizzazione della sostanza secca.

Verifica:
  - _yield_of() applica la normalizzazione W_n = I_n * (STA_n / STS_n)
    moltiplicando la resa base per il rapporto tra sostanza secca reale (STA) e standard (STS).
  - Gestione corretta degli override BMT attivi combinati con la normalizzazione della sostanza secca.
  - ghg_summary calcola la sostenibilità e i volumi in modo allineato.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Inserisci repo root nel sys.path per importare correttamente i moduli
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from app_mensile import (
    FEEDSTOCK_DB,
    _EFFECTIVE_DRY_MATTERS,
    _EFFECTIVE_YIELDS,
    _yield_of,
    ghg_summary,
)


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Pulisce gli override prima e dopo ogni test per evitare inquinamento dello stato."""
    _EFFECTIVE_YIELDS.clear()
    _EFFECTIVE_DRY_MATTERS.clear()
    yield
    _EFFECTIVE_YIELDS.clear()
    _EFFECTIVE_DRY_MATTERS.clear()


def test_yield_of_standard_no_override():
    """Se non ci sono override, _yield_of deve restituire il valore di default di FEEDSTOCK_DB."""
    for name, data in FEEDSTOCK_DB.items():
        assert _yield_of(name) == pytest.approx(data["yield"])


def test_yield_of_with_dry_matter_normalization():
    """Se la sostanza secca reale (STA) è diversa da quella standard (STS), la resa deve essere normalizzata."""
    name = "Trinciato di mais"
    sts = FEEDSTOCK_DB[name]["dry_matter_std"]  # Standard = 0.35 (35%)
    base_yield = FEEDSTOCK_DB[name]["yield"]  # 116.1

    # Impostiamo sostanza secca reale (STA) al 40%
    _EFFECTIVE_DRY_MATTERS[name] = 0.40
    expected_yield = base_yield * (0.40 / sts)

    assert _yield_of(name) == pytest.approx(expected_yield)

    # Impostiamo sostanza secca reale (STA) al 30%
    _EFFECTIVE_DRY_MATTERS[name] = 0.30
    expected_yield = base_yield * (0.30 / sts)

    assert _yield_of(name) == pytest.approx(expected_yield)


def test_yield_of_with_bmt_override_and_dry_matter():
    """Se sia l'override BMT che la sostanza secca reale sono attivi, si deve normalizzare la resa BMT."""
    name = "Trinciato di mais"
    sts = FEEDSTOCK_DB[name]["dry_matter_std"]  # Standard = 0.35

    # Override BMT attivo a 120.0 Nm3/t
    _EFFECTIVE_YIELDS[name] = 120.0
    # Sostanza secca reale (STA) al 40%
    _EFFECTIVE_DRY_MATTERS[name] = 0.40

    expected_yield = 120.0 * (0.40 / sts)
    assert _yield_of(name) == pytest.approx(expected_yield)


def test_ghg_summary_with_normalized_yield():
    """Verifica che ghg_summary usi la resa normalizzata per calcolare i volumi di gas e la ponderazione GHG."""
    name = "Trinciato di mais"
    sts = FEEDSTOCK_DB[name]["dry_matter_std"]  # Standard = 0.35
    base_yield = FEEDSTOCK_DB[name]["yield"]  # 116.1

    # Scenario 1: Sostanza secca standard
    masses_std = {name: 1000.0}
    summary_std = ghg_summary(masses_std, aux=1.0, ep=0.0)
    expected_sm3_std = 1000.0 * base_yield
    assert summary_std["nm3_gross"] == pytest.approx(expected_sm3_std)

    # Scenario 2: Sostanza secca reale al 40% (maggiore resa volumetrica per tonnellata tal quale)
    _EFFECTIVE_DRY_MATTERS[name] = 0.40
    summary_dm = ghg_summary(masses_std, aux=1.0, ep=0.0)
    expected_sm3_dm = 1000.0 * base_yield * (0.40 / sts)
    assert summary_dm["nm3_gross"] == pytest.approx(expected_sm3_dm)
    assert summary_dm["nm3_gross"] > summary_std["nm3_gross"]
