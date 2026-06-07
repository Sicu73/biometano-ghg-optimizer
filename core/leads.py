# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/leads.py — Cattura lead "Richiedi una demo".

Funnel marketing: registra le richieste di contatto generate dalla CTA
in-app. Scrive su SQLite (best-effort) e fornisce un helper per costruire
un link `mailto:` precompilato verso il titolare.

NOTA OPERATIVA (Streamlit Cloud):
  Il filesystem dell'app è effimero: il DB SQLite si azzera ad ogni
  reboot/redeploy. Il log su SQLite è quindi un BEST-EFFORT utile solo in
  locale o tra un redeploy e l'altro. Il canale di recapito affidabile è il
  link `mailto:` (build_mailto), che apre il client email del prospect e
  recapita la richiesta a CONTACT_EMAIL indipendentemente dal DB.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import quote

CONTACT_EMAIL = "carlo.sicurini@gmail.com"

_DEFAULT_DB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data")
)
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "metaniq_daily.db")


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def init_leads_table(path: str | None = None) -> str:
    """Crea la tabella `leads` se assente (idempotente). Ritorna il path."""
    db_path = path or _DEFAULT_DB_PATH
    _ensure_dir(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                name        TEXT DEFAULT '',
                email       TEXT DEFAULT '',
                company     TEXT DEFAULT '',
                message     TEXT DEFAULT '',
                source      TEXT DEFAULT 'in_app_cta'
            );
            """
        )
        conn.commit()
    return db_path


def log_lead(
    name: str = "",
    email: str = "",
    company: str = "",
    message: str = "",
    source: str = "in_app_cta",
    path: str | None = None,
) -> bool:
    """Registra un lead su SQLite (best-effort).

    Ritorna True se la scrittura è andata a buon fine, False altrimenti.
    Non solleva mai: la CTA non deve rompere l'app per un errore di I/O.
    """
    try:
        db_path = init_leads_table(path)
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO leads "
                "(created_at, name, email, company, message, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now_iso, name.strip(), email.strip(), company.strip(),
                 message.strip(), source),
            )
            conn.commit()
        return True
    except Exception:  # noqa: BLE001 — best-effort, mai propagare
        return False


def build_mailto(
    name: str = "",
    email: str = "",
    company: str = "",
    message: str = "",
    to: str = CONTACT_EMAIL,
) -> str:
    """Costruisce un link `mailto:` precompilato verso il titolare.

    Canale di recapito affidabile, indipendente dal DB effimero.
    """
    subject = "Richiesta demo Metan.iQ"
    if company.strip():
        subject += f" — {company.strip()}"
    body_lines = [
        "Richiesta inviata dalla demo live Metan.iQ.",
        "",
        f"Nome: {name.strip()}",
        f"Email: {email.strip()}",
        f"Azienda/Impianto: {company.strip()}",
        "",
        "Messaggio:",
        message.strip(),
    ]
    body = "\n".join(body_lines)
    return f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"


