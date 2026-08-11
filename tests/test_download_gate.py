# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Gate di identificazione sui download dei report."""
from __future__ import annotations

import pytest

from core import download_gate as gate
from core.download_gate import Identity


def _capture_posts(monkeypatch, status: int = 200, payload: dict | None = None):
    """Intercetta TUTTE le POST e le restituisce in ordine.

    `deliver()` prova piu' canali nello stesso giro (email, webhook,
    Supabase): un mock che tiene solo l'ultima chiamata testerebbe il canale
    sbagliato. Si filtra per URL con `_find_call`.
    """
    calls: list[dict] = []

    class _R:
        status_code = status
        content = b"{}"

        @staticmethod
        def json():
            return payload if payload is not None else {"success": "false"}

    def fake_post(url, json=None, headers=None, timeout=None, **kw):
        calls.append({"url": url, "json": json, "headers": headers or {}})
        return _R()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def _find_call(calls: list[dict], needle: str) -> dict | None:
    return next((c for c in calls if needle in str(c["url"])), None)


@pytest.fixture(autouse=True)
def clean_session(monkeypatch):
    """Sessione finta: i test non girano dentro il runtime Streamlit."""
    store: dict = {}
    monkeypatch.setattr(gate, "_session", lambda: store)
    monkeypatch.setattr(gate, "_secrets", lambda section: {})
    return store


# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,email,expected_ok", [
    ("Carlo Sicurini", "carlo@example.com", True),
    ("Carlo", "carlo.sicurini@sub.dominio.it", True),
    ("", "carlo@example.com", False),
    ("   ", "carlo@example.com", False),
    ("Carlo", "", False),
    ("Carlo", "non-una-email", False),
    ("Carlo", "manca@dominio", False),
    ("Carlo", "@example.com", False),
])
def test_validation(name, email, expected_ok):
    assert (gate.validate(name, email) is None) is expected_ok


# ---------------------------------------------------------------------------
# Stato del gate
# ---------------------------------------------------------------------------
def test_locked_by_default(clean_session):
    assert gate.gate_enabled() is True
    assert gate.is_unlocked() is False


def test_unlock_opens_downloads(clean_session):
    ok, err = gate.unlock("Carlo Sicurini", "carlo@example.com", "CAB Faenza",
                          document="Report PDF")
    assert ok and err == ""
    assert gate.is_unlocked() is True
    ident = gate.current_identity()
    assert ident.name == "Carlo Sicurini"
    assert ident.company == "CAB Faenza"


def test_unlock_rejects_bad_email(clean_session):
    ok, err = gate.unlock("Carlo", "non-valida")
    assert not ok
    assert "email" in err.lower()
    assert gate.is_unlocked() is False


def test_gate_can_be_disabled_from_secrets(monkeypatch, clean_session):
    monkeypatch.setattr(gate, "_secrets",
                        lambda section: {"gate_downloads": False} if section == "auth" else {})
    assert gate.gate_enabled() is False
    assert gate.is_unlocked() is True, "gate spento = tutto libero"


def test_authenticated_user_bypasses_gate(monkeypatch, clean_session):
    """Chi e' gia' loggato con core.auth non deve ricompilare nulla."""
    import core.auth as auth_mod
    monkeypatch.setattr(auth_mod, "current_user", lambda: object())
    assert gate.is_unlocked() is True


# ---------------------------------------------------------------------------
# Recapito del contatto
# ---------------------------------------------------------------------------
def test_deliver_uses_webhook_when_configured(monkeypatch, clean_session):
    sent = {}

    monkeypatch.setattr(
        gate, "_secrets",
        lambda section: {"webhook_url": "https://hook.example/x"} if section == "leads" else {},
    )

    calls = _capture_posts(monkeypatch)

    res = gate.deliver(Identity("Carlo", "c@example.com", "CAB"), "Report PDF")
    assert res["webhook"] is True
    assert res["persisted"] is True

    sent = _find_call(calls, "hook.example")
    assert sent, f"webhook non chiamato: {[c['url'] for c in calls]}"
    assert sent["json"]["email"] == "c@example.com"
    assert sent["json"]["document"] == "Report PDF"
    assert sent["json"]["source"] == "download_gate"


def test_discord_webhook_uses_embed_format(monkeypatch, clean_session):
    """Discord rifiuta il JSON generico: serve `content` o `embeds`."""
    sent = {}
    monkeypatch.setattr(
        gate, "_secrets",
        lambda section: {
            "webhook_url": "https://discord.com/api/webhooks/123/abc"
        } if section == "leads" else {},
    )

    calls = _capture_posts(monkeypatch, status=204)

    res = gate.deliver(Identity("Carlo Sicurini", "c@example.com", "CAB Faenza"),
                       "Report PDF")
    assert res["webhook"] is True

    sent = _find_call(calls, "discord.com")
    assert sent, f"webhook Discord non chiamato: {[c['url'] for c in calls]}"
    body = sent["json"]
    assert "embeds" in body, f"payload non compatibile con Discord: {body}"
    embed = body["embeds"][0]
    valori = " ".join(str(f["value"]) for f in embed["fields"])
    assert "Carlo Sicurini" in valori
    assert "c@example.com" in valori
    assert "CAB Faenza" in valori
    assert "Report PDF" in valori
    assert embed["color"] == 0xF59E0B


def test_generic_webhook_keeps_plain_json(monkeypatch, clean_session):
    """Un endpoint non-Discord riceve il JSON piatto, piu' facile da mappare."""
    sent = {}
    monkeypatch.setattr(
        gate, "_secrets",
        lambda section: {"webhook_url": "https://hooks.zapier.com/x"} if section == "leads" else {},
    )

    calls = _capture_posts(monkeypatch)

    gate.deliver(Identity("Carlo", "c@example.com"), "Excel")
    sent = _find_call(calls, "hooks.zapier.com")
    assert sent, f"webhook non chiamato: {[c['url'] for c in calls]}"
    assert "embeds" not in sent["json"]
    assert sent["json"]["email"] == "c@example.com"


def test_email_channel_is_off_under_pytest(monkeypatch, clean_session):
    """La suite non deve spedire email vere al Titolare."""
    import os

    import requests

    def boom(*a, **kw):
        raise AssertionError("nessuna chiamata di rete attesa sotto pytest")

    monkeypatch.setattr(requests, "post", boom)
    monkeypatch.delenv("METANIQ_LEADS_EMAIL_REMOTE", raising=False)
    assert os.environ.get("PYTEST_CURRENT_TEST"), "atteso ambiente pytest"

    res = gate.deliver(Identity("Carlo", "c@example.com"), "PDF")
    assert res["email"] is False


def test_email_channel_needs_no_configuration(monkeypatch, clean_session):
    """Il canale email deve partire senza secrets, verso CONTACT_EMAIL."""
    monkeypatch.setenv("METANIQ_LEADS_EMAIL_REMOTE", "1")   # bypassa il guard
    sent = {}

    class _R:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json():
            return {"success": "true", "message": "sent"}

    import requests
    monkeypatch.setattr(requests, "post",
                        lambda url, json=None, headers=None, timeout=None, **kw: (
                            sent.update(url=url, json=json, headers=headers or {}) or _R()))

    res = gate.deliver(Identity("Carlo", "c@example.com", "CAB"), "Report PDF")
    assert res["email"] is True
    assert res["persisted"] is True

    from core.leads import CONTACT_EMAIL
    assert CONTACT_EMAIL in sent["url"], sent["url"]
    # senza Referer il servizio rifiuta scambiando la chiamata per file locale
    assert sent["headers"].get("Referer"), "Referer mancante"
    assert sent["json"]["Email"] == "c@example.com"
    assert sent["json"]["Documento"] == "Report PDF"


def test_email_pending_activation_is_not_a_success(monkeypatch, clean_session):
    """Finche' il link di attivazione non e' cliccato, non e' recapitato."""
    monkeypatch.setenv("METANIQ_LEADS_EMAIL_REMOTE", "1")

    class _R:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json():
            return {"success": "false",
                    "message": "This form needs Activation. We've sent you an email..."}

    import requests
    monkeypatch.setattr(requests, "post",
                        lambda *a, **kw: _R())

    res = gate.deliver(Identity("Carlo", "c@example.com"), "Excel")
    assert res["email"] is False, (
        "in attesa di attivazione non si deve dichiarare il contatto recapitato"
    )


def test_email_channel_can_be_disabled(monkeypatch, clean_session):
    monkeypatch.setattr(
        gate, "_secrets",
        lambda section: {"disable_email": "true"} if section == "leads" else {},
    )

    import requests

    def boom(*a, **kw):
        raise AssertionError("nessuna chiamata attesa")

    monkeypatch.setattr(requests, "post", boom)
    res = gate.deliver(Identity("Carlo", "c@example.com"), "PDF")
    assert res["email"] is False


def test_deliver_reports_volatile_when_no_remote(monkeypatch, clean_session, tmp_path):
    """Senza webhook ne' Supabase il contatto e' raccolto ma non recapitato."""
    from core import leads
    monkeypatch.setattr(leads, "_DEFAULT_DB_PATH", str(tmp_path / "leads.db"))

    res = gate.deliver(Identity("Carlo", "c@example.com"), "Excel")
    assert res["webhook"] is False and res["supabase"] is False
    assert res["persisted"] is False, (
        "senza canale remoto il dato non deve risultare recapitato"
    )
    assert res["sqlite"] is True


def test_deliver_never_raises_if_all_channels_fail(monkeypatch, clean_session):
    monkeypatch.setattr(
        gate, "_secrets",
        lambda section: {"webhook_url": "https://hook.example/x"} if section == "leads" else {},
    )

    import requests

    def boom(*a, **kw):
        raise RuntimeError("rete giù")

    monkeypatch.setattr(requests, "post", boom)
    from core import leads
    monkeypatch.setattr(leads, "log_lead", lambda **kw: False)

    res = gate.deliver(Identity("Carlo", "c@example.com"), "PDF")
    assert res["persisted"] is False
    assert res["sqlite"] is False


def test_unlock_records_the_requested_document(monkeypatch, clean_session):
    seen = {}
    monkeypatch.setattr(gate, "deliver",
                        lambda ident, doc: seen.update(ident=ident, doc=doc) or {})
    gate.unlock("Carlo", "c@example.com", document="Dossier OdC")
    assert seen["doc"] == "Dossier OdC"
    assert seen["ident"].email == "c@example.com"
