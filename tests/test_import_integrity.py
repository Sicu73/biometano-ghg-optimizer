# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Integrita' degli import (anche quelli lazy dentro funzioni/try).

Motivazione: in Streamlit gli import lazy dentro `try/except Exception` non
fanno crashare l'app: mostrano un st.error e la feature sparisce
silenziosamente. Un modulo rinominato o un simbolo inesistente resta quindi
invisibile ai test tradizionali finche' un utente non clicca quel bottone.

Questo test scansiona TUTTI i file .py del progetto via AST (nessuna
esecuzione) e verifica che:
  1. ogni modulo importato sia risolvibile;
  2. per i moduli LOCALI del repo, ogni simbolo `from mod import nome`
     esista davvero come def/class/assegnazione a livello modulo.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist"}

# Moduli opzionali: assenti in CI non sono un bug (feature degradano di proposito).
OPTIONAL_MODULES = {"stripe", "bcrypt", "jwt", "pytest", "sitecustomize", "sentry_sdk"}


def _py_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def _local_module_path(mod: str) -> Path | None:
    """Ritorna il file del repo che implementa `mod`, se locale."""
    rel = mod.replace(".", "/")
    for cand in (ROOT / f"{rel}.py", ROOT / rel / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _module_level_names(path: Path) -> set[str]:
    """Nomi esportati a livello modulo (def/class/assegnazioni/import)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Try):
            # import opzionali in try/except a livello modulo
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(sub.name)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for alias in sub.names:
                        names.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(sub, ast.Assign):
                    for tgt in sub.targets:
                        if isinstance(tgt, ast.Name):
                            names.add(tgt.id)
    return names


def _collect_imports(path: Path):
    """(modulo, simbolo|None, riga) per ogni import del file, a qualsiasi livello."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # import relativo: fuori scope
                continue
            if node.module is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    yield node.module, None, node.lineno
                else:
                    yield node.module, alias.name, node.lineno


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_every_import_resolves(path: Path):
    """Nessun import (anche lazy) punta a un modulo inesistente."""
    errors = []
    for mod, _sym, lineno in _collect_imports(path):
        top = mod.split(".")[0]
        if top in OPTIONAL_MODULES:
            continue
        if _local_module_path(mod) is not None:
            continue
        try:
            spec = importlib.util.find_spec(mod)
        except (ImportError, ValueError, AttributeError):
            spec = None
        if spec is None:
            errors.append(f"{path.relative_to(ROOT)}:{lineno} modulo inesistente: {mod!r}")
    assert not errors, "Import irrisolvibili:\n" + "\n".join(errors)


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_local_import_symbols_exist(path: Path):
    """`from <modulo-locale> import nome`: il nome esiste davvero."""
    errors = []
    for mod, sym, lineno in _collect_imports(path):
        if sym is None:
            continue
        target = _local_module_path(mod)
        if target is None:
            continue  # modulo esterno: fuori scope
        # sottomodulo di un package (es. `from export import daily_pdf`)
        if _local_module_path(f"{mod}.{sym}") is not None:
            continue
        if sym not in _module_level_names(target):
            errors.append(
                f"{path.relative_to(ROOT)}:{lineno} "
                f"{mod!r} non espone {sym!r}"
            )
    assert not errors, "Simboli inesistenti:\n" + "\n".join(errors)
