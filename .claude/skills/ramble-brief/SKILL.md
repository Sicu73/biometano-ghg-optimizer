---
name: ramble-brief
description: >-
  Trasforma un racconto disordinato — dettatura vocale, braindump, messaggio lungo e sconnesso — in una specifica di lavoro verificata, prima di produrre qualsiasi cosa. Protocollo, ascolta senza agire, ricostruisci, separa ciò che l'utente ha detto da ciò che hai inferito tu, elenca ciò che manca, fai confermare per iscritto numeri e riferimenti normativi, poi lavora. Usa questa skill ogni volta che l'utente dice "ti racconto", "ti spiego a voce", "sto dettando", "scusa il disordine", "butto giù due cose", "braindump", "ramble", "vado a braccio" — e anche quando arriva un messaggio lungo, ripetitivo o pieno di frasi interrotte che descrive un impianto, una filiera, un caso di audit, un cliente o un modulo da sviluppare, senza che venga chiesto di strutturarlo. Cruciale nei contesti tecnico-normativi (biometano, calcoli GHG, UNI/TS 11567, dossier GSE) dove un numero trascritto male non produce un errore visibile ma un risultato sbagliato dall'aria credibile.
---

# Ramble brief

## Perché esiste

Quando qualcuno parla per dieci minuti invece di scrivere tre righe, non sta essendo pigro: sta trasferendo dieci volte più contesto. A voce si fanno ~150 parole al minuto contro ~40 digitando. Il monologo disordinato contiene informazioni che l'utente non si sarebbe mai messo a scrivere — e che tu non puoi indovinare.

Il rischio è l'altra faccia della stessa medaglia. Sei bravo a ricostruire un discorso sconnesso, e questo significa anche che sei bravo a **riempire i buchi con ciò che suona coerente**. Il riassunto ordinato che restituisci contiene idee dell'utente e tue interpolazioni, mescolate e indistinguibili. Se poi ci costruisci sopra un calcolo o un documento, l'errore è già a valle e nessuno lo vede più.

Tutta questa skill serve a una cosa sola: **incassare il contesto in più senza incassare anche le tue invenzioni.** Da qui discendono le due regole che contano — non agire prima di aver ricostruito, e tenere sempre separato "questo me l'hai detto" da "questo l'ho dedotto io".

## Quando attivarla

Segnali espliciti: "ti racconto", "sto dettando", "scusa se è confuso", "vado a braccio", "butto lì", "poi mettilo in ordine tu".

Segnali impliciti, spesso più affidabili: il messaggio è lungo e torna più volte sullo stesso punto; ci sono frasi interrotte o riprese; l'ordine è cronologico-associativo invece che logico; compaiono parentesi tipo "no aspetta", "anzi", "comunque poi ti dico"; il testo ha la punteggiatura irregolare tipica della trascrizione automatica.

Se sei incerto, attivala. Il costo di una ricostruzione non richiesta è un messaggio in più; il costo di partire a lavorare su un contesto frainteso è tutto il lavoro.

## Il protocollo

### 1. Ascolta e basta

Non produrre codice, documenti, calcoli o file in questo turno. Nemmeno se la richiesta sembra chiara e l'esecuzione banale — dopo un ramble la richiesta *sembra sempre* chiara, perché sei tu ad averla resa tale.

Se l'utente sta ancora parlando ("continua", "aspetta che ti dico anche"), limita la risposta a un cenno e lascialo finire. Interrompere un flusso di coscienza per chiedere chiarimenti a metà lo fa deragliare, e le informazioni che stavano per arrivare non arrivano più.

### 2. Ricostruisci con questo schema

Usa sempre questa struttura, nell'ordine. È fatta apposta perché l'utente possa leggere solo le ultime due sezioni quando ha fretta — sono quelle dove si nascondono gli errori.

```markdown
## Obiettivo
[Una frase. Cosa deve esistere alla fine che ora non esiste.]

## Cosa mi hai detto
[Ricostruzione ordinata, solo contenuto effettivamente presente nel racconto.
 Riorganizzata per logica, non per ordine di arrivo. Sintetica ma senza perdere pezzi:
 se ha nominato un vincolo una volta sola di sfuggita, resta.]

## Vincoli
[Scadenze, formati, destinatari, normativa applicabile, cosa NON si deve toccare.]

## Assunzioni che ho fatto io
[Ogni punto dove hai colmato un vuoto. Se questa sezione è vuota, non hai cercato bene.]

## Cosa non mi hai detto
[Le informazioni che servono per fare il lavoro e che non ci sono.
 Non domande generiche: la specifica lacuna e perché blocca o rischia di far sbagliare.]

## Da confermare per iscritto
[Numeri, unità di misura, sigle, riferimenti normativi, identificativi, nomi di file.
 Vedi la sezione dedicata qui sotto.]
```

La sezione **"Assunzioni che ho fatto io"** è il cuore del protocollo. Un ramble di dieci minuti ti costringe sempre a dedurre qualcosa: quale impianto, quale anno, quale versione del documento, se "il cliente" è quello di cui si parlava ieri. Elencare quelle deduzioni le rende contestabili in dieci secondi. Nasconderle dentro una prosa fluida le rende invisibili fino a quando non è tardi.

La sezione **"Cosa non mi hai detto"** ha un effetto secondario prezioso: spesso l'utente scopre lì che non lo sapeva nemmeno lui. È il punto in cui la skill smette di essere trascrizione e diventa pensiero.

### 3. Fai confermare i dati critici in forma scritta

Il riconoscimento vocale sbaglia in silenzio, e sbaglia peggio proprio sulle cose che contano. Non ti restituisce "non ho capito": ti restituisce un numero plausibile.

Non tentare di indovinare il valore giusto dal contesto e non correggerlo di tua iniziativa. Elencalo e chiedi che venga riscritto a mano.

Cosa finisce sempre in questa lista:

- **Numeri e percentuali** — la virgola decimale sparisce o si sposta: "5,4%" → "54%", "0,5" → "05". Un ordine di grandezza sbagliato passa inosservato dentro una tabella.
- **Unità di misura** — Nm³ e Sm³ si confondono tra loro e con m³; t tal quale contro t di sostanza secca; MJ contro kWh; g contro kg. Sono errori che moltiplicano o dividono il risultato per una costante, quindi il risultato resta "credibile".
- **Riferimenti normativi** — articolo, comma, lettera, allegato, anno della versione. "Allegato IX parte A" e "parte B" sono due mondi diversi e a voce suonano quasi uguali.
- **Sigle e acronimi** — LS, FIR, OdC, GSE, MASE, CIC, RED II, FFC, SS. La trascrizione le rende spesso in parole comuni o le storpia.
- **Identificativi** — codici lotto, identificativi LS, partite IVA, numeri di pratica, nomi esatti di file e di colonne. Qui non esiste "quasi giusto".
- **Date e periodi** — "il mese scorso", "l'anno di riferimento", "la campagna 2024" vanno risolti in date esplicite.

Formula la richiesta in modo che costi poco rispondere: elenco puntato, un valore per riga, con accanto quello che hai capito tu. L'utente conferma in blocco o corregge tre righe.

### 4. Congela e poi lavora

Quando l'utente conferma o corregge, riscrivi la specifica aggiornata **in forma breve** e usa quella come base operativa per tutto il resto della sessione. Se più avanti emerge una contraddizione con la specifica congelata, fermati e segnalala invece di risolverla da solo: significa che una delle due versioni è sbagliata, e non sei tu a sapere quale.

Da questo punto in poi lavora normalmente.

## Consolidare i task ricorrenti

Un ramble non è un artefatto riutilizzabile: la volta dopo l'utente rifà il monologo e ottiene un risultato leggermente diverso.

Se riconosci che il lavoro descritto è di un tipo che si ripete — la stessa dichiarazione ogni trimestre, lo stesso tipo di dossier per clienti diversi, lo stesso controllo su lotti diversi — proponi a fine sessione di salvare la specifica congelata come modello riutilizzabile, con i punti variabili marcati. Proponilo, non farlo di iniziativa: è l'utente a sapere se quel lavoro tornerà.

## Cosa non fare

**Non lodare il racconto.** "Ottimo contesto, molto chiaro" non aggiunge nulla e occupa lo spazio che serve alle domande.

**Non trasformare il ramble in un elenco di venti domande.** Se il racconto era ricco, la maggior parte delle risposte è già lì. Chiedi solo ciò che manca davvero e che blocca il lavoro; il resto mettilo tra le assunzioni, dove l'utente lo corregge se serve senza doverti rispondere.

**Non lisciare le contraddizioni.** Se a un certo punto l'utente ha detto una cosa e poi il contrario, non scegliere la versione più sensata: segnala entrambe. Le contraddizioni in un flusso di coscienza sono quasi sempre il punto in cui il problema è ancora aperto anche nella sua testa, ed è l'informazione più utile dell'intero racconto.

**Non correggere il gergo.** Se chiama una cosa in un modo suo, continua a chiamarla così. Tradurla nel termine "corretto" fa perdere il riferimento e introduce ambiguità dove non ce n'era.

**Non allungare.** La ricostruzione deve essere più corta dell'originale. Se è più lunga, stai aggiungendo roba tua — che è esattamente il fallimento che questa skill esiste per evitare.

---

*Il protocollo adatta la "ramble session" descritta da Andrej Karpathy (X, 21 luglio 2026: parlare a voce ~10 minuti a flusso di coscienza invece di scrivere un prompt curato) aggiungendo le verifiche necessarie quando l'output finisce in calcoli o documenti tecnico-normativi.*
