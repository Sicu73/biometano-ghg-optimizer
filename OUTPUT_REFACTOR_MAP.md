# OUTPUT_REFACTOR_MAP.md
## Metan.iQ — Mappa del refactoring architetturale output

**Data analisi:** 2026-05-03
**Branch:** refactor/output-simplification
**Analista:** Claude Sonnet 4.6

---

## 1. INPUT DA NON TOCCARE (solo lettura)

Le seguenti sezioni di `app_mensile.py` costituiscono la parte **input** che non va modificata:

| Zona | Righe approssimative | Descrizione |
|---|---|---|
| Costanti e DB | 1–1460 | FEEDSTOCK_DB, costanti RED III, CIC, FER2, BP defaults, formule helpers |
| Funzioni calcolo | 425–1460 | `compute_business_plan`, `compute_aux_factor`, `ghg_summary`, `solve_*`, `find_optimal_pair`, `e_total_feedstock`, `_yield_of`, `_emission_factors_of` |
| UI sidebar | 1460–3900 | Tema, mode selector, normativa expander, parametri impianto, BMT override, emission override, FER2, BP pro forma |
| Data editor mensile | 3900–4400 | Input tabella mensile (`st.data_editor`), state key, default masses |

---

## 2. OUTPUT ATTUALI (da semplificare e centralizzare)

| Componente | Dove si trova oggi | Problema |
|---|---|---|
| Tabella mensile risultati (`df_res`) | `app_mensile.py` righe ~4400–4700 | Costruita inline nel corpo principale, non isolata |
| Tabella ricavi per biomassa | `app_mensile.py` righe ~4660–4800 | Costruita inline, logica duplicata con Excel |
| KPI aggregati (tot_biomasse_t, tot_sm3, tot_mwh, saving_avg, valid_months, tot_revenue) | `app_mensile.py` righe ~4800–5200 | Calcolati come variabili locali sparse, non in struttura unica |
| Contesto XLSX (`_xlsx_ctx`) | `app_mensile.py` righe ~5207–5315 | Assemblato manualmente ogni run, ~80 chiavi, nessuna struttura dati |
| Contesto PDF (`_pdf_ctx`) | `app_mensile.py` righe ~5345–5430 | Identico al ctx XLSX ma con chiavi diverse -> duplicazione |
| CSV export | `app_mensile.py` righe ~5469–5490 | `df_res.to_csv()` inline, nessuna logica separata |
| Business plan display | `app_mensile.py` righe ~4950–5170 | Calcolo + display + tabelle inline |
| Audit trail BMT | `app_mensile.py` (variabile `_yield_audit_rows`) | Aggregato in modo disperso |
| Audit trail emission factors | `app_mensile.py` (variabile `_emission_audit_rows`) | Aggregato in modo disperso |
| Warning/errori GHG | `app_mensile.py` inline con `st.warning/st.error` | Non strutturati in lista |

---

## 3. DOVE SONO CALCOLATI I KPI OGGI

```
app_mensile.py (corpo principale, non in funzioni):
  - df_res:             costruito in loop sulle righe input (~riga 4450)
  - annual_t:           {biomassa: tonnellate_anno} (~riga 4450)
  - annual_mwh:         {biomassa: mwh_anno} (~riga 4450)
  - tot_biomasse_t:     df_res["Totale biomasse (t)"].sum() (~riga 5430)
  - tot_sm3_netti:      df_res["Sm³ netti"].sum() (~riga 5430)
  - tot_mwh:            sum(annual_mwh.values()) (~riga 4900)
  - saving_avg:         df_res["Saving %"].mean() (~riga 5430)
  - valid_months:       df_res["Validità"].str.startswith("✅").sum() (~riga 5430)
  - tot_revenue:        calcolato inline (~riga 4900)
  - tot_n_cic:          accumulato in loop (~riga 4662)
  - tariffa_media_pon.: calcolata inline
  - pdf_revenue_rows:   accumulato in loop (~riga 4699)
```

---

## 4. DUPLICAZIONI IDENTIFICATE

| Logica duplicata | Occorrenze |
|---|---|
| Formattazione italiana `_fmt_it` / `fmt_it` | `app_mensile.py` + `report_pdf.py` (copia locale) |
| Struttura contesto export | `_xlsx_ctx` e `_pdf_ctx` condividono ~70% delle chiavi ma sono costruiti separatamente |
| Calcolo tariffa equivalente media | Ripetuto in xlsx context builder e inline |
| Design tokens (NAVY, AMBER, SLATE_*) | `app_mensile.py` + `excel_export.py` + `report_pdf.py` |
| `ghg_summary()` chiamata per ogni riga tabella | Potenziale overhead se i mesi sono molti |

---

## 5. FUNZIONI DA ESTRARRE IN `core/calculation_engine.py`

Le seguenti funzioni esistono gia' in `app_mensile.py` e vanno **spostate** (non riscritte):

- `compute_business_plan(...)` — righe 425–640
- `compute_aux_factor(...)` — righe 740–830
- `ghg_summary(...)` — righe 1245–1283
- `solve_1_unknown_production(...)` — righe 1284–1300
- `solve_2_unknowns_dual(...)` — righe 1301–1367
- `find_optimal_pair(...)` — righe 1368–1456
- `e_total_feedstock(...)` — righe 1223–1244
- `_emission_factors_of(...)` — righe 1198–1222
- `_yield_of(...)` — righe 1149–1175
- `_feeds_by_category()` — righe 1125–1133
- `fmt_it(...)` — righe 166–179
- `parse_it(...)` — righe 181–220
- Costanti: `FEEDSTOCK_DB`, `FEED_NAMES`, `FEEDSTOCK_CATEGORIES`, `MONTHS`, `MONTH_HOURS`, `LHV_BIOMETHANE`, `NM3_TO_MWH`, `COMPARATOR_BY_END_USE`, `END_USE_THRESHOLDS`, `EP_*`, `METHANE_SLIP`, `HEAT_DEMAND_UPGRADING`, `ELEC_DEMAND_UPGRADING`, ecc.

**Strategia:** In questa iterazione, le funzioni rimangono in `app_mensile.py` per non rompere nulla. `core/calculation_engine.py` le **importa e ri-espone** (proxy pattern), permettendo ai test e ai nuovi moduli di puntare a `core/`.

---

## 6. FILE RISCHIOSI

| File | Rischio | Note |
|---|---|---|
| `app_mensile.py` | ALTO | 5596 righe, monolitico, ogni modifica puo' rompere la UI |
| `excel_export.py` | MEDIO | 2072 righe, dipende da ~80 variabili del ctx; il ctx e' costruito inline in app |
| `report_pdf.py` | MEDIO | 1673 righe, dipende da ctx simile ma non identico |
| `bmt_override.py` | BASSO | 276 righe, API stabile |
| `emission_factors_override.py` | BASSO | 538 righe, API stabile |

---

## 7. PIANO DI INTERVENTO MINIMO (questa iterazione)

### Fase 1 — Scaffolding modulare (questa PR)
1. Crea `core/__init__.py`, `output/__init__.py`, `export/__init__.py`
2. Crea `core/calculation_engine.py` — proxy che importa da `app_mensile` senza duplicare
3. Crea `core/validators.py` — funzioni di validazione input pulite
4. Crea `output/output_builder.py` — `build_output_model(ctx)` -> dict strutturato
5. Crea `output/tables.py` — funzioni per costruire le tabelle dal output_model
6. Crea `output/explanations.py` — testi spiegativi origine dati
7. Crea `export/csv_export.py` — `build_csv_from_output(output_model)`
8. Crea `export/excel_export.py` — `build_excel_from_output(output_model)` wrapping esistente
9. Crea `export/pdf_export.py` — `build_pdf_from_output(output_model)` wrapping esistente
10. Crea `tests/test_output_model.py` e `tests/test_exports.py`

### Fase 2 — Migrazione progressiva (futura PR)
- Spostare le funzioni di calcolo da `app_mensile.py` a `core/calculation_engine.py`
- Aggiornare `app_mensile.py` per usare `build_output_model()` prima degli export
- Eliminare la duplicazione `_xlsx_ctx` / `_pdf_ctx`

### Cosa NON viene fatto in questa PR
- NON si modifica la logica di calcolo
- NON si tocca la parte input/sidebar di `app_mensile.py`
- NON si spostano le funzioni dal monolite (solo proxy/wrapper)
- NON si duplicano formule o dati normativi

---

## 8. OUTPUT_MODEL — struttura target

Il dict `output_model` prodotto da `build_output_model(ctx)` sara' l'**unica fonte** per tutti gli export (CSV, Excel, PDF) e le spiegazioni. La struttura e' documentata in `output/output_builder.py`.

```
app_mensile.py
    |
    v (ctx dict)
output/output_builder.py::build_output_model(ctx)
    |
    v (output_model dict)
output/tables.py          -> DataFrame pronti per la UI e gli export
output/explanations.py    -> testi spiegativi origine dati
export/csv_export.py      -> CSV download
export/excel_export.py    -> XLSX (wrapping excel_export.py esistente)
export/pdf_export.py      -> PDF (wrapping report_pdf.py esistente)
```
