from decimal import Decimal

from django.db import transaction
from django.utils.crypto import get_random_string

from products.models import (
    SupplierPurchaseOrder,
    SupplierPurchaseOrderItem,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)


def generate_po_number():
    return f"KB-PO-{get_random_string(8).upper()}"


@transaction.atomic
def create_purchase_orders_from_order(order, created_by=None):
    """
    Create one purchase order per supplier from a paid customer order.

    Supplier selection and pricing come from the immutable supplier
    traceability stored on each OrderItem.
    """

    if order.payment_status != "paid":
        raise ValueError(
            "Purchase orders can only be created from paid orders."
        )

    existing_purchase_orders = list(
        order.supplier_purchase_orders.all()
    )

    if existing_purchase_orders:
        return existing_purchase_orders

    supplier_groups = {}

    order_items = (
        order.items
        .select_related(
            "product",
            "supplier_listing",
            "supplier_listing__supplier",
        )
        .all()
    )

    for order_item in order_items:
        supplier_listing = order_item.supplier_listing

        supplier = (
            supplier_listing.supplier
            if supplier_listing
            else None
        )

        supplier_groups.setdefault(
            supplier,
            [],
        ).append(order_item)

    purchase_orders = []

    for supplier, grouped_items in supplier_groups.items():
        purchase_order = SupplierPurchaseOrder.objects.create(
            supplier=supplier,
            customer_order=order,
            po_number=generate_po_number(),
            status="draft",
            created_by=created_by,
        )

        log_purchase_order_activity(
            purchase_order,
            action="created",
            message=(
                "Purchase order created from customer order "
                f"{order.order_number}."
            ),
            user=created_by,
        )

        for order_item in grouped_items:
            unit_cost = (
                order_item.supplier_unit_cost_snapshot
                or Decimal("0.00")
            )

            supplier_sku = (
                order_item.supplier_sku_snapshot
                or order_item.sku
                or ""
            )

            SupplierPurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                order_item=order_item,
                product=order_item.product,
                supplier_listing=order_item.supplier_listing,
                product_name=order_item.product_name,
                supplier_sku=supplier_sku,
                supplier_product_id_snapshot=(
                    order_item.supplier_product_id_snapshot
                    or ""
                ),
                supplier_product_name_snapshot=(
                    order_item.supplier_product_name_snapshot
                    or order_item.product_name
                ),
                supplier_catalog_snapshot=(
                    order_item.supplier_catalog_snapshot
                    or ""
                ),
                supplier_source_snapshot=(
                    order_item.supplier_source_snapshot
                    or ""
                ),
                setup_cost_snapshot=(
                    order_item.supplier_setup_cost_snapshot
                    or Decimal("0.00")
                ),
                minimum_quantity_snapshot=(
                    order_item.supplier_minimum_quantity_snapshot
                ),
                quantity=order_item.quantity,
                unit_cost=unit_cost,
                decoration=order_item.decoration or "",
                color=order_item.color or "",
            )

        purchase_orders.append(purchase_order)

    return purchase_orders