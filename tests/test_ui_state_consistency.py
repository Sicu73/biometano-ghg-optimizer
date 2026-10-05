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
from pathlib import Path

from streamlit.testing.v1 import AppTest

# Fixture condivise (pulizia singleton Streamlit + DB isolato).
from tests.test_app_smoke import _clean_streamlit_singletons, tmp_db  # noqa: F401

# Percorso assoluto: Streamlit recenti risolvono i percorsi relativi rispetto al file del test.
APP = str(Path(__file__).resolve().parent.parent / "app_mensile.py")
TIMEOUT = 180


def _num(s: str) -> float:
    """'1.234,5 Sm³/h' -> 1234.5 · '38.0%' -> 38.0 · '-0,39 M€' -> -0.39"""
    tok = re.search(r"-?[\d.,]+", str(s)).group(0).rstrip(".,")
    if "," in tok:
        tok = tok.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", tok):   # '3.218.588', '25.728'
        tok = tok.replace(".", "")
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


def test_manual_gross_net_ratio_is_bounded(tmp_db):  # noqa: F811
    """Lordo 2000 su netto 300 dava aux 6,667 senza avvisi (saving gonfiato)."""
    at = _app(tmp_db)
    [t for t in at.toggle if "Sincronizza" in t.label][0].set_value(False).run()
    [n for n in at.number_input if n.key == "input_smch_lordi_manual"][0].set_value(2000.0).run()
    assert _one(at, "⚙️") == 2.0
    assert abs(_one(at, "Produzione lorda richiesta") - 600.0) < 0.1
    assert any("fuori" in str(w.value) for w in at.sidebar.warning)


def test_manual_aux_disabled_when_manual_gross(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    assert not [c for c in at.checkbox if "Override aux" in c.label][0].disabled
    [t for t in at.toggle if "Sincronizza" in t.label][0].set_value(False).run()
    assert [c for c in at.checkbox if "Override aux" in c.label][0].disabled


def _seed_mix_year(year: int, plant: str) -> None:
    """Mix mais + liquame suino con e_w ~ 20 gCO2/MJ: saving ~75% con
    comparator 80 (rete: non valido all'80%), ~79% con 94 (trasporti: valido)."""
    import datetime as _dt
    from core import persistence
    from core.daily_model import DailyEntry
    for m in range(1, 13):
        persistence.save_month(year, m, [
            DailyEntry(date=_dt.date(year, m, d),
                       feedstocks={"Trinciato di mais": 10.0, "Liquame suino": 3.0},
                       hours_per_day=24.0, remi_vb=6_000.0, remi_e=58_740.0,
                       remi_qb_max=260.0, remi_pci=9.79, remi_rho=0.72)
            for d in range(1, 29)], plant_id=plant)


def _db_validity(at) -> list:
    for d in at.dataframe:
        df = d.value
        # tabella del consuntivo DB (unica con le letture REMI)
        if hasattr(df, "columns") and {"Mese", "Saving %", "Validità", "remi_vb"} <= set(df.columns):
            return [(str(r["Mese"]), str(r["Saving %"]), str(r["Validità"])) for _, r in df.iterrows()]
    return []


def test_db_validity_uses_current_end_use(tmp_db):  # noqa: F811
    _seed_mix_year(2026, "P1")
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["do_year"] = 2026
    at.session_state["do_plant_id"] = "P1"
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    before = _db_validity(at)
    [s for s in at.selectbox if "Destinazione biometano" in s.label][0] \
        .set_value("Trasporti (BioGNL/BioCNG)").run()
    after = _db_validity(at)
    assert before and after
    assert before[0][2].startswith("❌"), before[0]      # 66% < 80% rete
    assert after[0][2].startswith("✅"), after[0]        # trasporti, nello stesso run


def test_db_aggregate_reads_current_year_on_first_load(tmp_db):  # noqa: F811
    """Al primo avvio l'aggregato leggeva l'anno 2024 (fallback) mentre il
    pannello giornaliero parte dall'anno corrente."""
    import datetime as _dt
    _seed_mix_year(_dt.date.today().year, "default")
    at = _app(tmp_db)
    assert _db_validity(at), "consuntivo DB dell'anno corrente non letto"


def test_db_aggregate_follows_tech_panel_period(tmp_db):  # noqa: F811
    """Il pannello giornaliero del tab tecnico scrive tech_do_year /
    tech_do_plant_id: l'aggregato li ignorava."""
    _seed_mix_year(2025, "P9")
    at = _app(tmp_db)
    assert not _db_validity(at)
    [n for n in at.number_input if n.key == "tech_do_year"][0].set_value(2025).run()
    [t for t in at.text_input if t.key == "tech_do_plant_id"][0].set_value("P9").run()
    assert _db_validity(at), "periodo del pannello tecnico ignorato"


def test_english_feed_selection_survives_rerun(tmp_db):  # noqa: F811
    """In inglese le biomasse attive sparivano al secondo run: il format_func
    leggeva la lingua a chiamata e fuori contesto ricadeva su "it"."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["lang"] = "en"
    at.run()
    first = list(at.session_state["active_feeds"])
    at.run()
    assert not at.exception
    assert list(at.session_state["active_feeds"]) == first and first
    assert not [w for w in at.warning if "Select at least 1 feedstock" in str(w.value)]


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


def test_default_scenario_is_valid_every_month(tmp_db):  # noqa: F811
    """Al primo avvio (soglia 80%) il simulatore non deve aprirsi con 12 mesi
    non validi: prima mais 1800 + sorgo 400 t/mese davano saving 72-75%."""
    at = _app(tmp_db)
    assert [m.value for m in _metrics(at, "Mesi validi")] == ["12/12"]
    assert not [w for w in at.warning if "fattibilit" in str(w.value)]


def test_revenue_table_inherits_plant_tariff(tmp_db):  # noqa: F811
    """DM 2022: tariffa d'impianto (TR aggiudicata + premi). La tabella
    ricavi per biomassa partiva da 120 €/MWh fissi mentre il BP usava
    TR + premi (129,8): ricavi a video, export e BP divergevano."""
    at = _app(tmp_db)
    # «Tariffa applicata» ha 1 decimale, la media ponderata 2: tolleranza 0,05
    assert abs(_one(at, "Tariffa media ponderata") - _one(at, "Tariffa applicata")) <= 0.05

    [s for s in at.slider if s.key == "bp_ribasso"][0].set_value(5.0).run()
    applicata = _one(at, "Tariffa applicata")
    media = _one(at, "Tariffa media ponderata")
    assert abs(media - applicata) <= 0.05, (media, applicata)
    mwh = _one(at, "MWh netti totali/anno")
    ricavi = _one(at, "💰 Ricavi totali/anno")
    assert abs(ricavi - mwh * media) <= 0.001 * ricavi, (ricavi, mwh, media)


def test_manual_tariff_override_survives_plant_tariff_change(tmp_db):  # noqa: F811
    """Una tariffa modificata a mano resta; le altre seguono il BP."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["tariff_overrides_eur_mwh_biometano"] = {"Liquame suino": 50.0}
    at.run()
    assert not at.exception
    media0 = _one(at, "Tariffa media ponderata")
    assert media0 < _one(at, "Tariffa applicata") - 0.5, "override non applicato"

    [s for s in at.slider if s.key == "bp_ribasso"][0].set_value(5.0).run()
    assert at.session_state["tariff_overrides_eur_mwh_biometano"] == {"Liquame suino": 50.0}
    assert _one(at, "Tariffa media ponderata") < media0   # le altre sono scese col ribasso


def test_plant_tariff_with_third_decimal_5_creates_no_override(tmp_db):  # noqa: F811
    """53,985 €/MWh è mostrata 53,98: non deve diventare un override."""
    at = _app(tmp_db)
    [s for s in at.slider if s.key == "bp_ribasso"][0].set_value(0.0).run()
    [c for c in at.checkbox if c.key == "bp_pm_on"][0].uncheck().run()
    [c for c in at.checkbox if c.key == "bp_pu_on"][0].uncheck().run()
    [n for n in at.number_input if n.key == "bp_tariffa_base_input"][0].set_value(53.985).run()
    at.run()
    _k = "tariff_overrides_eur_mwh_biometano"
    over = at.session_state[_k] if _k in at.session_state else {}
    assert over == {}, over
    [s for s in at.slider if s.key == "bp_ribasso"][0].set_value(10.0).run()
    assert abs(_one(at, "Tariffa media ponderata") - _one(at, "Tariffa applicata")) <= 0.05


def _ni(at, key):
    return [n for n in at.number_input if n.key == key][0]


def test_tariff_and_capex_follow_plant_type_and_size(tmp_db):  # noqa: F811
    """TR di riferimento e CAPEX di default seguono tipo impianto e fascia,
    finché l'utente non li modifica. Prima: TR ferma a 118 e CAPEX sempre
    38.000 (chiavi "Nuova costruzione" vs "nuova_costruzione")."""
    at = _app(tmp_db)                                   # 300 Smc/h -> fascia B
    assert _ni(at, "bp_tariffa_base_input").value == 118.0
    assert _ni(at, "bp_input_capex").value == 38_000.0

    [s for s in at.selectbox if s.key == "bp_plant_type"][0].set_value("Riconversione parziale").run()
    assert _ni(at, "bp_tariffa_base_input").value == 100.0
    assert _ni(at, "bp_input_capex").value == 18_000.0
    irr, npv, _ = _hero_vs_full(at)
    assert irr[0] == irr[1] and abs(npv[0] - npv[1]) < 0.051

    _ni(at, "input_smch_netti").set_value(150.0).run()      # fascia A
    assert _ni(at, "bp_tariffa_base_input").value == 112.0

    _ni(at, "bp_tariffa_base_input").set_value(125.0).run()  # scelta utente
    [s for s in at.selectbox if s.key == "bp_plant_type"][0].set_value("Nuova costruzione").run()
    assert _ni(at, "bp_tariffa_base_input").value == 125.0     # resta dell'utente
    assert _ni(at, "bp_input_capex").value == 38_000.0         # CAPEX non toccato: segue


def test_hero_npv_uses_current_wacc(tmp_db):  # noqa: F811
    at = _app(tmp_db)
    [s for s in at.slider if s.key == "bp_input_discount"][0].set_value(9.0).run()
    _, npv, labels = _hero_vs_full(at)
    assert labels[0] == labels[1], labels
    assert "9" in labels[0], labels
    assert abs(npv[0] - npv[1]) < 0.051, npv
