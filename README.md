# Metan.iQ

**Pianificazione mensile, ottimizzazione GHG, business plan e report di sostenibilità per impianti di biometano** con immissione in rete (DM 2022 / RED III).

### [▶ Apri la demo](https://appco-6lmzj97bbbw8ndlwnvnocf.streamlit.app/)

Software dimostrativo e funzionante: si usa dal browser, senza installare nulla. Per una demo guidata, un account di prova o una valutazione sul tuo impianto: [carlo.sicurini@gmail.com](mailto:carlo.sicurini@gmail.com)

> ⚠ **Software proprietario, tutti i diritti riservati.** Il codice è pubblico solo come vetrina tecnica: questa pubblicazione non concede alcuna licenza d'uso. Vedi [Licenza](#licenza).

## Cosa fa

- **Registra** ore di funzionamento, biomasse caricate e produzione giornaliera (Sm³, MWh).
- **Confronta** lo scenario standard (UNI/TS, RED III tabellare) con lo scenario da analisi (BMT di laboratorio e fattori emissivi su misura).
- **Calcola** il risparmio GHG mensile secondo D.M. 15/09/2022, Direttive UE 2018/2001 (RED II) e 2023/2413 (RED III), JEC WTT v5, UNI/TS 11567:2024.
- **Ottimizza** il mix di biomasse con un solver di programmazione lineare, su risparmio GHG e produzione obiettivo.
- **Pianifica** i ricavi DM 2022: tariffa di riferimento e ribasso d'asta, premi, upgrading, conto capitale PNRR.
- **Esporta** report mensili e annuali in PDF, Excel, CSV e PowerPoint.

Interfaccia in italiano e inglese.

## Documentazione

| Per chi | Documento |
|---|---|
| Chi usa l'app | [Manuale utente IT](docs/user_manual/Metan.iQ_Manuale_Utente_IT.pdf) · [EN](docs/user_manual/Metan.iQ_Manuale_Utente_EN.pdf) · [Guida operativa](docs/DAILY_OPS_GUIDE.md) |
| Chi valuta il metodo | [Regole di scrittura normativa](docs/REGULATORY_WRITING_GUIDELINE.md) · [Audit e verifiche](docs/archive/) · [Novità](CHANGELOG.md) |
| Chi lavora sul codice, con autorizzazione | [Note tecniche](docs/SVILUPPO.md) |
| Aspetti legali | [Privacy](legal/privacy.md) · [Termini](legal/terms.md) |

## Licenza

**Copyright (c) 2026 Carlo Sicurini. Tutti i diritti riservati.** Testo integrale, che prevale su questa sintesi: [LICENSE](LICENSE) (IT + EN).

Sono protetti, tra l'altro, il codice sorgente, il dataset `FEEDSTOCK_DB`, i modelli di calcolo GHG, il motore di ottimizzazione, il design system, la documentazione, il nome e il logo "Metan.iQ".

Senza autorizzazione scritta è vietato:

1. copiare, riprodurre, modificare o redistribuire il software, anche in parte;
2. eseguire reverse engineering, decompilare o derivarne altri lavori;
3. usarlo per finalità commerciali, di consulenza o di analisi per terzi;
4. riutilizzare nome, logo o segni distintivi "Metan.iQ" in lavori derivati o concorrenti;
5. rimuovere o alterare gli avvisi di copyright.

La pubblicazione su GitHub non rende il software open source: il repository è pubblico per trasparenza e per la pubblicazione su Streamlit Cloud. Restano riservati tutti i diritti previsti dalla L. 633/1941 e dalle convenzioni internazionali.

Licenze commerciali, partnership, white-label, integrazioni API, uso in audit di terzi: [carlo.sicurini@gmail.com](mailto:carlo.sicurini@gmail.com)
