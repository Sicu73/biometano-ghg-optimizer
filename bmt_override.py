# -*- coding: utf-8 -*-
"""
bmt_override.py — Gestione override resa BMT certificata per Metan.iQ.

Permette, per una specifica biomassa, di sostituire la resa standard
tabellare con una resa BMT (Biochemical Methane Test) misurata in
laboratorio, purché sia caricato un certificato valido.

Funzioni esposte:
  - is_valid_certificate_filename(filename)
  - validate_bmt_override(bmt_value, standard_yield, certificate_uploaded,
                          lab_name, cert_date, sample_ref, cert_filename)
  - resolve_biomass_yield(biomass_name, standard_yield, bmt_overrides)
  - build_yield_audit_row(resolved)

Costanti:
  - ALLOWED_CERT_EXTS                       — estensioni certificato ammesse
  - BMT_DEVIATION_WARN_THRESHOLD            — soglia warning ±30%
  - YIELD_UNIT                              — "Sm³ biometano/t"
  - SOURCE_BMT, SOURCE_STD                  — etichette origine resa

Il modulo NON dipende da Streamlit, quindi è testabile in isolamento
con pytest.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# Estensioni certificato accettate (case-insensitive).
ALLOWED_CERT_EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".csv")

# Soglia oltre la quale il software emette un warning di scostamento
# tra resa BMT certificata e resa standard tabellare.
BMT_DEVIATION_WARN_THRESHOLD = 0.30  # ±30%

# Unità di misura standard per la resa BMT in Metan.iQ.
YIELD_UNIT = "Sm³ biometano/t"

# Etichette origine della resa usata nei calcoli (tracciabilità).
SOURCE_BMT = "BMT certificato laboratorio"
SOURCE_STD = "Tabella standard software / UNI-TS / default interno"


# ============================================================
# Modello dati
# ============================================================
@dataclass
class BMTCertificate:
    """Metadati completi di un certificato BMT caricato per una biomassa.

    Attributi:
      biomass_name: nome biomassa cui si riferisce il certificato.
      bmt_value: resa certificata in Sm³ biometano/t (deve essere > 0).
      lab_name: nome del laboratorio che ha emesso il certificato.
      cert_date: data emissione certificato (stringa libera, ideale ISO).
      sample_ref: riferimento campione / numero rapporto di prova.
      cert_filename: nome del file caricato (deve avere estensione ammessa).
      cert_size_bytes: dimensione del file (audit).
      cert_data: contenuto binario opzionale (per persistenza/export).
    """
    biomass_name: str
    bmt_value: float
    lab_name: str
    cert_date: str
    sample_ref: str
    cert_filename: str
    cert_size_bytes: int = 0
    cert_data: bytes | None = field(default=None, repr=False)


# ============================================================
# Helpers
# ============================================================
def is_valid_certificate_filename(filename: str | None) -> bool:
    """True se il filename ha un'estensione ammessa (case-insensitive)."""
    if not filename or not isinstance(filename, str):
        return False
    return filename.lower().endswith(ALLOWED_CERT_EXTS)


# ============================================================
# Validazione override BMT
# ============================================================
def validate_bmt_override(
    bmt_value: Any,
    standard_yield: float,
    certificate_uploaded: bool,
    lab_name: str = "",
    cert_date: str = "",
    sample_ref: str = "",
    cert_filename: str = "",
) -> tuple[bool, list[str], list[str]]:
    """Valida un override BMT per una biomassa.

    Ritorna:
      (is_valid, errors, warnings)

    Regole bloccanti (errors):
      - bmt_value deve essere numerico, finito, > 0
      - certificate_uploaded deve essere True
      - cert_filename, se non vuoto, deve avere estensione ammessa
      - lab_name, cert_date, sample_ref devono essere non vuoti

    Regole non-bloccanti (warnings):
      - se bmt e standard sono > 0 e |bmt − standard| / standard
        supera BMT_DEVIATION_WARN_THRESHOLD (±30%), emette warning.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ---- valore numerico ----
    try:
        bmt = float(bmt_value)
    except (TypeError, ValueError):
        errors.append(
            f"Valore BMT non numerico: {bmt_value!r}. "
            f"Inserire un numero in {YIELD_UNIT}."
        )
        return False, errors, warnings

    if not math.isfinite(bmt):
        errors.append(f"Valore BMT non finito (NaN/Inf): {bmt}.")
        return False, errors, warnings

    if bmt <= 0:
        errors.append(
            f"Valore BMT deve essere strettamente > 0 "
            f"(ricevuto {bmt} {YIELD_UNIT})."
        )

    # ---- certificato obbligatorio ----
    if not certificate_uploaded:
        errors.append(
            "Certificato BMT obbligatorio: caricare il file di laboratorio "
            f"in formato {', '.join(e.lstrip('.').upper() for e in ALLOWED_CERT_EXTS)}. "
            "Senza certificato l'override BMT NON può essere applicato."
        )

    # ---- formato file ----
    if cert_filename and not is_valid_certificate_filename(cert_filename):
        errors.append(
            f"Estensione certificato non ammessa: {cert_filename!r}. "
            f"Formati accettati: {', '.join(ALLOWED_CERT_EXTS)}."
        )

    # ---- metadati obbligatori ----
    if not (isinstance(lab_name, str) and lab_name.strip()):
        errors.append("Nome laboratorio obbligatorio.")
    if not (isinstance(cert_date, str) and cert_date.strip()):
        errors.append("Data certificato obbligatoria (suggerito formato YYYY-MM-DD).")
    if not (isinstance(sample_ref, str) and sample_ref.strip()):
        errors.append("Riferimento campione (rapporto di prova) obbligatorio.")

    # ---- warning scostamento dal valore standard ----
    try:
        std = float(standard_yield)
    except (TypeError, ValueError):
        std = 0.0
    if std > 0 and bmt > 0:
        deviation = abs(bmt - std) / std
        if deviation > BMT_DEVIATION_WARN_THRESHOLD:
            sign = "superiore" if bmt > std else "inferiore"
            warnings.append(
                f"Resa BMT {bmt:.2f} {YIELD_UNIT} è {sign} del "
                f"{deviation*100:.1f}% rispetto al valore standard "
                f"{std:.2f} {YIELD_UNIT} (soglia warning ±"
                f"{BMT_DEVIATION_WARN_THRESHOLD*100:.0f}%). "
                f"Verifica accuratamente la validità del certificato e "
                f"la rappresentatività del campione prima di usare "
                f"il valore in calcoli ufficiali."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ============================================================
# Risoluzione resa effettiva
# ============================================================
def resolve_biomass_yield(
    biomass_name: str,
    standard_yield: float,
    bmt_overrides: dict | None = None,
) -> dict:
    """Risolve la resa effettiva da usare nei calcoli per una biomassa.

    Args:
      biomass_name: nome biomassa.
      standard_yield: resa tabellare di default (FEEDSTOCK_DB[name]['yield']).
      bmt_overrides: dict { biomass_name: {'active': bool,
                                            'certificate': BMTCertificate} }.
        Se omesso o vuoto, non viene applicato alcun override.

    Logica:
      Se esiste un override con active=True, certificate non None,
      cert.bmt_value > 0 e cert.cert_filename con estensione ammessa,
      ritorna la resa BMT come yield_used. Altrimenti ritorna la
      resa standard. La tabella standard NON viene MAI modificata.

    Ritorna dict:
      biomass_name, yield_used, source, unit,
      certificate (BMTCertificate o None),
      standard_yield, override_active.
    """
    bmt_overrides = bmt_overrides or {}
    override = bmt_overrides.get(biomass_name)

    if override is not None and override.get("active"):
        cert = override.get("certificate")
        if (
            isinstance(cert, BMTCertificate)
            and cert.bmt_value > 0
            and is_valid_certificate_filename(cert.cert_filename)
        ):
            return {
                "biomass_name": biomass_name,
                "yield_used": float(cert.bmt_value),
                "source": SOURCE_BMT,
                "unit": YIELD_UNIT,
                "certificate": cert,
                "standard_yield": float(standard_yield),
                "override_active": True,
            }

    # Fallback: resa standard
    return {
        "biomass_name": biomass_name,
        "yield_used": float(standard_yield),
        "source": SOURCE_STD,
        "unit": YIELD_UNIT,
        "certificate": None,
        "standard_yield": float(standard_yield),
        "override_active": False,
    }


# ============================================================
# Costruzione riga audit (per UI, CSV, Excel, PDF)
# ============================================================
def build_yield_audit_row(resolved: dict) -> dict:
    """Costruisce una riga di audit normalizzata da un resolved-dict.

    Sempre presente (anche senza BMT): Biomassa, Resa standard,
    Resa usata, Unità, Origine resa.
    Se override attivo: Certificato, Laboratorio, Data certificato,
    Riferimento campione (altrimenti '—').
    """
    cert = resolved.get("certificate")
    return {
        "Biomassa":             resolved.get("biomass_name", ""),
        "Resa standard":        float(resolved.get("standard_yield", 0.0)),
        "Resa usata":           float(resolved.get("yield_used", 0.0)),
        "Unità":                resolved.get("unit", YIELD_UNIT),
        "Origine resa":         resolved.get("source", SOURCE_STD),
        "Certificato":          (cert.cert_filename if cert else "—"),
        "Laboratorio":          (cert.lab_name      if cert else "—"),
        "Data certificato":     (cert.cert_date     if cert else "—"),
        "Riferimento campione": (cert.sample_ref    if cert else "—"),
    }


__all__ = [
    "ALLOWED_CERT_EXTS",
    "BMT_DEVIATION_WARN_THRESHOLD",
    "YIELD_UNIT",
    "SOURCE_BMT",
    "SOURCE_STD",
    "BMTCertificate",
    "is_valid_certificate_filename",
    "validate_bmt_override",
    "resolve_biomass_yield",
    "build_yield_audit_row",
]
