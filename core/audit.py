# -*- coding: utf-8 -*-
"""core/audit.py — Audit log immutabile (Fase 2.5 — SCAFFOLDING).

⚠️ NON ANCORA IMPLEMENTATO. Scheletro per Fase 2.5 del piano SaaS.

Ogni azione critica viene registrata in tabella `audit_log` append-only,
mai modificata o cancellata. Utile per:
- GDPR (dimostrare trattamento corretto dei dati)
- Sicurezza (forensics in caso di account compromesso)
- Conformità (audit GSE può chiedere "chi ha modificato il dato il giorno X?")
- Customer support (debug problemi cliente)

Azioni tracciate:
  user_signup, user_login, user_logout, password_changed, password_reset_requested,
  email_verified, account_deleted,
  month_saved, month_loaded, month_deleted, month_reset, daily_edited,
  bmt_override_added, bmt_override_removed, ef_override_added, ef_override_removed,
  plant_renamed,
  pdf_exported, excel_exported, csv_exported, pptx_exported,
  subscription_started, subscription_cancelled, subscription_renewed,
  payment_succeeded, payment_failed,
  admin_action (con sub-type), api_key_created, api_key_revoked,
  gdpr_export_requested, gdpr_deletion_requested

Schema DB `audit_log`:
  id              UUID PK
  tenant_id       UUID NOT NULL (FK users.tenant_id) — per filtro multi-tenant
  user_id         UUID (FK users.id) — null per azioni di sistema
  action          TEXT NOT NULL — uno dei valori sopra
  resource_type   TEXT — "month", "user", "subscription", ...
  resource_id     TEXT — "2026-05", user_id target, ecc.
  payload         JSONB — dettagli (no PII pesanti, solo metadati)
  ip_address      INET
  user_agent      TEXT
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()

Indici raccomandati: (tenant_id, created_at DESC), (user_id, created_at DESC),
                     (action, created_at DESC).
"""
from __future__ import annotations

from typing import Any


def log(
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Registra un evento audit. Mai bloccante (silent failure su DB error)."""
    raise NotImplementedError("Fase 2.5 — TODO: INSERT INTO audit_log")


def query(
    tenant_id: str,
    *,
    user_id: str | None = None,
    action: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query log filtrabile (per UI admin / GDPR export)."""
    raise NotImplementedError("Fase 2.5 — TODO")


def export_user_log(user_id: str) -> bytes:
    """Esporta tutto il log di un utente in JSON (per GDPR right of access)."""
    raise NotImplementedError("Fase 2.5 — TODO")


__all__ = ["log", "query", "export_user_log"]
