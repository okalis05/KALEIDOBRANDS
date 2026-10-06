from datetime import timedelta

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.utils import timezone

from products.integrations.hpg.services import (
    HPGSyncService,
)
from products.models import HPGWeeklySyncCheckpoint


DEFAULT_TEST_PRODUCTS = {
    "denwell": ["GC16"],
    "hubpen": ["208"],
}

SUPPORTED_HPG_BRANDS = (
    "denwell",
    "hubpen",
    "sugarspot",
    "beacon",
    "best",
    "handstands",
    "mixie",
    "origaudio",
    "mapleridge",
)


class Command(BaseCommand):
    help = (
        "Synchronize brand products "
        "through PromoStandards."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--brand",
            choices=SUPPORTED_HPG_BRANDS,
            default="denwell",
            help=(
                "HPG brand to synchronize. "
                "Defaults to denwell."
            ),
        )

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

        parser.add_argument(
            "--resume",
            action="store_true",
            help=(
                "Resume the durable weekly HPG cycle "
                "using the PostgreSQL checkpoint."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        dry_run = options["dry_run"]
        brand = options["brand"]
        resume = options["resume"]

        limit = options.get("limit")
        since_days = options.get(
            "since_days"
        )

        product_ids = (
            options.get("product_ids")
            or []
        )

        explicit_product_ids = bool(
            product_ids
        )

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

        if resume and explicit_product_ids:
            raise CommandError(
                "--resume cannot be combined "
                "with --product-id."
            )

        if resume and since_days is None:
            raise CommandError(
                "--resume requires --since-days."
            )

        service = HPGSyncService(
            brand=brand,
            dry_run=dry_run,
        )

        checkpoint = None
        completed_ids = set()
        discovered_ids = []

        if explicit_product_ids:
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

            discovered_ids = sorted(
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

            product_ids = list(
                discovered_ids
            )

            self.stdout.write(
                f"Modified part records: "
                f"{len(items)}"
            )

            self.stdout.write(
                f"Unique products found: "
                f"{len(product_ids)}"
            )

            if resume:
                if dry_run:
                    checkpoint = (
                        HPGWeeklySyncCheckpoint
                        .objects
                        .filter(
                            brand=brand
                        )
                        .first()
                    )
                else:
                    checkpoint, created = (
                        HPGWeeklySyncCheckpoint
                        .objects
                        .get_or_create(
                            brand=brand,
                            defaults={
                                "window_days":
                                    since_days,
                                "cycle_started_at":
                                    timezone.now(),
                            },
                        )
                    )

                    if (
                        checkpoint.window_days
                        != since_days
                    ):
                        checkpoint.window_days = (
                            since_days
                        )
                        checkpoint.completed_product_ids = []
                        checkpoint.last_product_id = ""
                        checkpoint.cycle_started_at = (
                            timezone.now()
                        )
                        checkpoint.cycle_completed_at = (
                            None
                        )
                        checkpoint.save(
                            update_fields=[
                                "window_days",
                                "completed_product_ids",
                                "last_product_id",
                                "cycle_started_at",
                                "cycle_completed_at",
                                "updated_at",
                            ]
                        )

                if checkpoint is not None:
                    completed_ids = set(
                        checkpoint
                        .completed_product_ids
                        or []
                    )

                remaining_ids = [
                    product_id
                    for product_id
                    in product_ids
                    if product_id
                    not in completed_ids
                ]

                if (
                    not remaining_ids
                    and product_ids
                ):
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Previous HPG weekly cycle "
                            "is complete."
                        )
                    )

                    if not dry_run:
                        checkpoint.completed_product_ids = []
                        checkpoint.last_product_id = ""
                        checkpoint.cycle_started_at = (
                            timezone.now()
                        )
                        checkpoint.cycle_completed_at = (
                            timezone.now()
                        )
                        checkpoint.save(
                            update_fields=[
                                "completed_product_ids",
                                "last_product_id",
                                "cycle_started_at",
                                "cycle_completed_at",
                                "updated_at",
                            ]
                        )

                    completed_ids = set()
                    remaining_ids = list(
                        product_ids
                    )

                product_ids = remaining_ids

                self.stdout.write(
                    f"Checkpoint completed: "
                    f"{len(completed_ids)}"
                )

                self.stdout.write(
                    f"Checkpoint remaining: "
                    f"{len(product_ids)}"
                )

        else:
            if brand not in DEFAULT_TEST_PRODUCTS:
                raise CommandError(
                    f"{brand} requires "
                    "--product-id or --since-days."
                )

            product_ids = list(
                DEFAULT_TEST_PRODUCTS[
                    brand
                ]
            )

        if limit is not None:
            product_ids = (
                product_ids[:limit]
            )

        self.stdout.write(
            f"HPG brand: {brand}"
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

        succeeded = 0
        failed = 0

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
                failed += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"FAILED: {exc}"
                    )
                )
                continue

            succeeded += 1

            if (
                resume
                and not dry_run
                and checkpoint is not None
            ):
                completed_ids.add(
                    product_id
                )

                checkpoint.completed_product_ids = (
                    sorted(
                        completed_ids
                    )
                )

                checkpoint.last_product_id = str(
                    product_id
                )

                checkpoint.save(
                    update_fields=[
                        "completed_product_ids",
                        "last_product_id",
                        "updated_at",
                    ]
                )

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
                        row.get(
                            "part_id"
                        )
                    )
                    + " | Code: "
                    + str(
                        row.get(
                            "discount_code"
                        )
                    )
                )

        if (
            resume
            and not dry_run
            and checkpoint is not None
            and discovered_ids
        ):
            discovered_set = set(
                discovered_ids
            )

            completed_set = set(
                checkpoint.completed_product_ids
                or []
            )

            if discovered_set.issubset(
                completed_set
            ):
                checkpoint.cycle_completed_at = (
                    timezone.now()
                )

                checkpoint.save(
                    update_fields=[
                        "cycle_completed_at",
                        "updated_at",
                    ]
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        "HPG weekly cycle complete "
                        f"for {brand}."
                    )
                )

        self.stdout.write(
            "\n"
            + self.style.SUCCESS(
                "HPG synchronization "
                "command complete."
            )
        )

        self.stdout.write(
            f"Succeeded: {succeeded}"
        )

        self.stdout.write(
            f"Failed: {failed}"
        )

        if failed:
            raise CommandError(
                f"{failed} HPG product "
                "synchronization(s) failed."
            )
