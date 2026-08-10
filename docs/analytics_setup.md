# Contatore visite

**Non serve configurare niente.** Il contatore è attivo e funziona da solo.

Vive in [`core/analytics.py`](../core/analytics.py) e conta **una visita per
sessione browser**, non per interazione: Streamlit rilancia lo script a ogni
click, senza il guard un singolo utente conterebbe decine di visite.

Il numero compare in fondo alla barra laterale:

```
👁 128 visite totali
```

## Privacy

Non si registra nulla di personale: né indirizzo IP, né user agent, né
cookie, né referer. È un conteggio aggregato, non un profilo — per questo non
serve alcun banner di consenso.

## Backend

Il modulo sceglie da solo, in quest'ordine:

| Backend | Quando | Cosa dà | Configurazione |
|---|---|---|---|
| **Abacus** | default | totale complessivo | nessuna |
| Supabase | se compili i secrets | totale, ultimi 30/7 giorni, oggi, ripartizione per lingua | opzionale |
| SQLite locale | se la rete non è disponibile | tutto, ma solo in locale | nessuna |

### Abacus (quello attivo)

[abacus.jasoncameron.dev](https://abacus.jasoncameron.dev) è un servizio di
conteggio pubblico e gratuito, senza account né chiavi. Persiste ai riavvii di
Streamlit Cloud, dove invece un file locale verrebbe cancellato a ogni riciclo
del container.

Due limiti dichiarati:

- espone **solo il totale**: le finestre temporali non esistono, e la UI le
  nasconde invece di mostrare zeri fuorvianti;
- il namespace è scritto nel codice, quindi chi lo conosce può incrementare il
  contatore. È una metrica indicativa, non un dato contrattuale.

Se il servizio non risponde, il badge semplicemente non compare: un contatore
non deve mai impedire all'app di funzionare.

### Supabase (opzionale, per le statistiche complete)

Serve solo se vuoi le finestre temporali e la ripartizione per lingua.

1. Crea un progetto gratuito su [supabase.com](https://supabase.com).
2. Nel **SQL Editor** esegui:

```sql
create table if not exists visits (
    visit_id    text primary key,
    ts          timestamptz not null default now(),
    lang        text,
    app_version text
);

create index if not exists idx_visits_ts on visits (ts);
alter table visits enable row level security;
```

3. In **Project Settings → API** copia `Project URL` e la chiave
   `service_role`.
4. Su Streamlit Cloud, **Settings → Secrets**, aggiungi:

```toml
[analytics]
supabase_url = "https://xxxxxxxx.supabase.co"
service_key  = "eyJhbGciOi..."   # service_role, NON la anon key
```

5. **Reboot** dell'app.

La `service_role` bypassa la row level security: solo nei secrets del server,
mai nel codice.

## Variabili d'ambiente

| Variabile | Effetto |
|---|---|
| `METANIQ_ABACUS_NS` | namespace alternativo (utile per prove senza toccare il contatore vero) |
| `METANIQ_ANALYTICS_DB` | path del file SQLite |
| `METANIQ_ANALYTICS_REMOTE=1` | forza il contatore remoto anche sotto pytest |
| `METANIQ_ANALYTICS_URL` / `_KEY` | equivalenti dei secrets Supabase |

In `[analytics]` si può anche mettere `disable_remote = true` per tenere tutto
in locale.

## Nei test

La suite **non** incrementa il contatore di produzione: `get_backend()` rileva
`PYTEST_CURRENT_TEST` e ripiega su SQLite. Senza questo guard, ogni esecuzione
dei test — che avvia l'app headless — avrebbe gonfiato il totale.

## Leggere i numeri da riga di comando

```bash
python -c "from core.analytics import get_stats; print(get_stats())"
```

## Cosa NON misura

- Visite e cloni del repo → GitHub, **Insights → Traffic** (storico 14 giorni).
- Sessioni viste da Streamlit → dashboard Streamlit Cloud, **Analytics**.

Questo contatore è indipendente da entrambi e conta chi apre davvero l'app.
