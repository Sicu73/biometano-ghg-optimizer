# Linee guida per microcopy normativo Metan.iQ

> **Trigger di applicazione**: ogni volta che scrivi una stringa nell'app
> che cita una norma, un articolo, una soglia, o un valore €/MWh, prima
> di committare verifica che rispetti le 7 regole sotto.

## Background

Il **20/05/2026** abbiamo subito un audit interno che ha bocciato microcopy
in cui valori €/MWh dei premi cumulabili erano presentati come quote fisse
del DM 15/9/2022 quando in realtà sono **stime di mercato/contratto**
editabili. Safety score 43% (target 90%).

Questo documento codifica le regole per evitare regressioni. Per ottimizzazione
automatica via prompt optimization vedi anche il preset
[`compliance-normativa-DM2022`](file:///C:/Users/CarloSicurini/.claude/skills/teca-evolution/presets/compliance-normativa-DM2022/)
nel sistema teca-evolution.

## Le 7 regole

### 1. ❌ NON inventare numeri normativi

**Sbagliato**:
> "Premio matrice +8 €/MWh secondo DM 2022"

**Giusto**:
> "Stima del beneficio economico per biometano avanzato. Dipende dal
> mercato CIC (60-120 €/CIC tipico, non garantito). NON è quota DM 2022."

### 2. 🔍 Distingui sempre norma vs mercato vs default

| Tipo dato | Pattern obbligatorio |
|---|---|
| Quota normativa fissa | "previsto dall'art. N del DM 15/9/2022" |
| Valore di mercato | "valore tipico €/CIC, variabile" + range |
| Default UI editabile | "valore editabile, personalizza" |

### 3. 📚 Cita SOLO articoli verificabili

**Citazioni VALIDE**:
- ✅ `DM 15/9/2022 Allegato 1`
- ✅ `RED III All. V Parte C`
- ✅ `UNI-TS 11567:2024 §6.2`
- ✅ `GSE Linee Guida 2024 cap. 3`
- ✅ `D.Lgs. 5/2026`
- ✅ `Dir. (UE) 2023/2413`

**Citazioni AMBIGUE da evitare**:
- ❌ "DM 2022 art. 4-5" (verificare comma esatto)
- ❌ "Secondo la normativa" (senza articolo)
- ❌ "Previsto per legge" (vago)

### 4. 📐 Terminologia corretta

| Sigla | Significato completo |
|---|---|
| **TR** | Tariffa di Riferimento (Allegato 1 DM 2022) |
| **TP** | Tariffa Premio (solo incentivo, gas venduto separatamente) |
| **TO** | Tariffa Onnicomprensiva (GSE ritira gas + emette tariffa) |
| **CIC** | Certificato di Immissione in Consumo (mercato trasporti) |
| **GO** | Garanzia di Origine (mercato elettrico/gas) |
| **EP** | Emissioni di Processo (gCO₂eq/MJ) |
| **Annex IX** | Allegato IX RED III — matrici avanzate |

### 5. 📅 Riferimenti aggiornati

| ❌ Obsoleto | ✅ Attuale |
|---|---|
| CIP 6 | (cessato 2007) |
| FER 1 (DM 6/7/2012) | DM 2022 per biometano · DM 19/6/2024 per CHP <300kW |
| DM 2018 (CIC) | (sostituito da DM 2022 per nuovi impianti) |
| Direttiva 2018/2001 RED II | Dir. (UE) 2023/2413 RED III |
| UNI-TS 11567:2018 | UNI-TS 11567:2024 |

### 6. 🎯 User actionability

Ogni microcopy normativa DEVE indicare cosa fare:
- "Verifica nel tab **Mix annuale** la quota Annex IX"
- "Personalizza nel form **Configurazione**"
- "Carica certificato nel pannello **Override BMT**"
- "Documenta in **Relazione Tecnica** per audit GSE"

### 7. 🌐 Bilingue coerente

| Termine IT | EN preferito | EN da evitare |
|---|---|---|
| biometano | biomethane | biogas (è il pre-upgrading) |
| biomassa | feedstock | raw material, biomass (ambiguo) |
| saving GHG | sustainability saving | GHG reduction (giuridicamente diverso) |
| matrice avanzata | advanced feedstock | premium feedstock |
| comparator fossile | fossil fuel comparator | benchmark |

## Verifica automatica

Per stringhe critiche (>5 righe normative), gira la scoring function:

```python
import sys
sys.path.insert(0, str(Path.home() / ".claude/skills/teca-evolution/presets/compliance-normativa-DM2022"))
from metric import score

s = score("la mia microcopy candidata")
print(f"Score: {s['total']}/100  Safety: {s['safety']*100}%")
assert s['safety'] >= 0.90, f"Safety sotto target: {s['flags']}"
```

Target prima del commit:
- **Total score** ≥ 75/100
- **Safety score** ≥ 90% (no flag `hallucination_clean`)
- **Zero flag** rosse

## Esempi di "prima/dopo" — case study premi cumulabili

### Prima (audit 20/05/2026, score 62/100, safety 40%)

> Sono **incentivi aggiuntivi** che si sommano alla **TR aggiudicata**.
> Premio matrici DM 15/9/2022 art. 4-5: Sottoprodotti agricoli 10-15 €/MWh,
> Effluenti zootecnici 8-12 €/MWh.

### Dopo (commit `ef42c4b`, score 84/100, safety 100%)

> ⚠️ **Importante**: i valori €/MWh qui sotto NON sono quote fisse previste
> dal DM 15/9/2022, ma **stime indicative** del beneficio economico
> aggiuntivo ottenibile per due categorie di impianto: (1) biometano
> **avanzato** (matrici Allegato IX RED III) con accesso al mercato CIC,
> (2) upgrading con tecnologie qualificate. Personalizza in base al
> contratto specifico e all'andamento del mercato CIC.

**Delta**: +22 punti score, +60 punti safety.
