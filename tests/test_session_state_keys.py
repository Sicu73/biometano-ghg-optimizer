# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Nessuna chiave `st.session_state` letta ma mai scritta.

E' la classe di difetti piu' insidiosa dell'app: leggere una chiave che
nessun widget popola non produce alcun errore, `.get()` restituisce il
default e la feature si degrada in silenzio. Casi realmente trovati:

  * `do_plant`        -> la sezione annuale non vedeva i dati giornalieri;
  * `daily_year/month`-> LS-ID e periodo di rendicontazione col mese corrente;
  * `monthly_*`       -> bilancio di massa del PDF azzerato;
  * `bp_pnrr_pct`     -> Excel bloccato sul 40% di default;
  * `upgrading_opt_saved` -> premio upgrading sempre "da verificare".

Analisi statica (AST): nessuna esecuzione dell'app.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "tests"}

# Attributi di dict/Mapping, non chiavi di stato.
_DICT_METHODS = {"get", "pop", "setdefault", "update", "keys", "values",
                 "items", "clear", "copy"}

# Eccezioni motivate: chiave letta di proposito senza produttore in-app.
ALLOWED_WITHOUT_WRITER = {
    # Registro fornitori biomassa (UNI/TS 11567 cap. 2-3): la UI di
    # compilazione non esiste ancora; il PDF mostra un placeholder quando e'
    # vuoto (vedi app_mensile.py ~1380). Degradazione voluta, non un bug.
    "suppliers_registry",
}


def _is_session_state(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "session_state"


def _collect(tree: ast.AST, rel: str, reads: dict, writes: dict) -> None:
    def add(d, key, line):
        d.setdefault(key, []).append(f"{rel}:{line}")

    for node in ast.walk(tree):
        # --- scritture esplicite -------------------------------------
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and _is_session_state(t.value):
                    if isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
                        add(writes, t.slice.value, node.lineno)
                elif isinstance(t, ast.Attribute) and _is_session_state(t.value):
                    add(writes, t.attr, node.lineno)

        if isinstance(node, ast.Call):
            f = node.func
            # session_state.get/pop/setdefault("k")
            if (isinstance(f, ast.Attribute) and f.attr in ("get", "pop", "setdefault")
                    and _is_session_state(f.value) and node.args):
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                    add(reads, a0.value, node.lineno)
                    if f.attr in ("setdefault", "pop"):
                        add(writes, a0.value, node.lineno)
            # session_state.update({"k": ...})
            if (isinstance(f, ast.Attribute) and f.attr == "update"
                    and _is_session_state(f.value)):
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        for k in arg.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                add(writes, k.value, node.lineno)
            # key=... dei widget: scrittura implicita
            for kw in node.keywords:
                if kw.arg != "key":
                    continue
                v = kw.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    add(writes, v.value, node.lineno)
                elif isinstance(v, ast.JoinedStr):
                    lit = "".join(p.value for p in v.values
                                  if isinstance(p, ast.Constant))
                    if lit:
                        add(writes, lit, node.lineno)

        # --- letture -------------------------------------------------
        if isinstance(node, ast.Subscript) and _is_session_state(node.value):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                add(reads, node.slice.value, node.lineno)
        if (isinstance(node, ast.Attribute) and _is_session_state(node.value)
                and node.attr not in _DICT_METHODS):
            add(reads, node.attr, node.lineno)
        if isinstance(node, ast.Compare):
            for comp in node.comparators:
                if (_is_session_state(comp) and isinstance(node.left, ast.Constant)
                        and isinstance(node.left.value, str)):
                    add(reads, node.left.value, node.lineno)


def test_no_session_state_key_read_without_writer():
    reads: dict[str, list[str]] = {}
    writes: dict[str, list[str]] = {}

    for path in sorted(ROOT.rglob("*.py")):
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        _collect(tree, str(path.relative_to(ROOT)), reads, writes)

    assert reads, "nessuna lettura di session_state trovata: parser da rivedere"

    orphans = {
        k: v for k, v in reads.items()
        if k not in writes and k not in ALLOWED_WITHOUT_WRITER
    }
    detail = "\n".join(
        f"  {k!r} letta in {', '.join(sorted(set(v))[:3])}"
        for k, v in sorted(orphans.items())
    )
    assert not orphans, (
        "chiavi session_state lette ma mai scritte (la feature si degrada "
        f"in silenzio sul valore di default):\n{detail}"
    )
