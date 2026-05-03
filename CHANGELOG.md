# CHANGELOG — Metan.iQ

## [unreleased] — branch `refactor/output-simplification`

### Added
- **Architettura output centralizzata**: nuovi pacchetti `core/`, `output/`, `export/`.
  - `core/calculation_engine.py` — proxy che ri-espone le funzioni di calcolo
    di `app_mensile.py` (compute_business_plan, ghg_summary, solve_*,
    find_optimal_pair, e_total_feedstock, fmt_it, parse_it, ecc.) senza
    duplicare logica. Include fallback minimali per test isolati.
  - `core/validators.py` — funzioni `validate_plant_config`,
    `validate_feedstock_selection`, `validate_monthly_input`,
    `validate_ghg_results` con firma standard `(is_valid, errors, warnings)`.
  - `output/output_builder.py` — `build_output_model(ctx) -> dict` produce
    l'output_model unificato con chiavi: metadata, input_summary,
    calculation_summary, monthly_table, feedstock_table, ghg_table,
    business_plan_table, audit_trail, warnings, errors, explanations.
  - `output/tables.py` — `build_monthly_table`, `build_feedstock_table`,
    `build_ghg_table`, `build_business_plan_table`, `build_audit_table`
    restituiscono pd.DataFrame (o list[dict] se pandas non disponibile).
  - `output/explanations.py` — testi spiegativi IT/EN per `yield_origin`,
    `emission_factor_origin`, `ghg_method`, `regulatory_basis`.
  - `export/csv_export.py` — `build_csv_from_output(model, sheet)` per
    sheet "monthly" / "feedstock" / "ghg" / "business_plan" / "audit",
    formato italiano (separatore ';', decimale ',', UTF-8 BOM).
  - `export/excel_export.py` — `build_excel_from_output(model, snapshot)`
    adapter che ricostruisce il ctx legacy e chiama
    `excel_export.build_metaniq_xlsx`. Fallback openpyxl se legacy non
    disponibile.
  - `export/pdf_export.py` — `build_pdf_from_output(model)` adapter che
    ricostruisce il ctx legacy e chiama `report_pdf.build_metaniq_pdf`.
    Fallback reportlab se legacy non disponibile.
- **Documentazione**: `OUTPUT_REFACTOR_MAP.md` (mappa input/output
  attuali, KPI, duplicazioni, piano interventi) e
  `OUTPUT_REFACTOR_REPORT.md` (report finale).
- **47 nuovi test pytest** in `tests/test_output_model.py` e
  `tests/test_exports.py` che coprono: struttura output_model, KPI,
  tabelle, audit trail, warnings/errors, explanations IT/EN,
  CSV per tutti gli sheet, XLSX magic bytes (PK), PDF magic bytes (%PDF),
  fallback su ctx vuoto, ValueError su input invalido.

### Changed
- Nessuna modifica a `app_mensile.py`, `excel_export.py`, `report_pdf.py`,
  `bmt_override.py`, `emission_factors_override.py`. La parte input
  Streamlit e la logica di calcolo rimangono **invariate**.

### Architecture
- Tutti gli export (CSV, XLSX, PDF) leggono **dallo stesso `output_model`**.
- Nessuna formula duplicata: gli adapter trasformano l'output_model nel
  ctx legacy senza ricalcolare nulla.
- Strategia "proxy + adapter" per minimizzare il rischio di regressione.

---

## [unreleased] — branch `feature/real-emission-factors`

### Added
- **Override fattori emissivi reali da relazione tecnica** (per biomassa).
  - Nuovo modulo `emission_factors_override.py` con dataclass
    `EmissionFactorReport`, funzioni `validate_real_emission_factor_override`,
    `resolve_emission_factors`, `build_emission_factor_audit_row`,
    `calculate_emission_total`.
  - Sezione UI Streamlit "🧬 Fattori emissivi reali da relazione tecnica"
    nella sidebar, con file uploader (PDF/DOCX/XLSX/CSV/JPG/PNG),
    input per `eec_real`, `esca_real`, `etd_real`, `ep_real`,
    `crediti_extra`, e tutti i metadati relazione (titolo, autore,
    società, data, impianto, riferimento campione, note metodologiche).
  - Validazione live con errori bloccanti + warning ±30%.
  - Tabella audit "🧬 Audit fattori emissivi" nel corpo principale
    dell'app, dopo il database feedstock.
  - 5° foglio Excel "Audit fattori emissivi" con colonna scostamento %.
  - Sezione PDF `// EMISSION FACTORS AUDIT` con tabella riassuntiva
    + dettaglio metadati per biomasse con override attivo.
- 65 test pytest in `tests/test_emission_factors_override.py` che
  coprono i 10 requisiti della specifica.

### Changed
- `e_total_feedstock(name, ep)` ora consulta `_EMISSION_OVERRIDES`
  prima di usare `FEEDSTOCK_DB[name]`. La firma è invariata, retro-
  compatibile per tutti i call site esistenti (`ghg_summary`,
  `solve_*`, `lp_optimize`).
- Database feedstock display nel corpo principale ora mostra i
  fattori EFFETTIVI usati (override real se attivo, altrimenti
  standard) e una colonna "Origine fattori".
- Caption della formula RED III aggiornata: ora dichiara esplicitamente
  `e_total = eec + etd + ep − esca − crediti_extra` (no double-counting).

### Convention
- `e_total = eec + etd + ep − esca − crediti_extra`.
  - `esca` è un credito SOTTRATTO una sola volta dalla formula.
  - `crediti_extra` sono crediti AGGIUNTIVI dichiarati esplicitamente
    nella relazione tecnica, NON già inclusi in `esca`. Default 0.
  - Manure credit è incorporato in `eec` (negativo).

---

## [previous] — `master`

### Fixed
- `parse_it("0.800")` → 0.8 (era 800.0). Aggiunto guard
  `parts[0].lstrip("-") != "0"` per il caso "decimale con
  parte intera nulla".
- `metaniq_numeric.parse_it("1234.56")` → 1234.56 (era 123456.0).
  Portata l'euristica intelligente da `app_mensile.py`.
- `ghg_summary()` accetta ora `fossil_comparator` come parametro
  esplicito (race-condition fix per multi-utente Streamlit).
- `normativa_versions.json`: URL placeholder sostituiti per
  `dlgs_5_2026`, `dm_fer2_2024`, `gse_lg_biometano_2024`.

### Added
- Bilingual IT/EN selector in sidebar (`render_lang_selector`)
  con traduzioni in CSV, Excel, PDF.
- Audit completo del repository Metan.iQ contro RED III, DM 2018/2022/
  2012, FER 2, GSE LG 2024, UNI/TS 11567:2024, JEC WTT v5,
  IPCC 2019.
