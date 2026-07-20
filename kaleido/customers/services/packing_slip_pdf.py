from io import BytesIO

from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def safe_value(value, fallback="N/A"):
    if value in (None, ""):
        return fallback

    return str(value)


def generate_packing_slip_pdf(shipment):
    """
    Generate and save a packing-slip PDF for a shipment.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
        title=f"Packing Slip {shipment.shipment_number}",
        author="KaleidoBrands",
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            "KaleidoBrands",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            "Promotional Products and Brand Solutions",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 18))

    story.append(
        Paragraph(
            "PACKING SLIP",
            styles["Heading1"],
        )
    )

    story.append(Spacer(1, 12))

    order = shipment.order
    customer = order.customer

    customer_name = (
        customer.get_full_name()
        or customer.username
    )

    shipment_details = [
        [
            Paragraph("<b>Shipment Number</b>", styles["Normal"]),
            safe_value(shipment.shipment_number),
        ],
        [
            Paragraph("<b>Order Number</b>", styles["Normal"]),
            safe_value(order.order_number),
        ],
        [
            Paragraph("<b>Customer</b>", styles["Normal"]),
            safe_value(customer_name),
        ],
        [
            Paragraph("<b>Company</b>", styles["Normal"]),
            safe_value(order.company, "—"),
        ],
        [
            Paragraph("<b>Shipping Method</b>", styles["Normal"]),
            safe_value(
                shipment.shipping_method.name
                if shipment.shipping_method
                else order.shipping_method_name,
                "Not assigned",
            ),
        ],
        [
            Paragraph("<b>Carrier</b>", styles["Normal"]),
            safe_value(shipment.carrier, "Not assigned"),
        ],
        [
            Paragraph("<b>Tracking Number</b>", styles["Normal"]),
            safe_value(
                shipment.tracking_number,
                "Not available",
            ),
        ],
        [
            Paragraph("<b>Packing Date</b>", styles["Normal"]),
            shipment.created_at.strftime("%B %d, %Y"),
        ],
    ]

    details_table = Table(
        shipment_details,
        colWidths=[
            1.7 * inch,
            4.8 * inch,
        ],
    )

    details_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F2F4F7"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    story.append(details_table)
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "Ship To",
            styles["Heading2"],
        )
    )

    shipping_address_lines = [
        safe_value(order.shipping_name, customer_name),
        safe_value(order.shipping_address, ""),
        (
            f"{safe_value(order.shipping_city, '')}, "
            f"{safe_value(order.shipping_state, '')} "
            f"{safe_value(order.shipping_postal_code, '')}"
        ).strip(),
    ]

    shipping_address = "<br/>".join(
        line
        for line in shipping_address_lines
        if line
    )

    story.append(
        Paragraph(
            shipping_address or "Shipping address unavailable.",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 22))

    item_data = [
        [
            "Product",
            "SKU",
            "Quantity",
        ]
    ]

    for item in shipment.items.all():
        item_data.append(
            [
                Paragraph(
                    safe_value(item.product_name),
                    styles["Normal"],
                ),
                safe_value(item.sku),
                str(item.quantity),
            ]
        )

    items_table = Table(
        item_data,
        colWidths=[
            4.2 * inch,
            1.4 * inch,
            0.9 * inch,
        ],
        repeatRows=1,
    )

    items_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#0D6EFD"),
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
                    "ALIGN",
                    (2, 1),
                    (2, -1),
                    "CENTER",
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
                        colors.HexColor("#F8FAFC"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(
        Paragraph(
            "Shipment Items",
            styles["Heading2"],
        )
    )

    story.append(items_table)

    if shipment.notes:
        story.append(Spacer(1, 20))

        story.append(
            Paragraph(
                "Shipment Notes",
                styles["Heading2"],
            )
        )

        story.append(
            Paragraph(
                shipment.notes,
                styles["Normal"],
            )
        )

    story.append(Spacer(1, 30))

    story.append(
        Paragraph(
            (
                "Thank you for choosing KaleidoBrands. "
                "Please retain this packing slip for your records."
            ),
            styles["Normal"],
        )
    )

    document.build(story)

    pdf_content = buffer.getvalue()
    buffer.close()

    filename = (
        f"packing-slip-{shipment.shipment_number}.pdf"
    )

    shipment.packing_slip.save(
        filename,
        ContentFile(pdf_content),
        save=True,
    )

    return shipment.packing_slip