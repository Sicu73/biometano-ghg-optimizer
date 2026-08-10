# Contatore visite — configurazione

Il contatore vive in [`core/analytics.py`](../core/analytics.py) e registra
**una riga per sessione browser**: identificativo casuale, timestamp UTC,
lingua UI, versione app. Nessun IP, nessun user agent, nessun cookie, nessun
dato che permetta di risalire alla persona — è un conteggio aggregato, quindi
non richiede banner di consenso.

## Backend

| Backend | Quando si attiva | Persistenza |
|---|---|---|
| Supabase (REST) | `st.secrets["analytics"]` compilato | Sì, è quello da usare in produzione |
| SQLite locale | sempre, come fallback | No su Streamlit Cloud: il container viene riciclato e il file sparisce |

Senza configurazione l'app funziona identica: il contatore usa SQLite e il
badge in sidebar mostra i numeri della sessione corrente del container.

## Setup Supabase (gratuito, ~5 minuti)

1. Crea un progetto su [supabase.com](https://supabase.com) (piano free).
2. Nel **SQL Editor** esegui:

```sql
create table if not exists visits (
    visit_id    text primary key,
    ts          timestamptz not null default now(),
    lang        text,
    app_version text
);

create index if not exists idx_visits_ts on visits (ts);

-- Nessun accesso anonimo: si scrive solo con la service key lato server.
alter table visits enable row level security;
```

3. In **Project Settings → API** copia `Project URL` e la chiave
   `service_role`.
4. Su Streamlit Cloud, **Settings → Secrets** dell'app, incolla:

```toml
[analytics]
supabase_url = "https://xxxxxxxx.supabase.co"
service_key  = "eyJhbGciOi..."   # service_role, NON la anon key
```

5. Riavvia l'app (**Reboot**, non basta il redeploy).

La `service_role` key bypassa la row level security: va messa solo nei
secrets del server, mai in codice o in pagine pubbliche.

## In locale

Per non sporcare `data/analytics.db` durante i test:

```bash
METANIQ_ANALYTICS_DB=/tmp/analytics.db streamlit run app_mensile.py
```

In alternativa a Supabase si possono usare le variabili d'ambiente
`METANIQ_ANALYTICS_URL` e `METANIQ_ANALYTICS_KEY`, equivalenti ai secrets.

## Leggere i numeri

Il badge in fondo alla sidebar mostra totale e ultimi 30 giorni, con letture
**in cache 5 minuti** (con Supabase ogni statistica costa chiamate HTTP).

Per il dettaglio completo, da shell:

```bash
python -c "from core.analytics import get_stats; s = get_stats(); print(s)"
```

Restituisce totale, ultimi 30/7 giorni, oggi, prima e ultima visita, e la
ripartizione per lingua.

## Cosa NON misura

Le visite alla pagina GitHub e i cloni del repo stanno in
**GitHub → Insights → Traffic** (14 giorni di storico). Le visite viste da
Streamlit stanno nella dashboard di Streamlit Cloud → **Analytics**. Questo
contatore è indipendente da entrambe e conta le sessioni che aprono davvero
l'app.
