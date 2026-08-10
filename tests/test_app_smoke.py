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
    """Ramo consolidato: nessun errore e gli export sono raggiungibili."""
    year, plant = 2024, "default_plant"
    _seed_year(year, plant, "Liquame bovino", 120.0)

    at = _run(do_year=year, do_plant=plant)
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
    at = _run(do_year=year, do_plant=plant)
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
    at = _run(do_year=year, do_plant=plant)
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
