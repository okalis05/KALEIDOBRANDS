from products.models import Brand


def marketplace_brands(request):
    """
    Provide customer-facing marketplace brands to the global
    KaleidoBrands base template.

    Only active showcase brands with an attached logo are returned.
    """

    showcase_brands = (
        Brand.objects
        .filter(
            is_active=True,
            show_in_brand_showcase=True,
        )
        .order_by(
            "display_order",
            "name",
        )
    )

    return {
        "showcase_brands": showcase_brands,
    }