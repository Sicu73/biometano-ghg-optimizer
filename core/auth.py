# -*- coding: utf-8 -*-
"""core/auth.py — Sistema utenti (Fase 2 — SCAFFOLDING).

⚠️ NON ANCORA IMPLEMENTATO. Questo modulo è uno scheletro per la Fase 2 del
piano SaaS (vedi `~/.claude/plans/continua-il-lavoro-su-sunny-rainbow.md`).

API target (da implementare):
  signup(email, password, company) -> User
  login(email, password) -> str (JWT token)
  logout()
  current_user() -> User | None
  require_auth(fn) -> decorator
  reset_password(email)
  change_password(user_id, old, new)
  delete_account(user_id)

Stack tecnico scelto:
  - **Storage utenti**: PostgreSQL (Supabase free tier o Neon)
  - **Hashing**: argon2-cffi (più sicuro di bcrypt)
  - **Session**: cookie httpOnly + JWT firmato con HS256 (secret in st.secrets)
  - **Email transactional**: SMTP (Gmail/SendGrid) con template HTML
  - **MFA opzionale**: TOTP con pyotp (Fase 4)

Schema DB minimo (`users` tabella):
  id              UUID PK
  email           TEXT UNIQUE NOT NULL
  password_hash   TEXT NOT NULL
  full_name       TEXT
  company         TEXT
  vat_number      TEXT          -- Partita IVA per fatturazione B2B IT
  tenant_id       UUID NOT NULL -- isolation multi-tenant
  role            TEXT NOT NULL DEFAULT 'editor' -- admin|editor|viewer
  plan            TEXT NOT NULL DEFAULT 'free'   -- free|pro|enterprise
  trial_ends_at   TIMESTAMP
  stripe_customer_id  TEXT
  stripe_subscription_id  TEXT
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
  last_login_at   TIMESTAMP
  email_verified  BOOLEAN NOT NULL DEFAULT FALSE
  is_active       BOOLEAN NOT NULL DEFAULT TRUE
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    """Rappresentazione utente in-memory (carica da DB)."""
    id: str
    email: str
    full_name: str | None
    company: str | None
    tenant_id: str
    role: str = "editor"
    plan: str = "free"
    is_active: bool = True


def signup(email: str, password: str, company: str | None = None,
           full_name: str | None = None) -> User:
    """Crea nuovo utente. Trial Pro 14 gg automatico."""
    raise NotImplementedError("Fase 2 — TODO: integrazione DB + hashing argon2")


def login(email: str, password: str) -> str:
    """Verifica credenziali, restituisce JWT token. Aggiorna last_login_at."""
    raise NotImplementedError("Fase 2 — TODO: verifica hash, emetti JWT")


def logout() -> None:
    """Invalida sessione corrente."""
    raise NotImplementedError("Fase 2 — TODO: clear session cookie")


def current_user() -> User | None:
    """Restituisce utente loggato dal session_state Streamlit, o None."""
    try:
        import streamlit as st
        return st.session_state.get("_user")
    except Exception:  # noqa: BLE001
        return None


def require_auth(fn):
    """Decorator: redirect a /login se utente non autenticato."""
    raise NotImplementedError("Fase 2 — TODO")


def reset_password_request(email: str) -> None:
    """Invia email con link reset password (token TTL 1h)."""
    raise NotImplementedError("Fase 2 — TODO: SMTP + token")


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """Cambia password verificando la precedente."""
    raise NotImplementedError("Fase 2 — TODO")


def delete_account(user_id: str, hard: bool = False) -> None:
    """Soft-delete (default) o hard-delete (GDPR right to be forgotten)."""
    raise NotImplementedError("Fase 2 — TODO")


__all__ = [
    "User",
    "signup",
    "login",
    "logout",
    "current_user",
    "require_auth",
    "reset_password_request",
    "change_password",
    "delete_account",
]
