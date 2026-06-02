# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo@apros-ra.com
"""core/auth_ui.py — UI Streamlit per signup / login / account.

API:
  render_auth_gate() -> bool
      True se utente autenticato (o demo mode) → app può procedere.
      False se mostra form di login/signup → app deve fermarsi (st.stop()).

  render_account_widget()
      Widget account in sidebar (badge utente + logout) per utente loggato.
"""
from __future__ import annotations

import streamlit as st

from core import auth


def _login_form() -> bool:
    """Form login. True se login OK."""
    st.markdown("### 🔐 Accedi")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email", key="login_email")
        password = st.text_input("Password", type="password",
                                  autocomplete="current-password", key="login_pw")
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Accedi", type="primary",
                                                use_container_width=True)
        with col2:
            st.form_submit_button("Vai a Registrazione", use_container_width=True,
                                   on_click=lambda: st.session_state.update(
                                       {"_auth_view": "signup"}))
        if submitted:
            try:
                auth.login(email, password)
                st.success("Accesso effettuato ✓")
                st.rerun()
            except ValueError as exc:
                st.error(f"❌ {exc}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Errore: {exc}")
    return False


def _signup_form() -> bool:
    """Form signup."""
    st.markdown("### ✨ Crea account")
    st.caption("**14 giorni di trial gratuito** del piano Pro. Nessuna carta richiesta.")
    with st.form("signup_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Nome e cognome", key="signup_name")
        with col2:
            company = st.text_input("Azienda (opzionale)", key="signup_company")
        email = st.text_input("Email", autocomplete="email", key="signup_email")
        password = st.text_input("Password (min 8 char)", type="password",
                                  autocomplete="new-password", key="signup_pw")
        accept_terms = st.checkbox(
            "Accetto i [Termini di Servizio](legal/terms.md) e la "
            "[Privacy Policy](legal/privacy.md)",
            key="signup_accept",
        )
        col_a, col_b = st.columns([1, 1])
        with col_a:
            submitted = st.form_submit_button("Registrati", type="primary",
                                                use_container_width=True)
        with col_b:
            st.form_submit_button("Torna al Login", use_container_width=True,
                                   on_click=lambda: st.session_state.update(
                                       {"_auth_view": "login"}))
        if submitted:
            if not accept_terms:
                st.warning("Devi accettare Termini e Privacy per procedere.")
                return False
            try:
                user = auth.signup(email, password,
                                    full_name=full_name or None,
                                    company=company or None)
                auth.login(email, password)
                st.success(f"Benvenuto/a {user.full_name or user.email}! "
                            "Trial Pro attivo per 14 giorni.")
                st.rerun()
            except ValueError as exc:
                st.error(f"❌ {exc}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Errore: {exc}")
    return False


def render_auth_gate() -> bool:
    """Gate principale.

    Returns:
        True  → utente autenticato o demo_mode attivo → app continua
        False → form mostrato, app deve fare st.stop()
    """
    # Demo mode: bypass totale (default in dev)
    if auth.is_demo_mode():
        return True
    # Già autenticato
    if auth.current_user() is not None:
        return True

    # Layout centered del gate
    st.markdown(
        """
        <style>
        section.main > div.block-container {
            max-width: 480px;
            padding-top: 4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align:center;margin-bottom:24px;">'
        '<div style="font-size:0.72rem;font-weight:700;letter-spacing:2px;'
        'text-transform:uppercase;color:#F59E0B;margin-bottom:4px;">// PLATFORM</div>'
        '<div style="font-size:2.2rem;font-weight:800;color:#0F1F33;">'
        'Metan<span style="color:#F59E0B;">.</span>iQ</div>'
        '<div style="font-size:0.85rem;color:#64748B;margin-top:4px;">'
        'Decision Intelligence Platform · Biometano DM 2022 / RED III</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    view = st.session_state.get("_auth_view", "login")
    if view == "signup":
        _signup_form()
    else:
        _login_form()

    st.caption("---")
    st.caption(
        "🔒 Sistema sicuro · bcrypt + JWT · GDPR-compliant · © Carlo Sicurini 2026"
    )
    return False


def render_account_widget() -> None:
    """Widget account in sidebar per utente loggato. No-op in demo mode."""
    if auth.is_demo_mode():
        return
    # Trial downgrade lazy check (idempotente, cheap)
    try:
        auth.check_and_downgrade_expired_trials()
    except Exception:
        pass
    u = auth.current_user()
    if not u:
        return
    # Calcolo giorni trial residui
    trial_days_left = None
    if u.trial_ends_at and u.plan == "pro":
        try:
            from datetime import datetime
            t = datetime.fromisoformat(u.trial_ends_at.replace("Z", "+00:00"))
            delta = t - datetime.utcnow()
            trial_days_left = max(0, delta.days)
        except Exception:
            pass

    with st.sidebar:
        st.markdown("---")
        trial_badge = ""
        if trial_days_left is not None:
            trial_badge = (f"<div style='font-size:0.65rem;color:#F59E0B;"
                            f"margin-top:2px;'>Trial: {trial_days_left} giorni residui</div>")
        st.markdown(
            f"""
            <div style='padding:12px 14px;background:rgba(245,158,11,0.06);
                border-radius:10px;margin-bottom:8px;
                border:1px solid rgba(245,158,11,0.25);'>
                <div style='font-size:0.65rem;color:#94A3B8;font-weight:700;
                     letter-spacing:1px;text-transform:uppercase;'>Account</div>
                <div style='font-size:0.9rem;font-weight:700;color:#0F1F33;
                     margin-top:4px;'>{u.full_name or u.email}</div>
                <div style='font-size:0.75rem;color:#64748B;'>{u.email}</div>
                <div style='font-size:0.7rem;color:#F59E0B;font-weight:700;
                     margin-top:4px;text-transform:uppercase;'>
                     Plan: {u.plan}
                </div>
                {trial_badge}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("⚙️ Gestione account", expanded=False):
            _render_account_panel(u)

        if st.button("🚪 Logout", key="btn_logout", use_container_width=True):
            auth.logout()
            st.rerun()


def _render_account_panel(u) -> None:
    """Pannello: upgrade plan, change password, GDPR export, delete account."""
    from core import billing

    # Plan / Upgrade
    st.markdown(f"**Piano attuale**: `{u.plan}`")
    if u.plan == "free":
        if billing.is_configured():
            cycle = st.radio("Ciclo", ["monthly", "yearly"], horizontal=True,
                              key="acc_cycle")
            colp1, colp2 = st.columns(2)
            with colp1:
                if st.button("⬆️ Pro 49€", key="upgrade_pro",
                              use_container_width=True):
                    try:
                        url = billing.start_checkout(u, "pro", cycle)
                        st.link_button("Vai a Stripe", url, type="primary",
                                        use_container_width=True)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Checkout error: {exc}")
            with colp2:
                if st.button("🏢 Enterprise", key="upgrade_ent",
                              use_container_width=True):
                    try:
                        url = billing.start_checkout(u, "enterprise", cycle)
                        st.link_button("Vai a Stripe", url, type="primary",
                                        use_container_width=True)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Checkout error: {exc}")
        else:
            st.info("ℹ️ Billing non ancora attivo. Contatta il supporto.")
    elif u.stripe_customer_id:
        if st.button("💳 Gestisci abbonamento", use_container_width=True,
                      key="manage_sub"):
            try:
                url = billing.open_customer_portal(u)
                st.link_button("Vai a Stripe Portal", url, type="primary",
                                use_container_width=True)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Portal error: {exc}")

    st.markdown("---")
    st.markdown("**Cambia password**")
    with st.form("change_pw_form", clear_on_submit=True):
        old_pw = st.text_input("Password attuale", type="password",
                                key="old_pw")
        new_pw = st.text_input("Nuova password (min 8 char)", type="password",
                                key="new_pw")
        if st.form_submit_button("Aggiorna password", use_container_width=True):
            try:
                ok = auth.change_password(u.id, old_pw, new_pw)
                if ok:
                    st.success("Password aggiornata ✓")
                else:
                    st.error("Password attuale errata")
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("---")
    st.markdown("**Privacy / GDPR**")
    if st.button("📥 Esporta tutti i miei dati (JSON)",
                  use_container_width=True, key="gdpr_export"):
        try:
            from core.audit import export_user_log
            data = export_user_log(u.id)
            st.download_button("Scarica audit log",
                                data, file_name=f"metaniq_audit_{u.email}.json",
                                mime="application/json",
                                use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Export error: {exc}")

    with st.expander("⚠️ Cancella account (irreversibile)"):
        st.caption("Soft-delete: l'account viene disattivato ma i dati rimangono "
                    "30 gg per recovery. Hard delete contatta il supporto.")
        confirm = st.text_input("Digita 'ELIMINA' per confermare",
                                 key="del_confirm")
        if st.button("🗑️ Cancella il mio account", type="secondary",
                      use_container_width=True, key="del_btn"):
            if confirm == "ELIMINA":
                auth.delete_account(u.id, hard=False)
                auth.logout()
                st.success("Account disattivato. Logout effettuato.")
                st.rerun()
            else:
                st.warning("Digita esattamente 'ELIMINA' per confermare.")


__all__ = ["render_auth_gate", "render_account_widget"]
