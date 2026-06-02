# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/billing.py — Stripe billing wrapper (Fase 2.3 IMPLEMENTATA).

Sicurezza: nessuna chiamata Stripe se `secret_key` non è configurata in
`st.secrets["stripe"]["secret_key"]`. L'app funziona normalmente senza Stripe
(piano gratis di default per tutti).

Piani definiti in `legal/PRICING.md`:
  - free: 1 impianto, 10 mesi storia, export con watermark
  - pro: 49€/mese o 490€/anno
  - enterprise: 199€/mese o 1.990€/anno

API:
  is_configured() -> bool
  start_checkout(user, plan, cycle) -> str (URL Stripe Checkout)
  open_customer_portal(user) -> str (URL Stripe Portal)
  handle_webhook(payload, signature) -> dict (evento processato)
  cancel_subscription(user)
  get_subscription_status(user) -> dict
  feature_enabled(user, feature) -> bool

Per attivare:
1. Crea account Stripe → Dashboard → API keys → copia Secret key
2. Crea 4 prezzi su Stripe Dashboard → Products:
   - Pro Monthly  49€/mese
   - Pro Yearly   490€/anno
   - Enterprise Monthly  199€/mese
   - Enterprise Yearly   1990€/anno
3. Crea webhook endpoint → copia signing secret
4. Streamlit Cloud Secrets:
   [stripe]
   secret_key = "sk_live_..."
   publishable_key = "pk_live_..."
   webhook_secret = "whsec_..."
   price_pro_monthly = "price_xxx"
   price_pro_yearly = "price_xxx"
   price_enterprise_monthly = "price_xxx"
   price_enterprise_yearly = "price_xxx"
"""
from __future__ import annotations

from typing import Literal

Plan = Literal["free", "pro", "enterprise"]
BillingCycle = Literal["monthly", "yearly"]


# Feature gates per piano (single source of truth — usata nel codice app
# per gate condizionali: `if feature_enabled(user, 'lp_optimizer'): ...`)
PLAN_FEATURES: dict[Plan, set[str]] = {
    "free": {
        "basic_kpis", "daily_input", "monthly_calc",
    },
    "pro": {
        "basic_kpis", "daily_input", "monthly_calc",
        "unlimited_history", "all_exports", "bmt_override",
        "emission_override", "lp_optimizer", "business_plan",
        "comparison_standard_analysis", "audit_log_view", "email_support",
    },
    "enterprise": {
        "basic_kpis", "daily_input", "monthly_calc",
        "unlimited_history", "all_exports", "bmt_override",
        "emission_override", "lp_optimizer", "business_plan",
        "comparison_standard_analysis", "audit_log_view", "email_support",
        "multi_plant", "multi_user", "api_rest", "webhooks",
        "white_label", "sla_995", "priority_support",
    },
}


# ============================================================================
# CONFIG ACCESS (graceful)
# ============================================================================
def _cfg() -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get("stripe", {}))
    except Exception:
        return {}


def is_configured() -> bool:
    """True se la secret_key Stripe è settata e non vuota."""
    return bool(_cfg().get("secret_key"))


def _stripe():
    """Restituisce il modulo stripe configurato, o solleva RuntimeError."""
    if not is_configured():
        raise RuntimeError("Stripe non configurato. Vedi core/billing.py docstring.")
    import stripe as stripe_mod
    stripe_mod.api_key = _cfg()["secret_key"]
    return stripe_mod


def _price_id(plan: Plan, cycle: BillingCycle) -> str:
    if plan == "free":
        raise ValueError("Free plan non ha price_id")
    key = f"price_{plan}_{cycle}"
    pid = _cfg().get(key)
    if not pid:
        raise ValueError(f"Manca {key} nei secrets Stripe")
    return str(pid)


# ============================================================================
# FEATURE GATES
# ============================================================================
def feature_enabled(user, feature: str) -> bool:
    """True se il piano dell'utente include la feature."""
    if user is None:
        return False
    plan: Plan = getattr(user, "plan", "free")
    # In trial Pro automatico anche se plan='pro_trial' o similari
    if str(plan).startswith("pro"):
        plan = "pro"
    elif str(plan).startswith("enterprise"):
        plan = "enterprise"
    else:
        plan = "free"
    return feature in PLAN_FEATURES.get(plan, set())


# ============================================================================
# CHECKOUT FLOW
# ============================================================================
def start_checkout(user, plan: Plan, cycle: BillingCycle = "monthly",
                    success_url: str = "", cancel_url: str = "") -> str:
    """Crea sessione Stripe Checkout. Restituisce URL di redirect."""
    if plan == "free":
        raise ValueError("Free plan non richiede checkout")
    stripe = _stripe()
    price_id = _price_id(plan, cycle)
    # Riusa stripe_customer_id se esiste, altrimenti crea
    customer_id = getattr(user, "stripe_customer_id", None)
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or "",
            metadata={"user_id": user.id, "tenant_id": user.tenant_id},
        )
        customer_id = customer.id
        _persist_customer_id(user.id, customer_id)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url or "https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/?checkout=success",
        cancel_url=cancel_url or "https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/?checkout=cancel",
        metadata={"user_id": user.id, "tenant_id": user.tenant_id, "plan": plan},
        subscription_data={
            "metadata": {"user_id": user.id, "tenant_id": user.tenant_id, "plan": plan},
        },
        allow_promotion_codes=True,
    )
    try:
        from core.audit import log as audit_log
        audit_log("subscription_checkout_started", user_id=user.id,
                  tenant_id=user.tenant_id,
                  payload={"plan": plan, "cycle": cycle, "session_id": session.id})
    except Exception:
        pass
    return session.url


def open_customer_portal(user, return_url: str = "") -> str:
    """URL Stripe Customer Portal per gestione abbonamento."""
    if not getattr(user, "stripe_customer_id", None):
        raise ValueError("Utente senza stripe_customer_id (mai sottoscritto)")
    stripe = _stripe()
    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url or "https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/",
    )
    return portal.url


# ============================================================================
# WEBHOOK HANDLER
# ============================================================================
def handle_webhook(payload: bytes, signature: str) -> dict:
    """Verifica firma e dispatcha evento Stripe.

    Da chiamare da un endpoint HTTP POST (FastAPI sidecar per Fase 4, o
    Streamlit query_params hack come fallback).
    """
    if not is_configured():
        raise RuntimeError("Stripe non configurato")
    import stripe as stripe_mod
    stripe_mod.api_key = _cfg()["secret_key"]
    secret = _cfg().get("webhook_secret")
    if not secret:
        raise ValueError("webhook_secret mancante nei secrets")
    try:
        event = stripe_mod.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        raise ValueError(f"Webhook signature non valida: {exc}")

    et = event["type"]
    data = event["data"]["object"]
    if et == "checkout.session.completed":
        _on_checkout_completed(data)
    elif et in ("customer.subscription.created",
                 "customer.subscription.updated"):
        _on_subscription_change(data)
    elif et == "customer.subscription.deleted":
        _on_subscription_deleted(data)
    elif et == "invoice.payment_succeeded":
        _on_payment_succeeded(data)
    elif et == "invoice.payment_failed":
        _on_payment_failed(data)

    try:
        from core.audit import log as audit_log
        audit_log(f"stripe.{et}",
                  resource_type="stripe_event",
                  resource_id=event.get("id"),
                  payload={"type": et})
    except Exception:
        pass

    return {"received": True, "type": et, "id": event.get("id")}


# ============================================================================
# WEBHOOK HANDLERS (privati)
# ============================================================================
def _on_checkout_completed(session) -> None:
    user_id = (session.get("metadata") or {}).get("user_id")
    plan = (session.get("metadata") or {}).get("plan", "pro")
    sub_id = session.get("subscription")
    if user_id:
        _update_user_plan(user_id, plan=plan, subscription_id=sub_id,
                           trial_ends_at=None)


def _on_subscription_change(sub) -> None:
    user_id = (sub.get("metadata") or {}).get("user_id")
    status = sub.get("status")
    # status valori Stripe: trialing, active, past_due, canceled, unpaid, ...
    if status in ("canceled", "unpaid"):
        new_plan = "free"
    else:
        new_plan = (sub.get("metadata") or {}).get("plan", "pro")
    if user_id:
        _update_user_plan(user_id, plan=new_plan, subscription_id=sub.get("id"))


def _on_subscription_deleted(sub) -> None:
    user_id = (sub.get("metadata") or {}).get("user_id")
    if user_id:
        _update_user_plan(user_id, plan="free", subscription_id=None)


def _on_payment_succeeded(invoice) -> None:
    # Solo audit (no state change — la subscription_updated gestisce il rinnovo)
    pass


def _on_payment_failed(invoice) -> None:
    # TODO: inviare email all'utente per aggiornare carta. Grace period 7gg.
    pass


# ============================================================================
# DB HELPERS (SQLite via core.auth)
# ============================================================================
def _persist_customer_id(user_id: str, customer_id: str) -> None:
    try:
        from core import auth
        with auth._conn() as c:  # noqa: SLF001
            c.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                       (customer_id, user_id))
    except Exception:
        pass


def _update_user_plan(user_id: str, *,
                       plan: str | None = None,
                       subscription_id: str | None = "__NOCHANGE__",
                       trial_ends_at: str | None = "__NOCHANGE__") -> None:
    try:
        from core import auth
        sets = []
        params: list = []
        if plan is not None:
            sets.append("plan = ?")
            params.append(plan)
        if subscription_id != "__NOCHANGE__":
            sets.append("stripe_subscription_id = ?")
            params.append(subscription_id)
        if trial_ends_at != "__NOCHANGE__":
            sets.append("trial_ends_at = ?")
            params.append(trial_ends_at)
        if not sets:
            return
        params.append(user_id)
        with auth._conn() as c:  # noqa: SLF001
            c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
    except Exception:
        pass


# ============================================================================
# STATUS
# ============================================================================
def get_subscription_status(user) -> dict:
    """Stato abbonamento sintetico, OK anche senza Stripe."""
    plan = getattr(user, "plan", "free")
    trial_ends = getattr(user, "trial_ends_at", None)
    sub_id = getattr(user, "stripe_subscription_id", None)
    return {
        "plan": plan,
        "trial_ends_at": trial_ends,
        "subscription_id": sub_id,
        "stripe_configured": is_configured(),
    }


def cancel_subscription(user) -> None:
    """Cancella abbonamento alla fine del periodo già pagato."""
    if not getattr(user, "stripe_subscription_id", None):
        return
    stripe = _stripe()
    stripe.Subscription.modify(user.stripe_subscription_id,
                                cancel_at_period_end=True)
    try:
        from core.audit import log as audit_log
        audit_log("subscription_cancellation_requested", user_id=user.id,
                  tenant_id=user.tenant_id,
                  payload={"subscription_id": user.stripe_subscription_id})
    except Exception:
        pass


__all__ = [
    "Plan", "BillingCycle", "PLAN_FEATURES",
    "is_configured", "feature_enabled",
    "start_checkout", "open_customer_portal", "handle_webhook",
    "cancel_subscription", "get_subscription_status",
]
