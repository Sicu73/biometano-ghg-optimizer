# Copyright (c) 2026 Carlo Sicurini - Metan.iQ
"""solve_2_unknowns_dual: il saving e' un vincolo di DISUGUAGLIANZA.

Il solver risolve il 2x2 con saving = target. Se una massa esce negativa
perche' il saving sarebbe in ECCESSO, il mix clampato (quella massa a 0,
l'altra a chiudere la produzione) rispetta comunque produzione e saving
>= soglia: non va segnalato come infeasibile. Prima il banner diceva
"Saving e/o produzione non saranno entrambi soddisfatti" mentre la colonna
Validita' dello stesso mese diceva "Valido".
"""
from __future__ import annotations

import app_mensile as A

FIXED = {"Trinciato di mais": 1800.0, "Trinciato di sorgo da foraggio": 400.0}
UNKNOWN = ["Pollina ovaiole (aerobico)", "Liquame suino"]
HOURS, AUX, PLANT, EP = 744.0, 1.29, 300.0, 0.0


def _e_w_and_gross(masses: dict) -> tuple[float, float]:
    num = sum(m * A._yield_of(n) * A.e_total_feedstock(n, EP) for n, m in masses.items())
    den = sum(m * A._yield_of(n) for n, m in masses.items())
    return num / den, den


def test_saving_in_excess_is_feasible():
    target = 80.0 * (1 - 0.65)          # trasporti: e_max 28 gCO2/MJ
    sol, ok, msg = A.solve_2_unknowns_dual(FIXED, UNKNOWN, HOURS, AUX, PLANT, EP, target)
    assert ok, msg
    assert msg == ""
    assert all(v >= 0 for v in sol.values()), sol
    e_w, gross = _e_w_and_gross({**FIXED, **sol})
    assert abs(gross - PLANT * AUX * HOURS) < 1e-6 * gross
    assert e_w <= target + 1e-9, e_w


def test_saving_in_deficit_stays_infeasible():
    target = 80.0 * (1 - 0.80)          # rete: e_max 16 gCO2/MJ
    sol, ok, msg = A.solve_2_unknowns_dual(FIXED, UNKNOWN, HOURS, AUX, PLANT, EP, target)
    assert not ok
    assert "Infeasibile" in msg or "Infeasible" in msg
    e_w, _ = _e_w_and_gross({**FIXED, **sol})
    assert e_w > target


def test_interior_solution_unchanged():
    fixed = {"Trinciato di mais": 1500.0, "Trinciato di sorgo da foraggio": 400.0}
    target = 80.0 * (1 - 0.80)
    sol, ok, msg = A.solve_2_unknowns_dual(fixed, UNKNOWN, HOURS, AUX, PLANT, EP, target)
    assert ok and msg == ""
    assert all(v > 0 for v in sol.values()), sol
    e_w, _ = _e_w_and_gross({**fixed, **sol})
    assert abs(e_w - target) < 1e-6
