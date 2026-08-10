# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Nessuna chiave ripetuta nei dizionari di traduzione.

Una chiave ripetuta in un dict letterale non e' un errore Python: vince
l'ultima e le precedenti diventano codice morto. Nel catalogo i18n questo
significava avere due traduzioni inglesi diverse per la stessa etichetta
italiana (es. "Sm3 netti" -> "Net Sm3" e "Sm3 net"), con quella
effettivamente mostrata decisa dall'ordine nel file.

Controllo statico (AST): il dict caricato non conserva i duplicati, quindi
il confronto va fatto sul sorgente.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N_FILES = ["metaniq_i18n.py", "i18n_runtime.py"]


def _duplicate_keys(path: Path):
    """[(chiave, riga_prima, riga_seconda, valore_perso, valore_attivo)]"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dups = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen: dict[str, tuple[int, str]] = {}
        for k, v in zip(node.keys, node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            try:
                val = ast.unparse(v)
            except Exception:
                val = "<?>"
            if k.value in seen:
                prev_line, prev_val = seen[k.value]
                dups.append((k.value, prev_line, k.lineno, prev_val, val))
            seen[k.value] = (k.lineno, val)
    return dups


@pytest.mark.parametrize("filename", I18N_FILES)
def test_no_duplicate_translation_keys(filename):
    path = ROOT / filename
    if not path.is_file():
        pytest.skip(f"{filename} assente")
    dups = _duplicate_keys(path)
    detail = "\n".join(
        f"  {k!r} righe {l1} e {l2}\n"
        f"      ignorata: {pv}\n"
        f"      attiva  : {nv}"
        for k, l1, l2, pv, nv in dups
    )
    assert not dups, (
        f"{filename}: {len(dups)} chiavi ripetute (vince l'ultima, le altre "
        f"sono codice morto):\n{detail}"
    )


def test_catalog_is_not_empty_and_maps_to_strings():
    """Sanity: la deduplica non deve aver eroso il catalogo."""
    from metaniq_i18n import IT_EN

    assert len(IT_EN) > 700, f"catalogo sospettosamente piccolo: {len(IT_EN)}"
    for k, v in IT_EN.items():
        assert isinstance(k, str) and isinstance(v, str), (k, v)
        assert k.strip() and v.strip(), f"voce vuota: {k!r} -> {v!r}"
