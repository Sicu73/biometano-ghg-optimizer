# Privacy Policy — Metan.iQ

**Ultimo aggiornamento**: 19 maggio 2026

## 1. Titolare del trattamento

**Carlo Sicurini** — Email: carlo.sicurini@gmail.com

Il presente documento descrive come Metan.iQ ("il Servizio") raccoglie, utilizza
e protegge i dati personali e operativi degli utenti, in conformità al
Regolamento (UE) 2016/679 (GDPR) e al D.Lgs. 196/2003 e ss.mm.ii.

## 2. Dati raccolti

### 2.1 Dati di registrazione (Fase SaaS, futuro)
- Email, nome, password (hash + salt).
- Ragione sociale azienda, P.IVA, indirizzo (per fatturazione).

### 2.2 Dati operativi inseriti dall'utente
- Anagrafica impianto (nome, sede, taglia, regime applicato).
- Dati giornalieri: ore di funzionamento, biomasse caricate (tipo + quantità),
  letture contatore REMI (Vb, E, PCI).
- Override BMT (laboratorio) e Fattori Emissivi (relazione tecnica).
- Configurazione tariffaria (incentivi, premi cumulabili, PNRR).

### 2.3 Dati tecnici raccolti automaticamente
- Indirizzo IP (per logging accesso e sicurezza).
- User-Agent del browser.
- Log degli errori applicativi (con eventuali stack trace).
- Eventi di utilizzo (login, save, export) per audit interno.

## 3. Finalità del trattamento

- **Erogazione del Servizio**: calcolo GHG, ottimizzazione, generazione report.
- **Persistenza dei dati**: salvataggio dei mesi inseriti su database isolato
  per cliente.
- **Sicurezza**: rilevamento accessi anomali, prevenzione frodi.
- **Adempimenti contabili e fiscali** (in caso di sottoscrizione a pagamento).
- **Miglioramento del Servizio**: analisi aggregata e anonimizzata dell'utilizzo.

## 4. Base giuridica

- Esecuzione di un contratto (art. 6.1.b GDPR).
- Adempimento di obblighi legali (art. 6.1.c GDPR).
- Legittimo interesse del Titolare per sicurezza e migliorie (art. 6.1.f GDPR).

## 5. Conservazione

I dati operativi sono conservati per tutta la durata dell'abbonamento e per
**12 mesi** dopo la cessazione, dopo i quali vengono cancellati salvo obblighi
fiscali (10 anni per fatture).

## 6. Condivisione con terzi

I dati non vengono mai venduti. Sono accessibili a fornitori tecnici
strettamente necessari:

- **Streamlit Cloud / Snowflake** (hosting applicazione)
- **Supabase / Neon** (hosting database — futuro)
- **Stripe** (gestione pagamenti — futuro)
- **Sentry** (monitoring errori — opzionale)
- **GitHub** (codice sorgente — repository privato)

Tutti i fornitori sopra sono GDPR-compliant.

## 7. Diritti dell'utente (art. 15-22 GDPR)

L'utente può in qualsiasi momento:

- **Accedere** ai propri dati.
- **Rettificare** dati errati.
- **Cancellare** account e dati associati ("diritto all'oblio").
- **Esportare** i propri dati in formato Excel/CSV/PDF (portabilità).
- **Limitare** o **opporsi** al trattamento.
- **Revocare** il consenso in ogni momento.

Per esercitare questi diritti: invia email a `carlo.sicurini@gmail.com`.

## 8. Sicurezza

- Connessione cifrata HTTPS/TLS 1.3.
- Password salvate con hashing bcrypt/argon2 (mai in chiaro).
- Repository codice sorgente **privato** (solo il Titolare ha accesso).
- Backup database giornalieri (con retention 30 giorni).
- Audit log accessi mantenuto per 12 mesi.

## 9. Cookie

Metan.iQ utilizza **solo cookie tecnici di sessione** (autenticazione,
preferenze lingua e tema). Nessun cookie di profilazione o pubblicitario.

## 10. Modifiche

Eventuali modifiche a questa Policy saranno notificate via email almeno 30
giorni prima dell'entrata in vigore.

## 11. Reclami

L'utente ha diritto di proporre reclamo al **Garante per la Protezione dei
Dati Personali** — https://www.garanteprivacy.it.
