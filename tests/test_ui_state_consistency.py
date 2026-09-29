# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Coerenza fra KPI mostrati in punti diversi della stessa schermata.

Regressione di due difetti "un run in ritardo": valori calcolati piu'
avanti nello script letti da session_state prima di essere aggiornati.

  * sidebar Taglia Impianto: Lordi/aux leggevano l'aux del run precedente
    (1,290 di default al primo avvio contro 1,241 calcolato), e il lordo
    manuale veniva sovrascritto dall'aux automatico nei calcoli;
  * hero KPI del Business Plan: CAPEX/OPEX/PNRR presi da una copia salvata
    a fine run precedente, e NPV sempre "@ 6%" senza leva/tasso/WACC.
"""
from __future__ import annotations

import re

from streamlit.testing.v1 import AppTest

# Fixture condivise (pulizia singleton Streamlit + DB isolato).
from tests.test_app_smoke import _clean_streamlit_singletons, tmp_db  # noqa: F401

APP = "app_mensile.py"
TIMEOUT = 180


def _num(s: str) -> float:
    """'1.234,5 Sm³/h' -> 1234.5 · '38.0%' -> 38.0 · '-0,39 M€' -> -0.39"""
    tok = re.search(r"-?[\d.,]+", str(s)).group(0)
    if "," in tok:
        tok = tok.replace(".", "").replace(",", ".")
    return float(tok)


def _metrics(at, prefix: str) -> list:
    return [m for m in at.metric if m.label.startswith(prefix)]


def _one(at, prefix: str) -> float:
    found = _metrics(at, prefix)
    assert found, f"metric '{prefix}' non trovato"
    return _num(found[0].value)


def _app(tmp_db) -> AppTest:  # noqa: F811
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_sidebar_gross_uses_current_aux_on_first_run(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    netti = _one(at, "📤")
    lordi = _one(at, "📥")
    aux_side = _one(at, "⚙️")
    lordo_richiesto = _one(at, "Produzione lorda richiesta")
    assert abs(lordi - lordo_richiesto) < 1.0, (lordi, lordo_richiesto)
    assert abs(aux_side - lordo_richiesto / netti) < 0.001, (aux_side, lordo_richiesto / netti)


def test_manual_gross_drives_calculations(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    [t for t in at.toggle if "Sincronizza" in t.label][0].set_value(False).run()
    [n for n in at.number_input if n.key == "input_smch_lordi_manual"][0].set_value(450.0).run()
    netti = _one(at, "📤")
    assert _one(at, "📥") == 450.0
    assert abs(_one(at, "Produzione lorda richiesta") - 450.0) < 0.1
    assert abs(_one(at, "⚙️") - 450.0 / netti) < 0.001


def _hero_vs_full(at):
    irr = [_num(m.value) for m in _metrics(at, "IRR Equity")]
    npv = [_num(m.value) for m in _metrics(at, "NPV")]
    labels = [m.label for m in _metrics(at, "NPV")]
    assert len(irr) == 2 and len(npv) == 2, (irr, npv)
    return irr, npv, labels


def test_hero_bp_matches_full_bp_on_first_run_and_after_pnrr_change(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    irr, npv, _ = _hero_vs_full(at)
    assert irr[0] == irr[1], irr
    assert abs(npv[0] - npv[1]) < 0.051, npv

    [n for n in at.number_input if n.key == "bp_pnrr_pct"][0].set_value(10.0).run()
    irr2, npv2, _ = _hero_vs_full(at)
    assert irr2[0] == irr2[1], irr2
    assert irr2[0] != irr[0], "il PNRR non ha modificato l'IRR"
    assert abs(npv2[0] - npv2[1]) < 0.051, npv2


def test_hero_npv_uses_current_wacc(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    [s for s in at.slider if s.key == "bp_input_discount"][0].set_value(9.0).run()
    _, npv, labels = _hero_vs_full(at)
    assert labels[0] == labels[1], labels
    assert "9" in labels[0], labels
    assert abs(npv[0] - npv[1]) < 0.051, npv
