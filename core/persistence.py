# -*- coding: utf-8 -*-
"""core/persistence.py — Persistenza SQLite per la gestione giornaliera.

Salva e ricarica i dati operativi mese-per-mese in un database SQLite
locale. Schema:
  - daily_entries(plant_id, date, feedstock_type, qty_t, notes, updated_at)
  - month_meta(plant_id, year, month, regime, threshold, saved_at)

NB: il file DB NON va committato (vedi .gitignore -> data/*.db).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timezone
from typing import Iterable

from core.daily_model import DailyEntry


_DEFAULT_DB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data")
)
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "metaniq_daily.db")


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _connect(path: str) -> sqlite3.Connection:
    _ensure_dir(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(path: str | None = None) -> str:
    """Inizializza lo schema (idempotente). Ritorna il path effettivo."""
    db_path = path or _DEFAULT_DB_PATH
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_entries (
                plant_id        TEXT NOT NULL,
                date            TEXT NOT NULL,
                feedstock_type  TEXT NOT NULL,
                qty_t           REAL NOT NULL,
                notes           TEXT DEFAULT '',
                updated_at      TEXT NOT NULL,
                PRIMARY KEY (plant_id, date, feedstock_type)
            );
            CREATE TABLE IF NOT EXISTS month_meta (
                plant_id        TEXT NOT NULL,
                year            INTEGER NOT NULL,
                month           INTEGER NOT NULL,
                regime          TEXT DEFAULT '',
                threshold       REAL DEFAULT 0,
                saved_at        TEXT NOT NULL,
                PRIMARY KEY (plant_id, year, month)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_plant_date
                ON daily_entries (plant_id, date);
            """
        )
        conn.commit()
    return db_path


def save_month(year: int, month: int, daily_entries: list[DailyEntry],
               plant_id: str = "default", regime: str = "",
               threshold: float = 0.0, path: str | None = None) -> int:
    """Salva (overwrite) tutti i giorni del mese specificato.

    Cancella prima i record del mese per `plant_id` e poi reinserisce
    le nuove righe (operazione idempotente). Ritorna il numero di righe
    inserite (escludendo entry con quantita' nulle).
    """
    db_path = init_db(path)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inserted = 0
    with _connect(db_path) as conn:
        # Pulizia mese
        first = f"{year:04d}-{month:02d}-01"
        last_day = 31  # over-cover
        last = f"{year:04d}-{month:02d}-{last_day:02d}"
        conn.execute(
            "DELETE FROM daily_entries WHERE plant_id = ? "
            "AND date >= ? AND date <= ?",
            (plant_id, first, last),
        )
        for entry in (daily_entries or []):
            d_iso = entry.date.isoformat()
            for fname, qty in (entry.feedstocks or {}).items():
                if qty is None:
                    continue
                try:
                    qv = float(qty)
                except (TypeError, ValueError):
                    continue
                if qv <= 0:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO daily_entries "
                    "(plant_id, date, feedstock_type, qty_t, notes, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (plant_id, d_iso, str(fname), qv,
                     str(entry.notes or ""), now_iso),
                )
                inserted += 1
        conn.execute(
            "INSERT OR REPLACE INTO month_meta "
            "(plant_id, year, month, regime, threshold, saved_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (plant_id, int(year), int(month), str(regime or ""),
             float(threshold or 0.0), now_iso),
        )
        conn.commit()
    return inserted


def load_month(year: int, month: int, plant_id: str = "default",
               path: str | None = None) -> list[DailyEntry]:
    """Carica tutti i giorni del mese (anche giorni mancanti tornano vuoti)."""
    db_path = init_db(path)
    first = f"{year:04d}-{month:02d}-01"
    last = f"{year:04d}-{month:02d}-31"
    rows: dict[str, dict[str, float]] = {}
    notes_by_day: dict[str, str] = {}
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT date, feedstock_type, qty_t, notes "
            "FROM daily_entries WHERE plant_id = ? "
            "AND date >= ? AND date <= ? "
            "ORDER BY date, feedstock_type",
            (plant_id, first, last),
        )
        for d_iso, fname, qty, notes in cur.fetchall():
            d_map = rows.setdefault(d_iso, {})
            d_map[str(fname)] = float(qty)
            if notes:
                notes_by_day[d_iso] = str(notes)

    entries: list[DailyEntry] = []
    for d_iso in sorted(rows.keys()):
        try:
            d_obj = date.fromisoformat(d_iso)
        except ValueError:
            continue
        entries.append(DailyEntry(
            date=d_obj,
            feedstocks=rows[d_iso],
            notes=notes_by_day.get(d_iso, ""),
        ))
    return entries


def list_saved_months(plant_id: str = "default",
                      path: str | None = None) -> list[tuple[int, int]]:
    """Elenca i mesi salvati per il `plant_id` (ordine cronologico)."""
    db_path = init_db(path)
    out: list[tuple[int, int]] = []
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT year, month FROM month_meta WHERE plant_id = ? "
            "ORDER BY year, month",
            (plant_id,),
        )
        out = [(int(y), int(m)) for (y, m) in cur.fetchall()]
    return out


def delete_month(year: int, month: int, plant_id: str = "default",
                 path: str | None = None) -> int:
    """Elimina i dati del mese per il `plant_id`. Ritorna righe cancellate."""
    db_path = init_db(path)
    first = f"{year:04d}-{month:02d}-01"
    last = f"{year:04d}-{month:02d}-31"
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM daily_entries WHERE plant_id = ? "
            "AND date >= ? AND date <= ?",
            (plant_id, first, last),
        )
        n = cur.rowcount
        conn.execute(
            "DELETE FROM month_meta WHERE plant_id = ? "
            "AND year = ? AND month = ?",
            (plant_id, int(year), int(month)),
        )
        conn.commit()
    return int(n or 0)


__all__ = [
    "init_db",
    "save_month",
    "load_month",
    "list_saved_months",
    "delete_month",
]
