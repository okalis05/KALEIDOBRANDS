from decimal import Decimal, InvalidOperation

from django.utils import timezone

from products.models import (
    Product,
    SupplierInventoryHistory,
    SupplierPriceHistory,
)


def normalize_price(value):
    if value in (None, ""):
        return None

    try:
        return Decimal(
            str(value)
            .replace("$", "")
            .replace(",", "")
            .strip()
        )
    except (InvalidOperation, ValueError):
        return None


def normalize_inventory(value):
    if value in (None, ""):
        return None

    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def determine_inventory_status(quantity, discontinued=False):
    if discontinued:
        return "discontinued"

    if quantity is None:
        return "unknown"

    if quantity <= 0:
        return "out_of_stock"

    if quantity <= 25:
        return "low_stock"

    return "in_stock"


def update_supplier_product(
    product,
    *,
    supplier_price=None,
    supplier_inventory=None,
    discontinued=False,
):
    new_price = normalize_price(supplier_price)
    new_inventory = normalize_inventory(supplier_inventory)
    new_status = determine_inventory_status(
        new_inventory,
        discontinued=discontinued,
    )

    previous_price = product.supplier_price
    previous_inventory = product.supplier_inventory
    previous_status = product.inventory_status

    if new_price is not None and new_price != previous_price:
        SupplierPriceHistory.objects.create(
            product=product,
            supplier=product.supplier_record,
            previous_price=previous_price,
            new_price=new_price,
        )

        product.supplier_price = new_price

    if (
        new_inventory != previous_inventory
        or new_status != previous_status
    ):
        SupplierInventoryHistory.objects.create(
            product=product,
            supplier=product.supplier_record,
            previous_quantity=previous_inventory,
            new_quantity=new_inventory,
            previous_status=previous_status,
            new_status=new_status,
        )

        product.supplier_inventory = new_inventory
        product.inventory_status = new_status

    product.supplier_last_synced_at = timezone.now()

    product.save(
        update_fields=[
            "supplier_price",
            "supplier_inventory",
            "inventory_status",
            "supplier_last_synced_at",
        ]
    )

    return product