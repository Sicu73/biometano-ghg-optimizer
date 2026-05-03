# CHANGELOG — Metan.iQ

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
