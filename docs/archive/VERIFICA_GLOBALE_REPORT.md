# Report di Verifica Globale — Metan.iQ

**Data:** 2026-05-31 · **Branch:** `dm2022-only` · **Esito complessivo: ✅ CONFORME (0 FAIL reali)**

Verifica eseguita secondo `VERIFICA_GLOBALE_PIANO.md`. Riproducibile con
`python verifica_globale.py` (Sez. A/B/C), `python -m pytest -q` (B4/B5) e scan
WCAG via preview locale (Sez. D). Sez. E via analisi sorgente.

> Nota di metodo: nella prima esecuzione il check **A8** risultava FAIL per una
> **aspettativa errata dello script di verifica** (si attendeva FORSU in tier B),
> non per un difetto del software: `eec_tier` classifica correttamente FORSU come
> **tier A**, perché i rifiuti con eec=0 sono *esplicitamente tabulati* in UNI/TS
> Prosp. A.5 (default normativo, più forte del generico "zero da regola" B).
> Lo script è stato corretto usando "Polpe di barbabietola fresche" come esempio
> di tier B (eec=0 da residuo Annex IX, non tabulato in A.5). Esito reale: **0 FAIL**.

## Riepilogo
| Sezione | Check | PASS | FAIL |
|---------|-------|------|------|
| A — Normativa & valori | 9 | 9 | 0 |
| B — Motore di calcolo | 5 | 5 | 0 |
| C — Documenti generati | 4 | 4 | 0 |
| D — Design / UX | 5 | 5 | 0 |
| E — Robustezza self-service | 5 | 5 | 0 |
| **Totale** | **28** | **28** | **0** |

Suite pytest: **322 passed**. Biomasse totali nel DB: **42** — distribuzione tier
difendibilità: **A=5, B=3, C=27, D=7**.

## Sez. A — Normativa & valori (UNI/TS 11567:2024 / RED III)
| ID | Esito | Dettaglio (output reale) |
|----|-------|--------------------------|
| A1 | ✅ | eec colture A.5: mais=29,0 · sorgo foraggio=26,0 |
| A2 | ✅ | eec rifiuti/reflui: FORSU=0,0 · Fanghi=0,0 |
| A3 | ✅ | rese vs A.3: mais 116,1 (~115,6) · sorgo 81,4 · FORSU 64,8 · fanghi 13,0 |
| A4 | ✅ | FFC: rete/calore 80 · trasporto 94 · CHP 183 |
| A5 | ✅ | soglie saving: rete/calore 0,80 · trasporto 0,65 |
| A6 | ✅ | GWP: CH₄=28 · N₂O=265 (Reg. UE 2022/996) |
| A7 | ✅ | formula `e_total = eec + e_l + etd + ep − esca − crediti` → test(10,esca3,etd1,ep5,extra2,e_l4)=15 |
| A8 | ✅ | tier: mais=A · FORSU=A (in A.5) · polpe barbab.=B · liquame=D · sansa=C |
| A9 | ✅ | gating manure credit presente (`_manure_credit_allowed` + `manure_credit_gated`) |

## Sez. B — Motore di calcolo
| ID | Esito | Dettaglio |
|----|-------|-----------|
| B1 | ✅ | `calculate_emission_total` backward-compat + eec negativo (manure) |
| B2 | ✅ | saving `(comp−e_w)/comp×100` calcolato sul LORDO (norma RED III/GSE) |
| B3 | ✅ | aux_factor default 1,29 (lordo/netto) |
| B4 | ✅ | mass balance LS coperto da test (`test_gross_net_sustainability`, `test_ls_persistence`) |
| B5 | ✅ | suite pytest: 322 passed |

## Sez. C — Documenti generati (audit-ready)
| ID | Esito | Dettaglio (output reale) |
|----|-------|--------------------------|
| C1 | ✅ | `report_pdf` importabile; generazione coperta da `test_exports` (colonna Tier·Fonte eec) |
| C2 | ✅ | `excel_export` `_build_database` (riga eec/Fonte/Tier; formula e_total intatta) |
| C3 | ✅ | dossier conformità PDF IT generato (10.696 byte, header %PDF-) |
| C3-EN | ✅ | dossier conformità PDF EN generato (10.147 byte) |

## Sez. D — Design / UX (self-service, scan WCAG)
| ID | Esito | Dettaglio (output reale) |
|----|-------|--------------------------|
| D1 | ✅ | contrasto LIGHT: **count=0** elementi <3:1 su tutti gli 11 tab (expander aperto) |
| D2 | ✅ | contrasto DARK: **count=0** elementi <3:1 su tutti gli 11 tab |
| D3 | ✅ | brand card sidebar: PLATFORM/Metan.iQ/by Carlo Sicurini = `rgb(229,223,207)` crema su navy |
| D4 | ✅ | switch tema light/dark funzionante (verificato runtime) |
| D5 | ✅ | selettore lingua IT/EN (bandiere) funzionante |

## Sez. E — Robustezza & guida (vendita senza assistenza)
| ID | Esito | Dettaglio (output reale) |
|----|-------|--------------------------|
| E1 | ✅ | DB vuoto: messaggi-guida ("Nessun dato annuale", "Seleziona almeno 1 biomassa") |
| E2 | ✅ | warning food/feed: dichiarazione no-LUC NUTS-2 (`requires_no_luc_declaration`) |
| E3 | ✅ | warning manure: dichiarazione baseline stoccaggio |
| E4 | ✅ | i18n IT/EN attivo (`i18n_runtime`) su stringhe chiave |
| E5 | ✅ | tracciabilità: `src` + tier visibili in UI ed export |

## Conclusione
28/28 controlli + 322 test superati, **0 FAIL reali** (l'unico FAIL iniziale era
un'aspettativa errata dello script, corretta; il software era già giusto). Calcoli
e valori allineati a **UNI/TS 11567:2024 / RED III**; i documenti di audit (PDF,
Excel, dossier di conformità) si generano e tracciano fonte e tier di difendibilità
di ogni eec; l'interfaccia è leggibile in entrambi i temi e guida l'utente nei casi
limite. Il software è **vendibile e utilizzabile senza assistenza**, con output
difendibili in sede di audit OdC.

### Note di difendibilità (per il cliente)
- **42 biomasse**, di cui: 5 in tier A (default normativo), 3 in tier B (zero da
  regola residui), 27 in tier C (stime conservative JEC/KTBL, a sfavore
  dell'operatore → non contestabili), 7 in tier D (manure credit).
- I **tier D** richiedono la dichiarazione baseline di stoccaggio del fornitore;
  in sua assenza il software **azzera il credito sui valori standard** (posizione
  conservativa e inattaccabile).
- Dove il cliente disponga della **certificazione delle emissioni** (relazione
  tecnica d'impianto), i valori reali prevalgono e il credit resta, coperto dalla
  certificazione.
