# CHANGELOG — Metan.iQ

## [unreleased] — audit/gross-net-sustainability

### Audit base LORDO vs NETTO per controllo sostenibilità GHG

- **Diagnosi**: il motore `core.calculation_engine.ghg_summary` calcola già
  correttamente saving% e e_w come **intensità gCO₂eq/MJ sull'energia
  LORDA** (Sm³ lordi · LHV). Vincoli sostenibilità (RED III, DM 2022,
  DM 2018, DM 2012/CHP, DM 2024/FER 2) restano sul **LORDO**. Nessuna
  formula corretta è stata cambiata.
- **Esposizione esplicita**: aggiunti campi `tot_sm3_lordi`,
  `tot_mwh_lordi`, `sustainability_basis`, `sustainability_basis_note`,
  `biomethane_dual_view` in `output/output_builder.calculation_summary`.
- **Doppia vista biometano**: per regimi DM 2018 / DM 2022 i report
  mostrano **LORDO + NETTO** (NETTO = LORDO/aux_factor è l'effettiva
  immissione in rete). La base normativa resta esplicitamente sul LORDO.
- **MonthlyAggregate**: nuovi campi `mwh_gross`, `saving_pct_net`,
  `sustainability_basis = "LORDO"` con docstring che esplicita la
  semantica e la base usata.
- **Spiegazioni** (`output/explanations.py`): nuova funzione
  `explain_sustainability_basis(ctx)` (IT/EN) che dichiara LORDO come
  base e cita RED III, DM 15/9/2022, DM 2/3/2018, DM 6/7/2012, DM 18/9/2024.
  `explain_ghg_method` aggiornato con sezione `BASE SOSTENIBILITA': LORDO`.
- **Tabelle** (`output/tables.py`): nuova
  `build_sustainability_basis_table(om)` con righe Sm³/MWh/Saving e
  colonna esplicita `Base normativa applicata`.
- **Export**:
  - `export/csv_export.py` — metadata mensile + `_empty_csv` espongono
    Sm³/MWh LORDI/NETTI, base, nota.
  - `export/excel_export.py` — sheet `Riepilogo` con righe LORDO/NETTO
    + Base sostenibilità + flag vista NETTO biometano.
  - `export/pdf_export.py` — KPI box con doppia riga LORDO/NETTO
    (Sm³ + MWh) + Base sostenibilità.
- **Test**: `tests/test_gross_net_sustainability.py` (8 test):
  invarianza saving su aux_factor, dual view biometano, no dual view per
  CHP, presenza LORDO+NETTO in CSV, tabella basis, spiegazione dichiara
  LORDO+RED III, MonthlyAggregate field check, monthly_kpis include base.
- **Doc**: `AUDIT_GROSS_NET.md` con mappatura completa calcoli, regimi,
  base usata, esempi I/O, raccomandazioni.

Backward compat 100%: nessuna firma rotta, le nuove key sono additive,
fallback `getattr(..., default)` ovunque rilevante. 247/247 test verdi.

## [precedente] — branch `feature/daily-ops-monthly-sustainability`

### Added — Gestione giornaliera + verifica sostenibilità mensile
- **Nuovi moduli core/**:
  - `core/calendar.py` — `generate_month_days`, `month_label`, `is_leap_year`,
    `days_in_month` (gestione bisestile gregoriana).
  - `core/daily_model.py` — dataclass `DailyEntry` (input giornaliero) e
    `DailyComputed` (risultati derivati); `compute_daily(entry, ctx)` che
    riusa `ghg_summary` dal motore esistente per non duplicare formule.
  - `core/monthly_aggregate.py` — `MonthlyAggregate`, `aggregate_month`
    e `progressive_to_date`. La saving% mensile è ricalcolata
    sull'AGGREGATO (regola di compliance: la sostenibilità è mensile).
  - `core/sustainability.py` — `evaluate_monthly_sustainability` con
    vincoli regime (cap colture dedicate, FER2 sottoprodotti, CIC
    Annex IX, cap autorizzativo Sm³/h, cap MWh/anno).
  - `core/persistence.py` — SQLite locale (`data/metaniq_daily.db`)
    con `init_db`, `save_month`, `load_month`, `list_saved_months`,
    `delete_month`. Schema: `daily_entries`, `month_meta`.
- **Nuovi moduli output/**:
  - `output/daily_table_view.py` — `build_daily_dataframe` con cumulati
    mese (Sm³, MWh, t) e cap_ok per giorno.
  - `output/monthly_kpis.py` — `build_monthly_kpis` (esito ufficiale,
    saving, soglia, margine, vincoli).
  - `output/guidance.py` — `compute_end_of_month_guidance` con
    suggerimenti operativi italiani per chiudere il mese sostenibile.
- **Nuovi moduli export/**:
  - `export/daily_csv.py` — CSV giornaliero (sep `;`, decimale `,`).
  - `export/daily_excel.py` — XLSX 4 fogli (Giornaliero / Mensile KPI /
    Vincoli / Audit Trail).
  - `export/daily_pdf.py` — PDF report (KPI, vincoli, guidance, audit,
    tabella giornaliera) con fallback testuale se ReportLab manca.
- **Validazione**: `core.validators.validate_daily_entry` (rifiuta
  quantità negative, valida date, segnala tipologie sconosciute).
- **UI Streamlit**: nuova sezione "📅 Gestione Giornaliera" in fondo a
  `app_mensile.py` con selettore mese/anno, tabella editabile per
  giorno, KPI mensili in evidenza, badge Compliant/Non Compliant,
  vincoli regime, audit trail mese, salvataggio SQLite, download
  CSV/Excel/PDF.
- **Test**: 18 nuovi test `tests/test_daily_ops.py` (192 totali).
- **DAILY_OPS_GUIDE.md**: guida operativa utente, esempio mese,
  spiegazione regola compliance mensile vs giornaliero.
- **.gitignore**: esclusione `data/*.db` (DB locale non versionato).

### Compliance rule
- La sostenibilità è valutata sul **totale mese aggregato**.
- Singoli giorni "non sostenibili" sono ammessi se il totale mese
  rispetta la soglia (test `test_sustainability_isolated_bad_day_but_month_ok`).

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
