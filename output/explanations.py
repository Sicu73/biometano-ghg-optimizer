# -*- coding: utf-8 -*-
"""output/explanations.py — Testi spiegativi origine dati e metodo di calcolo.

Ogni funzione riceve il contesto (o l'output_model) e produce un testo
descrittivo in lingua italiana (o inglese se lang='en') che spiega:
  - da dove provengono le rese biomasse (yield_origin)
  - da dove provengono i fattori emissivi (emission_factor_origin)
  - come e' calcolato il bilancio GHG (ghg_method)
  - quale e' la base normativa applicata (regulatory_basis)

I testi sono usati in:
  - output_model["explanations"]
  - report PDF (sezione "Riferimenti metodologici")
  - Excel (sheet "Note metodologiche")
  - UI Streamlit (expander "Origine dati")

NON contengono dati numerici inventati. Fanno riferimento solo a
normative gia' cablate nel codice (RED III, DM 2022, DM 2018, UNI/TS,
JEC WTT v5, ecc.).
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Testi statici (template per lingua)
# ---------------------------------------------------------------------------

_YIELD_ORIGIN_IT = (
    "Le rese biomassa (Nm³ CH₄/t) utilizzate nei calcoli provengono da:\n"
    "- Letteratura tecnica di settore: UNI/TS 11567:2024, JEC Well-to-Tank v5 (JRC-CONCAWE-EUCAR), "
    "handbook IEA Bioenergy Task 37 e KTBL (Kuratorium für Technik und Bauwesen in der Landwirtschaft).\n"
    "- Parametri tipici Consorzio Monviso per colture locali (mais, sorgo, liquame suino).\n"
    "- Se l’utente ha caricato un certificato BMT (Biochemical Methane Test) "
    "da laboratorio accreditato, la resa certificata sovrascrive il valore tabellare "
    "per quella biomassa. La sostituzione e’ tracciata nell’audit trail."
)

_YIELD_ORIGIN_EN = (
    "Biomass yields (Nm³ CH₄/t) used in calculations are sourced from:\n"
    "- Technical literature: UNI/TS 11567:2024, JEC Well-to-Tank v5 (JRC-CONCAWE-EUCAR), "
    "IEA Bioenergy Task 37 handbook and KTBL.\n"
    "- Typical parameters for Consorzio Monviso local crops (maize, sorghum, pig slurry).\n"
    "- If a laboratory-certified BMT (Biochemical Methane Test) has been uploaded by the user, "
    "the certified yield replaces the table value for that feedstock. "
    "The substitution is recorded in the audit trail."
)

_EMISSION_FACTOR_ORIGIN_IT = (
    "I fattori emissivi (gCO₂eq/MJ) derivano da:\n"
    "- eec (emissioni estrazione/coltivazione): UNI/TS 11567:2024, JEC WTT v5, "
    "IPCC 2019 Vol.4 Cap.10. Il manure credit RED III (-45 gCO₂eq/MJ per "
    "liquami/letami) e’ incorporato direttamente nell’eec, come prassi GSE.\n"
    "- etd (estrazione/trasporto/distribuzione): standard 0,8 gCO₂eq/MJ (RED III default).\n"
    "- esca (carbon accumulation): 0 per tutte le biomasse salvo eccezioni specifiche.\n"
    "- ep (processing): contributo impianto calcolato automaticamente da aux_factor, "
    "tecnologia upgrading (PSA/membrane/amminico/scrubber), fonte calore/elettricità, "
    "pressione iniezione rete. Fonte: JEC WTT v5, UNI/TS 11567:2024.\n"
    "Se l’utente ha caricato una relazione tecnica con misure reali d’impianto, "
    "i fattori effettivi sostituiscono i valori tabellari. La sostituzione e’ "
    "tracciata nell’audit trail."
)

_EMISSION_FACTOR_ORIGIN_EN = (
    "Emission factors (gCO₂eq/MJ) are sourced from:\n"
    "- eec (extraction/cultivation emissions): UNI/TS 11567:2024, JEC WTT v5, "
    "IPCC 2019 Vol.4 Ch.10. The RED III manure credit (-45 gCO₂eq/MJ for slurries/manures) "
    "is incorporated directly into eec, per GSE practice.\n"
    "- etd (extraction/transport/distribution): standard 0.8 gCO₂eq/MJ (RED III default).\n"
    "- esca (carbon accumulation): 0 for all feedstocks unless specified otherwise.\n"
    "- ep (processing): plant contribution automatically calculated from aux_factor, "
    "upgrading technology (PSA/membrane/amine/water scrubber), heat/electricity source, "
    "injection pressure. Source: JEC WTT v5, UNI/TS 11567:2024.\n"
    "If the user has uploaded a technical report with real plant measurements, "
    "the actual factors replace the table values. The substitution is recorded in the audit trail."
)

_GHG_METHOD_IT = (
    "Metodo di calcolo GHG (RED III, Allegato V Parte C):\n"
    "1. Per ogni biomassa si calcola il contributo energetico: Eᵢ = Mᵢ × Yᵢ × LHV_CH4 (MJ)\n"
    "   dove M = massa in tonnellate, Y = resa Nm³ CH4/t, LHV = 35,9 MJ/Nm³.\n"
    "2. Emissioni ponderate: e_w = Σ(eᵢ × Eᵢ) / ΣEᵢ (gCO₂eq/MJ)\n"
    "   dove eᵢ = eecᵢ + etdᵢ + ep - escaᵢ per ogni biomassa.\n"
    "3. Saving GHG = (comparatore_fossile - e_w) / comparatore_fossile × 100 (%)\n"
    "4. Il comparatore fossile dipende dall’uso finale:\n"
    "   - Rete/elettricità/calore: 80 gCO₂eq/MJ (RED III Annex VI Part B)\n"
    "   - Trasporti (BioCNG/BioGNL): 94 gCO₂eq/MJ (RED III Annex V Part C)\n"
    "   - Biogas CHP (mix elettrico EU): 183 gCO₂eq/MJ (RED III Annex VI)\n"
    "5. Il biometano netto = biogas lordo / aux_factor (autoconsumo impianto)."
)

_GHG_METHOD_EN = (
    "GHG calculation method (RED III, Annex V Part C):\n"
    "1. For each feedstock the energy contribution is calculated: Eᵢ = Mᵢ × Yᵢ × LHV_CH4 (MJ)\n"
    "   where M = mass in tonnes, Y = yield Nm³ CH4/t, LHV = 35.9 MJ/Nm³.\n"
    "2. Weighted emissions: e_w = Σ(eᵢ × Eᵢ) / ΣEᵢ (gCO₂eq/MJ)\n"
    "   where eᵢ = eecᵢ + etdᵢ + ep - escaᵢ per feedstock.\n"
    "3. GHG Saving = (fossil_comparator - e_w) / fossil_comparator × 100 (%)\n"
    "4. Fossil comparator depends on end use:\n"
    "   - Grid/electricity/heat: 80 gCO₂eq/MJ (RED III Annex VI Part B)\n"
    "   - Transport (BioCNG/BioLNG): 94 gCO₂eq/MJ (RED III Annex V Part C)\n"
    "   - Biogas CHP (EU electricity mix): 183 gCO₂eq/MJ (RED III Annex VI)\n"
    "5. Net biomethane = gross biogas / aux_factor (plant self-consumption)."
)

_REGULATORY_BASIS_IT = (
    "Base normativa applicata:\n"
    "- RED III (Direttiva UE 2023/2413): obiettivi rinnovabili 2030, metodo calcolo GHG, "
    "Annex V Parte C (biometano), Annex IX (feedstock avanzati).\n"
    "- D.Lgs. 9 gennaio 2026, n. 5 (GU n. 15 del 20/01/2026), entrata in vigore 04/02/2026: "
    "recepimento italiano della RED III; soglie e comparatori allineati alla Direttiva UE 2023/2413.\n"
    "- DM 15/09/2022 (Decreto Biometano): incentivazione biometano immissione in rete "
    "con tariffa GSE, Premio matrice e Premio upgrading, periodo 15 anni.\n"
    "- DM 2/3/2018 (aggiornato D.Lgs. 199/2021): sistema CIC, double counting "
    "biometano avanzato Annex IX, regimi trasporti e altri usi.\n"
    "- DM 6/7/2012: incentivazione biogas cogenerativo agricolo (≤1 MW), "
    "tariffa onnicomprensiva (TO) + premio CAR.\n"
    "- DM 19/06/2024 (FER 2 — avviso GU 24A04589; regole operative GSE 24A06795): "
    "biogas CHP piccoli impianti ≤300 kWe, Tariffa di Riferimento + premi matrice/CAR, 20 anni.\n"
    "- UNI/TS 11567:2024: valori di riferimento italiani rese e fattori emissivi.\n"
    "- JEC Well-to-Tank v5 (JRC-CONCAWE-EUCAR): database europeo fattori emissivi.\n"
    "- GSE Linee Guida 2024: prassi operative per la qualificazione dell’impianto."
)

_REGULATORY_BASIS_EN = (
    "Regulatory basis applied:\n"
    "- RED III (EU Directive 2023/2413): 2030 renewable targets, GHG calculation method, "
    "Annex V Part C (biomethane), Annex IX (advanced feedstocks).\n"
    "- Italian Legislative Decree 9 January 2026, no. 5 (Official Gazette no. 15 of 20/01/2026), "
    "in force since 04/02/2026: Italian transposition of RED III; thresholds and comparators "
    "aligned with EU Directive 2023/2413.\n"
    "- DM 15/09/2022 (Biomethane Decree): grid-injection biomethane incentive, "
    "GSE tariff + matrix/upgrading bonuses, 15-year period.\n"
    "- DM 2/3/2018 (as amended by D.Lgs. 199/2021): CIC system, double counting for "
    "advanced Annex IX biomethane, transport and other end-uses.\n"
    "- DM 6/7/2012: agricultural biogas CHP incentive (≤1 MW), "
    "all-inclusive tariff (TO) + CAR bonus.\n"
    "- DM 19/06/2024 (FER 2 — Official Gazette notice 24A04589; GSE operating rules 24A06795): "
    "small CHP biogas ≤300 kWe, Reference Tariff + matrix/CAR bonuses, 20 years.\n"
    "- UNI/TS 11567:2024: Italian reference values for yields and emission factors.\n"
    "- JEC Well-to-Tank v5 (JRC-CONCAWE-EUCAR): European emission factor database.\n"
    "- GSE Guidelines 2024: operational practices for plant qualification."
)


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def explain_yield_origin(ctx: dict) -> str:
    """Testo spiegativo origine rese biomasse."""
    lang = ctx.get("lang", "it") if isinstance(ctx, dict) else "it"
    has_bmt = bool(ctx.get("yield_audit_rows")) if isinstance(ctx, dict) else False
    base = _YIELD_ORIGIN_EN if lang == "en" else _YIELD_ORIGIN_IT
    if has_bmt:
        suffix_it = (
            "\n[Override BMT attivi per questa sessione: "
            f"{len(ctx.get('yield_audit_rows', []))} biomassa/e. "
            "Vedi audit trail per dettagli.]"
        )
        suffix_en = (
            "\n[Active BMT overrides in this session: "
            f"{len(ctx.get('yield_audit_rows', []))} feedstock(s). "
            "See audit trail for details.]"
        )
        base += suffix_en if lang == "en" else suffix_it
    return base


def explain_emission_factor_origin(ctx: dict) -> str:
    """Testo spiegativo origine fattori emissivi."""
    lang = ctx.get("lang", "it") if isinstance(ctx, dict) else "it"
    has_ef = bool(ctx.get("emission_audit_rows")) if isinstance(ctx, dict) else False
    base = _EMISSION_FACTOR_ORIGIN_EN if lang == "en" else _EMISSION_FACTOR_ORIGIN_IT
    if has_ef:
        suffix_it = (
            "\n[Override fattori emissivi reali attivi per questa sessione: "
            f"{len(ctx.get('emission_audit_rows', []))} biomassa/e. "
            "Vedi audit trail per dettagli.]"
        )
        suffix_en = (
            "\n[Active real emission factor overrides in this session: "
            f"{len(ctx.get('emission_audit_rows', []))} feedstock(s). "
            "See audit trail for details.]"
        )
        base += suffix_en if lang == "en" else suffix_it
    return base


def explain_ghg_method(ctx: dict) -> str:
    """Testo spiegativo metodo di calcolo GHG."""
    lang = ctx.get("lang", "it") if isinstance(ctx, dict) else "it"
    return _GHG_METHOD_EN if lang == "en" else _GHG_METHOD_IT


def explain_regulatory_basis(ctx: dict) -> str:
    """Testo spiegativo base normativa applicata."""
    lang = ctx.get("lang", "it") if isinstance(ctx, dict) else "it"
    app_mode = ctx.get("APP_MODE", "biometano") if isinstance(ctx, dict) else "biometano"
    base = _REGULATORY_BASIS_EN if lang == "en" else _REGULATORY_BASIS_IT
    # Aggiunge note specifiche per mode
    if app_mode in ("biogas_chp", "biogas_chp_fer2"):
        note_it = (
            "\n[Nota: in modalita' CHP il comparatore fossile applicato e' 183 gCO2eq/MJ "
            "(mix elettrico EU, RED III Annex VI). Il saving GHG minimo richiesto e' 80%.]"
        )
        note_en = (
            "\n[Note: in CHP mode the fossil comparator is 183 gCO2eq/MJ "
            "(EU electricity mix, RED III Annex VI). Minimum GHG saving required is 80%.]"
        )
        base += note_en if lang == "en" else note_it
    return base


def build_all_explanations(ctx: dict) -> dict:
    """Costruisce il dict completo delle spiegazioni per il output_model."""
    return {
        "yield_origin":            explain_yield_origin(ctx),
        "emission_factor_origin":  explain_emission_factor_origin(ctx),
        "ghg_method":              explain_ghg_method(ctx),
        "regulatory_basis":        explain_regulatory_basis(ctx),
    }
