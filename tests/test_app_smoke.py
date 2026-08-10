# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Smoke test end-to-end dell'app Streamlit (headless, via AppTest).

Esegue davvero `app_mensile.py` e verifica che non compaiano eccezioni
ne' `st.error` a schermo. Copre due stati:

  * DB vuoto  -> ramo "nessun dato annuale";
  * DB popolato -> ramo consolidato, che renderizza gli export
    (XLSX/PDF/PPTX consolidati). Quel ramo non era coperto da alcun test:
    un import rotto la' dentro veniva inghiottito dal try/except e
    l'utente vedeva solo un messaggio d'errore rosso al posto del bottone.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from streamlit.testing.v1 import AppTest

from core import persistence
from core.daily_model import DailyEntry

APP = "app_mensile.py"
TIMEOUT = 180


@pytest.fixture(autouse=True)
def _clean_streamlit_singletons():
    """Ripulisce i DeltaGenerator singleton prima di ogni AppTest.

    Alcuni test importano `app_mensile` a livello modulo: lo script gira
    allora in bare mode, dove `DeltaGenerator._block()` restituisce se
    stesso invece di creare un blocco figlio (manca il cursor). Il
    `with st.form("lead_demo_form")` in sidebar marca cosi' il singleton
    `sidebar_dg` con `_form_data`, che resta appiccicato per tutto il
    processo: il successivo selettore lingua crede di stare dentro un form
    e solleva "st.button() can't be used in an st.form()".

    Riguarda solo l'esecuzione fuori da Streamlit (in produzione il cursor
    esiste sempre), ma senza questa pulizia l'esito dipende dall'ordine
    di raccolta dei test.
    """
    from streamlit.delta_generator_singletons import get_dg_singleton_instance

    def _reset():
        inst = get_dg_singleton_instance()
        for name in ("main_dg", "sidebar_dg", "event_dg", "bottom_dg"):
            dg = getattr(inst, name, None)
            if dg is not None and getattr(dg, "_form_data", None) is not None:
                dg._form_data = None

    _reset()
    yield
    _reset()


def _run(**session_state):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    for k, v in session_state.items():
        at.session_state[k] = v
    at.run()
    return at


def _assert_clean(at, label: str):
    excs = [str(e.value) for e in at.exception]
    errs = [str(e.value) for e in at.error]
    assert not excs, f"[{label}] eccezioni non gestite:\n" + "\n".join(excs)
    assert not errs, f"[{label}] st.error a schermo:\n" + "\n".join(errs)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """DB SQLite isolato: nessun rischio di toccare data/metaniq_daily.db."""
    db = tmp_path / "metaniq_test.db"
    monkeypatch.setattr(persistence, "_DEFAULT_DB_PATH", str(db))
    persistence.init_db(str(db))
    return str(db)


def _seed_year(year: int, plant_id: str, feed: str, qty_t: float) -> None:
    """Popola 12 mesi con dati plausibili (28 giorni/mese, 24 h/giorno).

    Include le letture REMI: senza `remi_vb` i Sm3 netti restano 0 e l'app
    imbocca il ramo "nessun dato annuale", lasciando gli export non coperti.
    """
    for month in range(1, 13):
        entries = [
            DailyEntry(
                date=_dt.date(year, month, day),
                feedstocks={feed: qty_t},
                hours_per_day=24.0,
                remi_vb=10_000.0,
                remi_e=97_900.0,        # 10.000 Sm3 x 9,79 kWh/Sm3
                remi_qb_max=450.0,
                remi_pci=9.79,
                remi_rho=0.72,
            )
            for day in range(1, 29)
        ]
        persistence.save_month(year, month, entries, plant_id=plant_id)


def test_app_runs_with_empty_db(tmp_db):
    """L'app parte pulita anche senza dati salvati."""
    at = _run()
    _assert_clean(at, "db-vuoto")
    assert at.tabs, "nessun tab renderizzato"


def test_app_runs_with_populated_db(tmp_db):
    """Ramo consolidato: nessun errore e gli export sono raggiungibili.

    `_dl_unlocked` simula l'utente che si e' gia' identificato: senza,
    i report stanno dietro il gate (vedi test_report_downloads_are_gated).
    """
    year, plant = 2024, "default_plant"
    _seed_year(year, plant, "Liquame bovino", 120.0)

    at = _run(do_year=year, do_plant_id=plant, _dl_unlocked=True)
    _assert_clean(at, "db-popolato")

    labels = [b.label for b in at.get("download_button")]

    # Blocco export consolidato (app_mensile.py ~5545): qui viveva
    # `from pdf_export import ...` -> modulo inesistente. Le label sono
    # esatte perche' altrove esistono bottoni simili ("Scarica Report PDF")
    # che renderebbero l'assert un falso verde.
    for expected in ("📊 Scarica Excel", "📄 Scarica PDF"):
        assert expected in labels, f"export consolidato assente: {expected!r} in {labels}"


def test_narrative_exports_receive_annual_aggregates(tmp_db, monkeypatch):
    """PDF e PPTX devono ricevere gli aggregati annuali, non il ctx dell'XLSX.

    Il PPTX legge `saving_avg`/`tot_revenue`/`valid_months` con
    `.get(...) or 0.0`: un contesto incompleto non genera errori, produce
    slide con saving 0%, ricavi 0 EUR e la dicitura "non conforme".
    Il difetto e' invisibile a schermo, quindi lo si verifica sul contesto.
    """
    import io

    import export.pptx_export as pptx_mod
    import report_pdf as pdf_mod

    captured: list[tuple[str, dict]] = []

    def _spy(kind, real):
        def _inner(ctx, *a, **kw):
            captured.append((kind, dict(ctx)))
            return real(ctx, *a, **kw)
        return _inner

    monkeypatch.setattr(pptx_mod, "build_metaniq_pptx",
                        _spy("pptx", pptx_mod.build_metaniq_pptx))
    monkeypatch.setattr(pdf_mod, "build_metaniq_pdf",
                        _spy("pdf", pdf_mod.build_metaniq_pdf))
    assert io  # ctx reale: i builder vengono comunque eseguiti davvero

    year, plant = 2024, "default_plant"
    # Biomassa presente in DEFAULT_ACTIVE_FEEDS: scenario di produzione,
    # con ricavi e MWh non nulli (l'altro test usa di proposito una
    # biomassa non attiva, per coprire le colonne df_res mancanti).
    _seed_year(year, plant, "Trinciato di mais", 120.0)
    at = _run(do_year=year, do_plant_id=plant)
    _assert_clean(at, "export-narrativi")

    kinds = {k for k, _ in captured}
    assert {"pdf", "pptx"} <= kinds, f"export narrativi non invocati: {kinds}"

    required = ("saving_avg", "valid_months", "tot_revenue",
                "tot_mwh_basis", "tariffa_media_ponderata", "revenue_rows")
    for kind, ctx in captured:
        missing = [k for k in required if k not in ctx]
        assert not missing, f"[{kind}] contesto incompleto, mancano: {missing}"
        assert float(ctx["saving_avg"]) > 0, (
            f"[{kind}] saving_avg={ctx['saving_avg']}: il deliverable "
            "dichiarerebbe l'impianto non conforme"
        )
        assert float(ctx["tot_revenue"]) > 0, f"[{kind}] tot_revenue nullo"


@pytest.mark.parametrize("plant_id", ["default", "CAB Bagnacavallo"])
def test_daily_data_reaches_annual_section(tmp_db, plant_id):
    """I dati salvati dalla Gestione Giornaliera devono arrivare all'annuale.

    Il pannello giornaliero salva con l'ID del campo "Impianto"
    (session_state `do_plant_id`, default "default" o il nome impianto
    dell'anagrafica). La sezione annuale leggeva invece `do_plant`, chiave
    che nessun widget dell'app scrive: restava sempre sul fallback
    "default_plant" e mostrava "Nessun dato annuale disponibile" anche con
    un anno intero di dati a DB, rendendo irraggiungibili tutti gli export
    consolidati.
    """
    year = 2024
    _seed_year(year, plant_id, "Liquame suino", 150.0)

    at = _run(do_year=year, do_plant_id=plant_id, _dl_unlocked=True)
    _assert_clean(at, f"annuale/{plant_id}")

    infos = [str(i.value) for i in at.get("info")]
    assert not [t for t in infos if "Nessun dato annuale" in t], (
        f"plant_id={plant_id!r}: la sezione annuale non vede i dati salvati "
        "dalla gestione giornaliera"
    )
    labels = [b.label for b in at.get("download_button")]
    assert "📄 Scarica PDF" in labels, (
        f"plant_id={plant_id!r}: export consolidati irraggiungibili ({labels})"
    )


def test_report_downloads_are_gated_but_manual_stays_public(tmp_db):
    """I report chiedono un contatto; l'app e il manuale restano liberi."""
    year, plant = 2024, "default"
    _seed_year(year, plant, "Liquame suino", 150.0)

    at = _run(do_year=year, do_plant_id=plant)     # nessuna identificazione
    _assert_clean(at, "gate-attivo")

    labels = [b.label for b in at.get("download_button")]
    for blocked in ("📄 Scarica PDF", "📊 Scarica Excel", "📄 Scarica Report PDF",
                    "📋 Excel snapshot"):
        assert blocked not in labels, (
            f"{blocked!r} scaricabile senza identificarsi: {labels}"
        )
    # il manuale utente e' documentazione, non un deliverable
    assert any("Manuale" in lbl for lbl in labels), (
        f"il manuale non deve stare dietro il gate: {labels}"
    )
    # l'app resta navigabile
    assert at.tabs, "il gate non deve bloccare l'uso dell'app"


def test_unlock_flow_end_to_end(tmp_db, monkeypatch):
    """Compilo il form nell'app reale e i report diventano scaricabili."""
    from core import download_gate

    delivered: list = []
    monkeypatch.setattr(download_gate, "deliver",
                        lambda ident, doc: delivered.append((ident, doc)) or {})

    year, plant = 2024, "default"
    _seed_year(year, plant, "Liquame suino", 150.0)
    at = _run(do_year=year, do_plant_id=plant)

    assert "📄 Scarica PDF" not in [b.label for b in at.get("download_button")]

    # ogni report ha il proprio popover, quindi il proprio form: compilo tutti
    # i campi cosi' il submit cliccato trova i dati (l'utente ne usa uno solo)
    # NB: i report con `key` esplicita generano campi `<key>__gate__name`,
    # non `dlgate_...`: si filtra sul suffisso, non sul prefisso.
    for w in at.get("text_input"):
        k = str(w.key or "")
        if k.endswith("__name"):
            w.set_value("Carlo Sicurini")
        elif k.endswith("__email"):
            w.set_value("carlo.sicurini@gmail.com")
        elif k.endswith("__company"):
            w.set_value("CAB Bagnacavallo")

    submits = [b for b in at.get("button")
               if "Sblocca" in str(getattr(b, "label", ""))]
    assert submits, "nessun pulsante di sblocco renderizzato"
    submits[0].click().run()
    _assert_clean(at, "sblocco")

    assert at.session_state["_dl_unlocked"] is True
    identity = at.session_state["_dl_identity"]
    assert identity["email"] == "carlo.sicurini@gmail.com"
    assert identity["company"] == "CAB Bagnacavallo"

    labels = [b.label for b in at.get("download_button")]
    assert "📄 Scarica PDF" in labels, labels

    assert delivered, "il contatto non e' stato recapitato"
    ident, doc = delivered[0]
    assert ident.email == "carlo.sicurini@gmail.com"
    assert doc, "il documento richiesto deve essere tracciato"


def test_identified_user_gets_the_reports(tmp_db):
    """Chi si identifica vede gli stessi download di prima."""
    year, plant = 2024, "default"
    _seed_year(year, plant, "Liquame suino", 150.0)

    at = _run(do_year=year, do_plant_id=plant, _dl_unlocked=True)
    _assert_clean(at, "gate-sbloccato")

    labels = [b.label for b in at.get("download_button")]
    assert "📄 Scarica PDF" in labels, labels
    assert "📊 Scarica Excel" in labels, labels


def test_sustainability_lot_uses_reported_period_and_mass_balance(tmp_db, monkeypatch):
    """Sezione "Tracciabilita' Lotto di Sostenibilita'" (UNI/TS 11567).

    LS-ID e "Periodo di rendicontazione" derivano da ctx["year"]/["month"],
    e il bilancio di massa da feedstock_totals_t / sm3_gross / sm3_netti.
    Quei campi venivano letti da chiavi session_state che nessun widget
    scrive (`daily_year`, `daily_month`, `monthly_*`): il report usciva con
    il mese corrente al posto del periodo rendicontato e con il bilancio di
    massa azzerato - due errori documentali in sede di audit OdC.
    """
    import report_pdf as pdf_mod

    captured: list[dict] = []
    real = pdf_mod.build_metaniq_pdf

    def _spy(ctx, *a, **kw):
        captured.append(dict(ctx))
        return real(ctx, *a, **kw)

    monkeypatch.setattr(pdf_mod, "build_metaniq_pdf", _spy)

    year, month, plant = 2024, 3, "default"
    qty = 150.0
    _seed_year(year, plant, "Liquame suino", qty)

    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["do_year"] = year
    at.session_state["do_month"] = month
    at.session_state["do_plant_id"] = plant
    at.run()
    captured.clear()   # il primo run popola le chiavi lette dal ctx
    at.run()           # rerun: come dopo una qualunque interazione utente
    _assert_clean(at, "lotto-sostenibilita")

    assert captured, "report PDF non generato"
    for ctx in captured:
        assert int(ctx["year"]) == year and int(ctx["month"]) == month, (
            f"periodo di rendicontazione errato: {ctx['month']}/{ctx['year']} "
            f"invece di {month}/{year} (LS-ID sbagliato)"
        )
        totals = ctx.get("feedstock_totals_t") or {}
        assert totals, "bilancio di massa senza biomasse in INPUT"
        # 28 giorni seminati per mese
        assert totals.get("Liquame suino") == pytest.approx(qty * 28), totals
        assert float(ctx.get("sm3_netti") or 0) > 0, "OUTPUT Sm3 netti azzerato"
        assert float(ctx.get("sm3_gross") or 0) > 0, "OUTPUT Sm3 lordi azzerato"


def test_valid_months_not_inflated_when_saving_below_threshold(tmp_db, monkeypatch):
    """`valid_months` non deve dichiarare mesi conformi sotto soglia.

    Il PDF stampa "Validita' mensile: N/12 mesi (tutti conformi) rispetto
    alle due condizioni RED III". Con il trinciato di mais il saving resta
    sotto l'80%: N deve essere 0, non 12.
    """
    import report_pdf as pdf_mod

    captured: list[dict] = []
    real = pdf_mod.build_metaniq_pdf

    def _spy(ctx, *a, **kw):
        captured.append(dict(ctx))
        return real(ctx, *a, **kw)

    monkeypatch.setattr(pdf_mod, "build_metaniq_pdf", _spy)

    year, plant = 2024, "default_plant"
    _seed_year(year, plant, "Trinciato di mais", 120.0)
    at = _run(do_year=year, do_plant_id=plant)
    _assert_clean(at, "valid-months")

    assert captured, "report PDF non generato"
    for ctx in captured:
        saving = float(ctx["saving_avg"])
        threshold = float(ctx["ghg_threshold"]) * 100.0
        if saving < threshold:
            assert int(ctx["valid_months"]) == 0, (
                f"saving {saving:.1f}% < soglia {threshold:.0f}% ma il report "
                f"dichiara {ctx['valid_months']}/12 mesi conformi"
            )
