# Metan.iQ

> **Decision Intelligence Platform per biometano DM 2022 / RED III** —
> Pianificazione mensile, ottimizzazione GHG, business plan e reporting
> di sostenibilità per impianti di biometano da digestione anaerobica
> con immissione in rete.

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)

> ⚠ **Software proprietario — All Rights Reserved.** Codice sorgente, dataset
> FEEDSTOCK, modelli di calcolo GHG, motore di ottimizzazione e marchio
> "Metan.iQ" sono di proprietà esclusiva di Carlo Sicurini. La pubblicazione
> di questo repository su GitHub **non concede alcuna licenza d'uso**: copia,
> redistribuzione, fork, reverse engineering e uso commerciale sono vietati
> senza autorizzazione scritta. Vedi [LICENSE](LICENSE) e la sezione
> [Licensing](#-licensing--ip) per i dettagli.

---

## 🎯 Cosa fa

Metan.iQ aiuta gli operatori di impianti biometano a:

- 📆 **Tracciare** ore di funzionamento, biomasse caricate e produzione
  giornaliera (Sm³, MWh) con auto-save su DB locale.
- 🧪 **Confrontare** scenari Standard (UNI-TS / RED III tabellare) vs
  Analisi (BMT lab + Fattori Emissivi su misura).
- 🌍 **Calcolare** il saving GHG mensile secondo D.M. 15/09/2022, Direttive
  UE 2018/2001 (RED II) e 2023/2413 (RED III), JEC WTT v5, UNI-TS 11567:2024.
- ⚡ **Ottimizzare** il mix biomasse con solver LP dual-constraint
  (saving GHG + produzione target).
- 💶 **Pianificare** ricavi DM 2022: tariffa di riferimento + ribasso d'asta,
  premi matrice (cumulabili), upgrading, PNRR conto capitale.
- 📊 **Esportare** report mensili (PDF brand Metan.iQ, Excel 6 fogli,
  CSV) e annuali (Excel modificabile, PPTX 8 slide).

## 🏗️ Stack tecnico

- **Frontend / runtime**: Streamlit 1.57+ (Python)
- **Calcoli**: NumPy, SciPy (solver LP), pandas
- **Visualizzazione**: Plotly, custom HTML/CSS Material 3
- **Export**: ReportLab (PDF), openpyxl (Excel), python-pptx (PowerPoint)
- **Persistenza**: SQLite locale per utente (Fase 2: migrazione a Postgres
  multi-tenant)
- **i18n**: dict-based IT/EN con substring replacement, locale-aware
  formatting per numeri (`1,234.56` EN / `1.234,56` IT) e date
  (`May 25, 2026` EN / `25/05/2026` IT)
- **Theme**: light/dark switcher (palette navy + amber, font Outfit)
- **Hosting**: Streamlit Cloud (privato, auth-gated)

## 🚀 Quick start

### Prerequisiti
- Python 3.11+
- pip / virtualenv

### Installazione locale

```bash
git clone https://github.com/Sicu73/biometano-ghg-optimizer.git
cd biometano-ghg-optimizer
pip install -e .
streamlit run app_mensile.py
```

### Dipendenze di sviluppo

```bash
pip install -e ".[dev]"
pytest tests/         # 65+ test
ruff check .          # linting
mypy core/            # type checking
```

### Deploy Streamlit Cloud

1. Fork del repo (privato) sul tuo account.
2. Collega l'app a Streamlit Cloud → Settings → connetti il repo.
3. **Secrets**: copia `.streamlit/secrets.toml.example` in
   `.streamlit/secrets.toml`, popola e incolla su **Manage app → Settings
   → Secrets**.

## 🗂️ Struttura repo

```
biometano-ghg-optimizer/
├── app_mensile.py              # Main Streamlit app (TODO: split in app/)
├── core/                       # Logica di dominio (calcolo, persistenza, i18n)
│   ├── daily_model.py          # DailyEntry, compute_daily()
│   ├── monthly_aggregate.py    # aggregate_month(), MonthlyAggregate
│   ├── sustainability.py       # evaluate_monthly_sustainability()
│   ├── persistence.py          # SQLite save/load (TODO: multi-tenant)
│   ├── i18n.py                 # core i18n
│   ├── design_tokens.py        # palette colors
│   ├── version.py              # __version__
│   └── logging_setup.py        # logger + Sentry init
├── output/                     # KPI builder, tabelle, spiegazioni
├── export/                     # Excel / PDF / CSV / PPTX builders
│   ├── daily_pdf.py            # Report PDF mensile brand
│   ├── daily_excel.py          # Excel 6 fogli
│   └── ...
├── tests/                      # 10 file pytest (~150 test)
├── legal/
│   ├── privacy.md              # GDPR Privacy Policy
│   ├── terms.md                # ToS
│   └── PRICING.md              # piani Free/Pro/Enterprise (draft)
├── docs/archive/               # documenti di audit/storia
├── .streamlit/
│   ├── config.toml             # theme brand + server config
│   └── secrets.toml.example    # template secrets
├── .github/workflows/
│   └── test.yml                # CI: ruff + mypy + pytest
├── pyproject.toml              # metadata + config strumenti
├── requirements.txt            # pin dipendenze runtime
├── LICENSE                     # All Rights Reserved (proprietary)
└── README.md                   # questo file
```

## 🛣️ Roadmap

Vedi `~/.claude/plans/continua-il-lavoro-su-sunny-rainbow.md` per il piano
completo. In sintesi:

| Fase | Status | Contenuto |
|---|---|---|
| Sprint 0 — Quick wins | ✅ Done | Pin deps, CI, theme brand, legali, Sentry attivo in prod |
| Fase 1 — Hardening | ✅ Done | XSS audit, formatting locale-aware (`core/formatting.py`), 143+ test |
| **Fase 2 — SaaS core** | ✅ **Done** | Auth bcrypt+JWT (`core/auth.py`), multi-tenant DB row-level isolation (`core/persistence.py`), Stripe billing wrapper (`core/billing.py`), audit log SQLite (`core/audit.py`), UI signup/login + account panel (`core/auth_ui.py`), trial auto-downgrade. Demo mode attivo di default |
| Fase 3 — Marketing | ⬜ Todo | Landing page, onboarding wizard, docs, casi studio |
| Fase 4 — Scale | ⬜ Todo | API REST, webhook, AI advisor, mobile PWA, hosting dedicato |

### 🚀 Per attivare la modalità SaaS commerciale

L'app è in **demo mode** di default → tutti vedono tutto, niente login.

Per passare in produzione SaaS:
1. Genera un JWT secret random (es. `openssl rand -hex 32`)
2. (Opzionale) Crea account Stripe + 4 price su Dashboard
3. Streamlit Cloud → **Settings → Secrets**, aggiungi:
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
4. Reboot app → gate signup/login attivo, multi-tenant isolation, billing.

## 📜 Licensing & IP

**Software proprietario — All Rights Reserved.**
Copyright (c) 2026 Carlo Sicurini. Testo completo: [LICENSE](LICENSE) (IT + EN).

### Cosa è protetto

- Codice sorgente di `app_mensile.py`, `core/`, `export/`, `output/`, `tests/`
- Dataset `FEEDSTOCK_DB` (42 biomasse con rese, FE, classificazione RED III)
- Costanti e fattori cablati in [core/constants.py](core/constants.py)
  (LHV, FFC, soglie saving, GWP, default aux factor JRC-CONCAWE)
- Motore di calcolo GHG (`ghg_summary`, `compute_daily`, `aggregate_month`,
  `e_total_feedstock`) e solver di ottimizzazione mix biomasse
- Design system Metan.iQ (palette navy/amber, font Outfit, template PDF/PPTX)
- Logo, naming, claim e marchio "Metan.iQ"
- Manuale utente e documentazione tecnica in `docs/user_manual/`

### Cosa NON è consentito senza autorizzazione scritta

1. Copiare, riprodurre, modificare o redistribuire il Software, anche parziale
2. Eseguire reverse engineering, decompilare o creare opere derivate
3. Usare il Software per finalità commerciali, consulenza o analisi per terzi
4. Riutilizzare nome, logo o segni distintivi "Metan.iQ" in prodotti concorrenti
5. Rimuovere o alterare gli header di copyright presenti nei file sorgente

### Pubblicazione su GitHub ≠ Open Source

Il repository è pubblico per ragioni di trasparenza e deploy su Streamlit
Cloud. **Non è rilasciato con licenza open source.** L'assenza di una licenza
permissiva (MIT, Apache, GPL) implica per default tutti i diritti riservati
ai sensi del diritto d'autore italiano (L. 633/1941) e internazionale
(Berne Convention, TRIPS).

### Contatto licensing

Per **licenze commerciali**, **partnership**, **white-label**, **integrazioni
API** o uso in **audit di terzi**:

**Carlo Sicurini** — [carlo.sicurini@gmail.com](mailto:carlo.sicurini@gmail.com)

## 🔒 Privacy

Vedi [legal/privacy.md](legal/privacy.md). GDPR compliant.

---

*Made with ❤️ in Italy — Decision Intelligence per la transizione energetica.*
