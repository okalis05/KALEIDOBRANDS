from products.models import SupplierListing


def select_supplier_listing(product):
    """
    Select the supplier listing used to source a checkout item.

    Priority:
    1. Active preferred listing
    2. Active in-stock listing with the lowest known unit cost
    3. Any active listing with the lowest known unit cost
    4. First active listing
    """

    if product is None:
        return None

    listings = (
        SupplierListing.objects
        .filter(
            product=product,
            is_active=True,
        )
        .select_related(
            "supplier",
            "catalog",
            "product",
        )
    )

    preferred = listings.filter(
        is_preferred=True,
    ).first()

    if preferred:
        return preferred

    in_stock = (
        listings
        .filter(
            inventory_status__in=[
                "in_stock",
                "low_stock",
            ],
            unit_cost__isnull=False,
        )
        .order_by(
            "unit_cost",
            "id",
        )
        .first()
    )

    if in_stock:
        return in_stock

    priced = (
        listings
        .filter(
            unit_cost__isnull=False,
        )
        .exclude(
            inventory_status__in=[
                "out_of_stock",
                "discontinued",
            ],
        )
        .order_by(
            "unit_cost",
            "id",
        )
        .first()
    )

    if priced:
        return priced

    return (
        listings
        .exclude(
            inventory_status="discontinued",
        )
        .order_by(
            "id",
        )
        .first()
    )