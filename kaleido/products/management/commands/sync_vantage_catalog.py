
from collections import OrderedDict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from django.core.management.base import BaseCommand, CommandError

from products.integrations.hpg.client import HPGClient
from products.integrations.hpg.services import HPGSyncService


DEFAULT_CHANGE_TIMESTAMP = "2000-01-01T00:00:00"

CHECKPOINT_DIR = Path("var/vantage_sync")
CHECKPOINT_FILE = CHECKPOINT_DIR / "checkpoint.json"


class Command(BaseCommand):
    help = (
        "Synchronize the VANTAGE PromoStandards catalog using "
        "complete parent/variant families."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Retrieve and normalize selected parent families "
                "without database writes."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=(
                "Maximum number of parent families to process."
            ),
        )

        parser.add_argument(
            "--start-after",
            type=str,
            default=None,
            help=(
                "Start after the specified parent product ID."
            ),
        )

        parser.add_argument(
            "--product-id",
            type=str,
            default=None,
            help=(
                "Process exactly one VANTAGE parent product."
            ),
        )

        parser.add_argument(
            "--resume",
            action="store_true",
            help=(
                "Skip parent IDs already recorded as successful "
                "in the checkpoint."
            ),
        )

        parser.add_argument(
            "--change-timestamp",
            type=str,
            default=DEFAULT_CHANGE_TIMESTAMP,
            help=(
                "PromoStandards getProductDateModified timestamp."
            ),
        )

        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help=(
                "Continue to the next parent after an isolated "
                "parent failure."
            ),
        )

    # ==============================================================
    # Checkpoint helpers
    # ==============================================================

    def _empty_checkpoint(self):
        return {
            "version": 1,
            "supplier": "VANTAGE",
            "successful_parent_ids": [],
            "failed_parent_ids": {},
            "last_successful_parent_id": None,
            "updated_at": None,
        }

    def _load_checkpoint(self):
        if not CHECKPOINT_FILE.exists():
            return self._empty_checkpoint()

        try:
            with CHECKPOINT_FILE.open(
                "r",
                encoding="utf-8",
            ) as handle:
                data = json.load(handle)
        except Exception as exc:
            raise CommandError(
                f"Could not read VANTAGE checkpoint: {exc}"
            )

        if not isinstance(data, dict):
            raise CommandError(
                "VANTAGE checkpoint is not a JSON object."
            )

        checkpoint = self._empty_checkpoint()
        checkpoint.update(data)

        checkpoint["successful_parent_ids"] = [
            str(value)
            for value in (
                checkpoint.get(
                    "successful_parent_ids"
                )
                or []
            )
        ]

        checkpoint["failed_parent_ids"] = {
            str(key): value
            for key, value in (
                checkpoint.get(
                    "failed_parent_ids"
                )
                or {}
            ).items()
        }

        return checkpoint

    def _save_checkpoint(self, checkpoint):
        CHECKPOINT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        checkpoint["updated_at"] = (
            datetime.now(timezone.utc)
            .isoformat()
        )

        temporary_file = CHECKPOINT_FILE.with_suffix(
            ".tmp"
        )

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                checkpoint,
                handle,
                indent=2,
                sort_keys=True,
            )

        temporary_file.replace(
            CHECKPOINT_FILE
        )

    # ==============================================================
    # Discovery
    # ==============================================================

    def _discover_families(
        self,
        client,
        change_timestamp,
    ):
        response = (
            client.get_products_modified_since(
                change_timestamp
            )
        )

        items = response.get("items") or []

        families = OrderedDict()

        raw_rows = 0

        for row in items:
            product_id = str(
                row.get("productId") or ""
            ).strip()

            part_id = str(
                row.get("partId") or ""
            ).strip()

            if not product_id or not part_id:
                continue

            raw_rows += 1

            if product_id not in families:
                families[product_id] = []

            if part_id not in families[product_id]:
                families[product_id].append(
                    part_id
                )

        return {
            "messages": response.get(
                "messages"
            ),
            "total_rows": len(items),
            "usable_rows": raw_rows,
            "families": families,
        }

    # ==============================================================
    # Selection
    # ==============================================================

    def _select_families(
        self,
        families,
        *,
        product_id=None,
        start_after=None,
        limit=None,
        resume=False,
        successful_ids=None,
    ):
        successful_ids = set(
            successful_ids or []
        )

        entries = list(
            families.items()
        )

        if product_id:
            product_id = str(
                product_id
            ).strip()

            if product_id not in families:
                raise CommandError(
                    f"VANTAGE product {product_id} "
                    "was not present in discovery."
                )

            entries = [
                (
                    product_id,
                    families[product_id],
                )
            ]

        elif start_after:
            start_after = str(
                start_after
            ).strip()

            product_ids = [
                value[0]
                for value in entries
            ]

            if start_after not in product_ids:
                raise CommandError(
                    f"--start-after product "
                    f"{start_after} was not found "
                    "in VANTAGE discovery."
                )

            start_index = (
                product_ids.index(
                    start_after
                )
                + 1
            )

            entries = entries[
                start_index:
            ]

        if resume:
            entries = [
                entry
                for entry in entries
                if entry[0]
                not in successful_ids
            ]

        if limit is not None:
            if limit < 1:
                raise CommandError(
                    "--limit must be at least 1."
                )

            entries = entries[:limit]

        return entries

    # ==============================================================
    # Main
    # ==============================================================

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        start_after = options[
            "start_after"
        ]
        product_id = options[
            "product_id"
        ]
        resume = options["resume"]
        continue_on_error = options[
            "continue_on_error"
        ]
        change_timestamp = options[
            "change_timestamp"
        ]

        self.stdout.write(
            "=" * 100
        )
        self.stdout.write(
            "VANTAGE PRODUCTION CATALOG SYNC"
        )
        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            f"MODE: "
            f"{'DRY RUN' if dry_run else 'WRITE'}"
        )

        self.stdout.write(
            f"CHANGE TIMESTAMP: "
            f"{change_timestamp}"
        )

        client = HPGClient(
            brand="vantage"
        )

        self.stdout.write(
            "\nDiscovering VANTAGE catalog..."
        )

        discovery = (
            self._discover_families(
                client,
                change_timestamp,
            )
        )

        families = discovery[
            "families"
        ]

        self.stdout.write(
            f"DISCOVERY ROWS: "
            f"{discovery['total_rows']}"
        )

        self.stdout.write(
            f"USABLE PART ROWS: "
            f"{discovery['usable_rows']}"
        )

        self.stdout.write(
            f"UNIQUE PARENTS: "
            f"{len(families)}"
        )

        total_unique_parts = sum(
            len(part_ids)
            for part_ids
            in families.values()
        )

        self.stdout.write(
            f"UNIQUE PARTS: "
            f"{total_unique_parts}"
        )

        if not families:
            raise CommandError(
                "VANTAGE discovery returned "
                "no usable parent families."
            )

        checkpoint = (
            self._load_checkpoint()
        )

        successful_ids = set(
            checkpoint.get(
                "successful_parent_ids"
            )
            or []
        )

        selected = (
            self._select_families(
                families,
                product_id=product_id,
                start_after=start_after,
                limit=limit,
                resume=resume,
                successful_ids=successful_ids,
            )
        )

        self.stdout.write(
            f"SELECTED PARENTS: "
            f"{len(selected)}"
        )

        selected_parts = sum(
            len(part_ids)
            for _, part_ids
            in selected
        )

        self.stdout.write(
            f"SELECTED PARTS: "
            f"{selected_parts}"
        )

        if not selected:
            self.stdout.write(
                self.style.WARNING(
                    "Nothing selected."
                )
            )
            return

        service = HPGSyncService(
            brand="vantage",
            dry_run=dry_run,
        )

        succeeded = 0
        failed = 0

        started_at = time.monotonic()

        for index, (
            current_product_id,
            part_ids,
        ) in enumerate(
            selected,
            start=1,
        ):
            parent_started = (
                time.monotonic()
            )

            self.stdout.write("")
            self.stdout.write(
                "-" * 100
            )

            self.stdout.write(
                f"[{index}/{len(selected)}] "
                f"PARENT "
                f"{current_product_id} "
                f"| VARIANTS "
                f"{len(part_ids)}"
            )

            try:
                result = (
                    service.sync_vantage_parent(
                        current_product_id,
                        part_ids,
                        complete_family=True,
                    )
                )

                elapsed = (
                    time.monotonic()
                    - parent_started
                )

                succeeded += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"SUCCESS "
                        f"{current_product_id} "
                        f"| action="
                        f"{result.get('action')} "
                        f"| variants="
                        f"{result.get('variant_count')} "
                        f"| elapsed="
                        f"{elapsed:.1f}s"
                    )
                )

                # Dry runs must never change
                # the production checkpoint.
                if not dry_run:
                    product_key = str(
                        current_product_id
                    )

                    if (
                        product_key
                        not in successful_ids
                    ):
                        successful_ids.add(
                            product_key
                        )

                    checkpoint[
                        "successful_parent_ids"
                    ] = sorted(
                        successful_ids
                    )

                    checkpoint[
                        "last_successful_parent_id"
                    ] = product_key

                    checkpoint[
                        "failed_parent_ids"
                    ].pop(
                        product_key,
                        None,
                    )

                    self._save_checkpoint(
                        checkpoint
                    )

            except Exception as exc:
                elapsed = (
                    time.monotonic()
                    - parent_started
                )

                failed += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"FAILED "
                        f"{current_product_id} "
                        f"| variants="
                        f"{len(part_ids)} "
                        f"| elapsed="
                        f"{elapsed:.1f}s "
                        f"| {type(exc).__name__}: "
                        f"{exc}"
                    )
                )

                if not dry_run:
                    checkpoint[
                        "failed_parent_ids"
                    ][
                        str(
                            current_product_id
                        )
                    ] = {
                        "error_type": (
                            type(exc).__name__
                        ),
                        "error": str(exc),
                        "updated_at": (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        ),
                    }

                    self._save_checkpoint(
                        checkpoint
                    )

                if not continue_on_error:
                    raise CommandError(
                        "VANTAGE synchronization "
                        "stopped after parent "
                        f"{current_product_id} "
                        "failed."
                    ) from exc

        elapsed_total = (
            time.monotonic()
            - started_at
        )

        self.stdout.write("")
        self.stdout.write(
            "=" * 100
        )
        self.stdout.write(
            "VANTAGE SYNC SUMMARY"
        )
        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            f"SELECTED: {len(selected)}"
        )

        self.stdout.write(
            f"SUCCEEDED: {succeeded}"
        )

        self.stdout.write(
            f"FAILED: {failed}"
        )

        self.stdout.write(
            f"ELAPSED: "
            f"{elapsed_total:.1f}s"
        )

        if dry_run:
            self.stdout.write(
                "CHECKPOINT UPDATED: NO "
                "(dry run)"
            )
        else:
            self.stdout.write(
                f"CHECKPOINT: "
                f"{CHECKPOINT_FILE}"
            )

        if failed:
            self.stdout.write(
                self.style.WARNING(
                    "VANTAGE SYNC COMPLETED "
                    "WITH FAILURES"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "VANTAGE SYNC: PASS"
                )
            )
