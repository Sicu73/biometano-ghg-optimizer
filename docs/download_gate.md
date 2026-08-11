# Report identificati (gate sui download)

**App aperta, report identificati.** Chiunque può usare il simulatore senza
registrarsi; per scaricare un deliverable (PDF, Excel, PPTX, dossier OdC,
business plan) si lasciano nome, email e azienda.

Chi ha un interesse reale si identifica, il curioso guarda e basta.

## Cosa è protetto e cosa no

| Contenuto | Accesso |
|---|---|
| Simulatore, calcoli, tabelle, grafici | libero |
| Manuale utente (PDF) | libero — è documentazione |
| Report PDF, Excel, PPTX, CSV, dossier OdC, business plan | richiede contatto |

Sono 13 download protetti. Al primo che l'utente prova, compare un pulsante
con il lucchetto: cliccandolo si apre un riquadro con tre campi. Compilati
quelli, **tutti** i download restano sbloccati per l'intera sessione.

## Perché non un account con password

`core/auth.py` implementa già registrazione, bcrypt e JWT, ma su Streamlit
Community Cloud il filesystem è effimero: la tabella utenti si azzera a ogni
riciclo del container. Chi si registrasse oggi non riuscirebbe più ad
accedere domani.

Il form di contatto ottiene lo stesso risultato — sapere chi scarica — senza
promettere una persistenza che l'infrastruttura non offre. Se un giorno
l'autenticazione vera viene attivata, chi è loggato salta il form
automaticamente (`core/download_gate.is_unlocked` riconosce `current_user()`).

## Dove finiscono i contatti

In ordine di affidabilità, tutti opzionali e cumulativi:

| Canale | Secret | Persiste |
|---|---|---|
| Webhook | `[leads] webhook_url` | sì, dove punta il webhook |
| Supabase | `[leads] supabase_url` + `service_key` | sì |
| SQLite locale | — | **no**, si perde al riciclo del container |

Senza almeno uno dei primi due il gate funziona lo stesso, ma **i contatti
raccolti non ti raggiungono**: restano nel database effimero.

### Discord (configurato)

Se l'URL del webhook è di Discord, il payload viene convertito automaticamente
nel formato che Discord richiede (`embeds`): un JSON generico verrebbe
rifiutato con 400. Nel canale arriva un messaggio come:

```
📥 Nuovo download report
Nome: Carlo Sicurini      Email: carlo@example.com
Azienda / Impianto: CAB Bagnacavallo
Documento: 📄 Scarica Report PDF
```

Nei secrets:

```toml
[leads]
webhook_url = "https://discord.com/api/webhooks/123456/abcdef..."
```

Il riconoscimento avviene sull'URL (`discord.com/api/webhooks`), non serve
altra configurazione.

### Webhook generico

Un POST JSON con questo corpo:

```json
{
  "name": "Carlo Sicurini",
  "email": "carlo@example.com",
  "company": "CAB Bagnacavallo",
  "document": "📄 Scarica Report PDF",
  "source": "download_gate",
  "created_at": "2026-08-10T17:40:00+00:00"
}
```

Nei secrets di Streamlit Cloud:

```toml
[leads]
webhook_url = "https://hooks.zapier.com/..."
```

Funziona con Zapier, Make, n8n, un webhook Discord o Slack, o un endpoint tuo.

### Supabase

```sql
create table if not exists leads (
    id          bigserial primary key,
    name        text,
    email       text,
    company     text,
    document    text,
    source      text,
    created_at  timestamptz default now()
);
alter table leads enable row level security;
```

```toml
[leads]
supabase_url = "https://xxxxxxxx.supabase.co"
service_key  = "eyJhbGciOi..."
```

## Disattivare il gate

```toml
[auth]
gate_downloads = false
```

Tutti i download tornano liberi.

## Privacy

Si raccolgono dati identificativi forniti volontariamente dall'utente
(nome, email, azienda) con una finalità dichiarata: scaricare il documento.
A differenza del contatore visite, qui **si tratta di dati personali**:
vanno indicati nell'informativa privacy dell'app, con base giuridica e tempi
di conservazione. Il testo in `legal/privacy.md` va aggiornato di
conseguenza.

Non si registrano IP né user agent.

## Nei test

`_dl_unlocked = True` in `session_state` simula l'utente identificato. Il
flusso completo (compilazione form → sblocco → download disponibili) è
coperto da `tests/test_app_smoke.py::test_unlock_flow_end_to_end`.
