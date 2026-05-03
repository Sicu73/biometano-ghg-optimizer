# -*- coding: utf-8 -*-
"""core/i18n.py — API i18n strutturata per Metan.iQ.

Fornisce:
  - TRANSLATIONS: dict {"it": {key: str}, "en": {key: str}}
  - t(key, lang=None) -> str    : traduzione per chiave (no-crash se mancante)
  - set_language(lang) -> None  : imposta la lingua corrente in session_state
  - get_language() -> str       : restituisce la lingua corrente

Compat:
  - Mantiene alias per ``i18n_runtime.t`` (sostituzione IT->EN per stringhe libere)
    accessibile come ``t_text``.
  - Il dizionario ``IT_EN`` di ``metaniq_i18n`` resta la fonte storica per le
    traduzioni di stringhe libere usate da CSV/Excel/PDF; questo modulo aggiunge
    invece il pattern key-based tipico ``t("key", lang)``.
"""
from __future__ import annotations

# Lingue supportate
SUPPORTED_LANGS = ("it", "en")
DEFAULT_LANG = "it"


# ---------------------------------------------------------------------------
# Dizionario chiavi -> traduzioni
# ---------------------------------------------------------------------------
# IMPORTANTE: ogni chiave presente in TRANSLATIONS["it"] DEVE essere presente
# anche in TRANSLATIONS["en"] (e viceversa). I test verificano la parita'.

TRANSLATIONS: dict[str, dict[str, str]] = {
    "it": {
        # --- Footer / versione ---
        "footer.tagline": "Software per ottimizzazione GHG biometano e biogas",
        "footer.copyright": "© 2026 Metan.iQ",

        # --- Sidebar / Navigazione ---
        "sidebar.language.title": "Lingua / Language",
        "sidebar.language.it": "Italiano",
        "sidebar.language.en": "English",
        "sidebar.theme.title": "Tema",
        "sidebar.theme.light": "Chiaro",
        "sidebar.theme.dark": "Scuro",

        # --- Sezione Gestione Giornaliera ---
        "daily.title": "Gestione giornaliera",
        "daily.subtitle": "Inserimento dati giornalieri e verifica sostenibilita' mensile",
        "daily.input.day": "Giorno",
        "daily.input.feedstock": "Biomassa",
        "daily.input.mass_t": "Massa caricata (t)",
        "daily.input.notes": "Note operatore",
        "daily.btn.save": "Salva giornata",
        "daily.btn.delete": "Elimina giornata",
        "daily.summary.title": "Riepilogo mensile",
        "daily.summary.month": "Mese",
        "daily.summary.total_t": "Totale biomasse (t)",
        "daily.summary.ghg_pct": "Saving GHG (%)",
        "daily.summary.compliant": "Conforme",
        "daily.summary.non_compliant": "Non conforme",

        # --- Output / KPI ---
        "output.title": "Risultati",
        "output.kpi.gross_sm3": "Sm³ lordi",
        "output.kpi.net_sm3": "Sm³ netti",
        "output.kpi.ghg_g_mj": "GHG (gCO₂eq/MJ)",
        "output.kpi.saving_pct": "Saving GHG (%)",
        "output.kpi.revenue_eur": "Ricavo (€)",

        # --- Esportazioni ---
        "export.csv.title": "Export CSV",
        "export.excel.title": "Export Excel",
        "export.pdf.title": "Report PDF",
        "export.btn.download": "Scarica",
        "export.audit.title": "Audit trail",
        "export.audit.timestamp": "Data/ora",
        "export.audit.user_action": "Azione utente",

        # --- Spiegazioni / metodologia ---
        "explain.yield_origin": "Origine rese biomasse",
        "explain.emission_factor_origin": "Origine fattori emissivi",
        "explain.ghg_method": "Metodo di calcolo GHG",
        "explain.regulatory_basis": "Base normativa applicata",

        # --- Errori / messaggi ---
        "msg.error.generic": "Errore",
        "msg.warning.generic": "Avviso",
        "msg.success.generic": "Operazione completata",
        "msg.no_data": "Nessun dato disponibile",
    },
    "en": {
        # --- Footer / version ---
        "footer.tagline": "Software for GHG optimization of biomethane and biogas",
        "footer.copyright": "© 2026 Metan.iQ",

        # --- Sidebar / Navigation ---
        "sidebar.language.title": "Language / Lingua",
        "sidebar.language.it": "Italian",
        "sidebar.language.en": "English",
        "sidebar.theme.title": "Theme",
        "sidebar.theme.light": "Light",
        "sidebar.theme.dark": "Dark",

        # --- Daily Operations section ---
        "daily.title": "Daily operations",
        "daily.subtitle": "Daily data entry and monthly sustainability check",
        "daily.input.day": "Day",
        "daily.input.feedstock": "Feedstock",
        "daily.input.mass_t": "Loaded mass (t)",
        "daily.input.notes": "Operator notes",
        "daily.btn.save": "Save day",
        "daily.btn.delete": "Delete day",
        "daily.summary.title": "Monthly summary",
        "daily.summary.month": "Month",
        "daily.summary.total_t": "Total feedstocks (t)",
        "daily.summary.ghg_pct": "GHG saving (%)",
        "daily.summary.compliant": "Compliant",
        "daily.summary.non_compliant": "Non-compliant",

        # --- Output / KPI ---
        "output.title": "Results",
        "output.kpi.gross_sm3": "Gross Sm³",
        "output.kpi.net_sm3": "Net Sm³",
        "output.kpi.ghg_g_mj": "GHG (gCO₂eq/MJ)",
        "output.kpi.saving_pct": "GHG saving (%)",
        "output.kpi.revenue_eur": "Revenue (€)",

        # --- Exports ---
        "export.csv.title": "CSV export",
        "export.excel.title": "Excel export",
        "export.pdf.title": "PDF report",
        "export.btn.download": "Download",
        "export.audit.title": "Audit trail",
        "export.audit.timestamp": "Timestamp",
        "export.audit.user_action": "User action",

        # --- Explanations / methodology ---
        "explain.yield_origin": "Biomass yield origin",
        "explain.emission_factor_origin": "Emission factor origin",
        "explain.ghg_method": "GHG calculation method",
        "explain.regulatory_basis": "Regulatory basis applied",

        # --- Errors / messages ---
        "msg.error.generic": "Error",
        "msg.warning.generic": "Warning",
        "msg.success.generic": "Operation completed",
        "msg.no_data": "No data available",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _normalize_lang(lang: str | None) -> str:
    if lang is None:
        return get_language()
    lang = str(lang).lower().strip()
    if lang not in SUPPORTED_LANGS:
        return DEFAULT_LANG
    return lang


def get_language() -> str:
    """Restituisce la lingua corrente (da streamlit session_state se disponibile)."""
    try:
        import streamlit as st  # type: ignore
        return str(st.session_state.get("lang", DEFAULT_LANG))
    except Exception:
        return DEFAULT_LANG


def set_language(lang: str) -> None:
    """Imposta la lingua corrente in streamlit session_state.

    Se streamlit non e' importabile (es. in test), e' un no-op silenzioso.
    """
    lang = _normalize_lang(lang)
    try:
        import streamlit as st  # type: ignore
        st.session_state["lang"] = lang
    except Exception:
        pass


def t(key: str, lang: str | None = None) -> str:
    """Restituisce la traduzione per ``key`` nella lingua ``lang``.

    Ricerca in ordine:
      1. TRANSLATIONS[lang][key]
      2. TRANSLATIONS[DEFAULT_LANG][key]
      3. ``key`` stessa (fallback non-crashing).
    """
    lang = _normalize_lang(lang)
    if not isinstance(key, str):
        return str(key)
    bucket = TRANSLATIONS.get(lang) or {}
    if key in bucket:
        return bucket[key]
    fallback = TRANSLATIONS.get(DEFAULT_LANG) or {}
    if key in fallback:
        return fallback[key]
    return key


# Compat con i18n_runtime: traduzione di stringhe libere IT->EN.
def t_text(text: object, lang: str | None = None) -> object:
    """Traduce una stringa libera IT->EN usando il vecchio dizionario IT_EN.

    Questa funzione esiste per agevolare il refactor: molte parti dell'app
    storica usano ``t_runtime.t("Stringa libera IT")``. Questo wrapper
    instrada verso ``i18n_runtime.t`` se presente, altrimenti restituisce
    il testo originale.
    """
    try:
        from i18n_runtime import t as _legacy_t  # type: ignore
        return _legacy_t(text, lang)
    except Exception:
        return text


__all__ = [
    "TRANSLATIONS",
    "SUPPORTED_LANGS",
    "DEFAULT_LANG",
    "t",
    "t_text",
    "get_language",
    "set_language",
]
