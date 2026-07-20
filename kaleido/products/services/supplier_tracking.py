from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from products.models import SupplierPurchaseOrder
from products.services.order_fulfillment import (
    synchronize_customer_order_from_purchase_orders,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)
from products.services.purchase_order_status import (
    update_purchase_order_status,
)


SUPPLIER_SHIPMENT_EVENT_STATUSES = {
    "shipped",
    "received",
}


@transaction.atomic
def update_supplier_tracking(
    purchase_order,
    *,
    tracking_number=None,
    tracking_url=None,
    estimated_ship_date=None,
    supplier_reference=None,
    shipment_status=None,
    user=None,
):
    """
    Apply a supplier shipment update to a purchase order.

    The operation is idempotent:
    - unchanged tracking data is not saved again
    - unchanged shipment status is not transitioned again
    - duplicate events do not create duplicate tracking activity
    """

    purchase_order = (
        SupplierPurchaseOrder.objects
        .select_for_update()
        .select_related("customer_order")
        .get(pk=purchase_order.pk)
    )

    if (
        shipment_status is not None
        and shipment_status
        not in SUPPLIER_SHIPMENT_EVENT_STATUSES
    ):
        raise ValidationError(
            "Supplier shipment status must be "
            "'shipped' or 'received'."
        )

    previous_tracking_number = (
        purchase_order.tracking_number
    )
    previous_tracking_url = purchase_order.tracking_url

    tracking_changed = False
    update_fields = []

    if (
        tracking_number is not None
        and tracking_number
        != purchase_order.tracking_number
    ):
        purchase_order.tracking_number = tracking_number
        update_fields.append("tracking_number")
        tracking_changed = True

    if (
        tracking_url is not None
        and tracking_url != purchase_order.tracking_url
    ):
        purchase_order.tracking_url = tracking_url
        update_fields.append("tracking_url")
        tracking_changed = True

    if (
        estimated_ship_date is not None
        and estimated_ship_date
        != purchase_order.estimated_ship_date
    ):
        purchase_order.estimated_ship_date = (
            estimated_ship_date
        )
        update_fields.append("estimated_ship_date")

    if (
        supplier_reference is not None
        and supplier_reference
        != purchase_order.supplier_reference
    ):
        purchase_order.supplier_reference = (
            supplier_reference
        )
        update_fields.append("supplier_reference")

    if update_fields:
        update_fields.append("updated_at")

        purchase_order.save(
            update_fields=list(
                dict.fromkeys(update_fields)
            )
        )

    if tracking_changed:
        log_purchase_order_activity(
            purchase_order,
            action="tracking_updated",
            message=(
                "Supplier shipment tracking information "
                "was updated."
            ),
            previous_value=(
                previous_tracking_number
                or previous_tracking_url
                or ""
            ),
            new_value=(
                purchase_order.tracking_number
                or purchase_order.tracking_url
                or ""
            ),
            user=user,
        )

    if (
        shipment_status is not None
        and shipment_status != purchase_order.status
    ):
        purchase_order = update_purchase_order_status(
            purchase_order,
            shipment_status,
            user=user,
        )
    elif (
        purchase_order.customer_order_id
        and update_fields
    ):
        synchronize_customer_order_from_purchase_orders(
            purchase_order.customer_order
        )

    return purchase_order