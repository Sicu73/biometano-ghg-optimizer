# -*- coding: utf-8 -*-
from __future__ import annotations

LANG_IT = "it"
LANG_EN = "en"
SUPPORTED_LANGS = (LANG_IT, LANG_EN)
LANG_LABELS = {LANG_IT: "Italiano", LANG_EN: "English"}

TRANSLATIONS = {
    LANG_IT: {},
    LANG_EN: {
        "Lingua": "Language",
        "Italiano": "Italian",
        "Inglese": "English",
        "Seleziona lingua": "Select language",
        "Scarica CSV": "Download CSV",
        "Scarica Excel": "Download Excel",
        "Scarica PDF": "Download PDF",
        "Report": "Report",
        "Tabella": "Table",
        "Risultati": "Results",
        "Scenario": "Scenario",
        "Biomassa": "Feedstock",
        "Quantità": "Quantity",
        "Mese": "Month",
        "Anno": "Year",
        "Totale": "Total",
        "Produzione": "Production",
        "Risparmio GHG": "GHG saving",
        "Emissioni": "Emissions",
        "Conforme": "Compliant",
        "Non conforme": "Not compliant",
        "Parametro": "Parameter",
        "Valore": "Value",
        "Unità": "Unit",
        "Note": "Notes",
        "Soglia": "Threshold",
        "Esito": "Outcome",
        "Costo": "Cost",
        "Ricavo": "Revenue",
        "Margine": "Margin",
        "Energia": "Energy",
        "Biometano": "Biomethane",
        "Biogas": "Biogas",
        "Calore": "Heat",
        "Liquame suino": "Pig slurry",
        "Pollina ovaiole": "Layer manure",
        "Trinciato di mais": "Maize silage",
        "Impianto": "Plant",
        "Potenza": "Capacity",
        "Business plan": "Business plan",
        "Piano mensile": "Monthly planner",
        "Calcola": "Calculate",
        "Reset": "Reset",
    },
}

COLUMN_TRANSLATIONS_EN = {
    "biomassa": "feedstock", "Biomassa": "Feedstock",
    "mese": "month", "Mese": "Month",
    "anno": "year", "Anno": "Year",
    "quantita": "quantity", "quantità": "quantity", "Quantità": "Quantity",
    "produzione": "production", "Produzione": "Production",
    "risparmio": "saving", "Risparmio": "Saving",
    "emissioni": "emissions", "Emissioni": "Emissions",
    "soglia": "threshold", "Soglia": "Threshold",
    "esito": "outcome", "Esito": "Outcome",
    "valore": "value", "Valore": "Value",
    "unità": "unit", "Unità": "Unit",
    "note": "notes", "Note": "Notes",
}

def get_lang(session_state=None, default=LANG_IT):
    lang = session_state.get("lang", default) if session_state is not None else default
    return lang if lang in SUPPORTED_LANGS else default

def tr(text, lang=LANG_IT):
    if not isinstance(text, str) or lang == LANG_IT:
        return text
    return TRANSLATIONS.get(lang, {}).get(text, text)

def translate_columns(df, lang=LANG_IT):
    if lang == LANG_IT or df is None:
        return df
    return df.rename(columns={col: COLUMN_TRANSLATIONS_EN.get(str(col), str(col)) for col in df.columns})

def export_filename(base, lang, ext):
    suffix = "en" if lang == LANG_EN else "it"
    return f"{base.replace(' ', '_').replace('/', '-')}_{suffix}.{ext.lstrip('.')}"
