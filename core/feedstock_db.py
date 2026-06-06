# -*- coding: utf-8 -*-
# Copyright (c) 2026 Carlo Sicurini. All Rights Reserved.
# Metan.iQ - Biometano GHG Optimizer (DM 2022 / RED III)
# Proprietary and confidential. See LICENSE for terms.
# Commercial licensing: carlo.sicurini@gmail.com
"""core/feedstock_db.py — Catalogo biomasse (single source of truth).

42 entries normate da UNI/TS 11567:2024, JEC WTT v5 e IPCC 2019.
Storicamente vivevano come dict literal dentro app_mensile.py (~340 LOC
nel mezzo della UI Streamlit); estratte qui per:
- modificare il catalogo senza toccare le 7300+ righe della UI
- consentire test parametrici per biomassa piu' puliti
- aprire la strada al passaggio a `data/feedstocks.json` (step futuro)

Schema di ogni entry:
- eec, esca, etd : float (gCO2eq/MJ) — fattori emissivi UNI/TS A.5
- yield          : float (Nm3 CH4/t tal quale) — UNI/TS A.3
- dry_matter_std : float (frazione) — sostanza secca standard
- color          : str — hex color per chart UI
- cat            : str — categoria UI ("Colture dedicate", ecc.)
- annex_ix       : str|None — "A"/"B"/None per Annex IX RED II/III
- e_l            : float — Land Use Change (default 0; richiede no-LUC)
- requires_no_luc_declaration : bool (opzionale, solo colture dedicate)
- src            : str — riferimento normativo del valore eec
- baseline_assumption / baseline_warning : str (opzionali, manure credit)

Convenzione: il "manure credit" RED III (-45 gCO2/MJ per liquami) e'
incorporato direttamente nell'eec, come da prassi GSE LG 2024.

NB: NON modificare i valori normativi senza aprire prima una NEW NORM
review tracciata in normativa_versions.json. Le costanti pure
(LHV/NM3_TO_MWH/FFC/manure credit puri) restano in core/constants.py.
"""
from __future__ import annotations

FEEDSTOCK_DB: dict = {
    # =========================================================
    # COLTURE DEDICATE (cap 30% RED III, eec alto da coltivazione)
    # Valori eec: UNI/TS 11567:2024 + JEC WTT v5 (cat. "energy crops")
    # NB: NON sono Annex IX -> single counting CIC, no premio DM 2018
    # =========================================================
    # NB: per le colture dedicate il campo `e_l` (Land Use Change) ha
    # default 0.0 ma RICHIEDE dichiarazione no-LUC NUTS-2 del fornitore
    # per essere effettivamente assumibile come zero (RED III All. V,
    # UNI/TS 11567:2024). In assenza, l'OdC puo' imputare valori
    # punitivi tabellari. La UI mostra warning quando si selezionano.
    "Trinciato di mais": {
        "eec": 29.0, "esca": 0.0, "etd": 0.8, "yield": 116.1, "dry_matter_std": 0.35,
        "color": "#F5C518", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.5, eec=29); ST agronomica (CRPA/KTBL)",
    },
    # SORGO — la UNI/TS 11567:2024 (Prosp. A.1) tabula un'unica voce "Sorgo"
    # (580 Nm3 biogas/t ST · 52% CH4 -> 301,6 Nm3 CH4/t ST) ed eec standard 26
    # (Prosp. A.5). La norma NON differenzia i tipi: la distinzione e' agronomica
    # sulla sostanza secca, che riscala la resa per t tal quale via la
    # normalizzazione A.1 (resa = 301,6 × ST_std). Manteniamo la resa specifica
    # normativa come ancora e differenziamo solo ST e la destinazione d'uso.
    "Trinciato di sorgo da foraggio": {
        # Sorgo zuccherino/da foraggio: ST piu' bassa (raccolta lattea-cerosa).
        "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 81.4, "dry_matter_std": 0.27,
        "color": "#9CCC65", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.1/A.5); ST agronomica foraggio (CRPA/KTBL)",
    },
    "Trinciato di sorgo uso energetico (biodigestori)": {
        # Sorgo da biomassa/fibra dedicato a digestione anaerobica: ST piu' alta,
        # ibridi ad alta produzione di sostanza secca per ettaro. Resa specifica
        # mantenuta sul valore normativo UNI/TS (la norma non differenzia).
        "eec": 26.0, "esca": 0.0, "etd": 0.8, "yield": 90.5, "dry_matter_std": 0.30,
        "color": "#689F38", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "UNI-TS 11567:2024 (Prosp. A.1/A.5); ST agronomica sorgo da biomassa (CRPA/KTBL)",
    },
    "Triticale insilato": {
        "eec": 20.0, "esca": 0.0, "etd": 0.8, "yield": 106.1, "dry_matter_std": 0.35,
        "color": "#AED581", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec da JEC v5/KTBL (non in Prosp. A.5); ST agronomica (CRPA/KTBL)",
    },
    "Segale insilata": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 80.0, "dry_matter_std": 0.35,
        "color": "#C5E1A5", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5 / KTBL",
    },
    "Orzo insilato": {
        "eec": 22.0, "esca": 0.0, "etd": 0.8, "yield": 82.0, "dry_matter_std": 0.35,
        "color": "#DCEDC8", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5",
    },
    "Loietto insilato (ryegrass)": {
        "eec": 18.0, "esca": 0.0, "etd": 0.8, "yield": 93.7, "dry_matter_std": 0.35,
        "color": "#9CCC65", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec JEC v5/KTBL (non in Prosp. A.5); ST agronomica (CRPA/KTBL)",
    },
    "Erba medica insilata": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 70.0, "dry_matter_std": 0.35,
        "color": "#7CB342", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5 (azotofissazione)",
    },
    "Doppia coltura (2° raccolto)": {
        "eec": 15.0, "esca": 0.0, "etd": 0.8, "yield": 95.0, "dry_matter_std": 0.35,
        "color": "#689F38", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "GSE LG 2024 (art. doppia coltura)",
    },
    "Erbaio misto insilato": {
        # Miscuglio graminacee+leguminose (es. loiessa/orzo + veccia/trifoglio)
        # insilato a raccolta lattea-cerosa. L'azotofissazione delle leguminose
        # abbassa il concime azotato -> eec tra loietto (18) ed erba medica (15).
        # Resa: 560 Nm3 biogas/t ST x 52% CH4 x 0,22 ST ~= 64 Nm3 CH4/t t.q.
        "eec": 16.0, "esca": 0.0, "etd": 0.8, "yield": 64.0, "dry_matter_std": 0.22,
        "color": "#8BC34A", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "eec JEC v5/KTBL (non in Prosp. A.5); ST agronomica erbaio misto (CRPA/KTBL)",
    },
    "Barbabietola da zucchero": {
        "eec": 12.0, "esca": 0.0, "etd": 0.8, "yield": 105.0, "dry_matter_std": 0.23,
        "color": "#CE93D8", "cat": "Colture dedicate",
        "annex_ix": None, "e_l": 0.0,
        "requires_no_luc_declaration": True,
        "src": "JEC v5",
    },
    # =========================================================
    # EFFLUENTI ZOOTECNICI (manure credit RED III Annex VI)
    # All. IX RED II/III parte A lett. (d): "letame animale e fanghi
    # di depurazione". Tutti -> AVANZATI con double counting CIC.
    # Credit eec proporzionale al beneficio di stoccaggio anaerobico
    # rispetto al baseline (lagone/vasca). Liquame liquido: -45.
    # Letami palabili (minore emissione CH4 baseline): -20/-30.
    # Pollina broiler/tacchini (lettiera): -10/-15.
    # Ovaiole stoccaggio aerobico su nastro: 0 (no credit).
    # =========================================================
    "Liquame suino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#8D6E63", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto (decomposizione anaerobica spontanea)",
        "baseline_warning": "Se il fornitore ha vasca coperta con captazione/N-stripping, il credit -45 va ridotto o annullato (richiede dichiarazione fornitore).",
        "e_l": 0.0,
    },
    "Liquame bovino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#795548", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto",
        "baseline_warning": "Verificare assenza vasca coperta in stalla per validare il credit.",
        "e_l": 0.0,
    },
    "Liquame bufalino": {
        "eec": -45.0, "esca": 0.0, "etd": 0.8, "yield": 14.0, "dry_matter_std": 0.10,
        "color": "#6D4C41", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "stoccaggio in vasca/lagone aperto",
        "baseline_warning": "Verificare assenza vasca coperta in stalla per validare il credit.",
        "e_l": 0.0,
    },
    "Letame bovino palabile": {
        "eec": -30.0, "esca": 0.0, "etd": 0.8, "yield": 35.0, "dry_matter_std": 0.25,
        "color": "#A1887F", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019 Vol.4 Cap.10 + GSE",
        "baseline_assumption": "cumulo solido in stoccaggio (decomposizione parzialmente anaerobica)",
        "baseline_warning": "Se il fornitore usa compostaggio aerobico controllato, il credit va ridotto.",
        "e_l": 0.0,
    },
    "Letame equino": {
        "eec": -20.0, "esca": 0.0, "etd": 0.8, "yield": 42.0, "dry_matter_std": 0.30,
        "color": "#BCAAA4", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "JEC v5",
        "baseline_assumption": "cumulo solido in scuderia/box",
        "baseline_warning": "Verificare modalità stoccaggio per validare il credit.",
        "e_l": 0.0,
    },
    "Pollina ovaiole (aerobico)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 84.0, "dry_matter_std": 0.60,
        "color": "#FF9800", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "GSE (no credit anaerobico)",
        "baseline_assumption": "essiccatore aerobico su nastro (gabbie arricchite moderne)",
        "baseline_warning": "Se il fornitore stocca in fossa anaerobica sotto le gabbie, il valore +5 va rivisto verso negativo (credit) come per pollina broiler (-15).",
        "e_l": 0.0,
    },
    "Pollina broiler (lettiera)": {
        "eec": -15.0, "esca": 0.0, "etd": 0.8, "yield": 105.0, "dry_matter_std": 0.60,
        "color": "#FFA726", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "manure credit RED III All. V/VI (std A.5=0); richiede dichiar. baseline fornitore",
        "baseline_assumption": "lettiera in capannone (decomposizione parzialmente anaerobica)",
        "baseline_warning": "Verificare frequenza rimozione lettiera per validare il credit.",
        "e_l": 0.0,
    },
    "Pollina tacchini": {
        "eec": -10.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.60,
        "color": "#FFB74D", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "IPCC 2019",
        "baseline_assumption": "lettiera in capannone",
        "baseline_warning": "Verificare modalità stoccaggio per validare il credit.",
        "e_l": 0.0,
    },
    "Deiezioni conigli": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 75.0, "dry_matter_std": 0.50,
        "color": "#FFCC80", "cat": "Effluenti zootecnici",
        "annex_ix": "A",
        "src": "eec JEC v5 (std A.5=0); All. IX RED III parte A",
        "baseline_assumption": "fossa di stoccaggio in conigliera",
        "baseline_warning": "Verificare modalità stoccaggio per validare l'eec.",
        "e_l": 0.0,
    },
    # =========================================================
    # SOTTOPRODOTTI AGROINDUSTRIALI (All. IX RED II/III)
    # Tutti -> AVANZATI con double counting CIC.
    # - Sanse, vinacce, raspi, fecce, lolla -> All. IX A (h, i, k, m)
    # - Scarti caseari, panificazione, ortofrutta -> All. IX A (c, m)
    # - UCO, scarti macellazione cat. 3 -> All. IX B (oli/grassi)
    # =========================================================
    "Sansa di olive umida": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 120.0, "dry_matter_std": 0.30,
        "color": "#6A1B9A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5 / All. IX RED III",
    },
    "Sansa vergine": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 140.0, "dry_matter_std": 0.50,
        "color": "#7B1FA2", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Pastazzo di agrumi": {
        "eec": 6.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.18,
        "color": "#FFB300", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Vinaccia (con raspi)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 130.0, "dry_matter_std": 0.30,
        "color": "#880E4F", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Raspi d'uva": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 70.0, "dry_matter_std": 0.35,
        "color": "#AD1457", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Feccia vinicola": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.10,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Siero di latte": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 30.0, "dry_matter_std": 0.06,
        "color": "#FFF9C4", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Scotta (siero residuo)": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 22.0, "dry_matter_std": 0.06,
        "color": "#FFF59D", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Trebbie di birra": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 140.0, "dry_matter_std": 0.25,
        "color": "#D4A574", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Lolla/pula di riso": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 50.0, "dry_matter_std": 0.90,
        "color": "#F5DEB3", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Melasso": {
        "eec": 8.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.75,
        "color": "#5D4037", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Scarti panificazione/pasticceria": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 280.0, "dry_matter_std": 0.80,
        "color": "#D7CCC8", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5, alta resa zuccheri (non in Prosp. A.5)",
    },
    "Grassi esausti / UCO": {
        "eec": 2.0, "esca": 0.0, "etd": 0.8, "yield": 700.0, "dry_matter_std": 0.99,
        "color": "#FFE082", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",
        "src": "JEC v5 (lipidi, All. IX parte B)",
    },
    "Scarti macellazione (cat. 3)": {
        "eec": 5.0, "esca": 0.0, "etd": 0.8, "yield": 180.0, "dry_matter_std": 0.30,
        "color": "#EF5350", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "B",
        "src": "JEC v5 / Reg. 1069/2009",
    },
    "Sottoprodotti ortofrutticoli": {
        "eec": 7.0, "esca": 0.0, "etd": 0.8, "yield": 100.0, "dry_matter_std": 0.15,
        "color": "#66BB6A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Scarti caseari vari": {
        "eec": 4.0, "esca": 0.0, "etd": 0.8, "yield": 40.0, "dry_matter_std": 0.15,
        "color": "#E1BEE7", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "JEC v5",
    },
    "Fanghi agro-industriali": {
        "eec": 3.0, "esca": 0.0, "etd": 0.8, "yield": 55.0, "dry_matter_std": 0.10,
        "color": "#90A4AE", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC v5 (non in Prosp. A.5)",
    },
    "Polpe di barbabietola fresche": {
        "eec": 0.0, "esca": 0.0, "etd": 2.0, "yield": 50.0, "dry_matter_std": 0.22,
        "color": "#F48FB1", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 by-product allocation (non in Prosp. A.5)",
    },
    "Polpe di barbabietola insilate": {
        "eec": 0.0, "esca": 0.0, "etd": 2.5, "yield": 75.0, "dry_matter_std": 0.28,
        "color": "#EC407A", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 (non in Prosp. A.5)",
    },
    "Melasso di barbabietola": {
        "eec": 0.0, "esca": 0.0, "etd": 1.5, "yield": 280.0, "dry_matter_std": 0.75,
        "color": "#C2185B", "cat": "Sottoprodotti agroindustriali",
        "annex_ix": "A",
        "src": "All. IX RED III (residuo); eec JEC WTT v5 (non in Prosp. A.5)",
    },
    # =========================================================
    # FORSU / RIFIUTI (All. IX RED II/III, parte A)
    # All. IX A (c): bio-waste · (d): sewage sludge
    # Tutti -> AVANZATI con double counting CIC.
    # =========================================================
    "FORSU selezionata": {
        # Resa da UNI/TS A.3: 450 Nm3 biogas/t ST x 60% CH4 x 0,24 ST = 64,8 Nm3 CH4/t t.q.
        "eec": 0.0, "esca": 0.0, "etd": 0.8, "yield": 64.8, "dry_matter_std": 0.24,
        "color": "#546E7A", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024 (Prosp. A.5 eec=0; resa A.3: 450x60%x0,24)",
    },
    "Fanghi depurazione": {
        # Resa da UNI/TS A.3: 350 Nm3 biogas/t ST x 62% CH4 x 0,06 ST = 13,0 Nm3 CH4/t t.q.
        "eec": 0.0, "esca": 0.0, "etd": 0.8, "yield": 13.0, "dry_matter_std": 0.06,
        "color": "#78909C", "cat": "FORSU / Rifiuti",
        "annex_ix": "A",
        "src": "UNI-TS 11567:2024 (Prosp. A.5 eec=0; resa A.3: 350x62%x0,06)",
    },
}

__all__ = ["FEEDSTOCK_DB"]
