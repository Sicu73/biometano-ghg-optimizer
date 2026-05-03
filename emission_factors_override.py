# -*- coding: utf-8 -*-
"""
emission_factors_override.py — Override fattori emissivi REALI da
relazione tecnica per Metan.iQ.

Permette, per una specifica biomassa/matrice, di sostituire i valori
emissivi standard tabellari (eec, esca, etd, ep) con i valori
REALI dichiarati in una relazione tecnica d'impianto, purché sia
caricata una relazione tecnica valida.

Funzioni esposte:
  - is_valid_report_filename(filename)
  - validate_real_emission_factor_override(...)
  - resolve_emission_factors(...)
  - build_emission_factor_audit_row(...)
  - calculate_emission_total(...)

Costanti:
  - ALLOWED_REPORT_EXTS                     — formati relazione ammessi
  - EMISSION_DEVIATION_WARN_THRESHOLD       — soglia warning ±30%
  - EMISSION_UNIT                           — "gCO2eq/MJ"
  - SOURCE_REAL, SOURCE_STD                 — etichette origine fattori
  - PLAUSIBILITY_RANGES                     — range numerici ragionevoli

Convenzione segno (coerente con app_mensile.e_total_feedstock):
  e_total = eec + etd + ep − esca − crediti_extra

Dove:
  - eec, etd, ep         sono emissioni positive che AUMENTANO e_total
  - esca                 è un credito già dichiarato come "positivo da
                          sottrarre" nel DB standard (manure credit
                          incorporato in eec è separato e ha eec
                          negativo: NON va in esca per evitare doppia
                          sottrazione)
  - crediti_extra        sono crediti emissivi AGGIUNTIVI (non già in
                          esca) dichiarati a parte nella relazione

Il modulo NON dipende da Streamlit, quindi e' testabile in isolamento
con pytest.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# Costanti
# ============================================================
# Formati relazione tecnica ammessi (case-insensitive).
ALLOWED_REPORT_EXTS = (".pdf", ".docx", ".xlsx", ".csv", ".jpg", ".jpeg", ".png")

# Soglia oltre la quale viene emesso un warning di scostamento
# tra fattore reale e fattore standard.
EMISSION_DEVIATION_WARN_THRESHOLD = 0.30  # ±30%

# Unità di misura standard per i fattori emissivi.
EMISSION_UNIT = "gCO2eq/MJ"

# Etichette origine dei fattori usati nei calcoli (tracciabilita').
SOURCE_REAL = "Relazione tecnica impianto"
SOURCE_STD = "Valori standard software / normativa / default interno"

# Range plausibili per ciascun fattore [min, max] in gCO2eq/MJ.
# Valori derivati da letteratura RED III All. V Parte C, JEC WTT v5,
# UNI/TS 11567:2024. Un valore fuori range NON e' bloccante (warning),
# ma molto fuori range emette warning aggiuntivo di sanity-check.
# Manure credit puo' arrivare a -100 gCO2eq/MJ in casi estremi.
PLAUSIBILITY_RANGES = {
    "eec":            (-150.0, 200.0),  # eec puo' essere negativo (manure credit)
    "esca":           (   0.0, 100.0),  # credit, sempre >= 0
    "etd":            (   0.0,  20.0),  # trasporto, tipico 0-5
    "ep":             (   0.0, 100.0),  # processing, tipico 5-50
    "crediti_extra":  (   0.0, 200.0),  # crediti aggiuntivi opzionali
}

# Campi numerici accettati nella struttura di override.
NUMERIC_FIELDS = ("eec_real", "esca_real", "etd_real", "ep_real",
                  "extra_credits_real")


# ============================================================
# Modello dati
# ============================================================
@dataclass
class EmissionFactorReport:
    """Metadati completi di una relazione tecnica caricata.

    Attributi:
      biomass_name: nome biomassa/matrice cui si riferisce.
      eec_real:        emissioni eec dichiarate [gCO2eq/MJ]
      esca_real:       credito esca dichiarato [gCO2eq/MJ] (positivo)
      etd_real:        emissioni etd dichiarate [gCO2eq/MJ]
      ep_real:         emissioni ep dichiarate [gCO2eq/MJ]
      extra_credits_real: crediti emissivi AGGIUNTIVI (non gia' in esca)
                          dichiarati nella relazione, in gCO2eq/MJ.
                          Default 0 (nessun credito extra).
      report_title:        titolo relazione
      author_name:         autore / tecnico redattore
      company_name:        societa' / studio tecnico
      report_date:         data relazione (YYYY-MM-DD)
      plant_reference:     impianto di riferimento
      sample_lot_ref:      riferimento campione / lotto
      methodology_notes:   note metodologiche
      report_filename:     nome file relazione caricata
      report_size_bytes:   dimensione file
      report_data:         contenuto binario (audit)
      unit:                unita' di misura (default gCO2eq/MJ)
    """
    biomass_name: str
    eec_real: float
    esca_real: float
    etd_real: float
    ep_real: float
    report_title: str
    author_name: str
    company_name: str
    report_date: str
    plant_reference: str
    sample_lot_ref: str
    report_filename: str
    extra_credits_real: float = 0.0
    methodology_notes: str = ""
    report_size_bytes: int = 0
    report_data: bytes | None = field(default=None, repr=False)
    unit: str = EMISSION_UNIT


# ============================================================
# Helpers
# ============================================================
def is_valid_report_filename(filename: str | None) -> bool:
    """True se il filename ha estensione ammessa (case-insensitive)."""
    if not filename or not isinstance(filename, str):
        return False
    return filename.lower().endswith(ALLOWED_REPORT_EXTS)


def _check_numeric(value: Any, name: str, errors: list[str]) -> float | None:
    """Valida un valore numerico finito; aggiunge errore se non valido.

    Ritorna float o None.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        errors.append(
            f"Valore '{name}' non numerico: {value!r}. "
            f"Richiesto un numero in {EMISSION_UNIT}."
        )
        return None
    if not math.isfinite(v):
        errors.append(f"Valore '{name}' non finito (NaN/Inf): {v}.")
        return None
    return v


def _check_range(value: float, field_name: str,
                 warnings: list[str]) -> None:
    """Avvisa se il valore esce dal range di plausibilita'."""
    if field_name not in PLAUSIBILITY_RANGES:
        return
    lo, hi = PLAUSIBILITY_RANGES[field_name]
    if value < lo or value > hi:
        warnings.append(
            f"Valore {field_name}={value:.2f} {EMISSION_UNIT} e' fuori "
            f"dal range plausibile [{lo}, {hi}]. Verificare unita' "
            f"di misura e correttezza della relazione tecnica."
        )


# ============================================================
# Validazione override fattori emissivi reali
# ============================================================
def validate_real_emission_factor_override(
    biomass_name: str,
    eec_real: Any,
    esca_real: Any,
    etd_real: Any,
    ep_real: Any,
    standard_factors: dict,
    report_uploaded: bool,
    report_filename: str = "",
    report_title: str = "",
    author_name: str = "",
    company_name: str = "",
    report_date: str = "",
    plant_reference: str = "",
    sample_lot_ref: str = "",
    extra_credits_real: Any = 0.0,
    methodology_notes: str = "",
) -> tuple[bool, list[str], list[str]]:
    """Valida un override fattori emissivi reali da relazione tecnica.

    Ritorna (is_valid, errors, warnings).

    Regole bloccanti (errors):
      - biomass_name non vuoto
      - report_uploaded == True
      - report_filename, se non vuoto, ha estensione ammessa
      - eec_real, esca_real, etd_real, ep_real, extra_credits_real
        devono essere numerici e finiti
      - esca_real >= 0 (credit, mai negativo nella convenzione interna)
      - extra_credits_real >= 0
      - etd_real >= 0, ep_real >= 0
      - report_title, author_name, company_name, report_date,
        plant_reference, sample_lot_ref tutti non vuoti

    Regole non-bloccanti (warnings):
      - valori fuori range plausibilita' → sanity-check
      - se uno dei fattori reali differisce >±30% dal valore standard
        corrispondente → warning di scostamento
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ---- biomassa associata ----
    if not (isinstance(biomass_name, str) and biomass_name.strip()):
        errors.append(
            "Biomassa associata obbligatoria: i fattori reali devono "
            "essere collegati a una biomassa specifica."
        )

    # ---- relazione tecnica obbligatoria ----
    if not report_uploaded:
        errors.append(
            "Per usare fattori emissivi reali devi prima caricare la "
            "relazione tecnica dell'impianto relativa alla biomassa "
            f"selezionata. Formati accettati: "
            f"{', '.join(e.lstrip('.').upper() for e in ALLOWED_REPORT_EXTS)}."
        )

    if report_filename and not is_valid_report_filename(report_filename):
        errors.append(
            f"Estensione relazione non ammessa: {report_filename!r}. "
            f"Formati accettati: {', '.join(ALLOWED_REPORT_EXTS)}."
        )

    # ---- fattori numerici ----
    eec = _check_numeric(eec_real, "eec_real", errors)
    esca = _check_numeric(esca_real, "esca_real", errors)
    etd = _check_numeric(etd_real, "etd_real", errors)
    ep = _check_numeric(ep_real, "ep_real", errors)
    extra = _check_numeric(extra_credits_real, "extra_credits_real",
                           errors)

    # vincoli di segno
    if esca is not None and esca < 0:
        errors.append(
            f"esca deve essere >= 0 (credit positivo da sottrarre); "
            f"ricevuto {esca}."
        )
    if etd is not None and etd < 0:
        errors.append(f"etd deve essere >= 0; ricevuto {etd}.")
    if ep is not None and ep < 0:
        errors.append(f"ep deve essere >= 0; ricevuto {ep}.")
    if extra is not None and extra < 0:
        errors.append(
            f"crediti_extra devono essere >= 0; ricevuto {extra}."
        )

    # ---- metadati relazione obbligatori ----
    metadata_required = {
        "Titolo relazione": report_title,
        "Autore / tecnico redattore": author_name,
        "Societa' / studio tecnico": company_name,
        "Data relazione": report_date,
        "Impianto di riferimento": plant_reference,
        "Riferimento campione / lotto": sample_lot_ref,
    }
    for label, value in metadata_required.items():
        if not (isinstance(value, str) and value.strip()):
            errors.append(f"{label} obbligatorio.")

    # ---- range plausibilita' (warning, no block) ----
    if eec is not None:
        _check_range(eec, "eec", warnings)
    if esca is not None and esca >= 0:
        _check_range(esca, "esca", warnings)
    if etd is not None and etd >= 0:
        _check_range(etd, "etd", warnings)
    if ep is not None and ep >= 0:
        _check_range(ep, "ep", warnings)
    if extra is not None and extra >= 0:
        _check_range(extra, "crediti_extra", warnings)

    # ---- warning scostamento dal valore standard ----
    std = standard_factors or {}
    deviation_msgs = []
    for name, real_val, std_key in [
        ("eec",  eec,   "eec"),
        ("esca", esca,  "esca"),
        ("etd",  etd,   "etd"),
        ("ep",   ep,    "ep"),
    ]:
        if real_val is None:
            continue
        std_val = std.get(std_key)
        if std_val is None:
            continue
        try:
            std_f = float(std_val)
        except (TypeError, ValueError):
            continue
        # Se il valore standard e' esattamente 0, il rapporto relativo
        # diverge: in questo caso e' piu' utile NON emettere warning di
        # scostamento (qualunque valore reale "differisce dell'infinito").
        # L'utente sa che sta inserendo un valore che lo standard non ha.
        # Eventuali warning utili: range plausibilita' (gia' coperto sopra).
        if std_f == 0:
            continue
        denom = abs(std_f)
        deviation = abs(real_val - std_f) / denom
        if deviation > EMISSION_DEVIATION_WARN_THRESHOLD:
            sign = "superiore" if real_val > std_f else "inferiore"
            deviation_msgs.append(
                f"{name}: reale {real_val:.2f} {sign} del "
                f"{deviation*100:.1f}% rispetto allo standard {std_f:.2f}"
            )
    if deviation_msgs:
        warnings.append(
            "Attenzione: il fattore emissivo reale inserito differisce "
            f"di oltre il "
            f"{EMISSION_DEVIATION_WARN_THRESHOLD*100:.0f}% dal valore "
            "standard. Verificare relazione tecnica, unita' di misura "
            f"e biomassa associata. Dettaglio: {'; '.join(deviation_msgs)}."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ============================================================
# Calcolo emission total
# ============================================================
def calculate_emission_total(
    eec: float,
    esca: float,
    etd: float,
    ep: float,
    extra_credits: float = 0.0,
) -> float:
    """Calcola e_total con convenzione coerente in tutto il software:

        e_total = eec + etd + ep − esca − extra_credits

    Note:
      - eec puo' essere negativo (manure credit gia' incorporato).
      - esca e' un credito positivo SOTTRATTO una sola volta.
      - extra_credits sono crediti emissivi AGGIUNTIVI (non gia' in
        esca) dichiarati esplicitamente a parte nella relazione.
        Tipicamente 0 per i feedstock standard. Mai sottrarre due
        volte la stessa voce.
    """
    return float(eec) + float(etd) + float(ep) - float(esca) - float(extra_credits)


# ============================================================
# Risoluzione fattori effettivi
# ============================================================
def resolve_emission_factors(
    biomass_name: str,
    standard_factors: dict,
    ep_default: float = 0.0,
    overrides: dict | None = None,
) -> dict:
    """Risolve i fattori emissivi effettivi per una biomassa.

    Args:
      biomass_name: nome biomassa.
      standard_factors: dict con eec, esca, etd (da FEEDSTOCK_DB[name])
      ep_default: ep standard impianto-wide (gCO2eq/MJ)
      overrides: dict { name: {'active': bool,
                                'report': EmissionFactorReport} }

    Logica:
      Se override active=True E report e' EmissionFactorReport con
      report_filename ad estensione ammessa, ritorna i valori reali.
      Altrimenti ritorna i valori standard. La tabella standard
      NON viene MAI modificata.

    Ritorna dict:
      biomass_name, eec_used, esca_used, etd_used, ep_used,
      extra_credits_used, e_total, source, unit, report (o None),
      standard_factors (originali), override_active.
    """
    overrides = overrides or {}
    override = overrides.get(biomass_name)

    eec_std = float(standard_factors.get("eec", 0.0))
    esca_std = float(standard_factors.get("esca", 0.0))
    etd_std = float(standard_factors.get("etd", 0.0))
    ep_std = float(ep_default)

    if override is not None and override.get("active"):
        report = override.get("report")
        if (
            isinstance(report, EmissionFactorReport)
            and is_valid_report_filename(report.report_filename)
        ):
            eec_u = float(report.eec_real)
            esca_u = float(report.esca_real)
            etd_u = float(report.etd_real)
            ep_u = float(report.ep_real)
            extra_u = float(report.extra_credits_real)
            return {
                "biomass_name":         biomass_name,
                "eec_used":             eec_u,
                "esca_used":            esca_u,
                "etd_used":             etd_u,
                "ep_used":              ep_u,
                "extra_credits_used":   extra_u,
                "e_total":              calculate_emission_total(
                                            eec_u, esca_u, etd_u,
                                            ep_u, extra_u),
                "source":               SOURCE_REAL,
                "unit":                 report.unit or EMISSION_UNIT,
                "report":               report,
                "standard_factors": {
                    "eec": eec_std, "esca": esca_std,
                    "etd": etd_std, "ep": ep_std,
                },
                "override_active":      True,
            }

    # Fallback: valori standard
    return {
        "biomass_name":         biomass_name,
        "eec_used":             eec_std,
        "esca_used":            esca_std,
        "etd_used":             etd_std,
        "ep_used":              ep_std,
        "extra_credits_used":   0.0,
        "e_total":              calculate_emission_total(
                                    eec_std, esca_std, etd_std,
                                    ep_std, 0.0),
        "source":               SOURCE_STD,
        "unit":                 EMISSION_UNIT,
        "report":               None,
        "standard_factors": {
            "eec": eec_std, "esca": esca_std,
            "etd": etd_std, "ep": ep_std,
        },
        "override_active":      False,
    }


# ============================================================
# Costruzione riga audit (per UI, CSV, Excel, PDF)
# ============================================================
def build_emission_factor_audit_row(resolved: dict) -> dict:
    """Costruisce una riga audit normalizzata da un resolved-dict.

    Sempre presente: Biomassa, fattori standard e usati per ogni
    componente, e_total, origine, unita'.
    Se override attivo: titolo relazione, autore, societa', data,
    impianto, riferimento campione, note metodologiche, file.
    Calcola anche scostamento % per ogni fattore.
    """
    report = resolved.get("report")
    std = resolved.get("standard_factors", {})

    def _dev_pct(real, std_v):
        """Restituisce lo scostamento % real-vs-standard come stringa.

        Edge cases:
          - real o std non numerici -> ""
          - real == 0 e std == 0     -> "0.0%"
          - std == 0 e real != 0     -> "n/a" (rapporto indefinito,
                                          evita output tipo "+50M%")
          - altrimenti               -> "+/-XX.X%"
        """
        try:
            real_f = float(real)
            std_f = float(std_v)
        except (TypeError, ValueError):
            return ""
        if std_f == 0 and real_f == 0:
            return "0.0%"
        if std_f == 0:
            return "n/a"
        return f"{((real_f - std_f) / abs(std_f)) * 100:+.1f}%"

    # Helper: normalizza stringhe vuote in "—" per coerenza export
    def _s(v):
        if v is None:
            return "—"
        s = str(v).strip()
        return s if s else "—"

    return {
        "Biomassa":             resolved.get("biomass_name", ""),
        "Origine fattori":      resolved.get("source", SOURCE_STD),
        "Unita'":               resolved.get("unit", EMISSION_UNIT),
        "eec standard":         float(std.get("eec", 0.0)),
        "eec usato":            float(resolved.get("eec_used", 0.0)),
        "eec scost. %":         _dev_pct(resolved.get("eec_used"),
                                          std.get("eec")),
        "esca standard":        float(std.get("esca", 0.0)),
        "esca usato":           float(resolved.get("esca_used", 0.0)),
        "esca scost. %":        _dev_pct(resolved.get("esca_used"),
                                          std.get("esca")),
        "etd standard":         float(std.get("etd", 0.0)),
        "etd usato":            float(resolved.get("etd_used", 0.0)),
        "etd scost. %":         _dev_pct(resolved.get("etd_used"),
                                          std.get("etd")),
        "ep standard":          float(std.get("ep", 0.0)),
        "ep usato":             float(resolved.get("ep_used", 0.0)),
        "ep scost. %":          _dev_pct(resolved.get("ep_used"),
                                          std.get("ep")),
        "Crediti extra":        float(resolved.get("extra_credits_used", 0.0)),
        "e_total":              float(resolved.get("e_total", 0.0)),
        "Relazione tecnica":    _s(report.report_filename if report else None),
        "Titolo relazione":     _s(report.report_title if report else None),
        "Autore":               _s(report.author_name if report else None),
        "Societa'":             _s(report.company_name if report else None),
        "Data relazione":       _s(report.report_date if report else None),
        "Impianto rif.":        _s(report.plant_reference if report else None),
        "Riferimento campione": _s(report.sample_lot_ref if report else None),
        "Note metodologiche":   _s(report.methodology_notes if report else None),
    }


__all__ = [
    "ALLOWED_REPORT_EXTS",
    "EMISSION_DEVIATION_WARN_THRESHOLD",
    "EMISSION_UNIT",
    "SOURCE_REAL",
    "SOURCE_STD",
    "PLAUSIBILITY_RANGES",
    "EmissionFactorReport",
    "is_valid_report_filename",
    "validate_real_emission_factor_override",
    "resolve_emission_factors",
    "build_emission_factor_audit_row",
    "calculate_emission_total",
]
