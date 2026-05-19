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
_SENTRY_INITIALIZED = False


def _init_sentry() -> None:
    """Inizializza Sentry SDK se DSN configurato in st.secrets o env.

    Cerca in ordine:
      1. ``st.secrets["sentry"]["dsn"]`` (Streamlit Cloud secrets)
      2. ``SENTRY_DSN`` env var (per dev locale)

    Silent skip se sentry-sdk non installato o DSN vuoto. Configura
    ``traces_sample_rate`` da secrets (default 0.1 = 10%).
    """
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return

    dsn: str = ""
    env: str = "production"
    sample_rate: float = 0.1
    try:
        import streamlit as st
        sentry_cfg = st.secrets.get("sentry", {})
        dsn = str(sentry_cfg.get("dsn") or "").strip()
        env = str(sentry_cfg.get("environment") or "production")
        sample_rate = float(sentry_cfg.get("traces_sample_rate") or 0.1)
    except Exception:  # noqa: BLE001
        # Streamlit non disponibile (CLI / test) o secrets non configurati
        dsn = os.environ.get("SENTRY_DSN", "").strip()

    if not dsn:
        # Niente DSN → niente Sentry, l'app gira con solo logging stderr/file.
        _SENTRY_INITIALIZED = True
        return

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            environment=env,
            traces_sample_rate=sample_rate,
            send_default_pii=False,    # GDPR: no PII di default
            attach_stacktrace=True,
            release=_read_version(),
        )
    except ImportError:
        # sentry-sdk non installato → silent skip
        pass
    except Exception as exc:  # noqa: BLE001
        # Init Sentry stesso fallisce (es. DSN malformato) → log e proceed
        logging.getLogger("metaniq").warning("Sentry init failed: %s", exc)
    finally:
        _SENTRY_INITIALIZED = True


def _read_version() -> str:
    """Legge la versione corrente dal modulo `core.version` se presente."""
    try:
        from core.version import __version__
        return f"metaniq@{__version__}"
    except Exception:  # noqa: BLE001
        return "metaniq@dev"


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

    # Inizializza Sentry (no-op se non configurato).
    _init_sentry()


def get_logger(name: str) -> logging.Logger:
    """Restituisce un logger figlio del root 'metaniq', configurato se necessario."""
    _setup_root()
    if not name.startswith("metaniq"):
        name = f"metaniq.{name}"
    return logging.getLogger(name)


__all__ = ["get_logger"]
