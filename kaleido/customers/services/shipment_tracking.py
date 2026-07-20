from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from customers.models import ShipmentStatusHistory


TRACKING_URLS = {
    "ups": "https://www.ups.com/track?tracknum={}",
    "fedex": "https://www.fedex.com/fedextrack/?tracknumbers={}",
    "usps": "https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1={}",
    "dhl": "https://www.dhl.com/us-en/home/tracking.html?tracking-id={}",
}


def normalize_carrier(carrier):
    """
    Convert carrier names into consistent lowercase lookup keys.
    """

    if not carrier:
        return ""

    normalized = carrier.strip().lower()

    aliases = {
        "united parcel service": "ups",
        "ups": "ups",
        "federal express": "fedex",
        "fed ex": "fedex",
        "fedex": "fedex",
        "united states postal service": "usps",
        "postal service": "usps",
        "usps": "usps",
        "dhl express": "dhl",
        "dhl": "dhl",
    }

    return aliases.get(normalized, normalized)


def build_tracking_url(carrier, tracking_number):
    """
    Build a carrier tracking link when the carrier is supported.
    """

    if not carrier or not tracking_number:
        return ""

    carrier_key = normalize_carrier(carrier)
    tracking_template = TRACKING_URLS.get(carrier_key)

    if not tracking_template:
        return ""

    clean_tracking_number = tracking_number.strip()

    return tracking_template.format(clean_tracking_number)


def assign_tracking(
    shipment,
    *,
    carrier,
    tracking_number,
):
    """
    Save carrier and tracking information on a shipment.
    """

    shipment.carrier = carrier.strip()
    shipment.tracking_number = tracking_number.strip()

    shipment.tracking_url = build_tracking_url(
        carrier,
        tracking_number,
    )

    shipment.save(
        update_fields=[
            "carrier",
            "tracking_number",
            "tracking_url",
            "updated_at",
        ]
    )

    return shipment


def synchronize_order_from_shipment(shipment):
    """
    Copy shipment progress and tracking information to the customer order.
    """

    order = shipment.order
    update_fields = []

    if shipment.tracking_number:
        order.tracking_number = shipment.tracking_number
        update_fields.append("tracking_number")

    if shipment.tracking_url:
        order.tracking_url = shipment.tracking_url
        update_fields.append("tracking_url")

    if shipment.carrier:
        order.carrier = shipment.carrier
        update_fields.append("carrier")

    if shipment.estimated_delivery_date:
        order.estimated_delivery = shipment.estimated_delivery_date
        update_fields.append("estimated_delivery")

    if shipment.status in {
        "label_created",
        "ready",
    }:
        if order.status == "pending":
            order.status = "approved"
            update_fields.append("status")

    elif shipment.status in {
        "in_transit",
        "out_for_delivery",
    }:
        if order.status != "shipped":
            order.status = "shipped"
            update_fields.append("status")

    elif shipment.status == "delivered":
        if order.status != "delivered":
            order.status = "delivered"
            update_fields.append("status")

    if update_fields:
        order.save(
            update_fields=list(dict.fromkeys(update_fields))
        )

    return order


def send_shipment_update_email(
    shipment,
    *,
    previous_status,
):
    """
    Email the customer after a meaningful shipment-status change.
    """

    if previous_status == shipment.status:
        return False

    customer = shipment.order.customer
    customer_email = customer.email

    if not customer_email:
        return False

    tracking_section = "Tracking information is not available yet."

    if shipment.tracking_number:
        tracking_section = (
            f"Tracking Number: {shipment.tracking_number}"
        )

        if shipment.tracking_url:
            tracking_section += (
                f"\nTracking Link: {shipment.tracking_url}"
            )

    estimated_delivery = (
        shipment.estimated_delivery_date
        or "To be determined"
    )

    body = f"""
Hello {customer.get_full_name() or customer.username},

Your KaleidoBrands shipment has been updated.

Order Number: {shipment.order.order_number}
Shipment Number: {shipment.shipment_number}
Status: {shipment.get_status_display()}
Carrier: {shipment.carrier or "To be determined"}
{tracking_section}
Estimated Delivery: {estimated_delivery}

Thank you for choosing KaleidoBrands.
"""

    try:
        EmailMessage(
            subject=(
                f"Shipment Update - "
                f"{shipment.shipment_number}"
            ),
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer_email],
        ).send(fail_silently=False)

    except Exception:
        return False

    return True


def update_shipment_status(
    shipment,
    new_status,
    *,
    user=None,
    message="",
):
    """
    Update shipment status, timestamps, history, customer order,
    and email notification.
    """

    valid_statuses = {
        value
        for value, label in shipment.STATUS_CHOICES
    }

    if new_status not in valid_statuses:
        raise ValueError("Invalid shipment status.")

    previous_status = shipment.status
    now = timezone.now()

    shipment.status = new_status

    if (
        new_status in {"in_transit", "out_for_delivery"}
        and shipment.shipped_at is None
    ):
        shipment.shipped_at = now

    if (
        new_status == "delivered"
        and shipment.delivered_at is None
    ):
        shipment.delivered_at = now

    update_fields = [
        "status",
        "updated_at",
    ]

    if shipment.shipped_at:
        update_fields.append("shipped_at")

    if shipment.delivered_at:
        update_fields.append("delivered_at")

    shipment.save(
        update_fields=list(dict.fromkeys(update_fields))
    )

    if previous_status != new_status or message:
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            previous_status=previous_status,
            new_status=new_status,
            message=message.strip(),
            created_by=(
                user
                if user and user.is_authenticated
                else None
            ),
        )

    synchronize_order_from_shipment(shipment)

    send_shipment_update_email(
        shipment,
        previous_status=previous_status,
    )

    return shipment