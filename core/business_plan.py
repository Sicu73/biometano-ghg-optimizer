# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/business_plan.py — Business Plan multi-anno con IRR / NPV / Payback.

Engine finanziario per la valutazione di un impianto biometano DM 2022.
Inputs di base: plant_smch, tariffa €/MWh, CAPEX, OPEX. Output: dict con
DataFrame 15 anni + KPI sintetici (IRR equity, IRR project, NPV, payback).

Formule:
  - Ricavi anno N = plant_smch * ore_anno * (tariffa/1000) * PCI_kWh/Smc
  - OPEX anno N = OPEX_base * (1 + inflation_pct)^N
  - EBITDA = Ricavi - OPEX
  - Imposte = max(0, EBITDA - Interessi - Ammortamenti) * tax_rate
  - Cash Flow operativo = EBITDA - Imposte
  - FCF Project = CFO - Rata_capitale
  - FCF Equity = FCF Project - Interessi
  - IRR = tasso che azzera NPV(FCF)
  - NPV = somma_anni FCF / (1 + discount_rate)^anno - Equity_iniziale
  - Payback (anni) = primo anno con cumulato FCF >= 0

NB: ammortamento lineare 15 anni standard (allineato durata tariffa).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any



# Costanti default
DEFAULT_DURATA_TARIFFA = 15        # anni
DEFAULT_ORE_ANNO = 8500.0          # ore funzionamento (~97% disponibilità)
DEFAULT_PCI_KWH_SMC = 9.79         # PCI biometano standard (UNI EN 16723-1, ~98% CH4)
DEFAULT_INFLATION_PCT = 2.5        # % annua OPEX
DEFAULT_LEVERAGE_PCT = 70.0        # % CAPEX finanziato
DEFAULT_INTEREST_RATE_PCT = 5.0    # % annuo finanziamento LT
DEFAULT_TAX_RATE_PCT = 24.0        # IRES + IRAP semplificato
DEFAULT_DISCOUNT_RATE_PCT = 6.0    # WACC tipico settore energia rinnovabile
DEFAULT_LOAN_DURATION_YEARS = 12   # ammortamento bancario standard


@dataclass
class BPYear:
    """Riga di un anno del Business Plan."""
    year: int
    ricavi: float = 0.0
    opex: float = 0.0
    ebitda: float = 0.0
    ammortamento: float = 0.0
    interessi: float = 0.0
    imposte: float = 0.0
    cfo: float = 0.0                  # Cash Flow Operativo (netto imposte)
    rata_capitale: float = 0.0        # Quota capitale del finanziamento
    fcf_project: float = 0.0          # CFO - rata capitale (Project)
    fcf_equity: float = 0.0           # FCF dopo interessi (Equity)
    debito_residuo: float = 0.0
    fcf_cumulato: float = 0.0


@dataclass
class BusinessPlan:
    """Output completo del Business Plan."""
    plant_smch: float
    tariffa_eur_mwh: float
    capex_total: float
    capex_equity: float
    capex_debt: float
    pnrr_grant: float                 # quota a fondo perduto PNRR
    opex_year1: float
    durata: int
    rows: list[BPYear] = field(default_factory=list)
    irr_project: float = 0.0          # IRR sul progetto
    irr_equity: float = 0.0           # IRR sull'equity
    npv_project: float = 0.0          # NPV @ discount_rate
    payback_years: float | None = None
    discount_rate_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "plant_smch": self.plant_smch,
            "tariffa_eur_mwh": self.tariffa_eur_mwh,
            "capex_total": self.capex_total,
            "capex_equity": self.capex_equity,
            "capex_debt": self.capex_debt,
            "pnrr_grant": self.pnrr_grant,
            "opex_year1": self.opex_year1,
            "durata": self.durata,
            "irr_project": self.irr_project,
            "irr_equity": self.irr_equity,
            "npv_project": self.npv_project,
            "payback_years": self.payback_years,
            "discount_rate_pct": self.discount_rate_pct,
            "rows": [r.__dict__ for r in self.rows],
        }


# ============================================================================
# IRR / NPV / PAYBACK
# ============================================================================
def _npv(cash_flows: list[float], rate: float) -> float:
    """NPV con flow[0] = -investimento, flow[1..] = ricavi netti."""
    return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cash_flows))


def _irr(cash_flows: list[float], guess: float = 0.10) -> float:
    """IRR via bisezione (più robusto di Newton-Raphson per BP).

    Casi edge:
    - Tutti cash_flow positivi (no investimento): return 0.0
    - Tutti cash_flow negativi: return 0.0
    - NPV(hi=10.0) ancora positivo (IRR > 1000%): return 10.0 (cap)
    - NPV(lo=-0.99) negativo (IRR < -99%): return -0.99
    """
    if not cash_flows:
        return 0.0
    # Tutti positivi: nessun investimento, IRR non definito
    if all(cf >= 0 for cf in cash_flows):
        return 0.0
    # Tutti negativi (compreso year 0): perdita totale, IRR = -100% (-1.0)
    if all(cf <= 0 for cf in cash_flows):
        return -1.0
    lo, hi = -0.99, 10.0
    npv_lo = _npv(cash_flows, lo)
    npv_hi = _npv(cash_flows, hi)
    # IRR > 1000%: caso "troppo bello per essere vero". Restituisco cap 10.0.
    if npv_hi > 0 and npv_lo > 0:
        return 10.0
    # IRR < -99%: catastrofico. Restituisco floor -0.99.
    if npv_hi < 0 and npv_lo < 0:
        return -0.99
    # Bisezione standard
    for _ in range(200):
        mid = (lo + hi) / 2.0
        npv_mid = _npv(cash_flows, mid)
        if abs(npv_mid) < 1e-6:
            return mid
        if npv_lo * npv_mid < 0:
            hi = mid
            npv_hi = npv_mid
        else:
            lo = mid
            npv_lo = npv_mid
    return (lo + hi) / 2.0


def _payback(cash_flows: list[float]) -> float | None:
    """Payback period (anni). Interpolazione lineare nell'anno di break-even."""
    cum = 0.0
    prev = 0.0
    for i, cf in enumerate(cash_flows):
        prev = cum
        cum += cf
        if cum >= 0 and i > 0:
            # Interpolazione lineare nel'anno
            if cf == 0:
                return float(i)
            frac = -prev / cf if cf != 0 else 0.0
            return (i - 1) + max(0.0, min(1.0, frac))
    return None  # mai recupera


# ============================================================================
# BUILDER
# ============================================================================
def build_business_plan(
    plant_smch: float,
    tariffa_eur_mwh: float,
    *,
    capex_eur_per_smch: float,
    opex_eur_per_smch_year: float,
    pnrr_quota_pct: float = 0.0,
    durata_tariffa: int = DEFAULT_DURATA_TARIFFA,
    ore_anno: float = DEFAULT_ORE_ANNO,
    pci_kwh_per_smc: float = DEFAULT_PCI_KWH_SMC,
    leverage_pct: float = DEFAULT_LEVERAGE_PCT,
    interest_rate_pct: float = DEFAULT_INTEREST_RATE_PCT,
    loan_duration_years: int = DEFAULT_LOAN_DURATION_YEARS,
    tax_rate_pct: float = DEFAULT_TAX_RATE_PCT,
    inflation_pct: float = DEFAULT_INFLATION_PCT,
    discount_rate_pct: float = DEFAULT_DISCOUNT_RATE_PCT,
) -> BusinessPlan:
    """Costruisce il Business Plan multi-anno.

    Args:
        plant_smch: portata netta autorizzata Sm³/h.
        tariffa_eur_mwh: tariffa onnicomprensiva o premio finale €/MWh.
        capex_eur_per_smch: investimento per Smc/h capacità nominale (€/Smc/h).
        opex_eur_per_smch_year: OPEX annuo per Smc/h (anno 1, scalerà con inflazione).
        pnrr_quota_pct: % contributo a fondo perduto PNRR su CAPEX (0-40).
        leverage_pct: % CAPEX finanziato con debito bancario (0-100).
        interest_rate_pct: tasso interesse finanziamento LT.
        loan_duration_years: durata ammortamento finanziamento (default 12).
        tax_rate_pct: aliquota IRES+IRAP semplificata.
        inflation_pct: incremento annuo OPEX.
        discount_rate_pct: WACC per calcolo NPV.

    Returns:
        BusinessPlan con tabella `rows` (lista BPYear), IRR project/equity,
        NPV e payback.
    """
    # CAPEX totale & ripartizione
    capex_total = float(plant_smch) * float(capex_eur_per_smch)
    pnrr_grant = capex_total * float(pnrr_quota_pct) / 100.0
    capex_net = capex_total - pnrr_grant
    capex_debt = capex_net * float(leverage_pct) / 100.0
    capex_equity = capex_net - capex_debt

    # Ricavo anno 1
    biometano_smc_anno = float(plant_smch) * float(ore_anno)
    tariffa_eur_smc = float(tariffa_eur_mwh) / 1000.0 * float(pci_kwh_per_smc)
    ricavo_year1 = biometano_smc_anno * tariffa_eur_smc

    # OPEX anno 1
    opex_year1 = float(plant_smch) * float(opex_eur_per_smch_year)

    # Ammortamento bancario (rata costante francese)
    rata_costante = _french_annuity(capex_debt,
                                     float(interest_rate_pct) / 100.0,
                                     int(loan_duration_years))

    # Ammortamento contabile lineare (15 anni) sulla base AMMORTIZZABILE, cioe'
    # al netto del contributo a fondo perduto PNRR (contributo in conto impianti:
    # i beni finanziati da contributo non sono fiscalmente ammortizzabili).
    ammort_annuo = capex_net / float(durata_tariffa)

    # Costruzione righe anno per anno
    rows: list[BPYear] = []
    debito_residuo = capex_debt
    fcf_cumulato_equity = -capex_equity

    # Year 0 (investimento iniziale, no produzione)
    rows.append(BPYear(
        year=0,
        ricavi=0.0, opex=0.0, ebitda=0.0, ammortamento=0.0,
        interessi=0.0, imposte=0.0, cfo=0.0,
        rata_capitale=0.0,
        fcf_project=-capex_net, fcf_equity=-capex_equity,
        debito_residuo=capex_debt,
        fcf_cumulato=fcf_cumulato_equity,
    ))

    for y in range(1, int(durata_tariffa) + 1):
        ricavi = ricavo_year1  # ricavi fissi (tariffa GSE costante 15 anni)
        opex = opex_year1 * ((1.0 + float(inflation_pct) / 100.0) ** (y - 1))
        ebitda = ricavi - opex

        # Calcolo interessi + capitale del finanziamento
        if y <= int(loan_duration_years) and debito_residuo > 0:
            interessi_y = debito_residuo * float(interest_rate_pct) / 100.0
            quota_capitale = rata_costante - interessi_y
            quota_capitale = max(0.0, min(quota_capitale, debito_residuo))
        else:
            interessi_y = 0.0
            quota_capitale = 0.0

        _tax = float(tax_rate_pct) / 100.0
        # Imposte EQUITY (reali, levered): deducono gli interessi passivi.
        utile_lordo = ebitda - interessi_y - ammort_annuo
        imposte = max(0.0, utile_lordo) * _tax
        # Imposte PROJECT (unlevered): SENZA deduzione interessi, cosi' l'IRR di
        # progetto e' indipendente dalla struttura finanziaria (no scudo debito).
        imposte_project = max(0.0, ebitda - ammort_annuo) * _tax

        # Cash flows
        cfo = ebitda - imposte
        # Project FCF unlevered: solo EBITDA - imposte unlevered (nessun flusso
        # di debito: ne' interessi ne' rimborso capitale).
        fcf_project = ebitda - imposte_project
        fcf_equity = cfo - quota_capitale - interessi_y  # Equity dopo interessi

        debito_residuo = max(0.0, debito_residuo - quota_capitale)
        fcf_cumulato_equity += fcf_equity

        rows.append(BPYear(
            year=y, ricavi=ricavi, opex=opex, ebitda=ebitda,
            ammortamento=ammort_annuo, interessi=interessi_y,
            imposte=imposte, cfo=cfo, rata_capitale=quota_capitale,
            fcf_project=fcf_project, fcf_equity=fcf_equity,
            debito_residuo=debito_residuo, fcf_cumulato=fcf_cumulato_equity,
        ))

    # IRR / NPV / Payback
    # IRR Project: investimento = CAPEX totale - PNRR (no debito), FCF = ricavi - opex - imposte
    cf_project = [-capex_net] + [r.fcf_project for r in rows[1:]]
    # IRR Equity: investimento = capex_equity, FCF = fcf_equity (dopo interessi+capitale)
    cf_equity = [-capex_equity] + [r.fcf_equity for r in rows[1:]]

    irr_project = _irr(cf_project)
    irr_equity = _irr(cf_equity)
    npv_project = _npv(cf_project, float(discount_rate_pct) / 100.0)
    payback = _payback(cf_equity)

    return BusinessPlan(
        plant_smch=float(plant_smch),
        tariffa_eur_mwh=float(tariffa_eur_mwh),
        capex_total=capex_total,
        capex_equity=capex_equity,
        capex_debt=capex_debt,
        pnrr_grant=pnrr_grant,
        opex_year1=opex_year1,
        durata=int(durata_tariffa),
        rows=rows,
        irr_project=irr_project,
        irr_equity=irr_equity,
        npv_project=npv_project,
        payback_years=payback,
        discount_rate_pct=float(discount_rate_pct),
    )


def _french_annuity(principal: float, annual_rate: float, n_years: int) -> float:
    """Rata costante (sistema francese) per finanziamento."""
    if principal <= 0 or n_years <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / float(n_years)
    r = float(annual_rate)
    n = int(n_years)
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


__all__ = [
    "BPYear",
    "BusinessPlan",
    "build_business_plan",
    "DEFAULT_DURATA_TARIFFA",
    "DEFAULT_ORE_ANNO",
    "DEFAULT_PCI_KWH_SMC",
    "DEFAULT_INFLATION_PCT",
    "DEFAULT_LEVERAGE_PCT",
    "DEFAULT_INTEREST_RATE_PCT",
    "DEFAULT_TAX_RATE_PCT",
    "DEFAULT_DISCOUNT_RATE_PCT",
    "DEFAULT_LOAN_DURATION_YEARS",
]
