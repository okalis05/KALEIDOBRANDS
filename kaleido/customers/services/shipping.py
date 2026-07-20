from django.db import transaction
from django.utils.crypto import get_random_string

from customers.models import (
    Shipment,
    ShipmentItem,
    ShipmentStatusHistory,
)
from customers.services.packing_slip_pdf import (
    generate_packing_slip_pdf,
)

def generate_shipment_number():
    return f"KB-SHP-{get_random_string(8).upper()}"


@transaction.atomic
def create_shipment_from_order(
    order,
    *,
    shipment_data=None,
    item_quantities=None,
    user=None,
):
    shipment_data = shipment_data or {}
    item_quantities = item_quantities or {}

    shipment = Shipment.objects.create(
        order=order,
        shipment_number=generate_shipment_number(),
        **shipment_data,
    )

    total_selected = 0

    for order_item in order.items.all():
        quantity = item_quantities.get(
            order_item.id,
            order_item.quantity,
        )

        quantity = int(quantity or 0)

        if quantity <= 0:
            continue

        ShipmentItem.objects.create(
            shipment=shipment,
            order_item=order_item,
            product_name=order_item.product_name,
            sku=order_item.sku or "",
            quantity=quantity,
        )

        total_selected += quantity

    if total_selected <= 0:
        raise ValueError(
            "Select at least one item quantity for the shipment."
        )

    ShipmentStatusHistory.objects.create(
        shipment=shipment,
        previous_status="",
        new_status="pending",
        message="Shipment created.",
        created_by=(
            user
            if user and user.is_authenticated
            else None
        ),
    )

    return shipment


@transaction.atomic
def create_default_shipment_for_paid_order(order):
    """
    Create one pending shipment for a paid order.

    Existing shipments are returned instead of creating duplicates.
    """

    existing_shipment = order.shipments.order_by(
        "created_at"
    ).first()

    if existing_shipment:
        return existing_shipment, False

    if order.payment_status != "paid":
        raise ValueError(
            "A shipment can only be created for a paid order."
        )

    shipment = create_shipment_from_order(
        order,
        shipment_data={
            "shipping_method": order.shipping_method,
            "carrier": (
                order.shipping_method.carrier
                if order.shipping_method
                else order.carrier or ""
            ),
            "service_level": (
                order.shipping_method.name
                if order.shipping_method
                else order.shipping_method_name or ""
            ),
            "shipping_cost": order.shipping or 0,
            "estimated_delivery_date": (
                order.estimated_delivery
            ),
            "status": "pending",
        },
    )
    try:
        generate_packing_slip_pdf(shipment)

    except Exception:
        pass

    return shipment, True