from io import BytesIO

from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_order_invoice_pdf(order):
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

    story.append(Paragraph("KaleidoBrands Invoice", styles["Title"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"<b>Order Number:</b> {order.order_number}", styles["Normal"]))
    story.append(Paragraph(f"<b>Customer:</b> {order.customer.get_full_name() or order.customer.username}", styles["Normal"]))
    story.append(Paragraph(f"<b>Company:</b> {order.company or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Status:</b> {order.get_status_display()}", styles["Normal"]))
    story.append(Spacer(1, 20))

    data = [["Product", "SKU", "Qty", "Unit Price", "Line Total"]]

    for item in order.items.all():
        data.append([
            item.product_name,
            item.sku or "N/A",
            str(item.quantity),
            f"${item.unit_price}",
            f"${item.line_total}",
        ])

    table = Table(data, colWidths=[200, 90, 50, 80, 90])
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

    totals = [
        ["Subtotal", f"${order.subtotal}"],
        ["Shipping", f"${order.shipping}"],
        ["Tax", f"${order.tax}"],
        ["Total", f"${order.total}"],
    ]

    totals_table = Table(totals, colWidths=[360, 120])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f6f7f9")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d5dd")),
    ]))

    story.append(totals_table)

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"invoice-{order.order_number}.pdf"
    order.invoice_pdf.save(filename, ContentFile(pdf), save=True)

    return order.invoice_pdf