# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""Casi limite del solver mensile a 2 incognite.

1. Coppia singolare (stesso e_total, es. liquame suino/bovino): prima masse
   0/0 e "infeasibile" anche quando il problema era risolvibile.
2. Margine di sicurezza: il solver punta a soglia + 1 pp; se il margine non
   è raggiungibile ma la soglia sì, il mese è valido (prima banner
   "Infeasibile" e colonna Validità "Valido" nello stesso mese).
"""
from __future__ import annotations

import app_mensile as A

HOURS, AUX, PLANT, EP = 744.0, 1.29, 300.0, 0.0
PAIR = ["Liquame suino", "Liquame bovino"]


def _e_w_gross(masses: dict) -> tuple[float, float]:
    num = sum(m * A._yield_of(n) * A.e_total_feedstock(n, EP) for n, m in masses.items())
    den = sum(m * A._yield_of(n) for n, m in masses.items())
    return num / den, den


def test_precondition_pair_is_singular():
    e = [A.e_total_feedstock(n, EP) for n in PAIR]
    assert abs(e[0] - e[1]) < 1e-9, e


def test_singular_pair_feasible_uses_higher_yield():
    fixed = {"Trinciato di mais": 600.0}
    target = 80.0 * (1 - 0.80)
    sol, ok, msg = A.solve_2_unknowns_dual(fixed, PAIR, HOURS, AUX, PLANT, EP, target)
    assert ok, msg
    best = max(PAIR, key=A._yield_of)
    other = [n for n in PAIR if n != best][0]
    assert sol[other] == 0.0 and sol[best] > 0, sol
    e_w, gross = _e_w_gross({**fixed, **sol})
    assert abs(gross - PLANT * AUX * HOURS) < 1e-6 * gross
    assert e_w <= target + 1e-9


def test_singular_pair_fixed_exceed_production_is_infeasible():
    fixed = {"Trinciato di mais": 2600.0}      # 301.860 Sm3 > 287.928 richiesti
    target = 80.0 * (1 - 0.80)
    sol, ok, msg = A.solve_2_unknowns_dual(fixed, PAIR, HOURS, AUX, PLANT, EP, target)
    assert not ok
    assert all(v == 0.0 for v in sol.values())
    assert "ingolare" in msg or "ingular" in msg


def test_singular_pair_saving_deficit_is_infeasible():
    fixed = {"Trinciato di mais": 2400.0}      # produzione chiudibile, saving no
    target = 80.0 * (1 - 0.80)
    sol, ok, msg = A.solve_2_unknowns_dual(fixed, PAIR, HOURS, AUX, PLANT, EP, target)
    assert not ok
    e_w, _ = _e_w_gross({**fixed, **sol})
    assert e_w > target


def _find_between_threshold_and_margin():
    """Mais fisso tale che l'81% sia irraggiungibile ma l'80% no."""
    unk = ["Pollina ovaiole (aerobico)", "Liquame suino"]
    e81, e80 = 80.0 * (1 - 0.81), 80.0 * (1 - 0.80)
    for mais in range(1000, 2600, 5):
        fx = {"Trinciato di mais": float(mais)}
        _, ok81, _ = A.solve_2_unknowns_dual(fx, unk, 672.0, AUX, PLANT, EP, e81)
        _, ok80, _ = A.solve_2_unknowns_dual(fx, unk, 672.0, AUX, PLANT, EP, e80)
        if not ok81 and ok80:
            return fx, unk, e81, e80
    raise AssertionError("nessun caso fra soglia e margine trovato")


def test_below_margin_but_above_threshold_is_valid():
    fx, unk, e81, e80 = _find_between_threshold_and_margin()
    sol, ok, msg, below = A._solve_month_dual(fx, unk, 672.0, AUX, PLANT, EP, e81, e80)
    assert ok and below and msg == ""
    e_w, _ = _e_w_gross({**fx, **sol})
    assert e81 < e_w <= e80 + 1e-9


def test_margin_reachable_is_not_flagged():
    fx = {"Trinciato di mais": 1200.0, "Trinciato di sorgo da foraggio": 300.0}
    unk = ["Pollina ovaiole (aerobico)", "Liquame suino"]
    sol, ok, msg, below = A._solve_month_dual(
        fx, unk, 744.0, AUX, PLANT, EP, 80.0 * (1 - 0.81), 80.0 * (1 - 0.80))
    assert ok and not below
