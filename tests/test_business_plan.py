# -*- coding: utf-8 -*-
"""Test core/business_plan.py — BP engine IRR/NPV/payback."""
from __future__ import annotations

import pytest

from core.business_plan import (
    build_business_plan,
    _irr,
    _npv,
    _payback,
    _french_annuity,
)


# ============================================================================
# IRR / NPV / PAYBACK MATH
# ============================================================================
class TestIRR:
    def test_irr_classic_case(self):
        """Caso noto: invest -1000, 5y x +300 → IRR ~ 15.24%"""
        cf = [-1000, 300, 300, 300, 300, 300]
        irr = _irr(cf)
        assert 0.14 < irr < 0.17, f"IRR atteso ~15%, got {irr*100:.2f}%"

    def test_irr_all_positive(self):
        assert _irr([100, 200, 300]) == 0.0

    def test_irr_all_negative(self):
        # Tutti cash flow negativi (perdita totale): IRR = -100%
        assert _irr([-100, -200, -300]) == -1.0

    def test_irr_empty(self):
        assert _irr([]) == 0.0

    def test_irr_zero_npv_at_rate(self):
        # invest -1000 → 1100 in 1 anno: IRR = 10%
        irr = _irr([-1000, 1100])
        assert 0.09 < irr < 0.11

    def test_irr_huge_returns_capped(self):
        # Investimento ridicolo, returns enormi
        irr = _irr([-1, 1000, 1000, 1000])
        assert irr == 10.0  # cap


class TestNPV:
    def test_npv_zero_rate(self):
        assert _npv([-100, 50, 50, 50], 0.0) == 50

    def test_npv_at_irr_is_zero(self):
        cf = [-1000, 600, 600]
        irr = _irr(cf)
        npv_at_irr = _npv(cf, irr)
        assert abs(npv_at_irr) < 1.0

    def test_npv_decreases_with_rate(self):
        cf = [-1000, 300, 300, 300, 300, 300]
        assert _npv(cf, 0.05) > _npv(cf, 0.15)


class TestPayback:
    def test_payback_simple(self):
        # invest -1000, +500/anno → recupera in 2 anni
        pb = _payback([-1000, 500, 500, 500])
        assert 1.9 < pb < 2.1

    def test_payback_first_year(self):
        pb = _payback([-100, 200])
        assert 0.4 < pb < 0.6  # interpolato

    def test_payback_never(self):
        pb = _payback([-1000, 100, 100, 100])
        assert pb is None


class TestFrenchAnnuity:
    def test_annuity_zero_principal(self):
        assert _french_annuity(0, 0.05, 10) == 0.0

    def test_annuity_zero_rate(self):
        # Senza interessi: rata = principal/n
        assert _french_annuity(1000, 0.0, 10) == 100.0

    def test_annuity_known(self):
        # 100k @ 5% per 10 anni = 12.950 €/anno (formula PMT standard)
        a = _french_annuity(100_000, 0.05, 10)
        assert 12_900 < a < 13_000


# ============================================================================
# BUSINESS PLAN END-TO-END
# ============================================================================
class TestBusinessPlan:
    def test_bp_realistic_scenario(self):
        """Impianto 250 Smc/h, tariffa 245 €/MWh, CAPEX 38k/Smc/h, no PNRR."""
        bp = build_business_plan(
            plant_smch=250, tariffa_eur_mwh=245,
            capex_eur_per_smch=38_000, opex_eur_per_smch_year=5_350,
            pnrr_quota_pct=0,
        )
        # CAPEX = 250 * 38000 = 9.5M
        assert bp.capex_total == pytest.approx(9_500_000, rel=0.001)
        # Senza PNRR il debito = 70% di 9.5M = 6.65M
        assert bp.capex_debt == pytest.approx(6_650_000, rel=0.001)
        # Equity = 9.5M - 6.65M = 2.85M
        assert bp.capex_equity == pytest.approx(2_850_000, rel=0.001)
        # PNRR grant = 0
        assert bp.pnrr_grant == 0.0
        # IRR positivo (settore biometano profittevole)
        assert bp.irr_project > 0.10  # > 10%
        # NPV positivo @ 6% WACC
        assert bp.npv_project > 0
        # Payback ragionevole
        assert bp.payback_years is not None
        assert 0 < bp.payback_years < 10

    def test_bp_pnrr_increases_returns(self):
        """PNRR 40% riduce CAPEX netto → IRR e payback migliorano."""
        common = dict(plant_smch=250, tariffa_eur_mwh=245,
                       capex_eur_per_smch=38_000,
                       opex_eur_per_smch_year=5_350)
        bp_no_pnrr = build_business_plan(**common, pnrr_quota_pct=0)
        bp_pnrr40 = build_business_plan(**common, pnrr_quota_pct=40)
        assert bp_pnrr40.irr_project > bp_no_pnrr.irr_project
        assert bp_pnrr40.payback_years < bp_no_pnrr.payback_years
        # Grant = 40% di 9.5M = 3.8M
        assert bp_pnrr40.pnrr_grant == pytest.approx(3_800_000, rel=0.001)

    def test_bp_year_count(self):
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
            durata_tariffa=15,
        )
        # 16 righe: anno 0 (investimento) + 15 anni operativi
        assert len(bp.rows) == 16
        assert bp.rows[0].year == 0
        assert bp.rows[-1].year == 15

    def test_bp_inflation_increases_opex(self):
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
            inflation_pct=2.5,
        )
        # OPEX anno 1 < anno 5 < anno 15
        opex_y1 = bp.rows[1].opex
        opex_y5 = bp.rows[5].opex
        opex_y15 = bp.rows[15].opex
        assert opex_y1 < opex_y5 < opex_y15

    def test_bp_debito_residuo_decrescente(self):
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
            loan_duration_years=10,
        )
        # Debito residuo decresce nel tempo
        debiti = [r.debito_residuo for r in bp.rows[1:11]]
        assert all(debiti[i] >= debiti[i + 1] for i in range(len(debiti) - 1))
        # Dopo loan_duration debito ~ 0 (tolleranza floating point)
        assert bp.rows[11].debito_residuo == pytest.approx(0.0, abs=1e-6)

    def test_bp_ebitda_positive(self):
        """Con tariffa 245 e opex 5350, EBITDA deve essere abbondantemente positivo."""
        bp = build_business_plan(
            plant_smch=250, tariffa_eur_mwh=245,
            capex_eur_per_smch=38_000, opex_eur_per_smch_year=5_350,
        )
        for r in bp.rows[1:]:
            assert r.ebitda > 0, f"EBITDA anno {r.year} negativo"

    def test_bp_to_dict(self):
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
        )
        d = bp.to_dict()
        assert "irr_project" in d
        assert "rows" in d
        assert len(d["rows"]) == 16
        assert all(isinstance(r, dict) for r in d["rows"])


class TestStressScenarios:
    """Scenari limite per robustezza."""

    def test_bp_tariff_too_low_negative_ebitda(self):
        """Tariffa molto bassa → EBITDA negativo, IRR negativo o capped."""
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=20,  # tariffa ridicola
            capex_eur_per_smch=38_000, opex_eur_per_smch_year=5_350,
        )
        assert bp.rows[1].ebitda < 0
        # IRR può essere negativo (irrecuperabile)
        assert bp.irr_project < 0.0

    def test_bp_huge_pnrr_grant(self):
        """100% PNRR (caso teorico): debito=0, equity=0."""
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
            pnrr_quota_pct=100,
        )
        assert bp.capex_debt == 0.0
        assert bp.capex_equity == 0.0
        assert bp.pnrr_grant == 3_000_000

    def test_bp_zero_leverage(self):
        """100% equity, 0% debito."""
        bp = build_business_plan(
            plant_smch=100, tariffa_eur_mwh=200,
            capex_eur_per_smch=30_000, opex_eur_per_smch_year=5_000,
            leverage_pct=0,
        )
        assert bp.capex_debt == 0.0
        assert bp.capex_equity == bp.capex_total
        # Nessun interesse pagato
        assert all(r.interessi == 0.0 for r in bp.rows)
