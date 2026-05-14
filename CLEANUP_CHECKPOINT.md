# Cleanup `remove-legacy-modes` — checkpoint sessione 1

**Data**: 2026-05-14
**Branch**: `cleanup/remove-legacy-modes` (rolling back point: tag `pre-cleanup-legacy-modes` su `c9408d3`)
**Stato**: ~50% completato — `app_mensile.py` parsa pulito ad ogni commit; ~40 ref `IS_*` ancora da rimuovere; support files non ancora toccati.

## Piano originale ("Opzione A — pulizia totale", approvato)

L'app è mono-mode dal commit `c9408d3` (flag `IS_CHP`/`IS_FER2`/`IS_DM2018` hardcoded `False`, `IS_DM2022` `True` in `app_mensile.py:1465-1469`). Pre-flight check ha confermato **nessun override** env/secrets/query-param/sidebar sui flag, quindi tutti i rami `if IS_FALSE_FLAG:` sono **dead code** rimovibile.

KPI di successo:
- `app_mensile.py` scende di ~1000 righe
- Nessuna stringa UI cita DM2018/CHP/FER2
- PDF/Excel senza label legacy
- `ripgrep "IS_DM2018|IS_CHP|IS_FER2"` torna **vuoto** su tutto il repo

## Commit fatti (10)

| # | SHA | Descrizione | Δ righe |
|---|-----|-------------|---------|
| 1  | `1790952` | UI: `page_title` solo DM 2022 (RED III) | +1 −1 |
| 2A | `fccb33c` | Top-of-file: dummy const + sezioni CHP/DM2018/FER2 + dict `DM2018_END_USES` | +2 −98 |
| 2B | `70b7c2a` | `_MODE_META` ridotto a singolo dict piatto `_MODE` | +9 −47 |
| 2C | `80f9ed9` | Sidebar Taglia Impianto + Config Tecnica (rimossi `if IS_CHP`) | +155 −235 |
| 2D | `fd50d64` | Blocco aggregazione DB (drop `IS_DM2018`/`IS_FER2`/`IS_CHP`) | +16 −51 |
| 2E | `2b88fbe` | Tab BP: rimosse sezioni DM 2018 CIC + FER 2 + collapse `if IS_DM2022` | +217 −435 |
| 2F | `eccc8d9` | Breakdown ep + bilancio energetico (no `IS_CHP`) | +28 −33 |
| 2G | `d063496` | Bulk ternary collapse single-line (regex line-by-line) | +20 −31 |
| 2H | `0a0e310` | `_om_ctx`/`_xlsx_ctx`: drop chiavi `IS_*`/`plant_kwe`/`eta_el` | +2 −20 |
| 2I | `25b62ce` | Grafici tab + BP tab5: collapse `if IS_DM2022` | +9 −19 |

**Totale**: −511 righe nette in `app_mensile.py` (da ~6030 a ~5500).

Ad ogni commit eseguito `py -c "import ast; ast.parse(open('app_mensile.py').read())"` → **PARSE OK** sempre.

## Stub transitori introdotti (da rimuovere)

In `app_mensile.py` dopo la sezione "Taglia Impianto" della sidebar (intorno a riga 1900), commit `80f9ed9` ha aggiunto:

```python
# Stub transitori per variabili "elettriche" legacy CHP: sono ancora
# referenziate in dict ctx passati a PDF/Excel/output_builder. Verranno
# rimosse del tutto quando saranno eliminati anche i consumer downstream.
eta_el        = 0.40
eta_th        = 0.42
aux_el_pct    = 0.0
plant_kwe     = plant_net_smch * eta_el * 9.97
plant_kwe_net = plant_kwe
```

Da eliminare quando tutti i consumer downstream (ctx readers in `output/`, `report_pdf.py`, `excel_export.py`) sono puliti.

## Lavoro residuo

### 1. Completare `app_mensile.py` (~3-5 commit ancora)

`grep -n "IS_CHP\|IS_FER2\|IS_DM2018\|IS_DM2022\|IS_CHP_DM2012" app_mensile.py` → ~50 hit, concentrati in:

- **Lines 3400-3600**: TextColumn config + tabelle Risultati & Export con ternari multi-line `... if IS_CHP else ...` (TextColumn help, label colonne)
- **Lines 3700-4150**: sezione CIC display + revenue loops con cascate `if IS_FER2 / elif IS_CHP / elif IS_DM2018 and cic_active / elif IS_DM2018 and not cic_active / else`
- **Lines 4332-4364**: BP tariffa cascading `if IS_FER2 / elif IS_CHP_DM2012 / elif IS_DM2018 / else` → tieni solo il ramo `else` (DM 2022)
- **Lines 4380, 4401**: ternari multi-line `IS_DM2022` (multi-line, regex single-line non li ha collassati)
- **Lines 4450-4506**: secondo dict ctx (PPTX export?) con chiavi `IS_*`/`fer2_*` da pulire
- **Lines 4512, 4515**: ternari multi-line `if IS_CHP and "MWh elettrici lordi" in df_res else 0.0`
- **Lines 1370-1374**: dichiarazioni `IS_CHP_DM2012 = False / IS_FER2 = False / IS_CHP = False / IS_DM2018 = False / IS_DM2022 = True` — **rimuovere PER ULTIME** (quando 0 ref).

### 2. Commit 3 — Support files

Comando di triage: `grep -rln "IS_CHP\|IS_FER2\|IS_DM2018\|FER2_KWE_CAP\|MWH_PER_CIC\|DM2018_END_USES" --include='*.py' --include='*.json'`

Aree da pulire:

- `core/calculation_engine.py:295-305` — `__all__` esporta nomi legacy (`MWH_PER_CIC`, `FER2_KWE_CAP`, ecc.) che non esistono come valori — entries fantasma, rimuovere dalla lista.
- `core/monthly_aggregate.py:220-223` — `if ctx.get("IS_CHP"):` branch che legge `eta_el`/`eta_th`/`aux_el_pct` → rimuovere
- `core/validators.py:71-119` — blocchi `if app_mode in ("biogas_chp", "biogas_chp_fer2"):` → rimuovere
- `output/explanations.py:217-244` — rami `if app_mode in ("biogas_chp", "biogas_chp_fer2"):` e `if is_chp` → rimuovere
- `output/output_builder.py:79-318` — legge `IS_CHP`/`IS_FER2`/`IS_DM2018` da ctx, label legacy → rimuovere
- `report_pdf.py:291-1641` — 25+ rami `if ctx["IS_CHP"]:` / `elif ctx.get("IS_FER2"):` / `elif ctx.get("IS_DM2018") and ctx.get("cic_active"):` → grossa pulizia
- `excel_export.py` (root) + `export/excel_export.py` + `export/pdf_export.py` — chiavi ctx + rami modali
- `metaniq_i18n.py` — rimuovere chiavi i18n con stringhe DM 2018/FER 2/CHP
- `normativa_versions.json` — rimuovere entries `GCAL_PER_CIC`/`MWH_PER_CIC`/`CIC_PRICE_DEFAULT`/`ANNEX_IX_THRESHOLD`/`FER2_*` (o spostare in `docs/normative_legacy.json` se servisse come catalogo storico)
- `tests/test_exports.py:69, 291` — test che setta `app_mode = "biogas_chp"` → rimuovere o snapshot legacy
- `tests/test_gross_net_sustainability.py:57-110, 183-203` — esercita `IS_CHP=True` → ridurre a soli test DM 2022
- `tests/test_output_model.py:65-76` — fixture con `IS_CHP=False, IS_FER2=False, ...` → rimuovere chiavi morte

### 3. Commit 4 — Hardening

Aggiungere guardrail esplicito in `app_mensile.py` subito dopo l'inizializzazione `APP_MODE`:

```python
if APP_MODE != "biometano":
    raise RuntimeError(
        f"Mode '{APP_MODE}' non supportato. L'app supporta solo biometano "
        "DM 2022 (RED III). Vedi tag 'pre-cleanup-legacy-modes' per la "
        "versione multi-mode storica."
    )
```

Aggiornare `README.md` / `DAILY_OPS_GUIDE.md` per riflettere il singolo mode.

### 4. Quality gate finale

```bash
pytest                          # tutti i test passano (dopo rimozione test legacy)
# Smoke: avvio Streamlit + generazione PDF + export Excel su dataset campione
grep -rn "IS_DM2018\|IS_CHP\|IS_FER2" --include='*.py'   # deve essere VUOTO
```

## Lezione appresa: regex sul codice è rischiosa

Tentativo di bulk collapse via Python regex (commit 2G) ha rotto 3 punti che ho dovuto fixare a mano:
- f-string con ternario annidato `f"... {'x' if IS_CHP else 'y'}"`
- ternario multi-line con prefisso `help=(`
- ternario multi-line `(text...) if IS_CHP else (other text...)` su 4-5 righe

Per i ternari multi-line residui in `app_mensile.py`, fare **edit chirurgici manuali** o uno script **AST-aware** (più affidabile ma perde commenti).

## Come riprendere

Da Claude Code Desktop, in una sessione fresca:

1. Clone/pull e check del branch:
   ```bash
   git fetch && git checkout cleanup/remove-legacy-modes
   git log --oneline -12   # devono comparire i 10 commit fatti
   ```
2. Leggere questo file
3. `grep -n "IS_CHP\|IS_FER2\|IS_DM2018\|IS_DM2022\|IS_CHP_DM2012" app_mensile.py` → vedere residui
4. Verificare parse:
   ```bash
   py -c "import ast; ast.parse(open('app_mensile.py').read()); print('OK')"
   ```
5. Continuare con sotto-commit chirurgici. Dopo ogni edit, riparsare prima di committare.
6. Quando `app_mensile.py` è pulito al 100%, rimuovere lo stub transitorio (vedi sopra) e le dichiarazioni `IS_*` a riga 1370.
7. Passare ai support files (Commit 3 del piano).
8. Commit 4 (hardening) + quality gate.
9. **Cancellare questo file** prima del merge in `dm2022-only`.
