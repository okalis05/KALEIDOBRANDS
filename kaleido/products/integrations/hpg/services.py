from django.db import transaction
from django.utils import timezone

from products.models import (
    Category,
    Product,
    ProductImage,
    Supplier,
    SupplierCatalog,
    SupplierPriceBreak,
)

from .client import HPGClient
from .mapper import map_product_bundle
from django.utils.text import slugify

HPG_SUPPLIER_NAME = "HPG"
HPG_SUPPLIER_SLUG = "hpg"

DENWELL_CATALOG_EXTERNAL_ID = "denwell-promostandards"

DENWELL_CATALOG_NAME = "Denwell PromoStandards Catalog"


class HPGSyncService:
    """
    Coordinates HPG / Denwell supplier synchronization.

    The client retrieves supplier data.
    The mapper normalizes supplier data.
    This service handles Django model persistence.
    """

    def __init__(
        self,
        *,
        dry_run=False,
        client=None,
    ):
        self.dry_run = dry_run

        self.client = (
            client
            or HPGClient()
        )

    # ==============================================================
    # Supplier / catalog
    # ==============================================================

    def get_supplier(self):
        supplier, _ = (
            Supplier.objects.get_or_create(
                slug=HPG_SUPPLIER_SLUG,
                defaults={
                    "name": HPG_SUPPLIER_NAME,
                    "website": (
                        "https://hpgbrands.com/"
                    ),
                    "api_enabled": True,
                    "is_active": True,
                },
            )
        )

        return supplier

    def get_catalog(
        self,
        supplier,
    ):
        catalog, _ = (
            SupplierCatalog.objects.get_or_create(
                supplier=supplier,
                external_id=DENWELL_CATALOG_EXTERNAL_ID,
                defaults={
                    "name": DENWELL_CATALOG_NAME,
                    "source_type": "api",
                    "description": (
                        "Denwell product data synchronized "
                        "through PromoStandards."
                    ),
                    "is_active": True,
                },
            )
        )

        return catalog

    # ==============================================================
    # Category mapping
    # ==============================================================

    def resolve_category(
        self,
        mapped,
    ):
        """
        Resolve supplier categories into KaleidoBrands storefront
        categories.

        Resolution order:
        1. Exact match against an existing KaleidoBrands category.
        2. Product-name/content based normalization for broad supplier
        categories such as "Auto & Home" or "Other".
        3. Return None when no confident mapping exists.

        We intentionally do not create arbitrary supplier categories.
        """

        supplier_categories = (
            mapped.get("supplier_categories")
            or []
        )

        # ----------------------------------------------------------
        # 1. Exact supplier-category match
        # ----------------------------------------------------------

        for name in supplier_categories:

            category = (
                Category.objects
                .filter(
                    name__iexact=name,
                    is_active=True,
                )
                .first()
            )

            if category:
                return category

        # ----------------------------------------------------------
        # 2. KaleidoBrands category normalization
        # ----------------------------------------------------------

        searchable_text = " ".join(
            [
                str(mapped.get("name") or ""),
                str(mapped.get("short_description") or ""),
                str(mapped.get("description") or ""),
                " ".join(
                    str(value)
                    for value in supplier_categories
                ),
            ]
        ).lower()

        # ----------------------------------------------------------
        # Avoid over-classifying kits/sets from accessory keywords
        # ----------------------------------------------------------

        product_name = (
            str(mapped.get("name") or "")
            .strip()
            .lower()
        )

        ambiguous_product_terms = (
            "kit",
            "set",
            "bundle",
        )

        if any(
            term in product_name
            for term in ambiguous_product_terms
        ):
            return None

        category_keywords = {
            "Drinkware": (
                "mug",
                "tumbler",
                "drinkware",
                "water bottle",
                "sports bottle",
                "vacuum bottle",
                "wine tumbler",
                "beer mug",
                "ceramic mug",
                "glass mug",
                "travel mug",
                "coffee mug",
                "old fashion glass",
                "old fashioned glass",
            ),
            "Apparel": (
                "t-shirt",
                "tee shirt",
                "polo",
                "hoodie",
                "sweatshirt",
                "jacket",
                "shirt",
                "vest",
                "apparel",
            ),
            "Bags": (
                "backpack",
                "tote bag",
                "duffel",
                "drawstring bag",
                "lunch bag",
                "cooler bag",
                "travel bag",
            ),
            "Tech": (
                "power bank",
                "wireless charger",
                "bluetooth",
                "speaker",
                "earbuds",
                "usb",
                "tech accessory",
            ),
            "Writing": (
                "ballpoint pen",
                "rollerball pen",
                "stylus pen",
                "pencil",
                "writing instrument",
                "notebook",
                "journal",
            ),
            "Wellness": (
                "wellness",
                "sanitizer",
                "first aid",
                "fitness",
                "yoga",
            ),
        }

        for category_name, keywords in category_keywords.items():

            if not any(
                keyword in searchable_text
                for keyword in keywords
            ):
                continue

            category = (
                Category.objects
                .filter(
                    name__iexact=category_name,
                    is_active=True,
                )
                .first()
            )

            if category:
                return category

        # ----------------------------------------------------------
        # 3. No confident mapping
        # ----------------------------------------------------------

        return None

    # ==============================================================
    # Product defaults
    # ==============================================================

    def build_product_defaults(
        self,
        mapped,
        supplier,
        catalog,
    ):
        category = self.resolve_category(
            mapped
        )

        now = timezone.now()

        defaults = {
            "supplier": HPG_SUPPLIER_NAME,
            "supplier_record": supplier,
            "catalog": catalog,
            "category": category,

            "name": mapped["name"],

            "short_description": (
                mapped.get(
                    "short_description"
                )
                or ""
            ),

            "description": (
                mapped.get(
                    "description"
                )
                or ""
            ),

            "supplier_price": (
                mapped.get(
                    "supplier_price"
                )
            ),

            "min_quantity": (
                mapped.get(
                    "min_quantity"
                )
                or 1
            ),

            "external_image_url": (
                mapped.get(
                    "external_image_url"
                )
                or ""
            ),

            "source": "PromoStandards",

            "supplier_last_synced_at": now,
            "last_synced_at": now,

            "is_active": (
                not mapped.get(
                    "is_closeout",
                    False,
                )
            ),
            "sku": (
                mapped.get("supplier_sku")
                or ""
            ),

            "supplier_product_id": (
                mapped.get("supplier_product_id")
                or mapped.get("supplier_sku")
                or ""),
    }

        return defaults

    # ==============================================================
    # Product sync
    # ==============================================================

    def sync_product(
        self,
        product_id,
    ):
        bundle = (
            self.client
            .get_product_bundle(
                product_id
            )
        )

        mapped = map_product_bundle(
            bundle
        )

        if self.dry_run:
            return {
                "action": "dry-run",
                "product_id": product_id,
                "mapped": mapped,
            }

        with transaction.atomic():

            supplier = (
                self.get_supplier()
            )

            catalog = (
                self.get_catalog(
                    supplier
                )
            )

            defaults = (
                self.build_product_defaults(
                    mapped,
                    supplier,
                    catalog,
                )
            )

            lookup = {
                "supplier_record": supplier,
                "supplier_sku": mapped[
                    "supplier_sku"
                ],
            }

            existing_product = (
                Product.objects.filter(
                    **lookup
                ).first()
            )

            if existing_product is None:
                defaults["slug"] = (
                    self.generate_unique_slug(
                        mapped.get("name")
                        or mapped[
                            "supplier_sku"
                        ],
                        mapped[
                            "supplier_sku"
                        ],
                    )
                )
                defaults["sku"] = (
                    mapped.get("supplier_sku")
                    or ""
                )


            product, created = (
                Product.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
            )


            self.sync_primary_image(
                product,
                mapped,
            )

            price_break_result = (
                self.sync_price_breaks(
                    product,
                    mapped,
                )
            )

            supplier.last_synced_at = (
                timezone.now()
            )

            supplier.save(
                update_fields=[
                    "last_synced_at"
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_id": product_id,
            "product_pk": product.pk,
            "mapped": mapped,
            "price_breaks": (
                price_break_result
            ),
    }
    def sync_price_breaks(
        self,
        product,
        mapped,
    ):
        """
        Synchronize supplier Net quantity-price breaks.

        Existing price breaks are updated when their values change.

        If the supplier pricing API is temporarily unavailable and
        no price breaks are returned, existing database records are
        preserved.
        """

        price_breaks = (
            mapped.get("price_breaks")
            or []
        )

        if not price_breaks:
            return {
                "created": 0,
                "updated": 0,
                "deleted": 0,
            }

        created_count = 0
        updated_count = 0

        active_keys = set()

        for row in price_breaks:
            min_quantity = row.get(
                "min_quantity"
            )

            price = row.get(
                "price"
            )

            if min_quantity is None:
                continue

            if price is None:
                continue

            part_id = (
                row.get("part_id")
                or ""
            )

            active_keys.add(
                (
                    part_id,
                    min_quantity,
                )
            )

            price_break, created = (
                SupplierPriceBreak.objects.update_or_create(
                    product=product,
                    part_id=part_id,
                    min_quantity=min_quantity,
                    defaults={
                        "price": price,
                        "price_uom": (
                            row.get("price_uom")
                            or ""
                        ),
                        "discount_code": (
                            row.get("discount_code")
                            or ""
                        ),
                        "part_description": (
                            row.get(
                                "part_description"
                            )
                            or ""
                        ),
                        "effective_date": (
                            row.get(
                                "effective_date"
                            )
                        ),
                        "expiry_date": (
                            row.get(
                                "expiry_date"
                            )
                        ),
                    },
                )
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        # Remove old price breaks that the supplier no longer returns.
        deleted_count = 0

        existing_breaks = (
            SupplierPriceBreak.objects
            .filter(product=product)
        )

        for price_break in existing_breaks:
            key = (
                price_break.part_id,
                price_break.min_quantity,
            )

            if key not in active_keys:
                price_break.delete()
                deleted_count += 1

        return {
            "created": created_count,
            "updated": updated_count,
            "deleted": deleted_count,
        }
    # ==============================================================
    # Product image
    # ==============================================================

    def sync_primary_image(
        self,
        product,
        mapped,
    ):
        image_url = (
            mapped.get(
                "external_image_url"
            )
            or ""
        )

        if not image_url:
            return None

        existing = (
            product.gallery_images
            .filter(
                order=0
            )
            .first()
        )

        if existing:
            changed = False

            if (
                existing.external_image_url
                != image_url
            ):
                existing.external_image_url = (
                    image_url
                )
                changed = True

            if not existing.alt_text:
                existing.alt_text = (
                    product.name
                )
                changed = True

            if changed:
                existing.save()

            return existing

        return ProductImage.objects.create(
            product=product,
            external_image_url=image_url,
            alt_text=product.name,
            order=0,
        )

    def generate_unique_slug(
        self,
        name,
        supplier_sku,
    ):
        max_length = (
            Product._meta
            .get_field("slug")
            .max_length
            or 255
        )

        base = slugify(
            f"{name}-{supplier_sku}"
        )

        if not base:
            base = slugify(
                supplier_sku
            ) or "product"

        base = base[:max_length]

        candidate = base
        counter = 2

        while Product.objects.filter(
            slug=candidate
        ).exists():
            suffix = f"-{counter}"

            candidate = (
                base[
                    : max_length
                    - len(suffix)
                ]
                + suffix
            )

            counter += 1

        return candidate