from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction


CUSTOMER_ORDER_STATUS_RANK = {
    "pending": 0,
    "approved": 1,
    "artwork": 2,
    "production": 3,
    "quality": 4,
    "shipped": 5,
    "delivered": 6,
    "cancelled": 7,
}


def get_active_purchase_orders(customer_order):
    """
    Return purchase orders that still participate in fulfillment.

    Cancelled purchase orders are excluded so they do not block the
    remaining supplier purchase orders from advancing the customer order.
    """

    return customer_order.supplier_purchase_orders.exclude(
        status="cancelled"
    )


def all_purchase_orders_reached(purchase_orders, allowed_statuses):
    """
    Return True when every purchase order is in one of the allowed statuses.
    """

    if not purchase_orders.exists():
        return False

    return not purchase_orders.exclude(
        status__in=allowed_statuses
    ).exists()


def determine_customer_order_status(customer_order):
    """
    Determine the appropriate customer-order status from all active
    supplier purchase orders.
    """

    all_purchase_orders = (
        customer_order.supplier_purchase_orders.all()
    )

    if not all_purchase_orders.exists():
        return None

    purchase_orders = get_active_purchase_orders(
        customer_order
    )

    if not purchase_orders.exists():
        return "cancelled"

    if all_purchase_orders_reached(
        purchase_orders,
        ["received"],
    ):
        return "delivered"

    if all_purchase_orders_reached(
        purchase_orders,
        ["shipped", "received"],
    ):
        return "shipped"

    if all_purchase_orders_reached(
        purchase_orders,
        [
            "in_production",
            "shipped",
            "received",
        ],
    ):
        return "production"

    if all_purchase_orders_reached(
        purchase_orders,
        [
            "sent",
            "confirmed",
            "in_production",
            "shipped",
            "received",
        ],
    ):
        return "approved"

    return "pending"


def send_customer_shipping_email(order):
    """
    Send the customer shipping notification once.
    """

    if order.shipping_email_sent:
        return

    customer_email = order.customer.email

    if not customer_email:
        return

    tracking_text = (
        order.tracking_number
        or "Tracking information pending"
    )

    tracking_line = tracking_text

    if order.tracking_url:
        tracking_line = (
            f"{tracking_text}\n"
            f"{order.tracking_url}"
        )

    body = f"""
Your KaleidoBrands order has shipped.

Order Number: {order.order_number}
Carrier: {order.carrier or "Carrier information pending"}
Tracking: {tracking_line}

Thank you for choosing KaleidoBrands.
""".strip()

    try:
        
        message = EmailMessage(
            subject=(
                "Your Order Has Shipped - "
                f"{order.order_number}"
            ),
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer_email],
        )

        message.send(fail_silently=True)

    except Exception:
        return

    order.shipping_email_sent = True

    order.save(
        update_fields=[
            "shipping_email_sent",
            "updated_at",
        ]
    )


@transaction.atomic
def synchronize_customer_order_from_purchase_orders(
    customer_order,
):
    """
    Synchronize the customer order from its supplier purchase orders.

    This function:
    - excludes cancelled POs from fulfillment calculations
    - prevents accidental backward status movement
    - copies supplier tracking details
    - copies the latest estimated ship date
    - sends the customer shipping email once
    """

    all_purchase_orders = (
        customer_order.supplier_purchase_orders.all()
    )

    if not all_purchase_orders.exists():
        return customer_order

    purchase_orders = get_active_purchase_orders(
        customer_order
    )

    previous_status = customer_order.status

    target_status = determine_customer_order_status(
        customer_order
    )

    if target_status is None:
        return customer_order

    current_rank = CUSTOMER_ORDER_STATUS_RANK.get(
        previous_status,
        0,
    )

    target_rank = CUSTOMER_ORDER_STATUS_RANK.get(
        target_status,
        0,
    )

    new_status = target_status

    if (
        target_status != "cancelled"
        and target_rank < current_rank
    ):
        new_status = previous_status

    shipped_purchase_order = (
        purchase_orders
        .filter(
            status__in=[
                "shipped",
                "received",
            ]
        )
        .exclude(tracking_number="")
        .order_by(
            "-shipped_at",
            "-updated_at",
        )
        .first()
    )

    update_fields = []

    if new_status != previous_status:
        customer_order.status = new_status
        update_fields.append("status")

    if shipped_purchase_order:
        if (
            shipped_purchase_order.tracking_number
            and customer_order.tracking_number
            != shipped_purchase_order.tracking_number
        ):
            customer_order.tracking_number = (
                shipped_purchase_order.tracking_number
            )
            update_fields.append(
                "tracking_number"
            )

        if (
            shipped_purchase_order.tracking_url
            and customer_order.tracking_url
            != shipped_purchase_order.tracking_url
        ):
            customer_order.tracking_url = (
                shipped_purchase_order.tracking_url
            )
            update_fields.append(
                "tracking_url"
            )

        if not customer_order.carrier:
            customer_order.carrier = (
                "Supplier Carrier"
            )
            update_fields.append("carrier")

    if (
        new_status == "shipped"
        and not customer_order.estimated_delivery
    ):
        latest_estimated_ship_date = (
            purchase_orders
            .exclude(
                estimated_ship_date__isnull=True
            )
            .order_by("-estimated_ship_date")
            .values_list(
                "estimated_ship_date",
                flat=True,
            )
            .first()
        )

        if latest_estimated_ship_date:
            customer_order.estimated_delivery = (
                latest_estimated_ship_date
            )
            update_fields.append(
                "estimated_delivery"
            )

    if update_fields:
        update_fields.append("updated_at")

        customer_order.save(
            update_fields=list(
                dict.fromkeys(update_fields)
            )
        )

    if (
        new_status == "shipped"
        and previous_status != "shipped"
    ):
        send_customer_shipping_email(
            customer_order
        )

    return customer_order