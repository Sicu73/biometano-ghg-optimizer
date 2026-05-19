# Metan.iQ — Pricing mockup (draft per iterazione)

**Stato**: bozza per validazione interna. Da iterare PRIMA di buildare Stripe.

## 🆓 Free — 0 €

Per esplorare il prodotto, scuole, tesisti.

- ✅ 1 impianto
- ✅ Inserimento dati giornalieri
- ✅ Calcolo GHG mensile (DM 2022 / RED III)
- ✅ Visualizzazione KPI base
- ⚠️ Storico limitato: **ultimi 10 mesi**
- ⚠️ Export PDF: **con watermark "Metan.iQ Free"**
- ❌ Export Excel/PPTX
- ❌ Override BMT / Fattori Emissivi su misura
- ❌ Ottimizzatore LP (solver dual-constraint)
- ❌ Business Plan & incentivi
- ❌ Multi-impianto

## 💼 Pro — 49 €/mese o 490 €/anno (sconto 17%)

Per il singolo operatore biometano.

- ✅ Tutto del Free
- ✅ Storico **illimitato** (12+ mesi, multi-anno)
- ✅ Export Excel + PDF + PPTX **senza watermark**
- ✅ **Override BMT** (laboratorio) + **Fattori Emissivi su misura**
- ✅ **Ottimizzatore LP** (solver dual-constraint)
- ✅ **Business Plan & incentivi** (DM 2022 — tariffa, premi, PNRR)
- ✅ Confronto Standard vs Analisi
- ✅ Audit log delle modifiche
- ✅ Support via email (risposta entro 2 giorni lavorativi)

## 🏢 Enterprise — 199 €/mese o 1.990 €/anno (sconto 17%)

Per consulenti energy / EPC / utility con più impianti.

- ✅ Tutto del Pro
- ✅ **Multi-impianto illimitati**
- ✅ **Multi-utente** con ruoli (admin / editor / viewer)
- ✅ **API REST** per integrazione con CRM/ERP/SCADA
- ✅ **Webhook** alert (saving sotto soglia, cap violato)
- ✅ **Esportazione white-label** (logo cliente sui report)
- ✅ **SLA 99.5%** uptime garantito
- ✅ **Support prioritario** (risposta entro 4h lavorative)
- ✅ Onboarding dedicato (1h call) + formazione

---

## Add-ons (su tutti i piani)

- **Onboarding/consulenza setup**: 500 € una tantum (per i piani Pro/Enterprise)
- **Personalizzazione report** (logo cliente, copertina custom): 200 €/anno
- **Sviluppo feature custom**: a preventivo, da 1.500 € a 10.000 €

---

## Trial

**14 giorni gratis** in modalità Pro, senza carta di credito richiesta.
Downgrade automatico a Free al termine.

---

## Note interne — domande aperte per Carlo

1. Prezzo Pro: 49€/mese è giusto? Il mercato target (operatori biogas medio-piccoli)
   ha budget per ~30-60€/mese su software, esperienza dice. Da validare con 2-3
   prospect.
2. **Sconto annuale 17%** è standard SaaS. Si può alzare al 20% per spingere
   l'annuale (commit utenti più alto, churn più basso).
3. **Free tier rischia di cannibalizzare Pro?** No, perché il watermark sui report
   è inaccettabile per chi li manda a GSE/clienti reali. Lo lascerei.
4. **Multi-impianto solo Enterprise** dà valore al tier alto. Però attenzione:
   se un consulente ha 2-3 impianti piccoli, 199€ è troppo. Eventualmente
   "Pro Multi-impianto" 99€/mese con max 3 impianti.
5. **Forme di pagamento**: Stripe accetta carta credito, SEPA Direct Debit, PayPal.
   Per ENTERPRISE valutare anche bonifico bancario con fattura prepaid (B2B IT preferisce).
6. **Sconto educational / no-profit**: 50% su Pro? Buona PR per startup/scuole.
7. **Affiliate program** (referral 20% per 12 mesi): da Fase 4 in poi.
