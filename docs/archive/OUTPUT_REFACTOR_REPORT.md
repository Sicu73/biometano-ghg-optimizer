# OUTPUT_REFACTOR_REPORT.md
## Metan.iQ — Report finale refactoring output

**Data:** 2026-05-03
**Branch:** `refactor/output-simplification`
**Repo:** `Sicu73/biometano-ghg-optimizer`
**Esecutore:** Claude Sonnet 4.6 (Opus 4.7 reprise)

---

## 1. Obiettivo

Separare in modo netto la parte di **output** (dashboard, tabelle,
grafici, CSV, Excel, PDF, audit, spiegazioni) dal monolite
`app_mensile.py` (5596 righe), introducendo un **`output_model` unico**
da cui tutti gli export leggono. La parte **input** (sidebar Streamlit,
data_editor mensile, BMT/EF override) e' rimasta invariata.

## 2. File creati

| Path | Righe | Descrizione |
|---|---:|---|
| `OUTPUT_REFACTOR_MAP.md` | 150 | Mappa pre-refactoring |
| `OUTPUT_REFACTOR_REPORT.md` | this | Report finale |
| `core/__init__.py` | 27 | Package init core |
| `core/calculation_engine.py` | 262 | Proxy a funzioni calcolo + fallback |
| `core/validators.py` | 243 | Validatori input/feedstock/monthly/GHG |
| `output/__init__.py` | 24 | Package init output |
| `output/output_builder.py` | 453 | `build_output_model(ctx) -> dict` |
| `output/tables.py` | 176 | Tabelle DataFrame da output_model |
| `output/explanations.py` | 217 | Testi spiegativi IT/EN |
| `export/__init__.py` | 16 | Package init export |
| `export/csv_export.py` | 207 | `build_csv_from_output(model, sheet)` |
| `export/excel_export.py` | 250 | Adapter `build_excel_from_output` |
| `export/pdf_export.py` | 362 | Adapter `build_pdf_from_output` |
| `tests/test_output_model.py` | 403 | 26 test per output_model |
| `tests/test_exports.py` | 338 | 21 test per CSV/XLSX/PDF export |

## 3. File modificati

| File | Tipo modifica |
|---|---|
| `CHANGELOG.md` | Sezione nuova `[unreleased] — refactor/output-simplification` in cima |

## 4. File NON modificati (vincolo rispettato)

- `app_mensile.py` — invariato (parte input + logica monolite)
- `excel_export.py` (root) — invariato (legacy XLSX builder)
- `report_pdf.py` — invariato (legacy PDF builder)
- `report_pdf_en.py` — invariato
- `bmt_override.py` — invariato
- `emission_factors_override.py` — invariato
- `app.py` — invariato

## 5. Cosa e' stato semplificato

1. **Unico schema dati di output**: `output_model` dict con 11 chiavi
   top-level (`metadata`, `input_summary`, `calculation_summary`,
   `monthly_table`, `feedstock_table`, `ghg_table`,
   `business_plan_table`, `audit_trail`, `warnings`, `errors`,
   `explanations`).
2. **Export uniformi**: CSV, XLSX, PDF accettano lo **stesso**
   `output_model` come input. Nessun ricalcolo nei generatori.
3. **Spiegazioni centralizzate**: tutti i testi normativi/metodologici
   (RED III, DM 2022, DM 2018, FER 2, UNI/TS 11567:2024, JEC v5)
   sono in `output/explanations.py`, IT + EN.
4. **Validatori puri**: 4 funzioni `validate_*` senza side effect
   (no Streamlit, no state mutation), testabili in isolamento.
5. **Fallback graceful**: ogni adapter ha un fallback minimale se la
   libreria/legacy non e' disponibile (openpyxl/reportlab).

## 6. Cosa e' rimasto monolitico (per scelta - vincolo "non rompere")

- `app_mensile.py` continua a contenere:
  - Tutte le funzioni di calcolo (`compute_business_plan`, `ghg_summary`,
    `solve_*`, `find_optimal_pair`, `compute_aux_factor`, ...).
  - Tutta la UI Streamlit (sidebar, data_editor, expander).
  - I builder dei ctx legacy `_xlsx_ctx` e `_pdf_ctx` (~400 righe).
- `excel_export.py` (2072 righe) e `report_pdf.py` (1673 righe) restano
  monolitici. Sono raggiunti tramite gli adapter `export/*.py`.
- `app_mensile.py` **non e' stato cablato** ai nuovi moduli: la chiamata
  a `build_output_model(ctx)` prima degli export e' lasciata alla
  prossima PR (Fase 2 in `OUTPUT_REFACTOR_MAP.md`).

## 7. Test eseguiti

```
python -m py_compile core/calculation_engine.py core/validators.py core/__init__.py \
                     output/output_builder.py output/tables.py output/explanations.py output/__init__.py \
                     export/csv_export.py export/excel_export.py export/pdf_export.py export/__init__.py
=> Exit 0 (tutti i moduli compilano puliti)

python -m py_compile app_mensile.py excel_export.py report_pdf.py
=> Exit 0 (legacy invariato)

python -m pytest -q
=> 174 passed in 2.36s
   - 26 test_output_model.py (struttura, KPI, tabelle, audit, warnings, explanations)
   - 21 test_exports.py (CSV per 5 sheet, XLSX magic bytes, PDF magic bytes,
     ValueError input invalido, fallback ctx vuoto)
   - 65 test_emission_factors_override.py (PRE-ESISTENTI, ancora verdi)
   - 62 test_bmt_override.py (PRE-ESISTENTI, ancora verdi)
```

## 8. Test falliti

**Nessuno.** 174/174 verdi.

## 9. Limiti residui / non fatto

1. **`app_mensile.py` non e' ancora stato cablato a `build_output_model`**:
   gli export attuali continuano a usare il path legacy. Questa PR
   crea l'infrastruttura; la Fase 2 (PR successiva) sostituira' i
   call site. Beneficio: rischio di regressione zero su questa PR.
2. **Il ctx ricostruito dall'adapter e' parziale**: alcuni dettagli
   BP avanzati (capex_breakdown, opex_breakdown, finance) usano
   defaults nel fallback adapter. Sufficiente per snapshot e fallback,
   ma il path legacy rimane piu' ricco quando chiamato direttamente
   da `app_mensile.py` con il ctx completo.
3. **Nessun test E2E con Streamlit live**: `streamlit run app_mensile.py`
   non e' stato eseguito in CI (richiede browser). I test pytest
   coprono solo la pipeline pura.
4. **Le funzioni di calcolo NON sono state spostate fisicamente**
   in `core/calculation_engine.py`. Il modulo le importa via proxy
   da `app_mensile`. Vantaggio: zero rischio. Svantaggio: la
   migrazione fisica deve avvenire in una PR successiva.

## 10. Prossimi step (Fase 2 — PR futura)

1. In `app_mensile.py`, dopo che `df_res` e tutti i KPI sono
   calcolati, costruire un dict `ctx` e chiamare:
   ```python
   from output import build_output_model
   from export import build_csv_from_output, build_excel_from_output, build_pdf_from_output
   output_model = build_output_model(ctx)
   ```
2. Sostituire i `st.download_button` per CSV/XLSX/PDF con chiamate
   ai nuovi adapter, mantenendo i pulsanti e i nomi file invariati.
3. Eliminare i builder inline `_xlsx_ctx` e `_pdf_ctx` (~400 righe).
4. Eventualmente spostare le funzioni di calcolo da `app_mensile.py`
   a `core/calculation_engine.py` e aggiornare gli import.
5. Aggiungere snapshot test che confrontano XLSX/PDF generati via
   nuovo path con quelli del path legacy (regressione binaria).

## 11. Risultato

L'architettura target e' in posto:

```
input Streamlit → contesto dati → motore calcolo → output_model unico → CSV/XLSX/PDF/dashboard
                                                          ↑
                                                    centralizzato qui
```

L'app esistente continua a funzionare invariata. Le prossime modifiche
agli output (nuovi report, nuove colonne, nuovi sheet, ridisegno PDF)
non richiederanno piu' di toccare `app_mensile.py`: bastera' modificare
`output_builder.py` e/o gli adapter `export/*.py`.
