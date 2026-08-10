# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/download_gate_ui.py — Widget Streamlit del gate sui download.

Separato da `core/download_gate.py` (logica pura, testabile senza runtime)
per la stessa ragione per cui `core/auth_ui.py` e' separato da `core/auth.py`.

Uso: sostituire `st.download_button(...)` con `gated_download_button(...)`,
stessa firma. Se l'utente si e' gia' identificato compare il download vero;
altrimenti un pulsante con lucchetto che apre il form in un popover.
"""
from __future__ import annotations

import streamlit as st

from core import download_gate as _gate

try:
    from i18n_runtime import t as _t_default
except Exception:  # i18n non disponibile: si resta in italiano
    def _t_default(s):
        return s


def _key_for(label: str, key: str | None) -> str:
    if key:
        return f"{key}__gate"
    safe = "".join(ch for ch in label if ch.isalnum())[:40]
    return f"dlgate_{safe}"


def render_unlock_form(document: str, key: str, t=None) -> bool:
    """Form di identificazione. True se l'utente si e' appena sbloccato."""
    _t = t or _t_default
    st.caption(_t(
        "Per scaricare i report lascia un contatto: l'app resta libera, "
        "i documenti no."
    ))
    with st.form(f"{key}__form", clear_on_submit=False):
        name = st.text_input(_t("Nome e cognome"), key=f"{key}__name")
        email = st.text_input(_t("Email"), key=f"{key}__email")
        company = st.text_input(_t("Azienda / Impianto"), key=f"{key}__company")
        submitted = st.form_submit_button("🔓 " + _t("Sblocca i download"),
                                          width='stretch', type="primary")
    if not submitted:
        return False

    ok, err = _gate.unlock(name, email, company, document=document)
    if not ok:
        st.warning(_t(err))
        return False
    st.success(_t("Grazie. I download sono attivi per questa sessione."))
    return True


def gated_download_button(label, data=None, file_name=None, mime=None,
                          key=None, t=None, document=None, **kwargs):
    """Come `st.download_button`, ma dietro identificazione.

    Il file viene comunque generato dal chiamante: qui si decide solo se
    consegnarlo. Il manuale utente e gli altri contenuti pubblici NON vanno
    passati da qui.
    """
    _t = t or _t_default
    if _gate.is_unlocked():
        return st.download_button(label, data=data, file_name=file_name,
                                  mime=mime, key=key, **kwargs)

    gate_key = _key_for(str(label), key)
    # `type` e `width` valgono anche per il pulsante-lucchetto, cosi' il
    # layout a colonne non cambia quando l'utente si sblocca.
    popover_kwargs = {}
    if "width" in kwargs:
        popover_kwargs["width"] = kwargs["width"]
    if kwargs.get("help"):
        popover_kwargs["help"] = kwargs["help"]

    with st.popover("🔒 " + str(label), **popover_kwargs):
        if render_unlock_form(document or str(label), gate_key, t=_t):
            st.rerun()
    return False


__all__ = ["gated_download_button", "render_unlock_form"]
