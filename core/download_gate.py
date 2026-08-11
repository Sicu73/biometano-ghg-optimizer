# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/download_gate.py — Identificazione richiesta per scaricare i report.

Modello scelto: **app aperta, report identificati**. Chiunque puo' usare il
simulatore; per portarsi via un deliverable (PDF, Excel, PPTX, dossier OdC)
si lasciano nome, email e azienda. Chi ha un interesse reale si identifica,
il curioso guarda e basta.

Perche' NON un account con password: su Streamlit Community Cloud il
filesystem e' effimero, quindi la tabella utenti di `core/auth.py` si azzera
a ogni riciclo del container. Un utente che si registra oggi non riuscirebbe
piu' ad accedere domani. Il form di contatto ottiene lo stesso risultato
(sapere chi scarica) senza promettere una persistenza che l'infrastruttura
non garantisce.

Dove finiscono i contatti, in ordine di affidabilita':

  1. webhook   ``st.secrets["leads"]["webhook_url"]`` -> POST JSON. Funziona
               con Zapier, Make, n8n, Discord, Slack, un bot Telegram...
  2. Supabase  ``st.secrets["leads"]["supabase_url"]`` + ``["service_key"]``
  3. SQLite    via ``core.leads.log_lead`` — best effort, si perde al riciclo

Senza almeno uno dei primi due i contatti raccolti vengono persi al riavvio
del container: il gate continua a funzionare, ma il dato non ti raggiunge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from core.logging_setup import get_logger

_LOG = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_TIMEOUT_S = 4.0

# chiavi di sessione
_SS_UNLOCKED = "_dl_unlocked"
_SS_IDENTITY = "_dl_identity"


@dataclass
class Identity:
    name: str
    email: str
    company: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "email": self.email, "company": self.company}


# ============================================================================
# CONFIGURAZIONE
# ============================================================================
def _secrets(section: str) -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get(section, {}) or {})
    except Exception:
        return {}


def gate_enabled() -> bool:
    """Attivo di default. Si disattiva con [auth] gate_downloads = false."""
    val = _secrets("auth").get("gate_downloads", True)
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() not in ("0", "false", "no", "off")


# ============================================================================
# STATO DI SESSIONE
# ============================================================================
def _session():
    import streamlit as st
    return st.session_state


def is_unlocked() -> bool:
    """True se l'utente si e' gia' identificato, o se il gate e' disattivo.

    Vale anche l'utente autenticato con `core.auth`, quando l'auth e' attiva.
    """
    if not gate_enabled():
        return True
    try:
        if _session().get(_SS_UNLOCKED):
            return True
    except Exception:
        return True    # fuori da Streamlit non si blocca nulla
    try:
        from core.auth import current_user
        if current_user() is not None:
            return True
    except Exception:
        pass
    return False


def current_identity() -> Identity | None:
    try:
        data = _session().get(_SS_IDENTITY)
    except Exception:
        return None
    return Identity(**data) if isinstance(data, dict) else None


def validate(name: str, email: str) -> str | None:
    """Ritorna il messaggio d'errore, o None se i dati vanno bene."""
    if not (name or "").strip():
        return "Inserisci nome e cognome."
    if not (email or "").strip():
        return "Inserisci un'email."
    if not _EMAIL_RE.match((email or "").strip()):
        return "L'email non sembra valida."
    return None


# ============================================================================
# RECAPITO DEI CONTATTI
# ============================================================================
def _is_discord(url: str) -> bool:
    return "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url


def _discord_payload(payload: dict) -> dict:
    """Discord non accetta JSON arbitrario: vuole `content` o `embeds`.

    Si costruisce un embed leggibile nel canale, con i colori del brand.
    """
    fields = [
        {"name": "Nome", "value": payload.get("name") or "—", "inline": True},
        {"name": "Email", "value": payload.get("email") or "—", "inline": True},
        {"name": "Azienda / Impianto",
         "value": payload.get("company") or "—", "inline": False},
        {"name": "Documento",
         "value": payload.get("document") or "—", "inline": False},
    ]
    return {
        "username": "Metan.iQ",
        "embeds": [{
            "title": "📥 Nuovo download report",
            "color": 0xF59E0B,          # amber del brand
            "fields": fields,
            "timestamp": payload.get("created_at"),
            "footer": {"text": "metaniq · download_gate"},
        }],
    }


def _post_webhook(payload: dict) -> bool:
    url = str(_secrets("leads").get("webhook_url", "") or "").strip()
    if not url:
        return False
    body = _discord_payload(payload) if _is_discord(url) else payload
    try:
        import requests
        r = requests.post(url, json=body, timeout=_TIMEOUT_S)
        return r.status_code < 300
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("download_gate: webhook fallito (%s)", exc)
        return False


def _post_supabase(payload: dict) -> bool:
    cfg = _secrets("leads")
    url = str(cfg.get("supabase_url", "") or "").strip()
    key = str(cfg.get("service_key", "") or "").strip()
    if not (url and key):
        return False
    try:
        import requests
        r = requests.post(
            url.rstrip("/") + "/rest/v1/leads",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal"},
            json=payload,
            timeout=_TIMEOUT_S,
        )
        return r.status_code < 300
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("download_gate: supabase lead fallito (%s)", exc)
        return False


def deliver(identity: Identity, document: str) -> dict:
    """Recapita il contatto su tutti i canali configurati.

    Ritorna quali hanno funzionato: serve a distinguere "raccolto ma
    volatile" da "raccolto e recapitato".
    """
    payload = {
        **identity.as_dict(),
        "document": document,
        "source": "download_gate",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out = {
        "webhook": _post_webhook(payload),
        "supabase": _post_supabase(payload),
        "sqlite": False,
    }
    try:
        from core import leads
        out["sqlite"] = bool(leads.log_lead(
            name=identity.name, email=identity.email, company=identity.company,
            message=f"Download: {document}", source="download_gate",
        ))
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("download_gate: log locale fallito (%s)", exc)
    out["persisted"] = out["webhook"] or out["supabase"]
    return out


def unlock(name: str, email: str, company: str = "", document: str = "") -> tuple[bool, str]:
    """Valida, recapita il contatto e sblocca i download della sessione."""
    err = validate(name, email)
    if err:
        return False, err
    ident = Identity(name.strip(), email.strip(), (company or "").strip())
    deliver(ident, document or "n/d")
    try:
        _session()[_SS_UNLOCKED] = True
        _session()[_SS_IDENTITY] = ident.as_dict()
    except Exception:
        pass
    return True, ""


__all__ = [
    "Identity",
    "gate_enabled",
    "is_unlocked",
    "current_identity",
    "validate",
    "deliver",
    "unlock",
]
