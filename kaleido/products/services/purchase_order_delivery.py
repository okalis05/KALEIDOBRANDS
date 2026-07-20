from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from products.services.order_fulfillment import (
    synchronize_customer_order_from_purchase_orders,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)
from products.services.purchase_order_pdf import (
    generate_purchase_order_pdf,
)


@transaction.atomic
def deliver_purchase_order(purchase_order, user=None):
    """
    Generate a purchase-order PDF and email it to the supplier.

    Returns:
        tuple[bool, str]: success flag and result message.
    """

    supplier = purchase_order.supplier

    if not supplier:
        return False, (
            "Purchase order does not have an assigned supplier."
        )

    if not supplier.email:
        return False, (
            f"{supplier.name} does not have a purchase-order email."
        )

    if (
        purchase_order.status == "sent"
        and purchase_order.sent_at
    ):
        return True, "Purchase order was already sent."

    if purchase_order.status not in {"draft", "ready"}:
        return False, (
            "Only draft or ready purchase orders can be sent."
        )

    if not purchase_order.pdf_file:
        generate_purchase_order_pdf(purchase_order)
        purchase_order.refresh_from_db(
            fields=["pdf_file"]
        )

    if not purchase_order.pdf_file:
        return False, (
            "Purchase-order PDF could not be generated."
        )

    customer_order_number = (
        purchase_order.customer_order.order_number
        if purchase_order.customer_order
        else "N/A"
    )

    body = f"""
Hello {supplier.name},

Please find attached purchase order {purchase_order.po_number}.

Customer Order: {customer_order_number}
Total Supplier Cost: ${purchase_order.total_cost():.2f}

Please confirm:

- Product availability
- Final supplier pricing
- Production schedule
- Estimated ship date
- Tracking information when available

Thank you,

KaleidoBrands
sales@kaleidobrands.com
""".strip()

    email = EmailMessage(
        subject=(
            f"Purchase Order {purchase_order.po_number}"
        ),
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[supplier.email],
        cc=["sales@kaleidobrands.com"],
    )

    email.attach_file(
        purchase_order.pdf_file.path
    )

    previous_status = purchase_order.status

    try:
        email.send(fail_silently=False)

    except Exception as error:
        log_purchase_order_activity(
            purchase_order,
            action="error",
            message=(
                "Purchase order email failed: "
                f"{error}"
            ),
            user=user,
        )

        return False, str(error)

    purchase_order.status = "sent"
    purchase_order.sent_at = timezone.now()

    purchase_order.save(
        update_fields=[
            "status",
            "sent_at",
            "updated_at",
        ]
    )

    log_purchase_order_activity(
        purchase_order,
        action="sent",
        message=(
            f"Purchase order emailed to {supplier.email}."
        ),
        previous_value=previous_status,
        new_value="sent",
        user=user,
    )

    if purchase_order.customer_order:
        synchronize_customer_order_from_purchase_orders(
            purchase_order.customer_order
        )

    return True, (
        f"{purchase_order.po_number} was sent to "
        f"{supplier.email}."
    )