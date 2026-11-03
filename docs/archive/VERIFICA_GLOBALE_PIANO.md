# Piano di Verifica Globale — Metan.iQ (vendibilità senza assistenza)

Obiettivo: certificare che il software sia **corretto, conforme UNI/TS 11567:2024 /
RED III, robusto e leggibile**, così da poter essere venduto e usato in autonomia
dal cliente, e difendibile in sede di audit OdC (RINA/SGS/ISCC) **senza supporto**.

Riferimenti: UNI/TS 11567:2024, RED III (Dir. UE 2023/2413), D.Lgs 199/2021,
Reg. (UE) 2022/996, GSE Regole Applicative DM 2022, JEC WTT v5.

Legenda esito: ✅ conforme · ⚠️ attenzione/nota · ❌ non conforme (da correggere).

---

## SEZIONE A — Normativa & valori tabellari
| ID | Verifica | Criterio di accettazione | Metodo |
|----|----------|--------------------------|--------|
| A1 | eec colture in A.5 | Mais=29, Sorgo=26 (Prosp. A.5) | lettura FEEDSTOCK_DB |
| A2 | eec rifiuti/reflui | FORSU=0, Fanghi=0, reflui std A.5=0 | lettura FEEDSTOCK_DB |
| A3 | Rese vs A.1/A.3 | resa = resa_biogas×%CH₄×ST (mais/sorgo/FORSU/fanghi) | calcolo |
| A4 | Comparatori FFC | rete/calore 80 · trasporto 94 · CHP 183 | core/constants.py |
| A5 | Soglie saving GHG | rete/calore 80% (nuovi) · trasporto 65% · CHP 80% | core/constants.py |
| A6 | GWP | CH₄=28, N₂O=265 (Reg 2022/996) | costanti |
| A7 | Formula GHG | e_total = eec + e_l + etd + ep − esca − crediti | emission_factors_override |
| A8 | Tier difendibilità | ogni eec classificato A/B/C/D coerentemente | eec_tier |
| A9 | Manure credit gating | credito negativo azzerato su std senza dichiarazione | _emission_factors_of |

## SEZIONE B — Motore di calcolo
| ID | Verifica | Criterio | Metodo |
|----|----------|----------|--------|
| B1 | calculate_emission_total | segni e somma corretti, e_l incluso | unit test |
| B2 | ghg_summary | saving=(comp−e_w)/comp×100, e_w sul LORDO | lettura + test |
| B3 | aux_factor | lordo/netto, default 1.29, ricalcolo bilancio | lettura |
| B4 | Mass balance LS | aggregazione mensile coerente (±15%, 6 mesi) | test |
| B5 | Suite test | 322/322 pass | pytest |

## SEZIONE C — Documenti generati (audit-ready)
| ID | Verifica | Criterio | Metodo |
|----|----------|----------|--------|
| C1 | Report PDF | genera senza crash; colonna "Tier · Fonte eec"; mass balance 5 col | build |
| C2 | Excel export | genera; foglio Database con riga eec/Fonte/Tier; formula e_total intatta | build |
| C3 | Dossier conformità PDF | genera; quadro normativo + legenda tier + catalogo biomasse | build |
| C4 | PPTX / CSV | generano senza crash | build |

## SEZIONE D — Design / UX (self-service)
| ID | Verifica | Criterio | Metodo |
|----|----------|----------|--------|
| D1 | Contrasto light | 0 elementi < 3:1 su tutti i tab | scan WCAG |
| D2 | Contrasto dark | 0 elementi < 3:1 su tutti i tab | scan WCAG |
| D3 | Brand card sidebar | testo chiaro su navy leggibile (light+dark) | inspect |
| D4 | Switch tema | light/dark funzionante | runtime |
| D5 | Lingua IT/EN | selettore bandiere funzionante | runtime |

## SEZIONE E — Robustezza & guida utente (vendita senza assistenza)
| ID | Verifica | Criterio | Metodo |
|----|----------|----------|--------|
| E1 | DB vuoto | nessun crash, messaggi guida | runtime |
| E2 | Warning food/feed | avviso dichiarazione no-LUC NUTS-2 | lettura |
| E3 | Warning manure | avviso dichiarazione baseline stoccaggio | lettura |
| E4 | i18n coverage | stringhe chiave tradotte IT/EN | check |
| E5 | Tracciabilità fonti | src + tier visibili in UI e export | verificato C1-C3 |

---

## Esecuzione
Gli esiti reali sono riportati in `VERIFICA_GLOBALE_REPORT.md`.
