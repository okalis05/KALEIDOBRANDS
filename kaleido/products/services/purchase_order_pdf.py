from io import BytesIO

from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)

def generate_purchase_order_pdf(purchase_order):
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            "KaleidoBrands Supplier Purchase Order",
            styles["Title"],
        )
    )
    story.append(Spacer(1, 18))

    supplier_name = (
        purchase_order.supplier.name
        if purchase_order.supplier
        else "Unassigned Supplier"
    )

    customer_order_number = (
        purchase_order.customer_order.order_number
        if purchase_order.customer_order
        else "N/A"
    )

    story.append(
        Paragraph(
            f"<b>PO Number:</b> {purchase_order.po_number}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Supplier:</b> {supplier_name}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Customer Order:</b> {customer_order_number}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Status:</b> {purchase_order.get_status_display()}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 20))

    table_data = [
        [
            "Product",
            "Supplier SKU",
            "Qty",
            "Unit Cost",
            "Line Total",
        ]
    ]

    for item in purchase_order.items.all():
        table_data.append(
            [
                item.product_name,
                item.supplier_sku or "N/A",
                str(item.quantity),
                f"${item.unit_cost:.2f}",
                f"${item.line_total:.2f}",
            ]
        )

    items_table = Table(
        table_data,
        colWidths=[190, 100, 45, 85, 90],
    )

    items_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#004B9B"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F6F7F9"),
                    ],
                ),
            ]
        )
    )

    story.append(items_table)
    story.append(Spacer(1, 20))

    total_table = Table(
        [
            [
                "Total Supplier Cost",
                f"${purchase_order.total_cost():.2f}",
            ]
        ],
        colWidths=[370, 140],
    )

    total_table.setStyle(
        TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, 0),
                    "RIGHT",
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F2F4F7"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
            ]
        )
    )

    story.append(total_table)

    if purchase_order.notes:
        story.append(Spacer(1, 20))
        story.append(
            Paragraph(
                f"<b>Notes:</b> {purchase_order.notes}",
                styles["Normal"],
            )
        )

    document.build(story)

    pdf_content = buffer.getvalue()
    buffer.close()

    filename = f"{purchase_order.po_number}.pdf"

    purchase_order.pdf_file.save(
        filename,
        ContentFile(pdf_content),
        save=True,
    )
    log_purchase_order_activity(
        purchase_order,
        action="pdf_generated",
        message=f"PDF generated: {filename}",
    )

    return purchase_order.pdf_file