# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Bootstrap del motore di calcolo indipendente dall'ordine di import.

`core.calculation_engine` popola FEEDSTOCK_DB/FEED_NAMES cercando
app_mensile in sys.modules. Se viene importato prima di app_mensile e
streamlit e' gia' caricato, l'import legacy viene saltato di proposito
(anti import-circolare): senza un default canonico il motore restava con
zero biomasse e i consumatori a valle non se ne accorgevano.

Il test forza proprio quell'ordine in un interprete separato.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit                      # streamlit PRIMA
import core.calculation_engine as ce  # app_mensile NON ancora caricato
print("FEED_NAMES", len(ce.FEED_NAMES))
print("FEEDSTOCK_DB", len(ce.FEEDSTOCK_DB))
print("YIELD", ce._yield_of(ce.FEED_NAMES[0]) if ce.FEED_NAMES else -1)
"""


def _run_isolated() -> dict[str, float]:
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT.format(root=str(ROOT))],
        capture_output=True, text=True, cwd=str(ROOT), timeout=180,
    )
    assert proc.returncode == 0, f"import fallito:\n{proc.stderr}"
    out = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return out


def test_engine_has_feedstocks_when_imported_before_app():
    res = _run_isolated()
    assert res.get("FEED_NAMES", 0) > 0, (
        "FEED_NAMES vuoto: il motore esporrebbe zero biomasse a valle"
    )
    assert res.get("FEEDSTOCK_DB", 0) == res.get("FEED_NAMES"), (
        "FEED_NAMES e FEEDSTOCK_DB disallineati"
    )
    assert res.get("YIELD", 0) > 0, "resa nulla sulla prima biomassa"


def test_engine_db_matches_canonical_source():
    """Il fallback deve essere la stessa fonte usata da app_mensile."""
    from core.calculation_engine import FEEDSTOCK_DB as ENGINE_DB
    from core.feedstock_db import FEEDSTOCK_DB as CANON_DB

    assert set(ENGINE_DB) == set(CANON_DB)
    for name, data in CANON_DB.items():
        assert ENGINE_DB[name]["yield"] == data["yield"]
