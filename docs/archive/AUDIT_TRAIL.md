# AUDIT TRAIL — Metan.iQ

Documento di tracciabilità per i fattori emissivi e le rese utilizzate
nei calcoli GHG di Metan.iQ. Ogni esecuzione del software produce
un audit-trail completo che viene incluso negli export Excel e PDF.

## 1. Origine dei fattori emissivi

Per ogni biomassa attiva nel mix, l'app riporta sempre l'origine dei
fattori emissivi usati nei calcoli, secondo due possibili etichette:

| Origine | Descrizione |
|---|---|
| `Valori standard software / normativa / default interno` | Fattori da tabella interna `FEEDSTOCK_DB` (UNI/TS 11567:2024, JEC WTT v5, Annex IX RED III, GSE LG 2024). |
| `Relazione tecnica impianto` | Fattori dichiarati in una relazione tecnica caricata dall'utente per quella specifica biomassa. La tabella standard NON viene modificata. |

## 2. Formula coerente

Tutti i calcoli emissivi (modulo Python, formule Excel, righe PDF)
usano la stessa convenzione di segno:

```
e_total = eec + etd + ep − esca − crediti_extra
```

dove:
- `eec` può essere negativo (manure credit incorporato)
- `esca` è un credito positivo SOTTRATTO una sola volta
- `crediti_extra` sono crediti AGGIUNTIVI dichiarati a parte nella
  relazione tecnica, mai già inclusi in `esca` (no double-counting)

## 3. Validazione override REALI

Il software accetta un override reale solo se **tutte** le condizioni
seguenti sono soddisfatte:

1. la relazione tecnica è stata caricata (PDF/DOCX/XLSX/CSV/JPG/PNG);
2. l'utente ha attivato esplicitamente l'override per la biomassa;
3. tutti i valori `eec_real`, `esca_real`, `etd_real`, `ep_real`,
   `extra_credits_real` sono numerici, finiti, con segno coerente
   (esca/etd/ep/extra ≥ 0; eec libero);
4. tutti i metadati relazione (titolo, autore, società, data,
   impianto, riferimento campione) sono compilati;
5. la biomassa è collegata alla relazione caricata.

Se manca una qualunque condizione bloccante, l'app mostra il
messaggio:

> Per usare fattori emissivi reali devi prima caricare la relazione
> tecnica dell'impianto relativa alla biomassa selezionata.

I valori standard restano in uso per quella biomassa.

## 4. Warning di scostamento

Per ciascun fattore reale, se lo scostamento dal valore standard
supera il **±30%**, l'app emette un warning:

> Attenzione: il fattore emissivo reale inserito differisce di oltre
> il 30% dal valore standard. Verificare relazione tecnica, unità
> di misura e biomassa associata.

Il warning NON blocca l'override (l'utente è responsabile della
correttezza della relazione), ma viene riportato chiaramente nei
report PDF e nel foglio Excel di audit.

## 5. Range di plausibilità

Per intercettare errori di unità di misura, l'app verifica anche
che ciascun fattore stia entro un range "ragionevole":

| Fattore | Range plausibile [gCO₂eq/MJ] |
|---|---|
| `eec` | [−150, +200] |
| `esca` | [0, +100] |
| `etd` | [0, +20] |
| `ep` | [0, +100] |
| `crediti_extra` | [0, +200] |

Se un valore esce dal range, viene emesso un warning aggiuntivo di
sanity-check.

## 6. Tracciabilità export

Tutti gli output (UI tabella, CSV, Excel, PDF) includono per ogni
biomassa:

- nome biomassa;
- valore standard (per ogni fattore);
- valore usato (= reale se override attivo, altrimenti = standard);
- scostamento %;
- origine del dato (etichetta esplicita);
- nome file relazione tecnica (se override);
- titolo relazione, autore, società, data, impianto, riferimento
  campione, note metodologiche (se override);
- e_total finale.

## 7. Protezione contro errori silenziosi

Il software non sostituisce MAI valori standard con valori reali
senza dichiararlo esplicitamente. L'etichetta `Origine fattori`
è sempre presente nei report e nei fogli Excel.

## 8. Immutabilità della tabella standard

La tabella interna `FEEDSTOCK_DB` non viene MAI modificata da un
override. Gli override sono salvati in `st.session_state[
"emission_factor_overrides"]` separatamente e applicati a runtime
via la funzione `_emission_factors_of(name, ep)`.

Quando l'utente disattiva un override (deselezionando il checkbox),
i valori standard tornano automaticamente in uso.

## 9. Audit log per certificazione

Per finalità di certificazione GSE / RT-31 Accredia, ogni report
PDF generato da Metan.iQ include una sezione dedicata
`// EMISSION FACTORS AUDIT` con:

- conteggio biomasse con override attivo vs totale;
- spiegazione metodologica (quando vengono usati valori standard
  vs quando vengono usati valori reali);
- tabella riassuntiva fattori per biomassa;
- sezione metadati per ciascuna relazione tecnica caricata.

Il consulente è responsabile di allegare al dossier di certificazione
il file della relazione tecnica originale (Metan.iQ conserva il
file in sessione ma NON lo distribuisce automaticamente con il
report PDF).
