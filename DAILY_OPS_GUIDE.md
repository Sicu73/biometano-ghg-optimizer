# Guida operativa — Gestione Giornaliera con verifica sostenibilità mensile

Questa guida descrive il workflow operativo "giorno per giorno" introdotto in
Metan.iQ con la branch `feature/daily-ops-monthly-sustainability`.

---

## 1. Regola fondamentale di compliance

**La sostenibilità è MENSILE, NON giornaliera.**

L'indicatore di "saving giornaliero (stima)" mostrato nella tabella è solo
informativo: serve a capire l'impatto del singolo giorno sull'aggregato. Il
verdetto ufficiale `Compliant` / `Non Compliant` viene calcolato
**solo sul totale mese aggregato**.

> Esempio: un mese può chiudere `Compliant` anche se 3 o 4 giorni hanno
> saving giornaliero sotto soglia, purché la **media pesata mensile** delle
> emissioni rispetti il limite normativo (RED III: 80%; trasporti: 65%; ecc.).

Questa regola è coperta da test (`tests/test_daily_ops.py`,
`test_sustainability_isolated_bad_day_but_month_ok`).

---

## 2. Dove si trova nella UI

Apri l'app sul link live:

```
https://sicu73-biometano-ghg-optimizer-app-mensile-aevnmc.streamlit.app/
```

In fondo alla pagina, dopo i KPI annuali e gli expander di spiegazione,
trovi la sezione:

> **📅 Gestione Giornaliera — Verifica sostenibilità mensile**

---

## 3. Workflow operativo passo passo

### 3.1 Selezione mese
1. Imposta **Anno** (default: anno corrente).
2. Scegli il **Mese** dal selettore (Gennaio → Dicembre, italiano).
3. Imposta **ID impianto** (`default` se hai un solo impianto;
   altrimenti un identificativo per separare i dati).

L'app genera automaticamente i giorni del mese (28/29/30/31, anni
bisestili gestiti).

### 3.2 Caricamento dati salvati
- Se per quel mese hai già salvato dati, vengono ricaricati dal database
  SQLite locale (`data/metaniq_daily.db`).
- Pulsante **🔄 Ricarica da DB** per ricaricare i dati salvati
  (scarta modifiche non salvate).
- Pulsante **🆕 Nuovo mese (vuoto)** per partire da zero.

### 3.3 Inserimento biomasse giornaliere
Nella tabella editabile:

| Data       | Trinciato di mais | Letame bovino | ... |
|------------|-------------------|---------------|-----|
| 01/05/2025 | 12.0              | 3.5           | ... |
| 02/05/2025 | 11.5              | 3.0           | ... |
| ...        | ...               | ...           | ... |

- Colonne dinamiche: una per ogni biomassa attiva (selezionate in sidebar).
- Valori in **t/giorno** (tonnellate al giorno).
- Quantità negative rifiutate; vuoto = 0 t.

### 3.4 Calcoli automatici
Ogni modifica ricalcola al volo:
- **Sm³ netti** giornalieri (resa biomassa / aux_factor).
- **MWh** netti giornalieri.
- **eec / esca / etd / ep / e_total** (gCO2eq/MJ medi pesati).
- **Saving giornaliero (stima %)** — solo informativo.
- **Cap OK** — vincolo capacità autorizzativa.
- **Cumulato mese** (Sm³, MWh, t) progressivi.

### 3.5 KPI mensili (esito ufficiale)
Sotto la tabella vedi 4 indicatori principali:
- **Saving GHG mese** con margine vs soglia
- **Soglia normativa** (es. 80%)
- **Biomassa totale** (t)
- **MWh netti mese**

Sotto, un badge **✅ MESE COMPLIANT** o **❌ MESE NON COMPLIANT** con
spiegazione del calcolo.

### 3.6 Vincoli regime
Expander dedicato che mostra lo stato di:
- Soglia saving GHG mensile
- Cap autorizzativo Sm³/h (se attivo)
- Eventuali vincoli FER2 / Annex IX (in funzione del regime selezionato)

### 3.7 Indicazioni operative fine mese
Negli ultimi giorni del mese, il modulo guidance suggerisce:
- saving cumulato vs soglia
- margine residuo (positivo o negativo)
- azioni correttive (es. "aumentare quota sottoprodotti", "ridurre
  biomasse alto eec", "verificare cap autorizzativo")

### 3.8 Audit Trail mese
Sezione che documenta:
- regime applicato
- soglia normativa e comparatore fossile
- aux_factor / EP totale / plant_net Sm³/h
- origine rese (standard/BMT)
- origine fattori emissivi (standard/relazione tecnica)
- formula sostenibilità mensile
- giorni con dati / giorni cap violato

### 3.9 Salvataggio ed export
Pulsanti finali:
- **💾 Salva mese** → SQLite locale `data/metaniq_daily.db`
- **⬇️ CSV giornaliero** (sep `;`, decimale `,`, UTF-8)
- **⬇️ Excel giornaliero+mensile** (4 fogli: Giornaliero / Mensile KPI / Vincoli / Audit Trail)
- **⬇️ PDF report** (KPI, vincoli, guidance, audit, tabella giornaliera)

> NOTA: il file DB è locale alla macchina/sessione e **NON è committato**
> (vedi `.gitignore` → `data/*.db`).

---

## 4. Esempio di mese compilato

**Maggio 2025 — Impianto biometano 300 Sm³/h, RED III (soglia 80%):**

| Data       | Liquame suino (t) | Pollina (t) | Trinciato mais (t) |
|------------|-------------------|-------------|--------------------|
| 01/05/2025 | 30                | 5           | 8                  |
| 02/05/2025 | 30                | 5           | 8                  |
| 03/05/2025 | 30                | 5           | 8                  |
| ...        | ...               | ...         | ...                |
| 31/05/2025 | 30                | 5           | 8                  |

Risultato (esempio sintetico):
- Biomassa totale mese: ~1.333 t
- Sm³ netti mese: ~210.000
- MWh netti mese: ~2.094
- Saving GHG mese: **84.2 %** ≥ 80 % → **✅ COMPLIANT**
- Margine: **+4.2 punti**

Anche se in 3 giornate isolate il saving giornaliero risulta `78%`
(per un picco di colture dedicate), l'aggregato mese resta sostenibile.

---

## 5. Comportamento "fine mese" — gestione del margine

Negli ultimi giorni il modulo `guidance` ti guida:

- Se il **margine è positivo** (+x punti): "Mantenere il mix attuale fino
  a fine mese."
- Se il **margine è negativo** (-x punti):
  - "Aumentare la quota di sottoprodotti / effluenti (eec basso)."
  - "Ridurre colture dedicate / insilati ad alto eec."
  - "Valorizzare biomasse Annex IX (avanzate) per migliorare il GHG."

---

## 6. Persistenza dei dati

I dati operativi vengono salvati in **SQLite locale** in
`<repo>/data/metaniq_daily.db` con due tabelle:

```sql
CREATE TABLE daily_entries (
    plant_id        TEXT NOT NULL,
    date            TEXT NOT NULL,
    feedstock_type  TEXT NOT NULL,
    qty_t           REAL NOT NULL,
    notes           TEXT DEFAULT '',
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (plant_id, date, feedstock_type)
);
CREATE TABLE month_meta (
    plant_id  TEXT NOT NULL,
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    regime    TEXT,
    threshold REAL,
    saved_at  TEXT NOT NULL,
    PRIMARY KEY (plant_id, year, month)
);
```

> NOTA STREAMLIT CLOUD: il filesystem dei container Streamlit Cloud è
> **effimero** — i dati salvati nella sessione live possono essere persi
> al redeploy. Per uso operativo continuativo si raccomanda di:
> 1. Esportare regolarmente CSV/Excel/PDF di backup.
> 2. Eseguire l'app in locale (clone repo + `streamlit run app_mensile.py`)
>    per persistenza affidabile su disco.

---

## 7. Snippet di codice — uso programmatico

```python
from datetime import date
from core.calendar import generate_month_days
from core.daily_model import DailyEntry, compute_daily
from core.monthly_aggregate import aggregate_month
from core.sustainability import evaluate_monthly_sustainability
from core.persistence import save_month, load_month

ctx = {
    "aux_factor": 1.29, "ep": 4.5,
    "fossil_comparator": 80.0, "plant_net_smch": 300.0,
    "hours_per_day": 24.0,
}

# Costruisci un mese di esempio
days = generate_month_days(2025, 5)
entries = [
    DailyEntry(date=d, feedstocks={"Liquame suino": 30, "Pollina": 5,
                                    "Trinciato di mais": 8})
    for d in days
]
computed = [compute_daily(e, ctx) for e in entries]
agg = aggregate_month(computed, ctx, year=2025, month=5)
res = evaluate_monthly_sustainability(agg, regime="RED III", threshold=80.0)
print("Compliant:", res["compliant"], "Saving:", res["saving"])

# Persistenza
save_month(2025, 5, entries, plant_id="impianto_demo",
            regime="RED III", threshold=0.80)
loaded = load_month(2025, 5, plant_id="impianto_demo")
```

---

## 8. Test

```bash
python -m pytest tests/test_daily_ops.py -v
```

Copertura: calendario (bisestili), aggregazione, sostenibilità (compliant /
non compliant / mese OK con giorni isolati bad), persistenza save/load
roundtrip + giorni vuoti, validatore (quantità negative, date invalide).
