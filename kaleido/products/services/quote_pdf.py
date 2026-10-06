from io import BytesIO
from xml.sax.saxutils import escape

from django.core.files.base import ContentFile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ============================================================
# KALEIDOBRANDS QUOTE PDF
# ============================================================

KB_BLUE = colors.HexColor("#1674EF")
KB_DARK_BLUE = colors.HexColor("#0757D7")
KB_PURPLE = colors.HexColor("#7047E8")
KB_NAVY = colors.HexColor("#0F172A")
KB_TEXT = colors.HexColor("#334155")
KB_MUTED = colors.HexColor("#64748B")
KB_LIGHT_TEXT = colors.HexColor("#94A3B8")

KB_BORDER = colors.HexColor("#E2E8F0")
KB_LIGHT_BLUE = colors.HexColor("#EFF6FF")
KB_LIGHT_PURPLE = colors.HexColor("#F5F3FF")
KB_LIGHT_GRAY = colors.HexColor("#F8FAFC")
KB_LIGHT_ORANGE = colors.HexColor("#FFF7E8")

KB_GREEN = colors.HexColor("#15803D")
KB_LIGHT_GREEN = colors.HexColor("#ECFDF3")


def _safe(value, fallback="N/A"):
    """
    Escape user-supplied text before placing it inside
    a ReportLab Paragraph.
    """
    if value is None:
        return fallback

    value = str(value).strip()

    if not value:
        return fallback

    return escape(value)


def _format_date(value):
    if not value:
        return "N/A"

    try:
        return value.strftime("%B %d, %Y")
    except (AttributeError, ValueError):
        return _safe(value)


def _format_datetime(value):
    if not value:
        return "N/A"

    try:
        return value.strftime("%B %d, %Y at %I:%M %p")
    except (AttributeError, ValueError):
        return _safe(value)


def generate_quote_pdf(quote):
    buffer = BytesIO()

    # --------------------------------------------------------
    # DOCUMENT
    # --------------------------------------------------------

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"KaleidoBrands Quote #{quote.id}",
        author="KaleidoBrands",
    )

    styles = getSampleStyleSheet()

    # --------------------------------------------------------
    # CUSTOM STYLES
    # --------------------------------------------------------

    brand_style = ParagraphStyle(
        "KBBrand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=KB_BLUE,
        spaceAfter=3,
    )

    title_style = ParagraphStyle(
        "KBTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=KB_NAVY,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "KBSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=KB_MUTED,
    )

    reference_style = ParagraphStyle(
        "KBReference",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=KB_BLUE,
        alignment=TA_CENTER,
    )

    status_style = ParagraphStyle(
        "KBStatus",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=KB_GREEN,
        alignment=TA_CENTER,
    )

    section_label_style = ParagraphStyle(
        "KBSectionLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=KB_PURPLE,
        spaceAfter=3,
    )

    section_title_style = ParagraphStyle(
        "KBSectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=KB_NAVY,
        spaceAfter=8,
    )

    info_label_style = ParagraphStyle(
        "KBInfoLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        textColor=KB_LIGHT_TEXT,
        spaceAfter=2,
    )

    info_value_style = ParagraphStyle(
        "KBInfoValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=KB_TEXT,
    )

    table_header_style = ParagraphStyle(
        "KBTableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
    )

    product_style = ParagraphStyle(
        "KBProduct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=KB_NAVY,
        wordWrap="CJK",
    )

    table_text_style = ParagraphStyle(
        "KBTableText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=KB_TEXT,
        wordWrap="CJK",
    )

    quantity_style = ParagraphStyle(
        "KBQuantity",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=KB_BLUE,
        alignment=TA_CENTER,
    )

    notes_title_style = ParagraphStyle(
        "KBNotesTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#B66B00"),
        spaceAfter=5,
    )

    notes_style = ParagraphStyle(
        "KBNotes",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#6F5B3D"),
    )

    footer_style = ParagraphStyle(
        "KBFooter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=10,
        textColor=KB_MUTED,
        alignment=TA_CENTER,
    )

    story = []

    # ========================================================
    # HEADER
    # ========================================================

    header_left = [
        Paragraph("KALEIDOBRANDS", brand_style),
        Paragraph("Quote Request", title_style),
        Paragraph(
            "Custom promotional products for your brand.",
            subtitle_style,
        ),
    ]

    header_right = [
        Paragraph(
            f"QUOTE #KB-{quote.id}",
            reference_style,
        ),
        Spacer(1, 5),
        Paragraph(
            "SUBMITTED",
            status_style,
        ),
    ]

    header = Table(
        [[header_left, header_right]],
        colWidths=[5.25 * inch, 1.45 * inch],
    )

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),

                (
                    "BACKGROUND",
                    (1, 0),
                    (1, 0),
                    KB_LIGHT_BLUE,
                ),

                (
                    "BOX",
                    (1, 0),
                    (1, 0),
                    0.5,
                    colors.HexColor("#DBEAFE"),
                ),

                (
                    "LEFTPADDING",
                    (1, 0),
                    (1, 0),
                    10,
                ),
                (
                    "RIGHTPADDING",
                    (1, 0),
                    (1, 0),
                    10,
                ),
                (
                    "TOPPADDING",
                    (1, 0),
                    (1, 0),
                    10,
                ),
                (
                    "BOTTOMPADDING",
                    (1, 0),
                    (1, 0),
                    10,
                ),
            ]
        )
    )

    story.append(header)
    story.append(Spacer(1, 10))

    # Accent bar
    accent = Table(
        [[""]],
        colWidths=[6.7 * inch],
        rowHeights=[4],
    )

    accent.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    KB_BLUE,
                ),
            ]
        )
    )

    story.append(accent)
    story.append(Spacer(1, 18))

    # ========================================================
    # PROJECT OVERVIEW
    # ========================================================

    story.append(
        Paragraph(
            "PROJECT DETAILS",
            section_label_style,
        )
    )

    story.append(
        Paragraph(
            _safe(
                quote.project_name,
                "Quote Request",
            ),
            section_title_style,
        )
    )

    info_data = [
        [
            Paragraph(
                "CUSTOMER",
                info_label_style,
            ),
            Paragraph(
                "COMPANY",
                info_label_style,
            ),
            Paragraph(
                "EMAIL",
                info_label_style,
            ),
        ],
        [
            Paragraph(
                _safe(quote.customer_name),
                info_value_style,
            ),
            Paragraph(
                _safe(quote.company),
                info_value_style,
            ),
            Paragraph(
                _safe(quote.email),
                info_value_style,
            ),
        ],
        [
            Paragraph(
                "PHONE",
                info_label_style,
            ),
            Paragraph(
                "DEADLINE",
                info_label_style,
            ),
            Paragraph(
                "SUBMITTED",
                info_label_style,
            ),
        ],
        [
            Paragraph(
                _safe(quote.phone),
                info_value_style,
            ),
            Paragraph(
                _format_date(quote.deadline),
                info_value_style,
            ),
            Paragraph(
                _format_datetime(
                    quote.created_at
                ),
                info_value_style,
            ),
        ],
    ]

    info_table = Table(
        info_data,
        colWidths=[
            2.05 * inch,
            2.05 * inch,
            2.60 * inch,
        ],
    )

    info_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    KB_LIGHT_GRAY,
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    KB_BORDER,
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    KB_BORDER,
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
                    10,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    10,
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

    story.append(info_table)
    story.append(Spacer(1, 22))

    # ========================================================
    # REQUESTED PRODUCTS
    # ========================================================

    story.append(
        Paragraph(
            "QUOTE ITEMS",
            section_label_style,
        )
    )

    story.append(
        Paragraph(
            "Requested Products",
            section_title_style,
        )
    )

    # IMPORTANT:
    # Every text cell is a Paragraph.
    # This is what fixes the overlap/wrapping problem.

    product_data = [
        [
            Paragraph(
                "PRODUCT",
                table_header_style,
            ),
            Paragraph(
                "CATEGORY",
                table_header_style,
            ),
            Paragraph(
                "QTY",
                table_header_style,
            ),
            Paragraph(
                "CUSTOMIZATION NOTES",
                table_header_style,
            ),
        ]
    ]

    for item in quote.items.all():
        product_data.append(
            [
                Paragraph(
                    _safe(item.product_name),
                    product_style,
                ),

                Paragraph(
                    _safe(
                        item.category,
                        "Product",
                    ),
                    table_text_style,
                ),

                Paragraph(
                    _safe(
                        item.quantity,
                        "0",
                    ),
                    quantity_style,
                ),

                Paragraph(
                    _safe(
                        item.notes,
                        "—",
                    ),
                    table_text_style,
                ),
            ]
        )

    # Total width = 6.7 inches.
    # Product gets the most room.
    product_table = Table(
        product_data,
        colWidths=[
            2.55 * inch,
            1.25 * inch,
            0.55 * inch,
            2.35 * inch,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )

    product_table.setStyle(
        TableStyle(
            [
                # Header
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    KB_BLUE,
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),

                # Body
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        KB_LIGHT_GRAY,
                    ],
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    KB_BORDER,
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),

                (
                    "ALIGN",
                    (2, 1),
                    (2, -1),
                    "CENTER",
                ),

                # Padding
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
                    (-1, 0),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, 0),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 1),
                    (-1, -1),
                    9,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 1),
                    (-1, -1),
                    9,
                ),
            ]
        )
    )

    story.append(product_table)

    # ========================================================
    # ADDITIONAL NOTES
    # ========================================================

    if quote.notes:
        story.append(Spacer(1, 20))

        notes_content = [
            [
                Paragraph(
                    "PROJECT NOTES",
                    notes_title_style,
                )
            ],
            [
                Paragraph(
                    _safe(quote.notes),
                    notes_style,
                )
            ],
        ]

        notes_table = Table(
            notes_content,
            colWidths=[6.7 * inch],
        )

        notes_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        KB_LIGHT_ORANGE,
                    ),

                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#FDE6B7"),
                    ),

                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        12,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        12,
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
            KeepTogether(notes_table)
        )

    # ========================================================
    # CUSTOMER MESSAGE
    # ========================================================

    story.append(Spacer(1, 24))

    next_step_data = [
        [
            Paragraph(
                "WHAT HAPPENS NEXT?",
                ParagraphStyle(
                    "KBNextLabel",
                    parent=styles["Normal"],
                    fontName="Helvetica-Bold",
                    fontSize=7,
                    leading=9,
                    textColor=KB_BLUE,
                    spaceAfter=4,
                ),
            )
        ],
        [
            Paragraph(
                "Our branding team will review your product "
                "selection, quantities, customization requirements, "
                "production details, and shipping needs. We will "
                "follow up with you with custom pricing and next steps.",
                ParagraphStyle(
                    "KBNextText",
                    parent=styles["Normal"],
                    fontName="Helvetica",
                    fontSize=8,
                    leading=12,
                    textColor=KB_TEXT,
                ),
            )
        ],
    ]

    next_step_table = Table(
        next_step_data,
        colWidths=[6.7 * inch],
    )

    next_step_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    KB_LIGHT_BLUE,
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#DBEAFE"),
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    12,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    12,
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
        KeepTogether(next_step_table)
    )

    # ========================================================
    # FOOTER
    # ========================================================

    story.append(Spacer(1, 24))

    story.append(
        Paragraph(
            f"Quote Reference: KB-{quote.id}",
            footer_style,
        )
    )

    story.append(Spacer(1, 3))

    story.append(
        Paragraph(
            "Thank you for choosing KaleidoBrands.",
            footer_style,
        )
    )

    # ========================================================
    # BUILD PDF
    # ========================================================

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"quote-{quote.id}.pdf"

    quote.pdf_file.save(
        filename,
        ContentFile(pdf),
        save=True,
    )

    return quote.pdf_file