# -*- coding: utf-8 -*-
"""output/output_builder.py — Costruttore del modello di output unificato.

Funzione principale:
    build_output_model(ctx: dict) -> dict

`ctx` e' il contesto dati gia' prodotto dall'app (tutte le variabili
calcolate in app_mensile.py prima degli export). `build_output_model`
normalizza, centralizza e arricchisce i dati in un output_model
strutturato che e' l'unica fonte per tutti gli export.

Struttura output_model:
  metadata              — info software, versione, lingua, scenario
  input_summary         — riepilogo impianto, biomasse, modalita'
  calculation_summary   — KPI aggregati principali
  monthly_table         — lista dict riga per mese
  feedstock_table       — lista dict riga per biomassa
  ghg_table             — lista dict riga per biomassa (fattori GHG)
  business_plan_table   — lista dict riga per anno BP (solo DM 2022)
  audit_trail           — lista dict righe audit BMT + EF
  warnings              — lista di stringhe warning
  errors                — lista di stringhe errori
  explanations          — dict testi spiegativi origine dati
"""
from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Import opzionali (non crashano se mancano)
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

try:
    from .explanations import build_all_explanations
except ImportError:
    def build_all_explanations(ctx: dict) -> dict:  # type: ignore[misc]
        return {
            "yield_origin": "",
            "emission_factor_origin": "",
            "ghg_method": "",
            "regulatory_basis": "",
        }

# ---------------------------------------------------------------------------
# Versione software (singolo punto di verita': core/version.py)
# ---------------------------------------------------------------------------
try:
    from core.version import __version__ as _SOFTWARE_VERSION, __product__ as _SOFTWARE_NAME
except Exception:  # noqa: BLE001
    _SOFTWARE_NAME = "Metan.iQ"
    _SOFTWARE_VERSION = "0.4.0"


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------

def build_output_model(ctx: dict) -> dict:
    """Costruisce il modello di output unificato da un contesto di calcolo.

    Args:
        ctx:    Dict con tutti i dati di calcolo prodotti da app_mensile.py.
                Chiavi supportate (vedi documentazione estesa in OUTPUT_REFACTOR_MAP.md):
                  - df_res (DataFrame o lista di dict)
                  - active_feeds (list[str])
                  - FEEDSTOCK_DB (dict)
                  - aux_factor (float)
                  - ep_total (float)
                  - fossil_comparator (float)
                  - ghg_threshold (float)
                  - plant_net_smch (float)
                  - IS_CHP, IS_FER2, IS_DM2018, IS_DM2022 (bool)
                  - APP_MODE (str)
                  - end_use (str)
                  - tot_biomasse_t, tot_sm3_netti, tot_mwh_netti (float)
                  - saving_avg (float)
                  - valid_months (int)
                  - tot_revenue (float)
                  - bp_result (dict | None)
                  - yield_audit_rows (list)
                  - emission_audit_rows (list)
                  - lang (str)

    Returns:
        output_model dict con struttura standardizzata.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # --- metadata -----------------------------------------------------------
    app_mode = ctx.get("APP_MODE", "biometano")
    lang = ctx.get("lang", "it")
    scenario_name = _build_scenario_name(ctx)

    metadata: dict[str, Any] = {
        "software_name": _SOFTWARE_NAME,
        "version": _SOFTWARE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "language": lang,
        "scenario_name": scenario_name,
        "app_mode": app_mode,
    }

    # --- input_summary -------------------------------------------------------
    active_feeds: list[str] = ctx.get("active_feeds", [])
    feedstock_db: dict = ctx.get("FEEDSTOCK_DB", {})
    plant_net_smch: float = float(ctx.get("plant_net_smch", 0.0))
    plant_kwe: float = float(ctx.get("plant_kwe", 0.0))
    aux_factor: float = float(ctx.get("aux_factor", 1.29))
    ep_total: float = float(ctx.get("ep_total", 0.0))
    end_use: str = ctx.get("end_use", "")
    is_chp: bool = bool(ctx.get("IS_CHP", False))
    is_fer2: bool = bool(ctx.get("IS_FER2", False))
    is_dm2018: bool = bool(ctx.get("IS_DM2018", False))
    is_dm2022: bool = bool(ctx.get("IS_DM2022", True))

    feedstocks_summary = []
    for name in active_feeds:
        db_entry = feedstock_db.get(name, {})
        feedstocks_summary.append({
            "name": name,
            "category": db_entry.get("cat", ""),
            "annex_ix": db_entry.get("annex_ix"),
            "yield_std": db_entry.get("yield", 0.0),
            "eec": db_entry.get("eec", 0.0),
            "etd": db_entry.get("etd", 0.0),
            "esca": db_entry.get("esca", 0.0),
            "src": db_entry.get("src", ""),
        })

    input_summary: dict[str, Any] = {
        "plant": {
            "plant_net_smch": plant_net_smch,
            "plant_kwe": plant_kwe if is_chp else None,
            "aux_factor": aux_factor,
            "ep_total": ep_total,
            "end_use": end_use,
            "is_chp": is_chp,
            "is_fer2": is_fer2,
            "is_dm2018": is_dm2018,
            "is_dm2022": is_dm2022,
            "ghg_threshold": float(ctx.get("ghg_threshold", 0.80)),
            "fossil_comparator": float(ctx.get("fossil_comparator", 80.0)),
            "upgrading_opt": ctx.get("upgrading_opt", ""),
            "offgas_opt": ctx.get("offgas_opt", ""),
            "injection_opt": ctx.get("injection_opt", ""),
        },
        "feedstocks": feedstocks_summary,
        "mode": app_mode,
    }

    # --- monthly_table (da df_res) ------------------------------------------
    monthly_table = _extract_monthly_table(ctx, warnings)

    # --- calculation_summary -------------------------------------------------
    tot_biomasse_t = _safe_float(ctx.get("tot_biomasse_t"), monthly_table,
                                  "Totale biomasse (t)", warnings)
    tot_sm3_netti = _safe_float(ctx.get("tot_sm3_netti"), monthly_table,
                                 "Sm³ netti", warnings)
    tot_sm3_lordi = _safe_float(ctx.get("tot_sm3_lordi"), monthly_table,
                                 "Sm³ lordi", warnings)
    tot_mwh = _safe_float(ctx.get("tot_mwh_netti") or ctx.get("tot_mwh"), None,
                           None, warnings)
    # MWh lordi: se non passato dall'app, derivato dai Sm3 lordi.
    # NM3_TO_MWH = 0.00997 MWh/Sm3 (biometano puro CH4 al ~100%, LHV).
    _NM3_TO_MWH = 0.00997
    tot_mwh_lordi_ctx = ctx.get("tot_mwh_lordi")
    if tot_mwh_lordi_ctx is not None:
        try:
            tot_mwh_lordi = float(tot_mwh_lordi_ctx)
        except (TypeError, ValueError):
            tot_mwh_lordi = tot_sm3_lordi * _NM3_TO_MWH
    else:
        tot_mwh_lordi = tot_sm3_lordi * _NM3_TO_MWH
        # Fallback: se manca il lordo ma c'e' il netto + aux, derivalo
        if tot_mwh_lordi <= 0 and tot_mwh > 0 and aux_factor > 0:
            tot_mwh_lordi = tot_mwh * aux_factor
        # Se manca anche il Sm3 lordi ma abbiamo Sm3 netti + aux
        if tot_sm3_lordi <= 0 and tot_sm3_netti > 0 and aux_factor > 0:
            tot_sm3_lordi = tot_sm3_netti * aux_factor
    saving_avg = _safe_float(ctx.get("saving_avg"), monthly_table,
                              "Saving %", warnings, is_mean=True)
    valid_months = ctx.get("valid_months")
    if valid_months is None and monthly_table:
        valid_months = sum(
            1 for r in monthly_table
            if str(r.get("Validità", r.get("validity", ""))).startswith("✅")
        )
    total_revenue = float(ctx.get("tot_revenue", 0.0))

    # --- Sostenibilita': base normativa esplicita ---------------------------
    # La saving% RED III/DM 2022/DM 2018/DM 2012/FER 2 e' calcolata come
    # intensita' gCO2eq/MJ sull'energia LORDA (Sm3 lordi x LHV).
    # Per il biometano (DM 2018 / DM 2022) esponiamo anche la vista NETTO
    # come informativo aggiuntivo (Sm3 netti = effettiva immissione in rete).
    is_biomethane = bool(is_dm2018 or is_dm2022) and not is_chp
    sustainability_basis = "LORDO"
    sustainability_basis_note = (
        "Saving GHG calcolato come intensita' gCO2eq/MJ sull'ENERGIA LORDA "
        "(Sm3 lordi x LHV biometano). Base ufficiale per RED III, DM 15/9/2022, "
        "DM 2/3/2018, DM 6/7/2012 (CHP) e DM 18/9/2024 (FER 2)."
    )
    if is_biomethane:
        sustainability_basis_note += (
            " Per il biometano viene esposta anche la vista NETTO "
            "(Sm3 netti = Sm3 lordi / aux_factor) come riferimento "
            "informativo aggiuntivo per l'energia effettivamente immessa "
            "in rete; il vincolo normativo resta sul LORDO."
        )

    calculation_summary: dict[str, Any] = {
        "tot_biomasse_t": tot_biomasse_t,
        "tot_sm3_netti": tot_sm3_netti,
        "tot_sm3_lordi": tot_sm3_lordi,
        "tot_mwh": tot_mwh,
        "tot_mwh_lordi": tot_mwh_lordi,
        "saving_avg": saving_avg,
        "valid_months": int(valid_months) if valid_months is not None else 0,
        "total_revenue": total_revenue,
        # CHP-specific
        "tot_mwh_el_lordo": float(ctx.get("tot_mwh_el_lordo", 0.0)),
        "tot_mwh_el_netto": float(ctx.get("tot_mwh_el_netto", 0.0)),
        # DM 2018 CIC
        "tot_n_cic": float(ctx.get("tot_n_cic", 0.0)),
        "cic_active": bool(ctx.get("cic_active", False)),
        "is_advanced": bool(ctx.get("is_advanced", False)),
        # tariffa
        "tariffa_media_ponderata": float(ctx.get("tariffa_media_ponderata", 0.0)),
        # base sostenibilita' esplicita
        "sustainability_basis": sustainability_basis,
        "sustainability_basis_note": sustainability_basis_note,
        "biomethane_dual_view": bool(is_biomethane),
    }

    # --- feedstock_table (dettaglio per biomassa) ----------------------------
    feedstock_table = _build_feedstock_table(ctx, active_feeds, feedstock_db)

    # --- ghg_table -----------------------------------------------------------
    ghg_table = _build_ghg_table(ctx, active_feeds, feedstock_db)

    # --- business_plan_table (solo DM 2022) ----------------------------------
    bp_result: dict | None = ctx.get("bp_result")
    business_plan_table = _build_bp_table(bp_result)

    # --- audit_trail (BMT + EF) ----------------------------------------------
    audit_trail = _build_audit_trail(ctx)

    # --- warnings / errors dall'app ------------------------------------------
    app_warnings: list = ctx.get("warnings", [])
    app_errors: list = ctx.get("errors", [])
    if isinstance(app_warnings, list):
        warnings.extend([str(w) for w in app_warnings])
    if isinstance(app_errors, list):
        errors.extend([str(e) for e in app_errors])

    # Aggiungi warning per mesi non validi
    invalid_months_list = [
        r.get("Mese", r.get("month", "?"))
        for r in monthly_table
        if not str(r.get("Validità", r.get("validity", ""))).startswith("✅")
        and str(r.get("Ore", r.get("hours", 1))) not in ("0", "0.0")
    ]
    if invalid_months_list:
        warnings.append(
            f"Mesi sotto soglia saving RED III "
            f"({calculation_summary['valid_months']}/12 validi): "
            f"{', '.join(invalid_months_list)}."
        )

    # --- explanations --------------------------------------------------------
    try:
        explanations = build_all_explanations(ctx)
    except Exception as exc:
        explanations = {
            "yield_origin": "",
            "emission_factor_origin": "",
            "ghg_method": "",
            "regulatory_basis": "",
        }
        warnings.append(f"Impossibile generare spiegazioni: {exc}")

    # --- output_model finale -------------------------------------------------
    output_model: dict[str, Any] = {
        "metadata": metadata,
        "input_summary": input_summary,
        "calculation_summary": calculation_summary,
        "monthly_table": monthly_table,
        "feedstock_table": feedstock_table,
        "ghg_table": ghg_table,
        "business_plan_table": business_plan_table,
        "audit_trail": audit_trail,
        "warnings": warnings,
        "errors": errors,
        "explanations": explanations,
    }
    return output_model


# ---------------------------------------------------------------------------
# Helpers privati
# ---------------------------------------------------------------------------

def _build_scenario_name(ctx: dict) -> str:
    """Costruisce un nome leggibile per lo scenario."""
    mode_labels = {
        "biometano":       "Biometano DM 2022",
        "biometano_2018":  "Biometano DM 2018 CIC",
        "biogas_chp":      "Biogas CHP DM 6/7/2012",
        "biogas_chp_fer2": "Biogas CHP FER 2",
    }
    mode = ctx.get("APP_MODE", "biometano")
    label = ctx.get("APP_MODE_LABEL") or mode_labels.get(mode, mode)
    plant = ctx.get("plant_net_smch", "")
    if plant:
        return f"{label} — {plant} Sm³/h"
    return label


def _extract_monthly_table(ctx: dict, warnings: list[str]) -> list[dict]:
    """Estrae la tabella mensile da df_res (DataFrame o lista di dict)."""
    df_res = ctx.get("df_res")
    if df_res is None:
        warnings.append("df_res non presente nel contesto: monthly_table sara' vuota.")
        return []
    try:
        if _HAS_PANDAS:
            import pandas as pd
            if isinstance(df_res, pd.DataFrame):
                return df_res.to_dict(orient="records")
        if isinstance(df_res, list):
            return df_res
        warnings.append(f"df_res di tipo inatteso ({type(df_res).__name__}): monthly_table vuota.")
        return []
    except Exception as exc:
        warnings.append(f"Errore estrazione monthly_table: {exc}")
        return []


def _safe_float(
    primary: Any,
    table: list[dict] | None,
    col: str | None,
    warnings: list[str],
    is_mean: bool = False,
) -> float:
    """Ritorna primary se valido, altrimenti lo calcola dalla tabella."""
    if primary is not None:
        try:
            return float(primary)
        except (TypeError, ValueError):
            pass
    if table and col:
        try:
            vals = []
            for row in table:
                v = row.get(col)
                if v is not None:
                    try:
                        vals.append(float(str(v).replace(",", ".").replace("%", "").strip()))
                    except (ValueError, TypeError):
                        pass
            if vals:
                return sum(vals) / len(vals) if is_mean else sum(vals)
        except Exception:
            pass
    return 0.0


def _build_feedstock_table(
    ctx: dict,
    active_feeds: list[str],
    feedstock_db: dict,
) -> list[dict[str, Any]]:
    """Costruisce la tabella feedstock con quantita' annuali."""
    annual_t: dict = ctx.get("annual_t", {})
    annual_mwh: dict = ctx.get("annual_mwh", {})
    revenue_rows: list = ctx.get("revenue_rows", [])
    revenue_map = {r[0]: r[1] for r in revenue_rows if isinstance(r, (list, tuple)) and len(r) >= 2}

    rows = []
    for name in active_feeds:
        db = feedstock_db.get(name, {})
        t = float(annual_t.get(name, 0.0))
        mwh = float(annual_mwh.get(name, 0.0))
        rev_data = revenue_map.get(name, {})
        rows.append({
            "biomassa": name,
            "categoria": db.get("cat", ""),
            "annex_ix": db.get("annex_ix"),
            "tonnellate_anno": t,
            "mwh_anno": mwh,
            "ricavi_eur": float(rev_data.get("ricavi", 0.0)) if isinstance(rev_data, dict) else 0.0,
            "tariffa_eur_mwh": float(rev_data.get("tariffa", 0.0)) if isinstance(rev_data, dict) else 0.0,
            "n_cic": float(rev_data.get("n_cic", 0.0)) if isinstance(rev_data, dict) else 0.0,
        })
    return rows


def _build_ghg_table(
    ctx: dict,
    active_feeds: list[str],
    feedstock_db: dict,
) -> list[dict[str, Any]]:
    """Costruisce la tabella fattori GHG per biomassa."""
    emission_overrides: dict = ctx.get("emission_overrides", {})

    rows = []
    for name in active_feeds:
        db = feedstock_db.get(name, {})
        override = emission_overrides.get(name, {})
        if override:
            eec  = float(override.get("eec",  db.get("eec",  0.0)))
            etd  = float(override.get("etd",  db.get("etd",  0.0)))
            esca = float(override.get("esca", db.get("esca", 0.0)))
            ep   = float(override.get("ep",   0.0))
            src  = str(override.get("source", "Relazione tecnica reale"))
            e_tot = float(override.get("e_total", eec + etd - esca + ep))
        else:
            eec  = float(db.get("eec",  0.0))
            etd  = float(db.get("etd",  0.0))
            esca = float(db.get("esca", 0.0))
            ep   = float(ctx.get("ep_total", 0.0))
            src  = str(db.get("src", "tabella standard"))
            e_tot = eec + etd - esca + ep
        rows.append({
            "biomassa": name,
            "eec": eec,
            "etd": etd,
            "esca": esca,
            "ep": ep,
            "e_total": e_tot,
            "fonte": src,
            "override_attivo": bool(override),
        })
    return rows


def _build_bp_table(bp_result: dict | None) -> list[dict[str, Any]]:
    """Costruisce la tabella Business Plan annuale da bp_result."""
    if not bp_result:
        return []
    ricavi: list = bp_result.get("ricavi", [])
    opex: list = bp_result.get("opex", [])
    ebitda: list = bp_result.get("ebitda", [])
    interessi: list = bp_result.get("interessi", [])
    ammort: list = bp_result.get("ammortamenti", [])
    utile_ante: list = bp_result.get("utile_ante", [])
    utile_netto: list = bp_result.get("utile_netto", [])
    fcf: list = bp_result.get("fcf", [])
    n = len(ricavi)
    rows = []
    for y in range(n):
        rows.append({
            "anno": y + 1,
            "ricavi_eur": _idx(ricavi, y),
            "opex_eur": _idx(opex, y),
            "ebitda_eur": _idx(ebitda, y),
            "interessi_eur": _idx(interessi, y),
            "ammortamenti_eur": _idx(ammort, y),
            "utile_ante_eur": _idx(utile_ante, y),
            "utile_netto_eur": _idx(utile_netto, y),
            "fcf_eur": _idx(fcf, y),
        })
    return rows


def _build_audit_trail(ctx: dict) -> list[dict[str, Any]]:
    """Costruisce l'audit trail unificato BMT + fattori emissivi."""
    rows: list[dict[str, Any]] = []
    yield_audit: list = ctx.get("yield_audit_rows", [])
    emission_audit: list = ctx.get("emission_audit_rows", [])

    for entry in yield_audit:
        if isinstance(entry, dict):
            rows.append({"tipo": "BMT_yield_override", **entry})
        else:
            rows.append({"tipo": "BMT_yield_override", "raw": str(entry)})

    for entry in emission_audit:
        if isinstance(entry, dict):
            rows.append({"tipo": "emission_factor_override", **entry})
        else:
            rows.append({"tipo": "emission_factor_override", "raw": str(entry)})

    return rows


def _idx(lst: list, i: int) -> float:
    """Ritorna lst[i] come float, 0.0 se fuori range."""
    try:
        return float(lst[i])
    except (IndexError, TypeError, ValueError):
        return 0.0
