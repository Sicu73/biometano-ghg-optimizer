# Metan.iQ — note tecniche

Per chi ha l'autorizzazione scritta del titolare a lavorare sul codice (vedi [LICENSE](../LICENSE)). Il prodotto si usa dalla [demo live](https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/).

## Stack

- **App**: Streamlit (Python 3.11+)
- **Calcoli**: NumPy, SciPy (solver LP), pandas
- **Grafici**: Plotly
- **Report**: ReportLab (PDF), openpyxl (Excel), python-pptx (PowerPoint)
- **Dati**: SQLite
- **Lingue**: italiano e inglese

## Avvio e controlli

```bash
pip install -e ".[dev]"
streamlit run app_mensile.py
pytest tests/
ruff check .
mypy core/
```

## Struttura

| Percorso | Contenuto |
|---|---|
| `app_mensile.py` | app Streamlit, punto di ingresso |
| `core/` | logica: calcolo GHG, business plan, persistenza, autenticazione, billing |
| `output/`, `export/` | KPI, tabelle, report Excel, PDF, CSV, PPTX |
| `report_pdf.py`, `excel_export.py`, `dossier_conformita.py` | report e dossier |
| `normativa_versions.json`, `emission_factors_override.py`, `bmt_override.py` | riferimenti normativi e fattori emissivi |
| `tests/` | test pytest |
| `legal/` | privacy, termini, bozza listino |
| `docs/` | guida operativa, manuale utente, questo file; audit e verifiche in `docs/archive/` |

## Pubblicazione su Streamlit Cloud

L'app pubblicata segue il ramo `dm2022-only`. I segreti vanno in **Manage app → Settings → Secrets**, partendo da `.streamlit/secrets.toml.example`.

## Attivare la modalità commerciale

L'app parte in **modalità demo**: nessun login. Per attivare accessi e pagamenti:

1. genera un segreto JWT casuale (per esempio `openssl rand -hex 32`);
2. se servono i pagamenti, crea un account Stripe con 4 prezzi;
3. in **Settings → Secrets** aggiungi:
   ```toml
   [auth]
   demo_mode = false
   jwt_secret = "<32-bytes-random>"

   [stripe]
   secret_key = "sk_live_..."
   webhook_secret = "whsec_..."
   price_pro_monthly = "price_..."
   price_pro_yearly = "price_..."
   price_enterprise_monthly = "price_..."
   price_enterprise_yearly = "price_..."
   ```
4. riavvia l'app.

## Piano di lavoro

| Fase | Stato | Contenuto |
|---|---|---|
| Sprint 0 | Fatto | dipendenze bloccate, CI, tema, testi legali, Sentry |
| Fase 1 | Fatto | controllo XSS, formati numerici e date per lingua, test |
| Fase 2 | Fatto | login, separazione dei dati per utente, Stripe, registro attività, modalità demo predefinita |
| Fase 3 | Da fare | landing page, percorso guidato, documentazione, casi studio |
| Fase 4 | Da fare | API REST, webhook, assistente AI, app per cellulare, hosting dedicato |
