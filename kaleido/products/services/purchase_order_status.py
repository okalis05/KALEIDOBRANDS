from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from products.services.order_fulfillment import (
    synchronize_customer_order_from_purchase_orders,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)


ALLOWED_TRANSITIONS = {
    "draft": {
        "ready",
        "sent",
        "cancelled",
    },
    "ready": {
        "sent",
        "cancelled",
    },
    "sent": {
        "confirmed",
        "in_production",
        "cancelled",
    },
    "confirmed": {
        "in_production",
        "cancelled",
    },
    "in_production": {
        "shipped",
        "cancelled",
    },
    "shipped": {
        "received",
    },
    "received": set(),
    "cancelled": set(),
}


def validate_purchase_order_transition(
    previous_status,
    new_status,
):
    if previous_status == new_status:
        return

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        previous_status,
        set(),
    )

    if new_status not in allowed_statuses:
        raise ValidationError(
            (
                "Invalid purchase-order transition: "
                f"{previous_status} → {new_status}."
            )
        )


@transaction.atomic
def update_purchase_order_status(
    purchase_order,
    new_status,
    *,
    user=None,
):
    previous_status = purchase_order.status

    validate_purchase_order_transition(
        previous_status,
        new_status,
    )

    if previous_status == new_status:
        return purchase_order

    now = timezone.now()

    purchase_order.status = new_status

    update_fields = [
        "status",
        "updated_at",
    ]

    if (
        new_status == "sent"
        and not purchase_order.sent_at
    ):
        purchase_order.sent_at = now
        update_fields.append("sent_at")

    if (
        new_status == "confirmed"
        and not purchase_order.confirmed_at
    ):
        purchase_order.confirmed_at = now
        update_fields.append("confirmed_at")

    if (
        new_status == "in_production"
        and not purchase_order.production_started_at
    ):
        purchase_order.production_started_at = now
        update_fields.append(
            "production_started_at"
        )

    if (
        new_status == "shipped"
        and not purchase_order.shipped_at
    ):
        purchase_order.shipped_at = now
        update_fields.append("shipped_at")

    if (
        new_status == "received"
        and not purchase_order.received_at
    ):
        purchase_order.received_at = now
        update_fields.append("received_at")

    purchase_order.save(
        update_fields=update_fields
    )

    log_purchase_order_activity(
        purchase_order,
        action="status_changed",
        message="Purchase order status updated.",
        previous_value=previous_status,
        new_value=new_status,
        user=user,
    )

    if purchase_order.customer_order:
        synchronize_customer_order_from_purchase_orders(
            purchase_order.customer_order
        )

    return purchase_order