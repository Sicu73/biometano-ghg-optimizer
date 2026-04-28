# -*- coding: utf-8 -*-
from __future__ import annotations

import streamlit as st
import sitecustomize  # noqa: F401

LANG_OPTIONS = {"it": "Italiano", "en": "English"}

st.sidebar.radio(
    "Lingua / Language",
    options=["it", "en"],
    format_func=lambda key: LANG_OPTIONS[key],
    index=0 if st.session_state.get("lang", "it") == "it" else 1,
    key="lang",
)

import app_mensile  # noqa: F401,E402
