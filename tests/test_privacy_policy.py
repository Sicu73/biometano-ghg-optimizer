# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Coerenza fra l'informativa privacy e cio' che il codice fa davvero.

L'informativa precedente dichiarava tre cose smentite dal codice: raccolta
di IP e user agent (colonne presenti in core/audit.py ma mai popolate),
repository "privato" (e' pubblico) e backup giornalieri (impossibili su
filesystem effimero). Un documento legale che descrive un software diverso
da quello in produzione e' un rischio, non una tutela.

Questi test non giudicano il merito giuridico: verificano che le
affermazioni verificabili restino vere quando il codice cambia.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRIVACY = ROOT / "legal" / "privacy.md"

# Host contattati a runtime -> come devono comparire nell'informativa.
THIRD_PARTY_HOSTS = {
    "formsubmit.co": "FormSubmit",
    "abacus.jasoncameron.dev": "Abacus",
}

# Host che NON trattano dati degli utenti: nessun obbligo di menzione.
HOSTS_WITHOUT_USER_DATA = {
    "docs.streamlit.io",
    "streamlit.io",
    "www.garanteprivacy.it",
    "garanteprivacy.it",
    "supabase.com",
    "github.com",
    "discord.com",
    "discordapp.com",
    "hooks.zapier.com",
    "appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app",
}


@pytest.fixture(scope="module")
def privacy_text() -> str:
    assert PRIVACY.is_file(), f"informativa mancante: {PRIVACY}"
    return PRIVACY.read_text(encoding="utf-8")


def test_privacy_names_every_third_party_that_receives_user_data(privacy_text):
    missing = [
        f"{host} ({label})"
        for host, label in THIRD_PARTY_HOSTS.items()
        if label.lower() not in privacy_text.lower()
    ]
    assert not missing, (
        "servizi terzi che ricevono dati degli utenti ma non citati "
        f"nell'informativa: {missing}"
    )


def test_no_runtime_host_is_undeclared(privacy_text):
    """Un endpoint nuovo nel codice deve comparire nell'informativa."""
    hosts: set[str] = set()
    for py in (ROOT / "core").rglob("*.py"):
        for m in re.finditer(r"https://([a-zA-Z0-9.\-]+)", py.read_text(encoding="utf-8")):
            hosts.add(m.group(1).rstrip("."))

    undeclared = []
    for host in sorted(hosts):
        if host in HOSTS_WITHOUT_USER_DATA or host in THIRD_PARTY_HOSTS:
            continue
        undeclared.append(host)

    assert not undeclared, (
        "host contattati dal codice e non classificati: aggiungerli "
        "all'informativa (se ricevono dati utente) o alla whitelist "
        f"motivata di questo test: {undeclared}"
    )


def test_claim_about_ip_collection_matches_the_code(privacy_text):
    """L'informativa dichiara di non raccogliere IP: deve restare vero."""
    dichiara_no_ip = "non" in privacy_text.lower() and "indirizzo ip" in privacy_text.lower()
    assert dichiara_no_ip, "l'informativa non si esprime piu' sulla raccolta di IP"

    offenders = []
    for py in list((ROOT / "core").rglob("*.py")) + [ROOT / "app_mensile.py"]:
        text = py.read_text(encoding="utf-8")
        # accesso reale all'IP del client, non il nome di una colonna
        if re.search(r"st\.context\.ip_address|context\.headers\[", text):
            offenders.append(py.relative_to(ROOT).as_posix())
    assert not offenders, (
        "il codice legge l'IP del client mentre l'informativa dichiara di non "
        f"raccoglierlo: {offenders}"
    )


def test_privacy_has_the_mandatory_sections(privacy_text):
    for heading in ("Titolare del trattamento", "diritti", "Cookie",
                    "Modifiche", "base giuridica"):
        assert heading.lower() in privacy_text.lower(), f"sezione mancante: {heading}"


def test_privacy_declares_an_update_date(privacy_text):
    assert re.search(r"\*\*Ultimo aggiornamento\*\*:\s*\d{1,2}\s+\w+\s+20\d\d",
                     privacy_text), "manca la data di ultimo aggiornamento"
