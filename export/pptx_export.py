import io
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    _HAS_PPTX = True
except ImportError:
    _HAS_PPTX = False

def _fmt_num(value, decimals=0, suffix=""):
    if value is None: return "N/D"
    try:
        if decimals == 0:
            formatted = f"{value:,.0f}".replace(",", "'")
        else:
            fmt_str = f"{{:,.{decimals}f}}"
            formatted = fmt_str.format(value).replace(",", "'").replace(".", ",")
            # fix reversed comma/dot for thousands and decimals
            parts = formatted.split(",")
            if len(parts) > 1:
                formatted = parts[0].replace("'", ".") + "," + parts[1]
            else:
                formatted = parts[0].replace("'", ".")
        return formatted + suffix
    except:
        return str(value)

def build_metaniq_pptx(ctx: dict) -> io.BytesIO:
    if not _HAS_PPTX:
        raise ImportError("python-pptx non e' installato. Aggiungilo a requirements.txt (python-pptx>=0.6.21).")
        
    prs = Presentation()
    
    def add_slide(title, lines):
        layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(layout)
        title_shape = slide.shapes.title
        title_shape.text = title
        body = slide.placeholders[1]
        tf = body.text_frame
        for i, text in enumerate(lines):
            p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
            p.text = text
            p.font.size = Pt(18)
        return slide

    # Slide 1: Titolo
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Metan.iQ - Report di Sostenibilita' e Business Plan"
    subtitle = slide.placeholders[1]
    subtitle.text = "Sintesi automatica del progetto (RED III & DM 2022)"

    # Extraction
    ghg_saving = ctx.get("saving_avg", 0.0)
    mwh = ctx.get("tot_mwh_basis", 0.0)
    rev = ctx.get("tot_revenue", 0.0)
    taglia = ctx.get("plant_net_smch", 300.0)
    aux = ctx.get("aux_factor", 1.29)
    valid_months = ctx.get("valid_months", 0)
    compliant = ghg_saving >= 80 and valid_months == 12

    # Slide 2: Executive Summary
    add_slide("1. Executive Summary", [
        f"• Saving GHG Medio Annuo: {_fmt_num(ghg_saving, 1, '%')}",
        f"• Conformita' RED III: {'VERIFICATA' if compliant else 'NON CONFORME'}",
        f"• Energia Netta Immessa: {_fmt_num(mwh, 0, ' MWh/anno')}",
        f"• Ricavi Stimati: {_fmt_num(rev, 0, ' €/anno')}",
    ])

    # Slide 3: Configurazione Impianto
    add_slide("2. Configurazione Impianto", [
        f"• Taglia Netta Autorizzata: {_fmt_num(taglia, 0, ' Sm3/h')}",
        f"• Fattore Ausiliari (CHP/Caldaia): {_fmt_num(aux, 2)}",
        f"• Assetto: {'Cogeneratore (CHP)' if ctx.get('IS_CHP') else 'Immissione in Rete (Biometano)'}",
    ])

    # Slide 4: Mix Biomasse
    tot_tonnes = ctx.get("tot_biomasse_t", 0.0)
    add_slide("3. Mix Biomasse", [
        f"• Fabbisogno Totale: {_fmt_num(tot_tonnes, 0, ' t/anno')}",
        "Il dettaglio del mix e' disponibile nel report PDF avanzato.",
        "Le quantita' sono calcolate per soddisfare sia la quota netta che gli ausiliari."
    ])

    # Slide 5: Bilancio Produttivo
    add_slide("4. Bilancio Produttivo", [
        f"• Energia Netta: {_fmt_num(mwh, 0, ' MWh/anno')}",
        f"• Base Calcolo GHG (Lordo): {_fmt_num(taglia * aux, 0, ' Sm3/h equivalenti')}",
    ])

    # Slide 6: Sostenibilita' GHG
    add_slide("5. Sostenibilita' GHG (Analisi Emissioni)", [
        "Metodologia RED III (Direttiva 2023/2413/UE)",
        "Valori eec, esca, etd calcolati ponderando le biomasse in ingresso.",
        f"• Emissioni Comparatore Fossile: {ctx.get('fossil_comparator', 94.0)} gCO2eq/MJ",
    ])

    # Slide 7: Conformita' RED III
    add_slide("6. Conformita' RED III", [
        f"• Saving Ottenuto: {_fmt_num(ghg_saving, 1, '%')}",
        f"• Soglia Normativa: {_fmt_num(ctx.get('ghg_threshold', 0.8)*100, 1, '%')}",
        f"• Mesi conformi (Target > Soglia): {valid_months}/12",
        f"• Esito Complessivo: {'IDONEO' if compliant else 'NON IDONEO'}",
    ])

    # Slide 8: Quadro Incentivi
    tariffa = ctx.get("tariffa_media_ponderata", 0.0)
    add_slide("7. Quadro Incentivi (DM 2022)", [
        f"• Tariffa Media Ponderata Aggiudicata: {_fmt_num(tariffa, 2, ' €/MWh')}",
        "Il valore considera il ribasso d'asta e la tipologia di impianto."
    ])

    # Slide 9: Struttura Ricavi
    add_slide("8. Struttura Ricavi", [
        f"• Ricavo Totale Annuo: {_fmt_num(rev, 0, ' €/anno')}",
        f"• Valore Cumulato a 15 anni: {_fmt_num(rev * 15, 0, ' €')}",
    ])

    # Slide 10: Quadro CAPEX
    bp = ctx.get("bp_result") or {}
    capex = bp.get("capex_totale", 0.0) if isinstance(bp, dict) else 0.0
    add_slide("9. Quadro CAPEX (Investimenti)", [
        f"• CAPEX Totale Stimato: {_fmt_num(capex, 0, ' €')}" if capex > 0 else "• Dati CAPEX non configurati o non disponibili nel contesto attuale."
    ])

    # Slide 11: Quadro OPEX
    opex_list = bp.get("opex", []) if isinstance(bp, dict) else []
    avg_opex = sum(opex_list)/len(opex_list) if opex_list else 0.0
    add_slide("10. Quadro OPEX (Costi Operativi)", [
        f"• OPEX Medio Annuo: {_fmt_num(avg_opex, 0, ' €/anno')}" if avg_opex > 0 else "• Dati OPEX non configurati."
    ])

    # Slide 12: Profilo Produzione
    add_slide("11. Profilo Produzione Mensile", [
        "Il modello garantisce un profilo mensile conforme, ricalcolando gli input",
        "in base ai vincoli stagionali o alla disponibilita' delle biomasse."
    ])

    # Slide 13: Indicatori Finanziari
    ebitda_list = bp.get("ebitda", []) if isinstance(bp, dict) else []
    avg_ebitda = sum(ebitda_list)/len(ebitda_list) if ebitda_list else 0.0
    add_slide("12. Indicatori Finanziari", [
        f"• EBITDA Medio Annuo: {_fmt_num(avg_ebitda, 0, ' €/anno')}" if avg_ebitda > 0 else "• EBITDA non calcolato in questa configurazione."
    ])

    # Slide 14: Analisi di Sensitivita'
    add_slide("13. Analisi di Sensitivita'", [
        "Variazioni del mix di biomasse (es. incremento pollina/reflui)",
        "possono aumentare il margine di sicurezza sul saving GHG",
        "e ottimizzare i costi operativi (OPEX) complessivi."
    ])

    # Slide 15: Conclusioni
    add_slide("14 & 15. Conclusioni e Raccomandazioni", [
        "Il progetto simulato " + ("rispetta " if compliant else "NON rispetta ") + "i parametri RED III.",
        "Si raccomanda di monitorare mensilmente l'approvvigionamento",
        "delle biomasse tramite il registro ufficiale."
    ])

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
