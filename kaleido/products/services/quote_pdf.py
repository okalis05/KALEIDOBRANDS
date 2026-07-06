from io import BytesIO

from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def generate_quote_pdf(quote):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("KaleidoBrands Quote Request", styles["Title"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"<b>Customer:</b> {quote.customer_name}", styles["Normal"]))
    story.append(Paragraph(f"<b>Company:</b> {quote.company or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Email:</b> {quote.email}", styles["Normal"]))
    story.append(Paragraph(f"<b>Phone:</b> {quote.phone or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Project:</b> {quote.project_name or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Deadline:</b> {quote.deadline or 'N/A'}", styles["Normal"]))
    story.append(Spacer(1, 20))

    data = [["Product", "Category", "Qty", "Notes"]]

    for item in quote.items.all():
        data.append([
            item.product_name,
            item.category or "N/A",
            str(item.quantity),
            item.notes or "",
        ])

    table = Table(data, colWidths=[180, 120, 60, 180])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004b9b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d5dd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7f9")]),
    ]))

    story.append(table)
    story.append(Spacer(1, 20))

    if quote.notes:
        story.append(Paragraph("<b>Additional Notes</b>", styles["Heading3"]))
        story.append(Paragraph(quote.notes, styles["Normal"]))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"quote-{quote.id}.pdf"
    quote.pdf_file.save(filename, ContentFile(pdf), save=True)

    return quote.pdf_file