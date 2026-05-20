# -*- coding: utf-8 -*-
"""core/billing.py — Wrapper Stripe per piani SaaS (Fase 2 — SCAFFOLDING).

⚠️ NON ANCORA IMPLEMENTATO. Scheletro per Fase 2.3 del piano SaaS.

Piani definiti in legal/PRICING.md:
  - free: 0€ — 1 impianto, 10 mesi storia, export con watermark
  - pro: 49€/mese o 490€/anno — 1 impianto illimitato, no watermark, ottimizzatore
  - enterprise: 199€/mese o 1.990€/anno — multi-impianto, API, SLA, white-label

API target:
  start_checkout(user, plan, billing_cycle) -> str (Stripe Checkout URL)
  handle_webhook(payload, signature) -> None
  open_customer_portal(user) -> str (Stripe Portal URL)
  cancel_subscription(user)
  get_subscription_status(user) -> dict
  feature_enabled(user, feature) -> bool

Stack:
  - stripe-python SDK
  - Stripe Checkout (no-code per UX semplice)
  - Webhook endpoint: POST /webhook/stripe (autenticato con signing secret)
  - Customer Portal Stripe per gestione abbonamento (no UI custom)

Eventi Stripe da gestire nel webhook:
  - checkout.session.completed       -> attiva piano user
  - invoice.payment_succeeded         -> estendi abbonamento
  - invoice.payment_failed            -> notifica + grace period 7gg
  - customer.subscription.deleted     -> downgrade a free
  - customer.subscription.updated     -> sync plan changes
"""
from __future__ import annotations

from typing import Literal

Plan = Literal["free", "pro", "enterprise"]
BillingCycle = Literal["monthly", "yearly"]

# Feature gates per piano (single source of truth)
PLAN_FEATURES: dict[Plan, set[str]] = {
    "free": {
        "basic_kpis",
        "daily_input",
        "monthly_calc",
    },
    "pro": {
        "basic_kpis",
        "daily_input",
        "monthly_calc",
        "unlimited_history",
        "all_exports",            # PDF/Excel/CSV/PPTX senza watermark
        "bmt_override",
        "emission_override",
        "lp_optimizer",
        "business_plan",
        "comparison_standard_analysis",
        "audit_log_view",
        "email_support",
    },
    "enterprise": {
        # tutto Pro +
        "basic_kpis",
        "daily_input",
        "monthly_calc",
        "unlimited_history",
        "all_exports",
        "bmt_override",
        "emission_override",
        "lp_optimizer",
        "business_plan",
        "comparison_standard_analysis",
        "audit_log_view",
        "email_support",
        # extra Enterprise:
        "multi_plant",
        "multi_user",
        "api_rest",
        "webhooks",
        "white_label",
        "sla_995",
        "priority_support",
    },
}


def feature_enabled(user, feature: str) -> bool:
    """True se il piano dell'utente include la feature richiesta."""
    if user is None:
        return False
    plan: Plan = getattr(user, "plan", "free")
    return feature in PLAN_FEATURES.get(plan, set())


def start_checkout(user, plan: Plan, cycle: BillingCycle = "monthly") -> str:
    """Crea sessione Stripe Checkout, restituisce URL di redirect."""
    raise NotImplementedError("Fase 2.3 — TODO: stripe.checkout.Session.create")


def open_customer_portal(user) -> str:
    """URL del Stripe Customer Portal per l'utente."""
    raise NotImplementedError("Fase 2.3 — TODO: stripe.billing_portal.Session.create")


def handle_webhook(payload: bytes, signature: str) -> None:
    """Endpoint webhook Stripe: verifica firma + dispatcha eventi."""
    raise NotImplementedError("Fase 2.3 — TODO: stripe.Webhook.construct_event")


def cancel_subscription(user) -> None:
    """Cancella subscription Stripe (al termine del periodo già pagato)."""
    raise NotImplementedError("Fase 2.3 — TODO")


def get_subscription_status(user) -> dict:
    """Dict con: plan, status, current_period_end, cancel_at_period_end."""
    raise NotImplementedError("Fase 2.3 — TODO")


__all__ = [
    "Plan",
    "BillingCycle",
    "PLAN_FEATURES",
    "feature_enabled",
    "start_checkout",
    "open_customer_portal",
    "handle_webhook",
    "cancel_subscription",
    "get_subscription_status",
]
