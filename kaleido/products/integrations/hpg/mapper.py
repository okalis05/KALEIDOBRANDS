import ast
import re

from decimal import Decimal
from typing import Any, Dict, List, Optional


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _safe_decimal(value):
    if value in (None, ""):
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _safe_int(value):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except Exception:
        return None

def _normalize_supplier_text(value):
    """
    Convert PromoStandards text values into clean plain text.

    Handles:
    - normal strings
    - lists
    - dictionaries
    - strings that contain Python-style list representations
      such as "['Description text']"
    """

    if value is None:
        return ""

    # ----------------------------------------------------------
    # Some existing records contain a serialized Python list:
    # "['Description text']"
    # ----------------------------------------------------------
    if isinstance(value, str):
        text = value.strip()

        if (
            text.startswith("[")
            and text.endswith("]")
        ):
            try:
                parsed = ast.literal_eval(text)

                if isinstance(parsed, (list, tuple)):
                    return " ".join(
                        _normalize_supplier_text(item)
                        for item in parsed
                        if _normalize_supplier_text(item)
                    ).strip()
            except (
                ValueError,
                SyntaxError,
            ):
                pass

        return text

    # ----------------------------------------------------------
    # Actual supplier arrays
    # ----------------------------------------------------------
    if isinstance(value, (list, tuple)):
        return " ".join(
            _normalize_supplier_text(item)
            for item in value
            if _normalize_supplier_text(item)
        ).strip()

    # ----------------------------------------------------------
    # Nested supplier objects
    # ----------------------------------------------------------
    if isinstance(value, dict):
        for key in (
            "value",
            "description",
            "text",
            "name",
        ):
            if value.get(key):
                return _normalize_supplier_text(
                    value.get(key)
                )

        return ""

    return str(value).strip()


def _extract_customer_description(value):
    """
    Return only customer-facing descriptive prose.

    PromoStandards descriptions may append structured supplier
    metadata directly to the description, for example:

        Material:
        Standard Decoration Includes:
        All Available Decoration Options:
        Standard Packaging:
        Tags:

    Those values should not appear inside marketplace card copy.
    """

    text = _normalize_supplier_text(
        value
    )

    if not text:
        return ""

    markers = (
        "Material:",
        "Standard Decoration Includes:",
        "All Available Decoration Options:",
        "Standard Packaging:",
        "Tags:",
    )

    first_marker_position = None

    for marker in markers:
        position = text.find(marker)

        if position != -1:
            if (
                first_marker_position is None
                or position < first_marker_position
            ):
                first_marker_position = position

    if first_marker_position is not None:
        text = text[
            :first_marker_position
        ]

    # Normalize repeated whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _extract_text_items(container, key):
    """
    Safely extract string-like values from PromoStandards
    nested array structures.
    """

    if not container:
        return []

    items = container.get(key) or []

    values = []

    for item in _as_list(items):
        if isinstance(item, str):
            values.append(item.strip())

        elif isinstance(item, dict):
            for candidate in [
                "value",
                "name",
                "description",
                "keyword",
            ]:
                value = item.get(candidate)

                if value:
                    values.append(
                        str(value).strip()
                    )
                    break

    return [
        value
        for value in values
        if value
    ]


def extract_net_price_breaks(
    pricing,
):
    """
    Convert PromoStandards PartPrice data into a predictable
    list of dictionaries.

    Example:
    [
        {
            "part_id": "603212 GC16",
            "part_description": "Clear",
            "min_quantity": 144,
            "price": Decimal("2.43"),
            "price_uom": "EA",
            "discount_code": "C",
        }
    ]
    """

    if not pricing:
        return []

    part_array = (
        pricing.get("PartArray")
        or {}
    )

    parts = (
        part_array.get("Part")
        or []
    )

    rows = []

    for part in _as_list(parts):

        part_id = part.get(
            "partId"
        )

        part_description = part.get(
            "partDescription"
        )

        price_array = (
            part.get("PartPriceArray")
            or {}
        )

        prices = (
            price_array.get("PartPrice")
            or []
        )

        for price in _as_list(prices):

            amount = _safe_decimal(
                price.get("price")
            )

            minimum = _safe_int(
                price.get("minQuantity")
            )

            if (amount is None 
                or amount <= 0):
                continue

            rows.append(
                {
                    "part_id": part_id,
                    "part_description": (
                        part_description
                    ),
                    "min_quantity": minimum,
                    "price": amount,
                    "price_uom": price.get(
                        "priceUom"
                    ),
                    "discount_code": (
                        price.get(
                            "discountCode"
                        )
                    ),
                    "effective_date": (
                        price.get(
                            "priceEffectiveDate"
                        )
                    ),
                    "expiry_date": (
                        price.get(
                            "priceExpiryDate"
                        )
                    ),
                }
            )

    rows.sort(
        key=lambda row: (
            row["min_quantity"]
            if row["min_quantity"] is not None
            else 10**12
        )
    )

    return rows


def get_lowest_net_price(
    pricing,
):
    """
    Lowest numeric supplier cost across returned price breaks.
    """

    rows = extract_net_price_breaks(
        pricing
    )

    prices = [
        row["price"]
        for row in rows
        if row["price"] is not None
    ]

    if not prices:
        return None

    return min(prices)


def get_moq_net_price(
    pricing,
):
    """
    Return the first quantity break.

    For GC16 this should be:
        MOQ 144
        Net 2.43
    """

    rows = extract_net_price_breaks(
        pricing
    )

    if not rows:
        return None

    return rows[0]


def extract_primary_image_url(
    media,
):
    if not media:
        return ""

    return (
        media.get("url")
        or ""
    ).strip()


def extract_product_category_names(
    product,
):
    """
    Extract supplier category labels without making assumptions
    about KaleidoBrands Category objects yet.
    """

    category_array = (
        product.get("ProductCategoryArray")
        or {}
    )

    categories = (
        category_array.get(
            "ProductCategory"
        )
        or []
    )

    names = []

    for category in _as_list(
        categories
    ):
        if isinstance(
            category,
            str,
        ):
            value = category

        elif isinstance(
            category,
            dict,
        ):
            value = (
                category.get(
                    "category"
                )
                or category.get(
                    "categoryName"
                )
                or category.get(
                    "name"
                )
            )

        else:
            value = None

        if value:
            names.append(
                str(value).strip()
            )

    return names


def map_product_bundle(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert an HPG supplier bundle into normalized data suitable
    for KaleidoBrands.

    IMPORTANT:
    supplier_price = supplier Net cost.

    starting_price is intentionally NOT set here. Customer-facing
    pricing must remain separate from supplier Net cost.
    """

    product = (
        bundle.get("product")
        or {}
    )

    media = bundle.get(
        "primary_image"
    )

    pricing = bundle.get(
        "pricing"
    )

    supplier_sku = (
        product.get("productId")
        or ""
    ).strip()

    name = (
        product.get("productName")
        or supplier_sku
    ).strip()

    description = (
        _extract_customer_description(
            product.get("description")
        )
    )

    primary_image_url = (
        extract_primary_image_url(
            media
        )
    )

    price_breaks = (
        extract_net_price_breaks(
            pricing
        )
    )

    moq_price = (
        get_moq_net_price(
            pricing
        )
    )

    supplier_price = None
    min_quantity = None

    if moq_price:
        supplier_price = (
            moq_price["price"]
        )

        min_quantity = (
            moq_price[
                "min_quantity"
            ]
        )

    product_brand = (
        product.get("productBrand")
        or ""
    )

    categories = (
        extract_product_category_names(
            product
        )
    )

    return {
        # ----------------------------------------------------------
        # Supplier identity
        # ----------------------------------------------------------

        "supplier_sku": (
            supplier_sku
        ),

        "supplier_product_id": (
            supplier_sku
        ),

        # ----------------------------------------------------------
        # Product content
        # ----------------------------------------------------------

        "name": name,

        "description": description,

        "short_description": (
            description[:240]
            if description
            else ""
        ),

        # ----------------------------------------------------------
        # Supplier pricing
        # ----------------------------------------------------------

        "supplier_price": (
            supplier_price
        ),

        "min_quantity": (
            min_quantity
        ),

        "price_breaks": (
            price_breaks
        ),

        "currency": (
            pricing.get(
                "currency"
            )
            if pricing
            else None
        ),

        "price_type": (
            pricing.get(
                "priceType"
            )
            if pricing
            else None
        ),

        # ----------------------------------------------------------
        # Media
        # ----------------------------------------------------------

        "external_image_url": (
            primary_image_url
        ),

        # ----------------------------------------------------------
        # Additional supplier metadata
        # ----------------------------------------------------------

        "supplier_brand": (
            product_brand
        ),

        "supplier_categories": (
            categories
        ),

        "is_closeout": bool(
            product.get(
                "isCloseout"
            )
        ),

        "line_name": (
            product.get(
                "lineName"
            )
            or ""
        ),

        "last_change_date": (
            product.get(
                "lastChangeDate"
            )
        ),

        # ----------------------------------------------------------
        # Preserve raw supplier information for diagnostics / future
        # mapping. This is not automatically written to Product.
        # ----------------------------------------------------------

        "raw": {
            "product": product,
            "media": media,
            "pricing": pricing,
        },
    }