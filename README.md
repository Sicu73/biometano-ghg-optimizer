# Metan.iQ

> **Decision Intelligence Platform per biometano DM 2022 / RED III** —
> Pianificazione mensile, ottimizzazione GHG, business plan e reporting
> di sostenibilità per impianti di biometano e biogas cogenerativo.

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)

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
| Sprint 0 — Quick wins | ✅ Done | Pin deps, CI, theme brand, legali, Sentry |
| Fase 1 — Hardening | 🟡 In progress | Modularizzazione, test coverage, XSS audit |
| Fase 2 — SaaS core | ⬜ Todo | Auth, multi-tenancy, Stripe billing, audit log |
| Fase 3 — Marketing | ⬜ Todo | Landing page, onboarding wizard, docs |
| Fase 4 — Scale | ⬜ Todo | API REST, webhook, AI advisor, mobile PWA |

## 📜 Licenza

**Software proprietario** — All Rights Reserved. Vedi [LICENSE](LICENSE).

Per licenze commerciali, partnership o collaborazioni:
**Carlo Sicurini** — carlo.sicurini@gmail.com

## 🔒 Privacy

Vedi [legal/privacy.md](legal/privacy.md). GDPR compliant.

---

*Made with ❤️ in Italy — Decision Intelligence per la transizione energetica.*
