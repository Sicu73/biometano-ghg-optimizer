# AUDIT — base LORDO vs NETTO per controllo sostenibilità GHG

Branch: `audit/gross-net-sustainability`
Data: 2026-05-03
Software: Metan.iQ (biometano-ghg-optimizer)

## 1. Scopo

Verificare che il calcolo del saving GHG e dei vincoli di sostenibilità
ambientale (RED III, DM 15/9/2022, DM 2/3/2018, DM 6/7/2012, DM 18/9/2024
FER 2) sia riferito **all'energia LORDA prodotta** (Sm³ lordi · LHV) e
**non** impropriamente all'energia netta immessa in rete; per il
biometano, esporre come informazione aggiuntiva la **doppia vista
LORDO + NETTO**, lasciando la base normativa sul **LORDO**.

## 2. Mappatura calcoli — base usata

### 2.1 Catena LORDO ↔ NETTO

```
LORDO (Sm³ lordi, da resa biomasse · LHV biometano)
   │
   │  / aux_factor   (autoconsumo elettrico/termico impianto)
   ▼
NETTO (Sm³ netti = LORDO / aux_factor → immissione in rete)
```

`aux_factor` (≥ 1, tipico 1.10–1.50) è la quota di energia LORDA
consumata dall'impianto. Esempio: aux 1.29 ⇒ il 29% della produzione
LORDA copre upgrading, compressione, cogeneratore di servizio.

### 2.2 GHG components (`core/calculation_engine.ghg_summary`)

| Grandezza | Formula | Base | Note |
|---|---|---|---|
| `nm3_gross` | Σ_feed (massa · resa) | LORDO | input dirette biomasse |
| `nm3_net` | `nm3_gross / aux` | NETTO | autoconsumo applicato |
| `mj_gross` | `nm3_gross · LHV_CH4` | LORDO | base intensità GHG |
| `mj_net` | `nm3_net · LHV_CH4` | NETTO | per CIC / ricavi |
| `eec`, `el`, `ep`, `etd`, `eu`, `esca`, `eccs`, `eccr` | weighted MJ_LORDO | LORDO | medie pesate su MJ lordi |
| `e_w` (gCO₂eq/MJ) | `(eec − esca + el + ep + etd + eu − eccs − eccr)` | LORDO | intensità su MJ lordi |
| `saving` (%) | `1 − e_w / fossil_comparator` | LORDO | invariante su aux |

**Verifica numerica** (test `test_ghg_summary_uses_gross_for_sustainability`):
- masse fissate, aux=1.10 → `nm3_net = nm3_gross/1.10`
- masse fissate, aux=1.50 → `nm3_net = nm3_gross/1.50`
- saving% identico a meno di errore numerico (1e-9): **OK, base LORDO confermata**.

### 2.3 Soglie e vincoli per regime

| Regime | Soglia saving | Base | Cap principali (su) |
|---|---|---|---|
| RED III (Annex V Part C, post-2026) | 80% | **LORDO** | — |
| DM 15/9/2022 (DM 2022) biometano grid | 65–80% (data avvio) | **LORDO** | Sm³/h autorizzati su NETTO |
| DM 2/3/2018 biometano CIC trasporti | 50–65% | **LORDO** | annex IX premium |
| DM 6/7/2012 biogas CHP | varia | **LORDO** | MWh elettrici cap |
| DM 18/9/2024 FER 2 | 80% | **LORDO** | quota sottoprodotti |

In **nessun** regime la base sostenibilità è il NETTO. Il NETTO entra solo
nella verifica del cap autorizzativo Sm³/h (capacità nominale immissione)
e nel calcolo dei ricavi/CIC.

### 2.4 Output — base esposta

| Output | LORDO | NETTO | Base esplicita |
|---|---|---|---|
| Dashboard KPI (Streamlit) | sì (nuovo) | sì | sì (badge) |
| `output/tables.build_sustainability_basis_table` | sì | sì | sì |
| `output/monthly_kpis.build_monthly_kpis` | `mwh_gross`, `saving_pct` | `mwh`, `saving_pct_net` | `sustainability_basis` |
| `output/output_builder.calculation_summary` | `tot_sm3_lordi`, `tot_mwh_lordi` | `tot_sm3_netti`, `tot_mwh` | `sustainability_basis`, `sustainability_basis_note`, `biomethane_dual_view` |
| CSV export | sì (metadata) | sì (metadata) | sì |
| Excel `Riepilogo` | sì | sì | sì |
| PDF KPI box | sì | sì | sì |
| `output/explanations.explain_sustainability_basis` | dichiarato | dichiarato (informativo) | sì (IT/EN) |

## 3. Diagnosi

### 3.1 Calcoli (motore)

Il motore era **già corretto**: `ghg_summary` calcola `e_w` come media
pesata su `mj_gross` e `saving` su `mj_gross / fossil_comparator`. La
verifica numerica con due aux diversi e stesse masse mostra saving
invariante: nessun bug.

### 3.2 Esposizione

Era invece **incompleta** sull'esposizione:

- `output_builder.calculation_summary` esponeva solo `tot_sm3_netti` e
  `tot_mwh` (NETTO). Mancava `tot_sm3_lordi`, `tot_mwh_lordi`.
- Le spiegazioni e i report **non dichiaravano** esplicitamente che la
  base del saving è il LORDO. L'utente di un report PDF non poteva
  capire se il 81% saving fosse stato calcolato su lordo o su netto.
- Non esisteva tabella riassuntiva con doppia vista LORDO/NETTO per
  biometano.
- `MonthlyAggregate` non aveva `mwh_gross` né `sustainability_basis`.

## 4. Correzioni applicate

### 4.1 Esposizione esplicita (additive, backward-compat)

`output/output_builder.py`:

```python
calculation_summary = {
    ...
    "tot_sm3_netti": ...,        # esistente
    "tot_sm3_lordi": ...,        # nuovo
    "tot_mwh":       ...,        # esistente (= netti)
    "tot_mwh_lordi": ...,        # nuovo
    "sustainability_basis": "LORDO",                # nuovo
    "sustainability_basis_note": "Saving GHG ...",  # nuovo
    "biomethane_dual_view": True/False,             # nuovo
}
```

`core/monthly_aggregate.py`: aggiunti `mwh_gross`, `saving_pct_net`,
`sustainability_basis = "LORDO"` con docstring che chiarisce semantica.

### 4.2 Tabella dual view

`output/tables.build_sustainability_basis_table(output_model)` produce
righe per **Sm³**, **MWh**, **Saving GHG (%)** e **Base normativa
applicata** con colonne `LORDO (base sostenibilita')` e `NETTO (immesso
in rete)` + colonna Note.

### 4.3 Export

- **CSV**: metadata in fondo a ogni sheet `monthly` (e CSV vuoto)
  espongono Sm³ LORDI, Sm³ NETTI, MWh LORDI, MWh NETTI, Base
  sostenibilità, Nota.
- **Excel**: sheet `Riepilogo` con righe separate LORDO/NETTO + Base.
- **PDF**: KPI box con doppia riga Sm³ e MWh + Base.

### 4.4 Spiegazioni

`output/explanations.py`:

- `_GHG_METHOD_IT/EN` arricchito con sezione `BASE SOSTENIBILITA': LORDO`
  che cita esplicitamente RED III, DM 15/9/2022, DM 2/3/2018, DM 6/7/2012,
  DM 18/9/2024.
- Nuova `explain_sustainability_basis(ctx)` (IT/EN): dichiara LORDO come
  base, e per i regimi biometano descrive la vista NETTO informativa.
- `build_all_explanations(ctx)` espone la chiave `sustainability_basis`.

## 5. Test

`tests/test_gross_net_sustainability.py` (8 test, tutti verdi):

1. `test_ghg_summary_uses_gross_for_sustainability` — saving% invariante
   sotto aux_factor.
2. `test_biomethane_has_net_variant` — `calculation_summary` espone
   LORDO+NETTO + flag `biomethane_dual_view=True` + base LORDO.
3. `test_chp_no_dual_view` — in CHP `biomethane_dual_view=False`.
4. `test_export_includes_both_gross_and_net` — CSV monthly espone LORDI
   e NETTI + base.
5. `test_sustainability_basis_table` — tabella ha `Base normativa
   applicata` + colonne LORDO/NETTO.
6. `test_explanation_states_basis` — IT contiene "LORDO" + "RED III" +
   "NETTO"; EN contiene "GROSS" + "RED III" + "NET".
7. `test_monthly_aggregate_dual_view_fields` — campi `mwh_gross`,
   `saving_pct_net`, `sustainability_basis`.
8. `test_monthly_kpis_includes_basis` — `build_monthly_kpis` espone
   `mwh_gross` e `sustainability_basis`.

Suite completa: **247 test, tutti verdi**.

## 6. Esempio output (biometano DM 2022)

Input ctx (estratto):
- `tot_sm3_lordi = 3 900 000`
- `tot_sm3_netti = 3 023 000`  (aux 1.29)
- `tot_mwh_lordi = 38 882`
- `tot_mwh = 30 139`
- `saving_avg = 81.5 %`

Tabella `build_sustainability_basis_table`:

| Voce | LORDO (base sostenibilita') | NETTO (immesso in rete) | Note |
|---|---:|---:|---|
| Sm³ biometano | 3 900 000 | 3 023 000 | LORDO = resa biomasse · NETTO = LORDO/aux |
| MWh biometano | 38 882 | 30 139 | 1 Sm³ ≈ 0.00997 MWh (LHV) |
| Saving GHG (%) | 81.5 | 81.5 | Intensità gCO₂eq/MJ su MJ LORDI |
| Base normativa applicata | LORDO | vista informativa | Saving GHG calcolato su MJ lordi (RED III, DM 2022, …) |

CSV monthly metadata footer:

```
# Sm3 LORDI (base sostenibilita'): 3.900.000,00
# Sm3 NETTI (immesso in rete): 3.023.000,00
# MWh LORDI (base sostenibilita'): 38.882,00
# MWh NETTI (immesso in rete): 30.139,00
# Base sostenibilita': LORDO
# Nota base: Saving GHG calcolato come intensita' gCO2eq/MJ sull'ENERGIA LORDA …
```

PDF KPI box (estratto):

```
Sm³ LORDI/anno (base sostenibilita')      3.900.000
Sm³ NETTI/anno (immesso in rete)          3.023.000
MWh LORDI/anno (base sostenibilita')         38.882
MWh NETTI/anno (immesso in rete)             30.139
Saving GHG medio (%) - base LORDA              81,5
Base sostenibilita'                           LORDO
```

Spiegazione (IT, biometano):

> Base sostenibilita': LORDO. Il saving GHG ed i vincoli normativi sono
> valutati sull'energia LORDA (Sm³ lordi · LHV biometano = MJ lordi).
> È la base richiesta da RED III (Allegato V Parte C), DM 15/9/2022 (DM
> 2022), DM 2/3/2018 (CIC), DM 6/7/2012 (biogas CHP) e DM 18/9/2024
> (FER 2): l'intera energia prodotta deve essere sostenibile.
>
> Per il biometano i report espongono anche la vista NETTO (Sm³ netti =
> Sm³ lordi / aux_factor) come riferimento informativo per l'energia
> effettivamente immessa in rete. Il vincolo normativo resta sul LORDO.

## 7. Conclusione

Il software era **calcolato correttamente** sulla base LORDA. La
correzione consiste interamente nell'**esporre esplicitamente** la base
in dashboard, tabelle, CSV/Excel/PDF e spiegazioni, e nell'aggiungere la
**doppia vista LORDO+NETTO** richiesta per il biometano (DM 2018, DM
2022, RED III). Nessuna formula è stata modificata. Backward
compatibility 100%.
