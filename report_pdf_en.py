from io import BytesIO


def build_metaniq_pdf_en(ctx: dict) -> BytesIO:
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph('Metan.iQ - English Report', styles['Title'])]
    doc.build(story)
    buf.seek(0)
    return buf
