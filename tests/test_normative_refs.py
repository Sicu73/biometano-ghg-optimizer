# -*- coding: utf-8 -*-
"""tests/test_normative_refs.py — Verifica integrita' riferimenti normativi.

Questi test prevengono la regressione delle correzioni del ciclo di
hardening 2026-05-03:

  - NON deve apparire piu' "5 marzo 2026" come data del recepimento
    italiano della RED III (era una bozza errata).
  - NON deve apparire piu' il codice GU "24A04836" associato a FER 2.
  - DEVE apparire la nuova stringa "D.Lgs. 9 gennaio 2026, n. 5" e
    i nuovi codici GU "24A04589" e "24A06795" per FER 2.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# File da scansionare: codice + JSON normativa.
SCAN_GLOBS = ("*.py", "core/*.py", "output/*.py", "export/*.py", "*.json")
EXCLUDE_DIRS = ("__pycache__", ".pytest_cache", ".git", "tests")


def _iter_target_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCAN_GLOBS:
        for p in REPO_ROOT.glob(pattern):
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            files.append(p)
    # tests directory esclusa di proposito (questo file menziona le stringhe vietate)
    return files


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return p.read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# 1. Stringhe VIETATE (bozze errate da rimuovere)
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("data RED III errata '5 marzo 2026'", re.compile(r"5\s+marzo\s+2026", re.IGNORECASE)),
    ("data RED III errata '05/03/2026'", re.compile(r"\b05/03/2026\b")),
    ("data RED III errata '5/3/2026'", re.compile(r"\b5/3/2026\b")),
    ("data RED III errata '2026-03-05'", re.compile(r"\b2026-03-05\b")),
    ("codice FER 2 errato '24A04836'", re.compile(r"\b24A04836\b")),
]


@pytest.mark.parametrize("label,pattern", FORBIDDEN_PATTERNS)
def test_no_forbidden_normative_string(label, pattern):
    """Nessuno dei file scansionati deve contenere le stringhe vietate."""
    offenders: list[str] = []
    for p in _iter_target_files():
        text = _read(p)
        for n, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{p.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        f"Trovata occorrenza vietata ({label}):\n  - " + "\n  - ".join(offenders)
    )


# ---------------------------------------------------------------------------
# 2. Stringhe RICHIESTE (correzioni applicate)
# ---------------------------------------------------------------------------

def _any_file_contains(needle: str) -> list[str]:
    hits: list[str] = []
    for p in _iter_target_files():
        text = _read(p)
        if needle in text:
            hits.append(str(p.relative_to(REPO_ROOT)))
    return hits


def test_dlgs_5_2026_correct_string_present():
    """Almeno un file deve contenere la stringa canonica del recepimento."""
    needle = "D.Lgs. 9 gennaio 2026, n. 5"
    hits = _any_file_contains(needle)
    assert hits, (
        f"La stringa canonica '{needle}' non e' presente in nessun file "
        f"scansionato ({len(_iter_target_files())} file controllati)."
    )


def test_fer2_avviso_code_present():
    needle = "24A04589"
    hits = _any_file_contains(needle)
    assert hits, f"Il codice GU '{needle}' (avviso DM 19/06/2024 FER 2) non e' presente."


def test_fer2_regole_operative_code_present():
    needle = "24A06795"
    hits = _any_file_contains(needle)
    assert hits, f"Il codice GU '{needle}' (regole operative GSE FER 2) non e' presente."


# ---------------------------------------------------------------------------
# 3. Verifica strutturata di normativa_versions.json
# ---------------------------------------------------------------------------

def test_normativa_json_dlgs_recepimento_correct():
    norms = _load_norms()
    entry = next((n for n in norms if n.get("id") == "dlgs_5_2026"), None)
    assert entry is not None, "Voce 'dlgs_5_2026' assente da normativa_versions.json"
    assert "D.Lgs. 9 gennaio 2026, n. 5" in entry.get("titolo", ""), (
        f"Titolo errato per dlgs_5_2026: {entry.get('titolo')!r}"
    )
    # data_pubblicazione canonica = data GU 20/01/2026
    assert entry.get("data_pubblicazione") == "2026-01-20"
    assert entry.get("data_entrata_in_vigore") == "2026-02-04"


def test_normativa_json_fer2_correct():
    norms = _load_norms()
    entry = next((n for n in norms if n.get("id") == "dm_fer2_2024"), None)
    assert entry is not None, "Voce 'dm_fer2_2024' assente da normativa_versions.json"
    assert "DM 19 giugno 2024" in entry.get("titolo", ""), (
        f"Titolo errato per dm_fer2_2024: {entry.get('titolo')!r}"
    )
    assert entry.get("data_pubblicazione") == "2024-06-19"
    assert entry.get("avviso_gu_codice") == "24A04589"
    assert entry.get("regole_operative_codice") == "24A06795"


def _load_norms() -> list[dict]:
    p = REPO_ROOT / "normativa_versions.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("norme", [])


# ---------------------------------------------------------------------------
# 4. Costanti core/constants.py allineate
# ---------------------------------------------------------------------------

def test_core_constants_dlgs_string():
    from core.constants import DLGS_RED_III_RECEPIMENTO
    assert "D.Lgs. 9 gennaio 2026, n. 5" in DLGS_RED_III_RECEPIMENTO
    assert "20/01/2026" in DLGS_RED_III_RECEPIMENTO
    assert "04/02/2026" in DLGS_RED_III_RECEPIMENTO


def test_core_constants_fer2_codes():
    from core.constants import (
        DM_FER2,
        DM_FER2_AVVISO_GU,
        DM_FER2_REGOLE_OPERATIVE,
    )
    assert "19/06/2024" in DM_FER2
    assert DM_FER2_AVVISO_GU == "24A04589"
    assert DM_FER2_REGOLE_OPERATIVE == "24A06795"
