# -*- coding: utf-8 -*-
"""output/guidance.py — Indicazioni operative "fine mese".

Genera stringhe di guida operativa in italiano per aiutare l'utente a
chiudere il mese in modo sostenibile (versione 1, semplice, basata sui
vincoli del regime attivo).
"""
from __future__ import annotations

from typing import Any

from core.monthly_aggregate import MonthlyAggregate


def compute_end_of_month_guidance(
    monthly_agg: MonthlyAggregate,
    sustainability_eval: dict[str, Any],
    regime: str = "RED III",
) -> list[str]:
    """Restituisce indicazioni operative come stringhe in italiano.

    Esempi di output:
      - "Saving mese ad oggi: 78.2% (soglia 80.0%)"
      - "Margine: -1.8 punti -> servono interventi correttivi"
      - "Suggerimento: aumentare la quota di sottoprodotti / effluenti"
      - "Suggerimento: ridurre le biomasse a piu' alto eec"
    """
    msgs: list[str] = []
    saving = float(sustainability_eval.get("saving", 0.0))
    threshold = float(sustainability_eval.get("threshold", 80.0))
    margin = float(sustainability_eval.get("margin", saving - threshold))
    compliant = bool(sustainability_eval.get("compliant", False))

    msgs.append(f"Regime applicato: {regime or 'RED III'}.")
    msgs.append(
        f"Saving mese ad oggi: {saving:.2f}% (soglia {threshold:.2f}%)."
    )
    msgs.append(
        f"Margine: {'+' if margin >= 0 else ''}{margin:.2f} punti percentuali."
    )

    if compliant:
        msgs.append(
            "Esito provvisorio: COMPLIANT. Mantenere il mix attuale fino a fine mese."
        )
    else:
        msgs.append(
            "Esito provvisorio: NON COMPLIANT. Servono azioni correttive entro fine mese."
        )
        # Suggerimenti generici
        msgs.append(
            "Suggerimento: aumentare la quota di sottoprodotti/effluenti "
            "(eec basso o nullo) nei giorni rimanenti."
        )
        msgs.append(
            "Suggerimento: ridurre la quota di colture dedicate/insilati "
            "ad alto eec (mais, sorgo, triticale, ecc.)."
        )
        msgs.append(
            "Suggerimento: verificare che le biomasse Annex IX (avanzate) "
            "siano valorizzate per migliorare la classificazione GHG."
        )

    # Vincoli specifici falliti
    for c in (sustainability_eval.get("constraints_status") or []):
        if not c.get("ok", True):
            msgs.append(f"ATTENZIONE - {c.get('name','?')}: {c.get('msg','')}.")

    # Cap autorizzativi
    cap_viol = list(getattr(monthly_agg, "cap_violation_days", []) or [])
    if cap_viol:
        days_str = ", ".join(d.isoformat() for d in cap_viol[:5])
        suffix = "..." if len(cap_viol) > 5 else ""
        msgs.append(
            f"Vincolo autorizzativo: superato in {len(cap_viol)} giorno/i "
            f"({days_str}{suffix}). Ridurre l'alimentazione giornaliera."
        )

    # Avviso compliance mensile
    msgs.append(
        "NB: il controllo ufficiale e' MENSILE. Singoli giorni 'non sostenibili' "
        "sono ammessi se il totale mese rispetta la soglia."
    )
    return msgs


__all__ = ["compute_end_of_month_guidance"]
