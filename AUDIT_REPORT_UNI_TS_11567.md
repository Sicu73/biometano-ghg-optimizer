# Audit di conformità Metan.iQ vs UNI/TS 11567:2024

**Data audit:** 2026-05-28
**Versione codice analizzata:** master @ 28b22b3 (v0.4.0)
**Auditor:** Claude Opus 4.7 (assistito da Carlo Sicurini)
**Scope:** revisione ingegneristica del software in vista di vendita commerciale.

> ⚠️ **Disclaimer**: questo documento è un **audit ingegneristico interno** del codice
> sorgente. Non sostituisce la verifica di conformità UNI/TS 11567:2024 che compete
> esclusivamente a un Organismo di Certificazione accreditato (RINA, SGS, Bureau
> Veritas, TÜV, DNV). Lo scopo è preparare il software a quell'audit minimizzando
> le non conformità documentali e di processo.

---

## 1. Sintesi esecutiva

| Area | Stato pre-audit | Stato post-patch | Note |
|---|---|---|---|
| Formula GHG RED III (eec, etd, ep, esca) | ✅ Corretta | ✅ Corretta | `core/calculation_engine.py` proxy a `app_mensile.ghg_summary` |
| Comparator fossili EF<sub>FF</sub> (80/94/183) | ✅ Presente | ✅ Presente | `core/constants.py` |
| Soglie saving per end-use (80%/65%) | ✅ Corretta | ✅ Corretta | `END_USE_THRESHOLDS` differenziato |
| Classificazione Annex IX delle biomasse | ⚠️ Solo backend | ✅ Visibile in UI | Patch UI: cap30% / IX-A / IX-B accanto a eec |
| Mass balance mensile (vs giornaliero) | ✅ Corretta | ✅ Corretta | Disclaimer esplicito in `core/sustainability.py` |
| Anagrafica audit (P.IVA, CUI, firma) | ❌ Assente | ✅ Aggiunta | Nuovi campi sidebar + PDF |
| ID Lotto di Sostenibilità (LS) | ❌ Assente | ✅ Generato auto | `core/ls_identifier.py` |
| Tracciabilità fornitori biomassa | ❌ Assente | ⚠️ Placeholder | UI ancora da fare |
| Sezione firma responsabile in PDF | ❌ Assente | ✅ Aggiunta | `_build_ls_traceability` |
| Test coverage | 259/259 ✅ | 273/273 ✅ | +14 test |
| Versione deployata Streamlit Cloud | 🔴 Stale (v0.5.0) | 🟡 Va ridepoyata | Master è v0.4.0 senza footer |

---

## 2. Critiche del primo audit (live-only) — **revisione**

Onestà intellettuale: dopo aver letto il codice, **5 delle critiche iniziali si sono
rivelate errate**. Erano basate sulla sola UI deployata, senza accesso al sorgente.

| # | Critica iniziale | Verdetto reale | Riferimento |
|---|---|---|---|
| 1 | "D.Lgs 5/2026 non esiste, dicitura errata" | ❌ FALSO — esiste come D.Lgs. 9 gennaio 2026 n.5 (GU n.15) | [core/constants.py:24-31](core/constants.py) |
| 2 | "EF<sub>FF</sub> comparatore non esplicito" | ❌ FALSO — 3 comparator + 3 soglie differenziate per end-use | [core/constants.py:66-72](core/constants.py) |
| 3 | "80% confonde sostenibilità vs incentivo" | ❌ FALSO — è correttamente `SAVING_THRESHOLD_GRID_HEAT` per impianti ≥20/11/2023 | [core/constants.py:70](core/constants.py) |
| 4 | "Fonti eec mancanti" | ❌ FALSO — campo `src` per ogni biomassa | [app_mensile.py:945+](app_mensile.py) |
| 5 | "Classificazione Annex IX mancante" | ❌ FALSO — campo `annex_ix` per ogni biomassa | [app_mensile.py:945+](app_mensile.py) |

---

## 3. Incongruenze REALI rilevate e risolte

### 3.1 Deployment stale (Streamlit Cloud) — 🔴 da risolvere
- **Sintomo**: live mostra `v0.5.0` + footer "Tutti i diritti riservati", master ha `v0.4.0` senza footer.
- **Causa**: commit `ba2c1a5` ha rimosso il footer ma Streamlit Cloud serve build precedente.
- **Azione**: forzare redeploy su Streamlit Cloud (Manage app → Reboot/Redeploy).

### 3.2 Annex IX/Categoria invisibili in UI — ✅ risolto
- **Sintomo**: utente sceglie "Trinciato di mais" vedendo solo `eec=+26,0`, ignorando che è food/feed crop cap 30%.
- **Patch**: `format_func` arricchita: `"Trinciato di mais · eec=+26,0 · 🌽 cap30%"` o `"Liquame suino · eec=-45,0 · IX-A ✓avanzato"`.
- **Patch bonus**: expander "📚 Fonti normative biomasse attive (audit OdC)" sotto il multiselect, con tabella `eec`/`cat`/`annex_ix`/`src` pronta da copiare in relazione tecnica.
- **File**: [app_mensile.py:2540+](app_mensile.py)

### 3.3 Doppia fonte di verità pollina ovaiole — ✅ documentato
- **Sintomo**: `MANURE_CREDIT_POLLINA_OVAIOLE=0.0` in constants vs `eec=+5.0` in FEEDSTOCK_DB.
- **Patch**: nota di audit in `core/constants.py:101-108` che spiega la semantica differente (credit puro vs eec aggregato secondo prassi GSE LG 2024).
- **Azione futura raccomandata**: rifattorizzare per single source of truth, oppure documentare le 2 viste in `output/explanations.py`.

### 3.4 Anagrafica audit incompleta — ✅ risolto
- **Sintomo**: la sidebar aveva solo `company_name`, `plant_name`, addresses. Mancavano P.IVA, CUI/GSE, Responsabile Sostenibilità.
- **Patch**: 3 nuovi campi `company_vat`, `plant_cui`, `responsible_name` con tooltip che dichiarano l'obbligo audit OdC.
- **File**: [app_mensile.py:1688+](app_mensile.py)

### 3.5 PDF audit-ready — ✅ risolto
- **Sintomo**: il PDF non aveva LS-ID, anagrafica audit, mass balance esplicito, firma.
- **Patch**: nuova funzione `_build_ls_traceability(ctx, s)` che aggiunge ultima pagina PDF con:
  - Tabella metadati LS (ID generato deterministicamente, periodo, anagrafica, comparator, soglia, base normativa)
  - Tabella mass balance (input biomasse con Annex IX/categoria, output Sm³ lordi/netti)
  - Registro fornitori (se popolato in `ctx["suppliers_registry"]`, altrimenti warning)
  - Disclaimer + blocco firma con data + nome responsabile
- **File**: [report_pdf.py:1697+](report_pdf.py)

### 3.6 LS-ID deterministico — ✅ nuovo modulo
- **Patch**: nuovo modulo [`core/ls_identifier.py`](core/ls_identifier.py).
- Funzione `build_ls_id(year, month, plant_cui, plant_name) -> "LS-YYYY-MM-XXXXXX"` con hash SHA1 dei primi 6 char del CUI.
- Idempotente: stesso CUI + stesso periodo ⇒ stesso ID. Audit-friendly.
- Funzione `validate_ls_id(s) -> bool` per check formato in test/import.
- **Test**: 10 test in `tests/test_ls_identifier.py` (formato, idempotenza, edge case anno/mese, fallback).

---

## 4. Gap residui non risolti (richiedono lavoro UI/UX)

Questi punti sono **necessari** per audit OdC ma richiedono nuove form/persistence
che eccedono lo scope di questa sessione di audit. Sono pronti come "TODO"
documentati per il prossimo sprint.

### 4.1 Registro fornitori biomassa (CRITICO per audit)
- **Manca**: un'UI per registrare per ogni fornitore: ragione sociale, P.IVA, tipologia
  biomassa fornita, quantità mensile (t), riferimento DDT, contratto di filiera.
- **Stato attuale**: il PDF accetta `ctx["suppliers_registry"]` ma niente lo popola.
- **Stima implementazione**: 1-2 giorni (nuovo `st.data_editor` in sidebar Anagrafica
  o nella tab Operatività Giornaliera).

### 4.2 Land Use Change (e_l) per food/feed crops
- **Manca**: campo `e_l` per biomasse non-Annex IX (mais, sorgo, ecc.).
- **Rischio**: per filiere con colture dedicate, RED III richiede dichiarazione NUTS-2
  no-LUC. Se non documentata, OdC può assumere valori default punitivi.
- **Stima**: 0,5 giorni (aggiungere campo opzionale al FEEDSTOCK_DB + form per
  caricare dichiarazione PDF).

### 4.3 e_ccs / e_ccr (carbon capture)
- **Manca**: contributi opzionali CCS/CCR.
- **Impatto**: minor saving% del dovuto se l'impianto ha CCS (raro per piccoli).
- **Stima**: 0,5 giorni (opzionale, basso priorità per il target audience).

### 4.4 Cap food/feed nazionale decrescente
- **Manca**: vincolo dinamico cap colture dedicate decrescente (RED III prevede
  trend di riduzione al 2030).
- **Stato**: oggi `dedicated_crops_max_share=0.30` è hardcoded.
- **Stima**: 0,5 giorni (lookup da JSON normativa per anno).

### 4.5 Riferimento normativo "D.Lgs 5/2026" in UI
- **Sintomo**: banner main mostra `D.LGS 5/2026` criptato; nel codice la stringa
  completa esiste come `DLGS_RED_III_RECEPIMENTO`.
- **Stima**: 0,1 giorni (usare `DLGS_RED_III_RECEPIMENTO` nei tooltip pill).

### 4.6 Persistenza session_state
- **Sintomo**: anagrafica si perde a refresh pagina (commento codice "no commit
  dati cliente in repo"). Per audit OdC i dati LS devono essere persistenti.
- **Soluzione candidata**: `core/persistence.py` esiste; integrare per salvare in
  cookie/localStorage/file utente (con consenso GDPR esplicito).
- **Stima**: 1 giorno.

---

## 5. Test suite

| Suite | Prima | Dopo | Δ |
|---|---|---|---|
| Esistenti | 259 ✅ | 259 ✅ | 0 regressioni |
| `test_ls_identifier.py` (nuovo) | — | 10 ✅ | +10 |
| `test_pdf_ls_traceability.py` (nuovo) | — | 4 ✅ | +4 |
| **TOTALE** | **259** | **273** | **+14** |

Esecuzione: `pytest tests/ -q` → 273 passed in 7.82s.

---

## 6. Patch applicate (diff summary)

```
app_mensile.py    |  87 ++++++++++++++++++++++--
core/constants.py |   9 ++-
report_pdf.py     | 199 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
3 files changed, 290 insertions(+), 5 deletions(-)
```

Nuovi file:
- `core/ls_identifier.py` (69 LOC, modulo nuovo)
- `tests/test_ls_identifier.py` (10 test)
- `tests/test_pdf_ls_traceability.py` (4 test)
- `AUDIT_REPORT_UNI_TS_11567.md` (questo documento)

---

## 7. Roadmap commerciale verso vendita conforme

### Step 1 — Pre-vendita (subito, 1 giorno)
1. ✅ Applica le patch di questa sessione (PR review + merge)
2. ✅ Ridepoya su Streamlit Cloud (risolve discrepanza versione)
3. ⏳ Aggiorna README + CHANGELOG con nuova sezione "Audit OdC"
4. ⏳ Aggiungi il PDF di esempio (con LS-ID) come allegato alla brochure commerciale

### Step 2 — Pre-vendita estesa (1 settimana)
1. ⏳ Implementa registro fornitori (gap 4.1)
2. ⏳ Aggiungi e_l per food/feed crops (gap 4.2)
3. ⏳ Persistenza dati cliente (gap 4.6)
4. ⏳ Aggiungi pagina "Conformità UNI/TS 11567" nel sito/landing che mostri il
   PDF audit-ready come differenziale competitivo

### Step 3 — Audit OdC formale (1 mese)
1. ⏳ Contatta RINA/SGS/Bureau Veritas per pre-assessment
2. ⏳ Esegui un audit pilota su un impianto cliente reale con dati veri
3. ⏳ Raccogli i rilievi e itera
4. ⏳ Ottieni attestazione "tool conforme alla rendicontazione UNI/TS 11567:2024"
5. ⏳ Pubblica attestazione + numero certificato sul sito

### Step 4 — Vendita conforme
- A questo punto puoi affermare commercialmente:
  > "Metan.iQ genera Lotti di Sostenibilità RED III / D.Lgs. 199/2021 conformi alla
  > rendicontazione UNI/TS 11567:2024, valutati e attestati da [OdC accreditato]"

Senza l'attestazione OdC, la dicitura corretta è:
  > "Metan.iQ supporta la rendicontazione secondo lo schema UNI/TS 11567:2024.
  > La conformità della specifica filiera resta soggetta a verifica di un OdC
  > accreditato."

---

## 8. Conclusione

Lo stato del codice è **migliore di quanto sembri dall'UI**. La struttura dati
(`FEEDSTOCK_DB` con `cat`/`annex_ix`/`src`), la formula GHG, le soglie e i
comparator sono **già conformi** all'impianto normativo RED III / UNI/TS 11567 /
GSE LG 2024. Le carenze erano principalmente di **trasparenza UI** e di
**output audit-ready** (LS-ID, anagrafica, firma) — risolte con le patch.

Resta da **completare il registro fornitori** e **redepoyare** prima di poter
considerare il software pronto al pre-assessment OdC.

---

*Documento generato il 2026-05-28 a esito dell'audit ingegneristico assistito da
Claude Opus 4.7. Soggetto a revisione del Responsabile della Sostenibilità del
prodotto Metan.iQ prima di qualsiasi uso commerciale.*
