# -*- coding: utf-8 -*-
"""tests/test_gross_net_sustainability.py — Audit base LORDO vs NETTO.

Verifica i requisiti del task `audit/gross-net-sustainability`:

1. La funzione `ghg_summary` calcola il saving% sull'energia LORDA
   (intensita' gCO2eq/MJ su MJ lordi). L'aux_factor non altera saving.
2. Per il biometano (DM 2018 / DM 2022) viene esposta la doppia vista
   LORDO + NETTO nel calculation_summary del output_model.
3. Gli output (CSV/Excel/PDF + dashboard) espongono entrambi i valori
   con etichetta "base sostenibilita'" esplicita.
4. La spiegazione (`output/explanations.py`) dichiara esplicitamente la
   base usata e cita le normative di riferimento.
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1) Saving GHG calcolato su LORDO (invariante sotto aux_factor)
# ---------------------------------------------------------------------------

def test_ghg_summary_uses_gross_for_sustainability():
    """`ghg_summary` deve calcolare saving% su MJ LORDI: cambiando aux
    cambia solo Sm3/MWh netti, NON deve cambiare saving GHG."""
    from core.calculation_engine import ghg_summary, FEED_NAMES

    if not FEED_NAMES:
        pytest.skip("FEED_NAMES vuoto: motore calcolo non disponibile in questo runtime")

    feed = FEED_NAMES[0]
    masses = {feed: 100.0}

    s_low = ghg_summary(masses, aux=1.10, ep=0.0)
    s_high = ghg_summary(masses, aux=1.50, ep=0.0)

    # Il saving DEVE essere uguale (intensita' gCO2eq/MJ su MJ lordi)
    assert pytest.approx(s_low["saving"], rel=1e-9) == s_high["saving"], (
        "saving% DEVE essere invariante su aux_factor (base LORDO)"
    )
    # Il LORDO Sm3 e' identico
    assert pytest.approx(s_low["nm3_gross"], rel=1e-9) == s_high["nm3_gross"]
    # I NETTI scalano con aux (LORDO/aux)
    assert s_low["nm3_net"] > s_high["nm3_net"]


# ---------------------------------------------------------------------------
# 2) Per biometano output_model espone la dual view LORDO + NETTO
# ---------------------------------------------------------------------------

def _ctx_biometano():
    return {
        "APP_MODE": "biometano",
        "IS_DM2022": True,
        "IS_DM2018": False,
        "IS_CHP": False,
        "IS_FER2": False,
        "lang": "it",
        "active_feeds": [],
        "FEEDSTOCK_DB": {},
        "aux_factor": 1.29,
        "ep_total": 6.0,
        "fossil_comparator": 80.0,
        "ghg_threshold": 0.80,
        "plant_net_smch": 300.0,
        "tot_biomasse_t": 12000.0,
        "tot_sm3_lordi": 3_900_000.0,
        "tot_sm3_netti": 3_023_000.0,
        "tot_mwh_lordi": 38_882.0,
        "tot_mwh_netti": 30_139.0,
        "saving_avg": 81.5,
        "valid_months": 12,
        "tot_revenue": 4_519_500.0,
    }


def test_biomethane_has_net_variant():
    """Per biometano, output_model.calculation_summary contiene LORDO,
    NETTO e flag biomethane_dual_view=True."""
    from output.output_builder import build_output_model

    om = build_output_model(_ctx_biometano())
    calc = om["calculation_summary"]

    assert "tot_sm3_lordi" in calc
    assert "tot_sm3_netti" in calc
    assert "tot_mwh_lordi" in calc
    assert "tot_mwh" in calc
    assert calc["tot_sm3_lordi"] > 0
    assert calc["tot_sm3_netti"] > 0
    assert calc["tot_sm3_lordi"] >= calc["tot_sm3_netti"], (
        "Sm3 lordi devono essere >= Sm3 netti (LORDO = NETTO * aux_factor)"
    )
    assert calc["biomethane_dual_view"] is True
    assert calc["sustainability_basis"] == "LORDO"
    assert "RED III" in calc["sustainability_basis_note"]


def test_chp_no_dual_view():
    """In modalita' CHP la dual view biometano e' disattivata
    (la base resta LORDO ma non e' rilevante esporre la vista NETTO
    biometano: per CHP si parla di MWh elettrici/termici)."""
    from output.output_builder import build_output_model

    ctx = _ctx_biometano()
    ctx["APP_MODE"] = "biogas_chp"
    ctx["IS_CHP"] = True
    ctx["IS_DM2022"] = False
    om = build_output_model(ctx)
    calc = om["calculation_summary"]
    assert calc["sustainability_basis"] == "LORDO"
    assert calc["biomethane_dual_view"] is False


# ---------------------------------------------------------------------------
# 3) Gli export espongono entrambi LORDO e NETTO
# ---------------------------------------------------------------------------

def test_export_includes_both_gross_and_net():
    """Test che il CSV monthly includa righe LORDO e NETTO + base
    sostenibilita' esplicita."""
    from output.output_builder import build_output_model
    from export.csv_export import build_csv_from_output

    om = build_output_model(_ctx_biometano())
    csv_bytes = build_csv_from_output(om, sheet="monthly")
    assert isinstance(csv_bytes, (bytes, bytearray))
    text = csv_bytes.decode("utf-8")
    assert "LORDI" in text or "lordi" in text.lower(), (
        "CSV mensile deve esporre Sm3/MWh LORDI"
    )
    assert "NETTI" in text or "netti" in text.lower(), (
        "CSV mensile deve esporre Sm3/MWh NETTI"
    )
    assert "Base sostenibilita" in text or "LORDO" in text, (
        "CSV mensile deve dichiarare la base sostenibilita'"
    )


def test_sustainability_basis_table():
    """`build_sustainability_basis_table` espone la riga 'Base normativa
    applicata' e i valori LORDO/NETTO per Sm3, MWh e Saving."""
    from output.output_builder import build_output_model
    from output.tables import build_sustainability_basis_table

    om = build_output_model(_ctx_biometano())
    tbl = build_sustainability_basis_table(om)
    # Tbl puo' essere DataFrame o lista
    if hasattr(tbl, "to_dict"):
        rows = tbl.to_dict(orient="records")
    else:
        rows = tbl
    voci = {r["Voce"] for r in rows}
    assert "Sm³ biometano" in voci
    assert "MWh biometano" in voci
    assert "Saving GHG (%)" in voci
    assert "Base normativa applicata" in voci
    # Verifica colonna "LORDO" presente come label nelle key
    sample = rows[0]
    has_lordo_col = any("LORDO" in str(k) for k in sample.keys())
    has_netto_col = any("NETTO" in str(k) for k in sample.keys())
    assert has_lordo_col and has_netto_col


# ---------------------------------------------------------------------------
# 4) La spiegazione dichiara esplicitamente la base usata
# ---------------------------------------------------------------------------

def test_explanation_states_basis():
    """`explain_sustainability_basis` deve dichiarare 'LORDO' come base
    e citare almeno una normativa rilevante (RED III)."""
    from output.explanations import (
        explain_sustainability_basis,
        explain_ghg_method,
        build_all_explanations,
    )

    txt_it = explain_sustainability_basis({"lang": "it",
                                            "APP_MODE": "biometano"})
    assert "LORDO" in txt_it
    assert "RED III" in txt_it

    txt_en = explain_sustainability_basis({"lang": "en",
                                            "APP_MODE": "biometano"})
    assert "GROSS" in txt_en
    assert "RED III" in txt_en

    # Versione biometano deve menzionare la vista NETTO informativa
    assert "NETTO" in txt_it
    assert "NET" in txt_en

    # Verifica anche che il metodo GHG dichiari LORDO
    method_it = explain_ghg_method({"lang": "it"})
    assert "LORDO" in method_it
    assert "BASE SOSTENIBILITA" in method_it

    # E build_all_explanations ritorna la chiave
    all_expl = build_all_explanations({"lang": "it",
                                        "APP_MODE": "biometano"})
    assert "sustainability_basis" in all_expl
    assert "LORDO" in all_expl["sustainability_basis"]


# ---------------------------------------------------------------------------
# 5) MonthlyAggregate: nuovi campi mwh_gross + saving_pct_net
# ---------------------------------------------------------------------------

def test_monthly_aggregate_dual_view_fields():
    """Il MonthlyAggregate espone mwh_gross, saving_pct_net e
    sustainability_basis."""
    from core.monthly_aggregate import MonthlyAggregate

    agg = MonthlyAggregate()
    assert hasattr(agg, "mwh_gross")
    assert hasattr(agg, "saving_pct_net")
    assert hasattr(agg, "sustainability_basis")
    assert agg.sustainability_basis == "LORDO"


def test_monthly_kpis_includes_basis():
    """`build_monthly_kpis` espone mwh_gross e sustainability_basis."""
    from core.monthly_aggregate import MonthlyAggregate
    from output.monthly_kpis import build_monthly_kpis

    agg = MonthlyAggregate(year=2025, month=10,
                           sm3_gross=120000.0, sm3_netti=93000.0,
                           mwh=927.0, mwh_gross=1196.0,
                           saving_pct=82.0, saving_pct_net=82.0)
    kpis = build_monthly_kpis(agg, sustainability_eval={
        "compliant": True, "threshold": 80.0, "margin": 2.0,
        "constraints_status": [], "regime": "DM 2022",
    })
    assert kpis["mwh_gross"] == pytest.approx(1196.0)
    assert kpis["sustainability_basis"] == "LORDO"
    assert kpis["saving_pct"] == pytest.approx(82.0)
