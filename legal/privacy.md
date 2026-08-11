# Privacy Policy — Metan.iQ

**Ultimo aggiornamento**: 11 agosto 2026

Informativa resa ai sensi degli artt. 13-14 del Regolamento (UE) 2016/679
(GDPR) e del D.Lgs. 196/2003 come modificato dal D.Lgs. 101/2018.

## 1. Titolare del trattamento

**Carlo Sicurini** — carlo.sicurini@gmail.com

Per esercitare i tuoi diritti o per qualunque domanda su questa informativa,
scrivi a quell'indirizzo.

## 2. Cosa raccogliamo, e quando

Metan.iQ è utilizzabile **senza registrazione e senza fornire dati
personali**. La raccolta avviene solo nei casi qui sotto.

### 2.1 Dati che inserisci tu nel simulatore

Anagrafica impianto, ore di funzionamento, biomasse caricate, letture del
contatore REMI, override BMT e fattori emissivi, parametri tariffari.

Sono dati **tecnici e aziendali**, non personali, salvo che tu scelga di
scrivere nei campi liberi (es. "Nome impianto", note) informazioni riferite a
persone fisiche.

Restano nella sessione del tuo browser e nel database dell'applicazione.
**Attenzione**: l'app gira su Streamlit Community Cloud, dove il disco è
temporaneo — i dati salvati vengono cancellati a ogni riavvio del servizio.
Non usare Metan.iQ come archivio: scarica i report ed esporta ciò che ti
serve conservare.

### 2.2 Dati che fornisci per scaricare i report

Per scaricare un report (PDF, Excel, PPTX, dossier di conformità, business
plan) vengono richiesti **nome e cognome, email e azienda/impianto**.
Insieme a questi viene registrato quale documento hai richiesto e la data.

Il conferimento è facoltativo, ma senza quei dati il download non è
disponibile. L'uso del simulatore resta libero.

### 2.3 Conteggio delle visite

L'app conta quante sessioni la aprono. Per ogni sessione registra un
identificativo **casuale**, generato al momento e non collegato a te, la data,
la lingua dell'interfaccia e la versione dell'app.

**Non** vengono raccolti indirizzo IP, user agent, cookie di tracciamento né
altri identificatori del dispositivo: è un conteggio aggregato dal quale non
è possibile risalire a una persona.

### 2.4 Account e pagamenti

Le funzioni di registrazione con password e di pagamento sono presenti nel
software ma **attualmente disattivate**. Se verranno attivate, questa
informativa sarà aggiornata prima della raccolta di qualunque dato.

### 2.5 Diagnostica errori

In caso di errore applicativo può essere generato un log tecnico contenente
il messaggio di errore e lo stack trace. Se il Titolare ha configurato il
servizio di monitoraggio (Sentry), tali log sono trasmessi a quel fornitore
con la trasmissione di dati personali disattivata (`send_default_pii=False`).

## 3. Perché trattiamo questi dati

| Dato | Finalità | Base giuridica |
|---|---|---|
| Dati del simulatore | erogare il calcolo e produrre i report che richiedi | art. 6.1.b — servizio richiesto dall'interessato |
| Nome, email, azienda | consegnarti il documento e poterti ricontattare in merito | art. 6.1.b e art. 6.1.f (legittimo interesse a conoscere gli utilizzatori professionali del software) |
| Conteggio visite | misurare l'utilizzo del servizio | dato non personale, fuori dall'ambito GDPR |
| Log di errore | sicurezza e correzione dei malfunzionamenti | art. 6.1.f — legittimo interesse |

I contatti raccolti al punto 2.2 **non** vengono usati per invii commerciali
non richiesti né ceduti a terzi per finalità di marketing.

## 4. Per quanto tempo

- **Dati del simulatore**: fino al riavvio del servizio (tipicamente ore o
  giorni); non esiste un archivio storico.
- **Contatti dei download**: 24 mesi dalla raccolta, salvo tua richiesta di
  cancellazione anticipata.
- **Conteggio visite**: il totale è un numero aggregato e viene conservato
  senza limite; non contiene dati personali.
- **Log di errore**: secondo la retention del fornitore di monitoraggio, se
  attivo.

## 5. Chi altro tratta i dati

I dati non vengono venduti. Sono trattati dai fornitori tecnici necessari a
far funzionare il servizio:

| Fornitore | Ruolo | Dati coinvolti |
|---|---|---|
| Streamlit (Snowflake Inc.) | hosting dell'applicazione | tutti i dati in transito |
| FormSubmit | inoltro via email dei contatti dei download | nome, email, azienda, documento |
| Abacus (abacus.jasoncameron.dev) | contatore visite | solo un numero progressivo |
| Sentry | monitoraggio errori, se configurato | log tecnici |
| GitHub | repository del codice sorgente | nessun dato personale degli utenti |

Alcuni fornitori hanno sede negli Stati Uniti: il trasferimento avviene sulla
base delle garanzie previste dal Capo V del GDPR (clausole contrattuali
standard o adesione al Data Privacy Framework, secondo quanto dichiarato da
ciascun fornitore).

Il **codice sorgente** di Metan.iQ è pubblicato in un repository pubblico su
GitHub. Il codice non contiene dati degli utenti.

## 6. Cookie

Metan.iQ non usa cookie di profilazione, pubblicitari o di tracciamento di
terze parti. La piattaforma Streamlit utilizza cookie tecnici necessari a
mantenere la sessione; le preferenze di lingua e tema restano nella sessione
del browser.

## 7. Sicurezza

- Connessione cifrata HTTPS/TLS.
- Nessuna raccolta di indirizzi IP o user agent da parte dell'applicazione.
- Le credenziali dei servizi esterni sono conservate nel gestore segreti
  della piattaforma di hosting, mai nel codice sorgente.
- Se le funzioni di account verranno attivate, le password saranno conservate
  esclusivamente come hash bcrypt.

Poiché il servizio è ospitato su un'infrastruttura con archiviazione
temporanea, **non sono previsti backup**: i dati che inserisci non sono
recuperabili dopo un riavvio.

## 8. I tuoi diritti (artt. 15-22 GDPR)

Puoi in ogni momento chiedere di:

- **accedere** ai dati che ti riguardano;
- **rettificare** dati inesatti;
- **cancellare** i tuoi dati;
- **limitare** o **opporti** al trattamento;
- ottenere la **portabilità** dei dati in formato leggibile;
- **revocare** un consenso eventualmente prestato, senza pregiudicare la
  liceità del trattamento precedente.

Scrivi a `carlo.sicurini@gmail.com`: riceverai riscontro entro un mese
(art. 12.3 GDPR).

Hai inoltre diritto di proporre **reclamo al Garante per la protezione dei
dati personali** (www.garanteprivacy.it) o all'autorità di controllo dello
Stato in cui risiedi.

## 9. Modifiche a questa informativa

Le modifiche sostanziali saranno pubblicate su questa pagina con la nuova
data di aggiornamento. Ti invitiamo a consultarla periodicamente.
