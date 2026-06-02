# -*- coding: utf-8 -*-
"""Inserisce header di copyright proprietario nei moduli Python principali.

Idempotente: se l'header e' gia' presente, salta il file.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADER = (
    "# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.\n"
    "# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)\n"
    "# Proprietary and confidential. See LICENSE for terms.\n"
    "# Commercial licensing: carlo.sicurini@gmail.com\n"
)

MARKER = "Copyright (c) 2026 Carlo Sicurini"

TARGETS: list[Path] = [
    ROOT / "app_mensile.py",
    *sorted((ROOT / "core").glob("*.py")),
    *sorted((ROOT / "export").glob("*.py")),
]


def patch(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "skip"
    lines = text.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if insert_at < len(lines) and "coding" in lines[insert_at] and lines[insert_at].lstrip().startswith("#"):
        insert_at += 1
    new = "".join(lines[:insert_at]) + HEADER + "".join(lines[insert_at:])
    path.write_text(new, encoding="utf-8")
    return "patched"


def main() -> None:
    for p in TARGETS:
        if not p.exists():
            print(f"miss   {p.relative_to(ROOT)}")
            continue
        status = patch(p)
        print(f"{status:6} {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
