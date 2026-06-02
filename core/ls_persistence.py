# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/ls_persistence.py — Persistenza dati anagrafica + fornitori + LS.

UNI/TS 11567:2024 cap. 3 (Mass balance e tracciabilita') richiede che
i dati di un Lotto di Sostenibilita' siano riproducibili e conservati
per almeno 5 anni. Streamlit `session_state` e' volatile per design
(perso a refresh/sleep). Questo modulo offre:

  - `LSStore`: salva/legge anagrafica + suppliers + LS metadata in
    formato JSON nel file system locale.
  - `save_user_data(data, path) / load_user_data(path)`: helper.
  - Esporta/importa "dossier" JSON per backup off-app.

Privacy / GDPR
--------------
- Tutti i dati salvati sono dell'utente (ragione sociale, P.IVA, CUI,
  Responsabile Sostenibilita', fornitori). Non vengono trasmessi a
  servizi terzi.
- L'utente deve dare consenso esplicito prima del primo salvataggio
  (UI sidebar checkbox).
- Su Streamlit Cloud il filesystem e' EPHEMERAL: il salvataggio dura
  fino al prossimo rebuild del container. Per persistenza vera offrire
  download del JSON come backup off-app.
- Default storage path: directory `.metaniq_ls_data/` accanto a
  app_mensile.py. Override via env `METANIQ_LS_DATA_DIR`.

Schema dossier
--------------
{
  "schema_version": 1,
  "saved_at": "2026-05-28T17:55:00",
  "company": {
    "name": str, "vat": str, "legal_address": str,
  },
  "plant": {
    "name": str, "cui": str, "operational_address": str,
  },
  "responsible": {
    "name": str,
  },
  "suppliers": [
    {"name": str, "vat": str, "feedstock": str, "tons_per_month": float,
     "contract_ref": str, "ddt_ref": str, "baseline_storage": str},
    ...
  ],
  "ls_history": [
    {"ls_id": "LS-YYYY-MM-XXXXXX", "year": int, "month": int,
     "biomass_total_t": float, "saving_pct": float, "compliant": bool},
    ...
  ]
}
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_DIR_NAME = ".metaniq_ls_data"


def _resolve_storage_dir(override: str | os.PathLike | None = None) -> Path:
    """Determina la directory di storage. Crea se assente."""
    if override:
        p = Path(override)
    else:
        env = os.environ.get("METANIQ_LS_DATA_DIR")
        if env:
            p = Path(env)
        else:
            p = Path.cwd() / DEFAULT_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def _empty_dossier() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "saved_at": "",
        "company": {"name": "", "vat": "", "legal_address": ""},
        "plant": {"name": "", "cui": "", "operational_address": ""},
        "responsible": {"name": ""},
        "suppliers": [],
        "ls_history": [],
    }


def save_dossier(data: dict[str, Any], path: str | os.PathLike) -> Path:
    """Salva il dossier su file JSON. Idempotente. Aggiorna saved_at."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = dict(data)
    out["schema_version"] = SCHEMA_VERSION
    out["saved_at"] = datetime.now().isoformat(timespec="seconds")
    with p.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return p


def load_dossier(path: str | os.PathLike) -> dict[str, Any]:
    """Legge il dossier; se file assente o invalido ritorna dossier vuoto."""
    p = Path(path)
    if not p.is_file():
        return _empty_dossier()
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_dossier()
    # Schema migration placeholder
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        # Per ora schema unico; future versioni possono migrare qui.
        pass
    # Defensive defaults
    base = _empty_dossier()
    base.update(data)
    base.setdefault("company", {"name": "", "vat": "", "legal_address": ""})
    base.setdefault("plant", {"name": "", "cui": "", "operational_address": ""})
    base.setdefault("responsible", {"name": ""})
    base.setdefault("suppliers", [])
    base.setdefault("ls_history", [])
    return base


def default_dossier_path(plant_cui: str = "", company_vat: str = "") -> Path:
    """File di default per il dossier dell'utente.

    Usa il CUI come chiave (preferito), fallback su VAT, fallback su 'default'.
    """
    storage = _resolve_storage_dir()
    if plant_cui.strip():
        token = plant_cui.strip().replace("/", "_").replace(" ", "_")
    elif company_vat.strip():
        token = company_vat.strip().replace("/", "_").replace(" ", "_")
    else:
        token = "default"
    return storage / f"dossier_{token}.json"


def build_dossier_from_session(session_data: dict[str, Any]) -> dict[str, Any]:
    """Costruisce dossier-ready dict a partire dai campi st.session_state.

    `session_data` deve contenere le chiavi tipiche dell'app Metan.iQ:
    company_name, company_vat, company_legal_address, plant_name,
    plant_cui, plant_operational_address, responsible_name,
    suppliers_registry (list), ls_history (list).
    """
    d = _empty_dossier()
    d["company"] = {
        "name":          session_data.get("company_name", ""),
        "vat":           session_data.get("company_vat", ""),
        "legal_address": session_data.get("company_legal_address", ""),
    }
    d["plant"] = {
        "name":                session_data.get("plant_name", ""),
        "cui":                 session_data.get("plant_cui", ""),
        "operational_address": session_data.get("plant_operational_address", ""),
    }
    d["responsible"] = {
        "name": session_data.get("responsible_name", ""),
    }
    sup = session_data.get("suppliers_registry") or []
    if isinstance(sup, list):
        d["suppliers"] = [dict(s) for s in sup if isinstance(s, dict)]
    hist = session_data.get("ls_history") or []
    if isinstance(hist, list):
        d["ls_history"] = [dict(h) for h in hist if isinstance(h, dict)]
    return d


def apply_dossier_to_session(dossier: dict[str, Any]) -> dict[str, Any]:
    """Genera dict piatto compatibile con st.session_state.update()."""
    out: dict[str, Any] = {}
    c = dossier.get("company") or {}
    p = dossier.get("plant") or {}
    r = dossier.get("responsible") or {}
    out["company_name"]              = c.get("name", "")
    out["company_vat"]               = c.get("vat", "")
    out["company_legal_address"]     = c.get("legal_address", "")
    out["plant_name"]                = p.get("name", "")
    out["plant_cui"]                 = p.get("cui", "")
    out["plant_operational_address"] = p.get("operational_address", "")
    out["responsible_name"]          = r.get("name", "")
    out["suppliers_registry"]        = list(dossier.get("suppliers") or [])
    out["ls_history"]                = list(dossier.get("ls_history") or [])
    return out


def dossier_to_json_bytes(dossier: dict[str, Any]) -> bytes:
    """Serializza dossier in bytes UTF-8 (per download Streamlit)."""
    return json.dumps(dossier, ensure_ascii=False, indent=2).encode("utf-8")


def json_bytes_to_dossier(payload: bytes | str) -> dict[str, Any]:
    """Parsea bytes/string JSON. Valida schema_version; ritorna dossier completo."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Dossier non valido: root non e' dict")
    if data.get("schema_version") not in (SCHEMA_VERSION, None):
        # Future schema migration entry point.
        pass
    base = _empty_dossier()
    base.update(data)
    return base


__all__ = [
    "SCHEMA_VERSION",
    "save_dossier",
    "load_dossier",
    "default_dossier_path",
    "build_dossier_from_session",
    "apply_dossier_to_session",
    "dossier_to_json_bytes",
    "json_bytes_to_dossier",
]
