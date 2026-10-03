from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
import json
from pathlib import Path
import time

from django.core.management.base import BaseCommand, CommandError

from products.integrations.hpg.client import HPGClient
from products.integrations.hpg.services import HPGSyncService


class Command(BaseCommand):
    help = (
        "Synchronize the Jornik Manufacturing Corp catalog "
        "through PromoStandards / DC OneSource."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--product",
            dest="product_id",
            help="Sync one Jornik parent product ID.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Retrieve and normalize data without "
                "database writes."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of parent products.",
        )

        parser.add_argument(
            "--start-after",
            default=None,
            help=(
                "Start after the supplied product ID. "
                "Useful for controlled resume."
            ),
        )

        parser.add_argument(
            "--change-timestamp",
            default=None,
            help=(
                "Only discover products modified on or after "
                "this ISO-8601 timestamp. If omitted, full "
                "historical discovery is used."
            ),
        )

    def handle(self, *args, **options):
        client = HPGClient(
            brand="jornik"
        )

        service = HPGSyncService(
            brand="jornik",
            dry_run=options["dry_run"],
            client=client,
        )

        self.stdout.write(
            "JORNIK MANUFACTURING CORP"
        )
        self.stdout.write(
            "DC OneSource Supplier ID: "
            "JORNIKMANUFACTURINGCORP"
        )

        discovery = (
            client.get_products_modified_since(
                (
                    options.get("change_timestamp")
                    or datetime(
                        2000,
                        1,
                        1,
                        tzinfo=dt_timezone.utc,
                    )
                )
            )
        )

        rows = (
            discovery.get("items")
            or []
        )

        if not isinstance(rows, list):
            rows = [rows]

        families = defaultdict(list)

        for row in rows:
            if not isinstance(row, dict):
                continue

            product_id = str(
                row.get("productId")
                or ""
            ).strip()

            part_id = str(
                row.get("partId")
                or ""
            ).strip()

            if not product_id:
                continue

            if (
                part_id
                and part_id
                not in families[product_id]
            ):
                families[product_id].append(
                    part_id
                )

            elif product_id not in families:
                families[product_id] = []

        selected_product = (
            options.get("product_id")
        )

        if selected_product:
            selected_product = str(
                selected_product
            ).strip()

            if selected_product not in families:
                raise CommandError(
                    f"Jornik product "
                    f"{selected_product} was not "
                    "found in discovery."
                )

            product_ids = [
                selected_product
            ]

        else:
            product_ids = sorted(
                families
            )

        start_after = (
            options.get("start_after")
        )

        if start_after:
            product_ids = [
                product_id
                for product_id in product_ids
                if product_id > start_after
            ]

        limit = options.get("limit")

        if limit is not None:
            product_ids = (
                product_ids[:limit]
            )

        self.stdout.write(
            f"Discovery rows: {len(rows)}"
        )

        self.stdout.write(
            f"Parents selected: "
            f"{len(product_ids)}"
        )

        succeeded = 0
        failed = 0
        started = time.time()

        checkpoint_dir = Path(
            "var/jornik_sync"
        )

        checkpoint_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        checkpoint_path = (
            checkpoint_dir
            / "checkpoint.json"
        )

        for index, product_id in enumerate(
            product_ids,
            start=1,
        ):
            part_ids = families[
                product_id
            ]

            try:
                if options["dry_run"]:
                    result = (
                        service
                        .build_jornik_parent_dry_run(
                            product_id,
                            part_ids,
                        )
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{index}/"
                            f"{len(product_ids)}] "
                            f"DRY RUN {product_id} "
                            f"variants="
                            f"{result.get('variant_count')} "
                            f"priced="
                            f"{result.get('priced_variant_count')} "
                            f"starting_price="
                            f"{result.get('starting_price')}"
                        )
                    )

                else:
                    result = (
                        service
                        .sync_jornik_parent(
                            product_id,
                            part_ids,
                            complete_family=True,
                        )
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{index}/"
                            f"{len(product_ids)}] "
                            f"{result.get('action')} "
                            f"{product_id} "
                            f"variants="
                            f"{result.get('variant_count')} "
                            f"priced="
                            f"{result.get('priced_variant_count')} "
                            f"starting_price="
                            f"{result.get('starting_price')}"
                        )
                    )

                succeeded += 1

                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "supplier": (
                                "Jornik Manufacturing Corp"
                            ),
                            "last_product_id": (
                                product_id
                            ),
                            "processed": index,
                            "succeeded": succeeded,
                            "failed": failed,
                            "dry_run": (
                                options["dry_run"]
                            ),
                        },
                        indent=2,
                    )
                )

            except Exception as exc:
                failed += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"[{index}/"
                        f"{len(product_ids)}] "
                        f"FAILED {product_id}: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                )

        elapsed = time.time() - started

        self.stdout.write("")
        self.stdout.write(
            "=" * 80
        )
        self.stdout.write(
            "JORNIK SYNC SUMMARY"
        )
        self.stdout.write(
            "=" * 80
        )
        self.stdout.write(
            f"Selected:  {len(product_ids)}"
        )
        self.stdout.write(
            f"Succeeded: {succeeded}"
        )
        self.stdout.write(
            f"Failed:    {failed}"
        )
        self.stdout.write(
            f"Elapsed:   {elapsed:.1f}s"
        )
        self.stdout.write(
            f"Checkpoint: {checkpoint_path}"
        )

        if failed:
            raise CommandError(
                f"Jornik sync completed with "
                f"{failed} failure(s)."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "JORNIK SYNC: PASS"
            )
        )
