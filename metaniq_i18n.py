# -*- coding: utf-8 -*-
"""metaniq_i18n.py — Dizionario IT->EN completo per Metan.iQ."""
from __future__ import annotations

IT_EN: dict = {
    # Mesi
    "Gennaio":"January","Febbraio":"February","Marzo":"March","Aprile":"April",
    "Maggio":"May","Giugno":"June","Luglio":"July","Agosto":"August",
    "Settembre":"September","Ottobre":"October","Novembre":"November","Dicembre":"December",
    # Fogli Excel / sezioni PDF
    "Piano mensile":"Monthly plan","Database feedstock":"Feedstock database",
    "Sintesi annuale":"Annual summary","Business Plan":"Business Plan",
    # Colonne tabella mensile
    "Mese":"Month","Ore":"Hours","Totale biomasse (t)":"Total feedstocks (t)",
    "Sm³ lordi":"Gross Sm³","Sm³ netti":"Net Sm³",
    "Sm³/h netti":"Net Sm³/h","MWh netti":"Net MWh",
    "MWh elettrici lordi":"Gross MWh el.","MWh elettrici netti":"Net MWh el.",
    "MWh termici":"Thermal MWh","kW lordi medi":"Avg. gross kW",
    "GHG (gCO₂/MJ)":"GHG (gCO₂/MJ)","Saving %":"Saving %",
    "Validità":"Validity","Note":"Notes",
    # Colonne database
    "Biomassa":"Feedstock","Biomasse":"Feedstocks","Categoria":"Category",
    "Resa (Nm³/t)":"Yield (Nm³/t)","All. IX":"Ann. IX",
    # KPI / sintesi
    "Parametro":"Parameter","Valore":"Value","Unità":"Unit","Totale":"Total",
    "Media":"Average","Minimo":"Minimum","Massimo":"Maximum",
    "Mesi validi":"Valid months","Soglia GHG":"GHG threshold","Esito":"Outcome",
    "Conforme":"Compliant","Non conforme":"Non-compliant",
    # Ricavi
    "Ricavo (€)":"Revenue (€)","Ricavi (€)":"Revenue (€)",
    "Ricavo annuo (€)":"Annual revenue (€)",
    "Tariffa (€/MWh)":"Tariff (€/MWh)","t/anno":"t/year",
    "MWh netti/anno":"Net MWh/year","Premio matrice":"Feedstock bonus","Premio CAR":"CAR bonus",
    # Business Plan
    "Anno":"Year","CAPEX (k€)":"CAPEX (k€)","OPEX (k€)":"OPEX (k€)",
    "Ricavi (k€)":"Revenue (k€)","EBITDA (k€)":"EBITDA (k€)",
    "Cash flow (k€)":"Cash flow (k€)","Flusso netto (k€)":"Net flow (k€)",
    "Rata annua (k€)":"Annual instalment (k€)",
    "Debito residuo (k€)":"Residual debt (k€)","Investimento":"Investment",
    "Periodo tariffa":"Tariff period","Tasso LT":"LT rate","Leva fin.":"Fin. leverage",
    "VAN (k€)":"NPV (k€)","Payback (anni)":"Payback (years)",
    # Sidebar
    "🎨 Tema":"🎨 Theme","☀️ Chiaro":"☀️ Light","🌙 Scuro":"🌙 Dark",
    # Tab names
    "🌾 Biomasse per mese":"🌾 Feedstocks per month",
    "🌍 Sostenibilità":"🌍 Sustainability",
    "⚡ Produzione":"⚡ Production",
    "🥧 Mix annuale":"🥧 Annual mix",
    "💼 Business Plan":"💼 Business Plan",
    # Headers
    "📈 Sintesi annuale":"📈 Annual summary",
    "🎯 Modalità di calcolo":"🎯 Calculation mode",
    "📆 Tabella mensile – modifica le celle ✏️, il resto si ricalcola":
        "📆 Monthly table – edit cells ✏️, the rest recalculates",
    "💼 Business Plan — pro forma 15 anni":
        "💼 Business Plan — 15-year pro forma",
    "🌾 Biomasse del tuo impianto":"🌾 Your plant feedstocks",
    "⚙️ Parametri impianto":"⚙️ Plant parameters",
    "🏭 Configurazione impianto (ep)":"🏭 Plant configuration (ep)",
    "🌿 DM 2018 — Sistema CIC":"🌿 DM 2018 — CIC system",
    "🔋 FER 2 — Tariffa e premi":"🔋 FER 2 — Tariff & bonuses",
    "⚡ Fattore netto→lordo (aux_factor)":"⚡ Net→gross factor (aux_factor)",
    "💰 Tariffa FER 2 [€/MWh_el]":"💰 FER 2 tariff [€/MWh_el]",
    # Download
    "📊 Scarica Excel modificabile":"📊 Download editable Excel",
    "📄 Scarica Report PDF":"📄 Download PDF report",
    "📋 Excel snapshot":"📋 Excel snapshot",
    "📥 Scarica CSV":"📥 Download CSV",
    "Scarica CSV":"Download CSV","Scarica Excel":"Download Excel",
    "Scarica PDF":"Download PDF","Report PDF":"PDF report",
    "Excel modificabile":"Editable Excel",
    # Validità
    "✅ Valido":"✅ Valid","❌ Non valido":"❌ Invalid",
    # Modalità
    "Biometano DM 2022":"Biomethane DM 2022","Biometano DM 2018 (CIC)":"Biomethane DM 2018 (CIC)",
    "Biogas CHP DM 6/7/2012":"Biogas CHP DM 6/7/2012","Biogas CHP FER 2 (≤300 kW)":"Biogas CHP FER 2 (≤300 kW)",
    # PDF sezioni
    "Sintesi annuale":"Annual summary","Configurazione impianto":"Plant configuration",
    "Pianificazione mensile":"Monthly planning","Analisi ricavi":"Revenue analysis",
    "Metodologia":"Methodology","Disclaimer":"Disclaimer",
    "Riferimenti normativi":"Regulatory references","Biomasse (t)":"Feedstocks (t)",
    "CH₄ motore (Sm³)":"CH₄ engine (Sm³)",
    # Varie
    "Conforme RED III":"RED III compliant","Non conforme RED III":"RED III non-compliant",
    "Mesi conformi":"Compliant months","Fattore ausiliario":"Auxiliary factor",
    "Comparatore fossile":"Fossil comparator","Soglia risparmio":"Saving threshold",
    "Ore annue":"Annual hours","Ore mensili":"Monthly hours",
    "Colture dedicate":"Dedicated crops","Effluenti zootecnici":"Livestock effluents",
    "Sottoprodotti agroindustriali":"Agro-industrial by-products","FORSU/Rifiuti":"OFMSW/Waste",
    # BMT Override (resa certificata laboratorio)
    "🧪 Override resa BMT certificata (opzionale, per biomassa)":
        "🧪 BMT certified yield override (optional, per feedstock)",
    "Audit rese BMT":"BMT yield audit",
    "Audit rese biomasse (BMT certificato vs tabella standard)":
        "Feedstock yield audit (BMT certificate vs standard table)",
    "Resa standard":"Standard yield","Resa usata":"Used yield",
    "Origine resa":"Yield source","Certificato":"Certificate",
    "Laboratorio":"Laboratory","Data certificato":"Certificate date",
    "Riferimento campione":"Sample reference",
    "BMT certificato laboratorio":"BMT certified laboratory",
    "Tabella standard software / UNI-TS / default interno":
        "Software standard table / UNI-TS / internal default",
    # Override fattori emissivi reali (relazione tecnica)
    "🧬 Fattori emissivi reali da relazione tecnica (opzionale)":
        "🧬 Real emission factors from technical report (optional)",
    "Audit fattori emissivi":"Emission factors audit",
    "Origine fattori":"Factors source","Relazione tecnica":"Technical report",
    "Titolo relazione":"Report title","Autore":"Author",
    "Societa'":"Company","Data relazione":"Report date",
    "Impianto rif.":"Plant ref.","Riferimento campione":"Sample reference",
    "Note metodologiche":"Methodology notes",
    "Relazione tecnica impianto":"Plant technical report",
    "Valori standard software / normativa / default interno":
        "Standard software values / regulatory / internal default",
    "Crediti extra":"Extra credits",
}
