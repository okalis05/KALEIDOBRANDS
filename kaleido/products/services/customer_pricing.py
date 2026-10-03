from decimal import Decimal, ROUND_HALF_UP


# ----------------------------------------------------------------------
# KaleidoBrands customer pricing policy
# ----------------------------------------------------------------------

CUSTOMER_MARKUP_RATE = Decimal("0.10")
ONE = Decimal("1.00")
CENT = Decimal("0.01")


def customer_price_from_supplier_cost(supplier_cost):
    """
    Convert an internal supplier Net unit cost into the
    KaleidoBrands customer-facing unit price.

    Current KaleidoBrands policy:
        supplier Net cost + 10% markup

    Supplier pricing must never be modified by this function.
    """

    if supplier_cost is None:
        return None

    supplier_cost = Decimal(str(supplier_cost))

    if supplier_cost < 0:
        raise ValueError("Supplier cost cannot be negative.")

    return (
        supplier_cost
        * (ONE + CUSTOMER_MARKUP_RATE)
    ).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def customer_price_breaks(product):
    """
    Return customer-facing quantity pricing for a Product.

    SupplierPriceBreak rows remain untouched. Each returned
    customer price includes the KaleidoBrands markup.
    """

    breaks = []

    for supplier_break in (
        product.supplier_price_breaks
        .all()
        .order_by("min_quantity")
    ):
        customer_price = customer_price_from_supplier_cost(
            supplier_break.price
        )

        breaks.append(
            {
                "min_quantity": supplier_break.min_quantity,
                "supplier_price": supplier_break.price,
                "customer_price": customer_price,
                "price_uom": supplier_break.price_uom,
            }
        )

    return breaks


def customer_starting_price(product):
    """
    Return the lowest customer-facing unit price available
    from the supplier quantity breaks.

    This is suitable for the storefront's:
        "Starting at $X.XX"

    If no price breaks exist, fall back to Product.supplier_price.

    Supplier Net cost is never returned directly.
    """

    prices = [
        row["customer_price"]
        for row in customer_price_breaks(product)
        if row["customer_price"] is not None
    ]

    if prices:
        return min(prices)

    return customer_price_from_supplier_cost(
        product.supplier_price
    )


# ----------------------------------------------------------------------
# Quantity-aware checkout pricing
# ----------------------------------------------------------------------

def _decimal_or_none(value):
    if value in (None, ""):
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _variant_customer_price_breaks(product, variant=None):
    """
    Return customer-facing quantity breaks stored in a ProductVariant
    source_payload.

    Some PromoStandards integrations preserve exact-part customer
    pricing on the variant rather than Product.supplier_price_breaks.

    Only explicitly calculable customer pricing is returned.
    """

    variants = []

    if variant is not None:
        variants = [variant]
    else:
        try:
            variants = list(
                product.variants
                .filter(
                    is_active=True,
                    is_default=True,
                )
                .order_by("id")
            )

            if not variants:
                variants = list(
                    product.variants
                    .filter(is_active=True)
                    .order_by("id")[:1]
                )
        except Exception:
            variants = []

    rows = []

    for current_variant in variants:
        payload = getattr(
            current_variant,
            "source_payload",
            None,
        )

        if not isinstance(payload, dict):
            continue

        # Some integrations explicitly mark an exact part as unpriced.
        # Never turn a placeholder zero adjustment into a customer price.
        if payload.get("pricing_available") is False:
            continue

        for row in (
            payload.get("customer_price_breaks")
            or []
        ):
            if not isinstance(row, dict):
                continue

            try:
                minimum_quantity = int(
                    row.get("min_quantity")
                )
            except (TypeError, ValueError):
                continue

            customer_price = _decimal_or_none(
                row.get("customer_price")
            )

            if (
                minimum_quantity <= 0
                or customer_price is None
                or customer_price < 0
            ):
                continue

            rows.append(
                {
                    "min_quantity": minimum_quantity,
                    "customer_price": customer_price.quantize(
                        CENT,
                        rounding=ROUND_HALF_UP,
                    ),
                    "price_uom": (
                        row.get("price_uom")
                        or "EA"
                    ),
                    "source": "variant_payload",
                    "variant": current_variant,
                }
            )

    rows.sort(
        key=lambda row: row["min_quantity"]
    )

    return rows


def resolve_customer_unit_price(
    product,
    quantity,
    variant=None,
):
    """
    Resolve the customer unit price applicable to an actual order
    quantity.

    This differs from customer_starting_price(), which intentionally
    returns the lowest advertised "Starting at" price.

    Resolution order:

    1. Exact/default variant customer_price_breaks when present.
    2. Product SupplierPriceBreak rows converted using the standard
       KaleidoBrands customer markup.
    3. Product supplier_price converted using the standard markup.
    4. Product starting_price only as a final already-customer-facing
       fallback for legacy/manual products.

    Returns None when no valid customer price can be resolved.
    """

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return None

    if quantity <= 0:
        return None

    # --------------------------------------------------------------
    # Exact/default variant pricing
    # --------------------------------------------------------------

    variant_breaks = _variant_customer_price_breaks(
        product,
        variant=variant,
    )

    applicable_variant_breaks = [
        row
        for row in variant_breaks
        if row["min_quantity"] <= quantity
    ]

    if applicable_variant_breaks:
        return applicable_variant_breaks[-1][
            "customer_price"
        ]

    # If exact variant pricing exists but the quantity is below its
    # first tier, it is not valid to silently use the cheapest tier.
    if variant_breaks:
        return None

    # --------------------------------------------------------------
    # Product-level SupplierPriceBreak pricing
    # --------------------------------------------------------------

    product_breaks = customer_price_breaks(product)

    applicable_product_breaks = [
        row
        for row in product_breaks
        if (
            row.get("customer_price") is not None
            and row.get("min_quantity") is not None
            and int(row["min_quantity"]) <= quantity
        )
    ]

    if applicable_product_breaks:
        return applicable_product_breaks[-1][
            "customer_price"
        ]

    # Product-level breaks exist, but quantity is below the first
    # available tier.
    if product_breaks:
        return None

    # --------------------------------------------------------------
    # Supplier-price fallback
    # --------------------------------------------------------------

    supplier_price = getattr(
        product,
        "supplier_price",
        None,
    )

    if supplier_price is not None:
        return customer_price_from_supplier_cost(
            supplier_price
        )

    # --------------------------------------------------------------
    # Legacy/manual customer-facing fallback
    # --------------------------------------------------------------

    starting_price = _decimal_or_none(
        getattr(
            product,
            "starting_price",
            None,
        )
    )

    if (
        starting_price is not None
        and starting_price >= 0
    ):
        return starting_price.quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )

    return None

