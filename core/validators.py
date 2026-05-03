# -*- coding: utf-8 -*-
"""core/validators.py — Validatori input per Metan.iQ.

Funzioni di validazione che operano su dati di input gia' raccolti
dalla UI (sidebar, data_editor). Restituiscono liste di errori/warning
senza toccare Streamlit.

Tutte le funzioni seguono la convenzione:
  validate_*(data) -> tuple[bool, list[str], list[str]]
  returns: (is_valid, errors, warnings)

Le funzioni sono SENZA effetti collaterali (no state mutation,
no st.* calls) e sono testabili in isolamento.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Validazione configurazione impianto
# ---------------------------------------------------------------------------

def validate_plant_config(
    plant_net_smch: float,
    aux_factor: float,
    ep_total: float,
    ghg_threshold: float,
    fossil_comparator: float,
    app_mode: str,
    plant_kwe: float | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Valida i parametri principali dell'impianto.

    Args:
        plant_net_smch:     Potenza netta autorizzata (Sm3/h).
        aux_factor:         Fattore autoconsumo lordo/netto (>= 1.0).
        ep_total:           Contributo processing impianto (gCO2eq/MJ).
        ghg_threshold:      Soglia saving RED III (0.0–1.0).
        fossil_comparator:  Comparatore fossile (gCO2eq/MJ).
        app_mode:           Modalita' applicazione (biometano/biogas_chp/...).
        plant_kwe:          Potenza elettrica CHP (kWe), solo se IS_CHP.

    Returns:
        (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    if plant_net_smch <= 0:
        errors.append(f"Potenza netta impianto non valida: {plant_net_smch} Sm3/h (deve essere > 0).")
    if plant_net_smch > 10000:
        warnings.append(f"Potenza netta impianto molto alta: {plant_net_smch} Sm3/h. Verificare.")

    if aux_factor < 1.0:
        errors.append(f"aux_factor deve essere >= 1.0 (attuale: {aux_factor:.4f}).")
    if aux_factor > 2.0:
        warnings.append(f"aux_factor molto alto ({aux_factor:.4f}): autoconsumo > 50%, verificare impianto.")

    if ep_total < 0:
        errors.append(f"ep_total non puo' essere negativo (attuale: {ep_total:.2f} gCO2eq/MJ).")
    if ep_total > 30:
        warnings.append(f"ep_total alto ({ep_total:.2f} gCO2eq/MJ). Tipicamente < 20 per impianti efficienti.")

    if not (0.0 < ghg_threshold <= 1.0):
        errors.append(f"ghg_threshold deve essere tra 0 e 1 (attuale: {ghg_threshold}).")

    if fossil_comparator <= 0:
        errors.append(f"fossil_comparator deve essere > 0 (attuale: {fossil_comparator}).")

    if app_mode in ("biogas_chp", "biogas_chp_fer2") and plant_kwe is not None:
        if plant_kwe <= 0:
            errors.append(f"Potenza CHP non valida: {plant_kwe} kWe (deve essere > 0).")
        if app_mode == "biogas_chp_fer2" and plant_kwe > 300.0:
            errors.append(
                f"FER 2: potenza CHP ({plant_kwe} kWe) supera il cap normativo 300 kWe "
                "(DM 18/9/2024 art. 4)."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ---------------------------------------------------------------------------
# Validazione biomasse attive
# ---------------------------------------------------------------------------

def validate_feedstock_selection(
    active_feeds: list[str],
    feedstock_db: dict,
    app_mode: str,
    fer2_feedstock_req_threshold: float = 0.80,
    fer2_subprod_share: float | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Valida la selezione di biomasse attive.

    Args:
        active_feeds:               Lista nomi biomasse attive.
        feedstock_db:               Database feedstock (FEEDSTOCK_DB).
        app_mode:                   Modalita' applicazione.
        fer2_feedstock_req_threshold: Soglia sottoprodotti FER 2 (0.0–1.0).
        fer2_subprod_share:         Quota effettiva sottoprodotti (0.0–1.0).

    Returns:
        (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not active_feeds:
        errors.append("Nessuna biomassa selezionata. Seleziona almeno una biomassa.")
        return False, errors, warnings

    for name in active_feeds:
        if name not in feedstock_db:
            errors.append(f"Biomassa sconosciuta nel database: '{name}'. "
                          "Potrebbe essere stata rimossa o rinominata.")

    if app_mode == "biogas_chp_fer2" and fer2_subprod_share is not None:
        if fer2_subprod_share < fer2_feedstock_req_threshold - 1e-6:
            warnings.append(
                f"FER 2: quota sottoprodotti/effluenti in massa "
                f"({fer2_subprod_share*100:.1f}%) sotto la soglia normativa "
                f"({fer2_feedstock_req_threshold*100:.0f}%). "
                "Il premio matrice non e' applicabile."
            )

    # Avviso se si usano solo colture dedicate (cap 30% RED III)
    dedicated_feeds = [
        n for n in active_feeds
        if n in feedstock_db and feedstock_db[n].get("annex_ix") is None
    ]
    if len(dedicated_feeds) == len(active_feeds) and len(active_feeds) > 0:
        warnings.append(
            "Tutte le biomasse selezionate sono colture dedicate (nessun Annex IX). "
            "Verifica che la quota colture dedicate non superi il 30% RED III."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ---------------------------------------------------------------------------
# Validazione tabella mensile input
# ---------------------------------------------------------------------------

def validate_monthly_input(
    monthly_rows: list[dict[str, Any]],
    active_feeds: list[str],
    fixed_feeds: list[str],
) -> tuple[bool, list[str], list[str]]:
    """Valida la tabella mensile prima del calcolo.

    Args:
        monthly_rows:   Lista di dict, uno per mese.
                        Chiavi attese: "Mese", "Ore", + fixed_feeds.
        active_feeds:   Tutte le biomasse attive.
        fixed_feeds:    Solo le biomasse con quantita' impostata dall'utente.

    Returns:
        (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not monthly_rows:
        errors.append("La tabella mensile e' vuota.")
        return False, errors, warnings

    for i, row in enumerate(monthly_rows):
        mese = row.get("Mese", f"riga {i+1}")

        ore = row.get("Ore", 0)
        try:
            ore = float(ore)
        except (TypeError, ValueError):
            ore = 0.0
        if ore <= 0:
            warnings.append(f"{mese}: Ore = {ore}, il mese verra' escluso dal calcolo.")
        elif ore > 744:
            errors.append(f"{mese}: Ore ({ore}) supera le ore massime mensili (744).")

        for feed in fixed_feeds:
            val = row.get(feed)
            if val is None:
                warnings.append(f"{mese}: massa non specificata per '{feed}' (usato 0).")
                continue
            try:
                m = float(val)
            except (TypeError, ValueError):
                errors.append(f"{mese}: valore non numerico per '{feed}': {val!r}.")
                continue
            if m < 0:
                errors.append(f"{mese}: massa negativa per '{feed}': {m:.1f} t.")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ---------------------------------------------------------------------------
# Validazione risultati GHG mensili
# ---------------------------------------------------------------------------

def validate_ghg_results(
    monthly_results: list[dict[str, Any]],
    ghg_threshold: float,
    fossil_comparator: float,
) -> tuple[bool, list[str], list[str]]:
    """Valida i risultati GHG mensili post-calcolo.

    Args:
        monthly_results:    Lista dict risultati per mese (da df_res).
        ghg_threshold:      Soglia saving RED III (frazione 0–1).
        fossil_comparator:  Comparatore fossile (gCO2eq/MJ).

    Returns:
        (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    invalid_months = []
    for row in monthly_results:
        saving_raw = row.get("Saving %", row.get("saving", None))
        if saving_raw is None:
            continue
        try:
            saving = float(str(saving_raw).replace(",", ".").replace("%", "").strip())
        except (TypeError, ValueError):
            continue
        if saving < ghg_threshold * 100 - 1e-3:
            invalid_months.append(row.get("Mese", "?"))

    if invalid_months:
        warnings.append(
            f"I seguenti mesi NON raggiungono la soglia saving RED III "
            f"({ghg_threshold*100:.0f}%): {', '.join(invalid_months)}. "
            "Controllare il mix biomasse."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ---------------------------------------------------------------------------
# Validazione INPUT GIORNALIERO (gestione operativa)
# ---------------------------------------------------------------------------

def validate_daily_entry(
    entry_date: Any,
    feedstocks: dict,
    allowed_feeds: list | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Valida un singolo input giornaliero.

    Args:
        entry_date:     data del giorno (datetime.date o stringa ISO).
        feedstocks:     {tipologia: quantita_t}, t/giorno.
        allowed_feeds:  elenco tipologie ammesse (se None: nessun controllo).

    Returns:
        (is_valid, errors, warnings)
    """
    from datetime import date as _date

    errors: list[str] = []
    warnings: list[str] = []

    d_obj = entry_date
    if isinstance(entry_date, str):
        try:
            d_obj = _date.fromisoformat(entry_date)
        except ValueError:
            errors.append(f"Data non valida: '{entry_date}' (formato ISO atteso).")
            d_obj = None
    if d_obj is not None and not isinstance(d_obj, _date):
        errors.append("Data: tipo non riconosciuto, atteso datetime.date.")

    if not isinstance(feedstocks, dict):
        errors.append("Feedstocks: deve essere un dizionario.")
        return (False, errors, warnings)

    for fname, qty in feedstocks.items():
        if qty is None:
            continue
        try:
            qv = float(qty)
        except (TypeError, ValueError):
            errors.append(f"Quantita' non numerica per '{fname}': {qty!r}.")
            continue
        if qv < 0:
            errors.append(
                f"Quantita' negativa non ammessa per '{fname}': {qv:g} t."
            )
        if allowed_feeds is not None and fname not in allowed_feeds:
            warnings.append(
                f"Tipologia '{fname}' non riconosciuta nel database biomasse."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ---------------------------------------------------------------------------
# Validazione INPUT GIORNALIERO (gestione operativa)
# ---------------------------------------------------------------------------

def validate_daily_entry(
    entry_date: Any,
    feedstocks: dict,
    allowed_feeds: list | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Valida un singolo input giornaliero.

    Args:
        entry_date:     data del giorno (datetime.date o stringa ISO).
        feedstocks:     {tipologia: quantita_t}, t/giorno.
        allowed_feeds:  elenco tipologie ammesse (se None: nessun controllo).

    Returns:
        (is_valid, errors, warnings)
    """
    from datetime import date as _date

    errors: list[str] = []
    warnings: list[str] = []

    d_obj = entry_date
    if isinstance(entry_date, str):
        try:
            d_obj = _date.fromisoformat(entry_date)
        except ValueError:
            errors.append(f"Data non valida: '{entry_date}' (formato ISO atteso).")
            d_obj = None
    if d_obj is not None and not isinstance(d_obj, _date):
        errors.append("Data: tipo non riconosciuto, atteso datetime.date.")

    if not isinstance(feedstocks, dict):
        errors.append("Feedstocks: deve essere un dizionario.")
        return (False, errors, warnings)

    for fname, qty in feedstocks.items():
        if qty is None:
            continue
        try:
            qv = float(qty)
        except (TypeError, ValueError):
            errors.append(f"Quantita' non numerica per '{fname}': {qty!r}.")
            continue
        if qv < 0:
            errors.append(
                f"Quantita' negativa non ammessa per '{fname}': {qv:g} t."
            )
        if allowed_feeds is not None and fname not in allowed_feeds:
            warnings.append(
                f"Tipologia '{fname}' non riconosciuta nel database biomasse."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings
