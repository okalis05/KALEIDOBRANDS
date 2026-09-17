import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import (
    Category,
    Product,
    ProductImage,
    Supplier,
    SupplierCatalog,
    SupplierPriceBreak,
)


class Command(BaseCommand):
    help = (
        "Load the approved HPG catalog into production "
        "using supplier SKU based upserts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="products/fixtures/hpg_catalog.json",
            help="Path to the approved HPG catalog fixture.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the complete import and roll it back.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"])
        dry_run = options["dry_run"]

        if not fixture_path.exists():
            raise CommandError(
                f"Fixture not found: {fixture_path}"
            )

        with fixture_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        # --------------------------------------------------
        # Validate fixture
        # --------------------------------------------------

        fixture_products = [
            item
            for item in data
            if item["model"] == "products.product"
        ]

        if len(fixture_products) != 61:
            raise CommandError(
                "Safety check failed: expected exactly "
                f"61 HPG products, found "
                f"{len(fixture_products)}."
            )

        supplier_values = {
            item["fields"].get("supplier")
            for item in fixture_products
        }

        if supplier_values != {"HPG"}:
            raise CommandError(
                "Safety check failed: fixture contains "
                "non-HPG products."
            )

        supplier_skus = [
            item["fields"].get("supplier_sku")
            for item in fixture_products
        ]

        if (
            None in supplier_skus
            or "" in supplier_skus
            or len(set(supplier_skus)) != 61
        ):
            raise CommandError(
                "Safety check failed: supplier SKUs "
                "must be present and unique."
            )

        # --------------------------------------------------
        # Supplier
        # --------------------------------------------------

        supplier_items = [
            item
            for item in data
            if item["model"] == "products.supplier"
        ]

        if len(supplier_items) != 1:
            raise CommandError(
                "Safety check failed: expected exactly "
                "one supplier record."
            )

        supplier_fields = supplier_items[0]["fields"]

        supplier, supplier_created = (
            Supplier.objects.update_or_create(
                slug="hpg",
                defaults={
                    "name": supplier_fields.get(
                        "name",
                        "HPG",
                    ),
                    "website": supplier_fields.get(
                        "website",
                        "",
                    ),
                    "api_base_url": supplier_fields.get(
                        "api_base_url",
                        "",
                    ),
                    "is_active": supplier_fields.get(
                        "is_active",
                        True,
                    ),
                    "api_enabled": supplier_fields.get(
                        "api_enabled",
                        True,
                    ),
                    "api_key_name": supplier_fields.get(
                        "api_key_name",
                        "",
                    ),
                    "sync_frequency_hours": (
                        supplier_fields.get(
                            "sync_frequency_hours",
                            24,
                        )
                    ),
                    "email": supplier_fields.get(
                        "email",
                        "",
                    ),
                },
            )
        )

        # --------------------------------------------------
        # Categories
        # --------------------------------------------------

        category_map = {}

        for item in data:
            if item["model"] != "products.category":
                continue

            fields = item["fields"]

            category, _ = (
                Category.objects.update_or_create(
                    slug=fields["slug"],
                    defaults={
                        "name": fields["name"],
                        "icon": fields.get(
                            "icon",
                            "",
                        ),
                        "description": fields.get(
                            "description",
                            "",
                        ),
                        "banner_image": fields.get(
                            "banner_image",
                            "",
                        ),
                        "is_active": fields.get(
                            "is_active",
                            True,
                        ),
                        "order": fields.get(
                            "order",
                            0,
                        ),
                    },
                )
            )

            category_map[item["pk"]] = category

        # --------------------------------------------------
        # Supplier catalogs
        # --------------------------------------------------

        catalog_map = {}

        for item in data:
            if (
                item["model"]
                != "products.suppliercatalog"
            ):
                continue

            fields = item["fields"]

            external_id = (
                fields.get("external_id")
                or ""
            )

            if external_id:
                lookup = {
                    "supplier": supplier,
                    "external_id": external_id,
                }
            else:
                lookup = {
                    "supplier": supplier,
                    "name": fields["name"],
                }

            catalog, _ = (
                SupplierCatalog.objects.update_or_create(
                    **lookup,
                    defaults={
                        "name": fields["name"],
                        "catalog_url": fields.get(
                            "catalog_url",
                            "",
                        ),
                        "description": fields.get(
                            "description",
                            "",
                        ),
                        "cover_image": fields.get(
                            "cover_image",
                            "",
                        ),
                        "year": fields.get("year"),
                        "valid_from": fields.get(
                            "valid_from"
                        ),
                        "valid_until": fields.get(
                            "valid_until"
                        ),
                        "source_type": fields.get(
                            "source_type",
                            "other",
                        ),
                        "metadata": fields.get(
                            "metadata",
                            {},
                        ),
                        "is_active": fields.get(
                            "is_active",
                            True,
                        ),
                    },
                )
            )

            catalog_map[item["pk"]] = catalog

        # --------------------------------------------------
        # Products
        # --------------------------------------------------

        product_map = {}

        created_count = 0
        updated_count = 0

        relationship_fields = {
            "category",
            "supplier_record",
            "catalog",
            "industry_groups",
            "collections",
            "imprint_methods",
        }

        for item in fixture_products:
            fields = dict(item["fields"])

            supplier_sku = fields["supplier_sku"]

            local_category_id = fields.get(
                "category"
            )

            local_catalog_id = fields.get(
                "catalog"
            )

            defaults = {}

            for field, value in fields.items():
                if field in relationship_fields:
                    continue

                defaults[field] = value

            defaults["supplier"] = "HPG"
            defaults["supplier_record"] = supplier

            defaults["category"] = category_map.get(
                local_category_id
            )

            defaults["catalog"] = catalog_map.get(
                local_catalog_id
            )

            product, created = (
                Product.objects.update_or_create(
                    supplier_record=supplier,
                    supplier_sku=supplier_sku,
                    defaults=defaults,
                )
            )

            product_map[item["pk"]] = product

            if created:
                created_count += 1
            else:
                updated_count += 1

        # --------------------------------------------------
        # Product images
        # --------------------------------------------------

        fixture_images = [
            item
            for item in data
            if item["model"] == "products.productimage"
        ]

        images_by_product = {}

        for item in fixture_images:
            local_product_id = (
                item["fields"]["product"]
            )

            images_by_product.setdefault(
                local_product_id,
                [],
            ).append(item)

        image_count = 0

        for local_pk, product in product_map.items():
            ProductImage.objects.filter(
                product=product
            ).delete()

            for item in images_by_product.get(
                local_pk,
                [],
            ):
                fields = item["fields"]

                ProductImage.objects.create(
                    product=product,
                    image=fields.get(
                        "image",
                        "",
                    ),
                    external_image_url=fields.get(
                        "external_image_url",
                        "",
                    ),
                    alt_text=fields.get(
                        "alt_text",
                        "",
                    ),
                    order=fields.get(
                        "order",
                        0,
                    ),
                )

                image_count += 1

        # --------------------------------------------------
        # Supplier price breaks
        # --------------------------------------------------

        fixture_breaks = [
            item
            for item in data
            if (
                item["model"]
                == "products.supplierpricebreak"
            )
        ]

        breaks_by_product = {}

        for item in fixture_breaks:
            local_product_id = (
                item["fields"]["product"]
            )

            breaks_by_product.setdefault(
                local_product_id,
                [],
            ).append(item)

        price_break_count = 0

        for local_pk, product in product_map.items():
            SupplierPriceBreak.objects.filter(
                product=product
            ).delete()

            for item in breaks_by_product.get(
                local_pk,
                [],
            ):
                fields = item["fields"]

                SupplierPriceBreak.objects.create(
                    product=product,
                    min_quantity=fields[
                        "min_quantity"
                    ],
                    price=fields["price"],
                    price_uom=fields.get(
                        "price_uom",
                        "",
                    ),
                    discount_code=fields.get(
                        "discount_code",
                        "",
                    ),
                    part_id=fields.get(
                        "part_id",
                        "",
                    ),
                    part_description=fields.get(
                        "part_description",
                        "",
                    ),
                    effective_date=fields.get(
                        "effective_date"
                    ),
                    expiry_date=fields.get(
                        "expiry_date"
                    ),
                )

                price_break_count += 1

        # --------------------------------------------------
        # Verification
        # --------------------------------------------------

        gc16 = Product.objects.filter(
            supplier_record=supplier,
            supplier_sku="GC16",
        ).first()

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "HPG Production Catalog Import"
            )
        )

        self.stdout.write(
            "Supplier: HPG "
            f"({'created' if supplier_created else 'updated'})"
        )

        self.stdout.write(
            f"Products created: {created_count}"
        )

        self.stdout.write(
            f"Products updated: {updated_count}"
        )

        self.stdout.write(
            f"Products processed: {len(product_map)}"
        )

        self.stdout.write(
            f"Images imported: {image_count}"
        )

        self.stdout.write(
            f"Price breaks imported: {price_break_count}"
        )

        if gc16:
            self.stdout.write("")
            self.stdout.write("GC16 verification:")
            self.stdout.write(
                f"  Public price: {gc16.starting_price}"
            )
            self.stdout.write(
                f"  Supplier cost: {gc16.supplier_price}"
            )
            self.stdout.write(
                f"  MOQ: {gc16.min_quantity}"
            )
            self.stdout.write(
                f"  Slug: {gc16.slug}"
            )

        if dry_run:
            transaction.set_rollback(True)

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: all database changes "
                    "were rolled back."
                )
            )

        else:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    "IMPORT COMPLETE"
                )
            )