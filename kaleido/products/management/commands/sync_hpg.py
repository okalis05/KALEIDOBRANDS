from datetime import timedelta

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.utils import timezone

from products.integrations.hpg.services import (
    HPGSyncService,
)


DEFAULT_TEST_PRODUCTS = [
    "GC16",
]


class Command(BaseCommand):
    help = (
        "Synchronize HPG / Denwell products "
        "through PromoStandards."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Fetch and map supplier data "
                "without writing to the database."
            ),
        )

        parser.add_argument(
            "--product-id",
            action="append",
            dest="product_ids",
            help=(
                "Supplier product ID to sync. "
                "May be supplied more than once."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=(
                "Maximum number of products "
                "to process."
            ),
        )

        parser.add_argument(
            "--since-days",
            type=int,
            default=None,
            help=(
                "Discover products modified "
                "within the last N days."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        dry_run = options["dry_run"]

        limit = options.get("limit")
        since_days = options.get(
            "since_days"
        )

        product_ids = (
            options.get("product_ids")
            or []
        )

        # Validate arguments.
        if (
            limit is not None
            and limit < 1
        ):
            raise CommandError(
                "--limit must be at least 1."
            )

        if (
            since_days is not None
            and since_days < 1
        ):
            raise CommandError(
                "--since-days must be "
                "at least 1."
            )

        service = HPGSyncService(
            dry_run=dry_run
        )

        #
        # Product selection priority:
        #
        # 1. Explicit --product-id
        # 2. --since-days discovery
        # 3. Default GC16 test product
        #
        if product_ids:
            self.stdout.write(
                "Using explicitly supplied "
                "product IDs."
            )

        elif since_days is not None:
            since = (
                timezone.now()
                - timedelta(
                    days=since_days
                )
            )

            self.stdout.write(
                "Discovering products "
                f"modified since {since}..."
            )

            discovery = (
                service.client
                .get_products_modified_since(
                    since
                )
            )

            items = (
                discovery.get("items")
                or []
            )

            #
            # PromoStandards returns
            # part-level rows.
            #
            # Deduplicate them so each
            # parent product is synced once.
            #
            product_ids = sorted(
                {
                    item.get(
                        "productId"
                    )
                    for item in items
                    if item.get(
                        "productId"
                    )
                }
            )

            self.stdout.write(
                f"Modified part records: "
                f"{len(items)}"
            )

            self.stdout.write(
                f"Unique products found: "
                f"{len(product_ids)}"
            )

        else:
            product_ids = list(
                DEFAULT_TEST_PRODUCTS
            )

        if limit is not None:
            product_ids = (
                product_ids[:limit]
            )

        self.stdout.write(
            f"Products to process: "
            f"{len(product_ids)}"
        )

        if not product_ids:
            self.stdout.write(
                self.style.WARNING(
                    "No products found "
                    "to synchronize."
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — no database "
                    "changes will be saved."
                )
            )

        for product_id in product_ids:

            self.stdout.write(
                "\n"
                + "=" * 60
            )

            self.stdout.write(
                f"Product: {product_id}"
            )

            self.stdout.write(
                "=" * 60
            )

            try:
                result = (
                    service.sync_product(
                        product_id
                    )
                )

            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"FAILED: {exc}"
                    )
                )
                continue

            mapped = result[
                "mapped"
            ]

            self.stdout.write(
                f"Action: "
                f"{result['action']}"
            )

            self.stdout.write(
                f"Name: "
                f"{mapped.get('name')}"
            )

            self.stdout.write(
                f"Supplier SKU: "
                f"{mapped.get('supplier_sku')}"
            )

            self.stdout.write(
                f"Supplier Net Price: "
                f"{mapped.get('supplier_price')}"
            )

            self.stdout.write(
                f"MOQ: "
                f"{mapped.get('min_quantity')}"
            )

            self.stdout.write(
                f"Currency: "
                f"{mapped.get('currency')}"
            )

            self.stdout.write(
                f"Price Type: "
                f"{mapped.get('price_type')}"
            )

            self.stdout.write(
                "Image: "
                + str(
                    mapped.get(
                        "external_image_url"
                    )
                )
            )

            categories = (
                mapped.get(
                    "supplier_categories"
                )
                or []
            )

            self.stdout.write(
                "Supplier Categories: "
                + (
                    ", ".join(
                        categories
                    )
                    if categories
                    else "None"
                )
            )

            self.stdout.write(
                "\nPrice Breaks:"
            )

            for row in (
                mapped.get(
                    "price_breaks"
                )
                or []
            ):
                self.stdout.write(
                    "  "
                    + str(
                        row.get(
                            "min_quantity"
                        )
                    )
                    + " => "
                    + str(
                        row.get(
                            "price"
                        )
                    )
                    + " "
                    + str(
                        row.get(
                            "price_uom"
                        )
                    )
                    + " | Part: "
                    + str(
                         row.get("part_id"
                        )
                    )
                    + " | Code: "
                    + str(
                         row.get("discount_code"))
                )
         

        self.stdout.write(
            "\n"
            + self.style.SUCCESS(
                "HPG synchronization "
                "command complete."
            )
        )