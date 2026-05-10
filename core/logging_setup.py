# -*- coding: utf-8 -*-
"""core/logging_setup.py — Logging strutturato per produzione.

Configura una sola volta un logger root con:
  - StreamHandler su stderr (visibile nei log Streamlit Cloud)
  - File rotativo opzionale (logs/metaniq.log, 5 file × 1 MB)
  - Formato: timestamp, livello, modulo, messaggio + traceback se exc_info

Usato dai punti di catch eccezioni in app_mensile.py per registrare
stack trace completi anche quando l'utente vede solo un messaggio
amichevole (audit robustezza #3).

Uso:
    from core.logging_setup import get_logger
    log = get_logger(__name__)
    try:
        ...
    except Exception as exc:
        log.exception("Operazione X fallita: %s", exc)
        st.error(f"Errore: {exc}")
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def _setup_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("metaniq")
    if root.handlers:
        _CONFIGURED = True
        return

    level_name = os.environ.get("METANIQ_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console (stderr)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(level)
    root.addHandler(sh)

    # File rotativo (best-effort: skip se filesystem read-only)
    try:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "metaniq.log",
            maxBytes=1_000_000,  # 1 MB
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        fh.setLevel(level)
        root.addHandler(fh)
    except OSError:
        # FS read-only (es. Streamlit Cloud container) → solo stderr
        pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Restituisce un logger figlio del root 'metaniq', configurato se necessario."""
    _setup_root()
    if not name.startswith("metaniq"):
        name = f"metaniq.{name}"
    return logging.getLogger(name)


__all__ = ["get_logger"]
