# Istruzioni per gli agenti (Claude, Codex e altri)

Metan.iQ: app Streamlit (Python 3.11+) per impianti di biometano DM 2022 / RED III. Pianificazione mensile, calcolo e ottimizzazione GHG, business plan, report PDF/Excel/PPTX.
Software proprietario di Carlo Sicurini: il codice è pubblico solo come vetrina (vedi `LICENSE`).

Le regole generali di Carlo, le skill di settore (`biogas-norme`, `uni-ts-11567`, `biogas-tecnico`) e i prompt stanno nel repo privato `Sicu73/istruzioni-ai`. Se è disponibile in questa sessione, leggi il suo `istruzioni/globali.md` prima di iniziare.

## Comandi

```
pip install -e ".[dev]"
streamlit run app_mensile.py      # avvia l'app
pytest tests/ -v --tb=short       # i test (devono passare prima di ogni push: la CI li esegue su Python 3.11 e 3.12)
ruff check .                      # lint (in CI avvisa ma non blocca)
```

## Dove stanno le cose

- `app_mensile.py`: l'app Streamlit (punto di ingresso).
- `core/`: logica (calcolo GHG `calculation_engine.py` e `sustainability.py`, business plan, persistenza SQLite, autenticazione).
- `export/`, `output/`, `report_pdf.py`, `excel_export.py`: i report.
- `normativa_versions.json`, `emission_factors_override.py`, `bmt_override.py`: riferimenti normativi e fattori emissivi.
- `i18n_runtime.py`, `metaniq_i18n.py`: testi italiano/inglese.
- `tests/`: pytest.

## Regole

- **Testi che citano norme, soglie o €/MWh**: segui `docs/REGULATORY_WRITING_GUIDELINE.md` (7 regole: non inventare numeri normativi; distinguere norma, mercato e default; citare solo articoli verificabili; terminologia corretta; riferimenti aggiornati; dire all'utente cosa fare; italiano e inglese coerenti).
- Ogni testo nuovo nell'interfaccia va in italiano **e** in inglese.
- Non cambiare fattori emissivi, soglie GHG o valori normativi senza citare la fonte (articolo, allegato, tabella) nel commit.
- Lingua: commenti, commit e risposte in italiano.
- Mai segreti nel repo (chiavi, password, token, file `.env`).
