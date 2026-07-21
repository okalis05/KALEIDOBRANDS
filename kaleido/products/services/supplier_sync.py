import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from products.models import Product
from products.services.csv_importer import (
    ProductCSVImporter,
)
from products.services.supplier_inventory import (
    update_supplier_product,
)


DEFAULT_KAESER_BLAIR_CSV_PATH = (
    "data/sample_kaeser_blair_products.csv"
)


ProgressCallback = Callable[..., None]


@dataclass
class SupplierCSVSyncResult:
    """
    Standard result returned by CSV synchronization services.
    """

    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    checkpoint: Dict[str, Any] = field(
        default_factory=dict
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


def resolve_supplier_csv_path(
    file_path=None,
):
    """
    Resolve an absolute supplier CSV path.

    Resolution order:
    1. Explicit file_path argument.
    2. KAESER_BLAIR_CSV_PATH Django setting.
    3. Default sample CSV path.
    """

    configured_path = (
        file_path
        or getattr(
            settings,
            "KAESER_BLAIR_CSV_PATH",
            DEFAULT_KAESER_BLAIR_CSV_PATH,
        )
    )

    path = Path(configured_path)

    if not path.is_absolute():
        path = (
            Path(settings.BASE_DIR)
            / path
        )

    return path


class KaeserBlairCSVSyncService:
    """
    Reusable Kaeser & Blair CSV synchronization workflow.

    This service can be called by:
    - sync_suppliers management command
    - KaeserBlairAdapter
    - SupplierSyncOrchestrator
    - future scheduled jobs
    """

    def __init__(
        self,
        *,
        file_path=None,
    ):
        self.file_path = (
            resolve_supplier_csv_path(
                file_path
            )
        )

        self.csv_importer = (
            ProductCSVImporter()
        )

        self.importer = (
            self.csv_importer.importer
        )

        self.supplier = (
            self.importer.supplier
        )

    def validate(self):
        """
        Validate the configured CSV file and its required columns.
        """

        path = (
            self.csv_importer
            .validate_file_exists(
                self.file_path
            )
        )

        with path.open(
            newline="",
            encoding="utf-8-sig",
        ) as csvfile:
            reader = csv.DictReader(
                csvfile
            )

            self.csv_importer.validate_columns(
                reader.fieldnames
            )

        return path

    def sync_catalog(
        self,
        *,
        checkpoint=None,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Import or update complete supplier product records.

        checkpoint["offset"] is the number of CSV data rows already
        completed during an earlier execution.
        """

        path = self.validate()

        checkpoint = dict(
            checkpoint or {}
        )

        start_offset = self._checkpoint_offset(
            checkpoint
        )

        sync_log = self.importer.start_log()

        processed = 0
        succeeded = 0
        failed = 0
        created = 0
        updated = 0
        current_offset = start_offset

        try:
            with path.open(
                newline="",
                encoding="utf-8-sig",
            ) as csvfile:
                reader = csv.DictReader(
                    csvfile
                )

                self.csv_importer.validate_columns(
                    reader.fieldnames
                )

                for row_index, row in enumerate(
                    reader
                ):
                    if row_index < start_offset:
                        continue

                    normalized = (
                        self.csv_importer
                        .normalize_row(row)
                    )

                    processed += 1
                    current_offset = (
                        row_index + 1
                    )

                    row_succeeded = 0
                    row_failed = 0
                    product = None
                    was_created = False

                    try:
                        with transaction.atomic():
                            product, was_created = (
                                self.importer
                                .import_product_dict(
                                    normalized,
                                    sync_log=sync_log,
                                )
                            )

                        if product is None:
                            failed += 1
                            row_failed = 1
                        else:
                            succeeded += 1
                            row_succeeded = 1

                            if was_created:
                                created += 1
                            else:
                                updated += 1

                    except Exception:
                        failed += 1
                        row_failed = 1

                        sync_log.products_failed += 1

                        sync_log.save(
                            update_fields=[
                                "products_failed",
                            ]
                        )

                    self._notify_progress(
                        progress_callback,
                        processed=1,
                        succeeded=row_succeeded,
                        failed=row_failed,
                        checkpoint={
                            "offset": current_offset,
                        },
                    )

            final_status = (
                "partial"
                if failed
                else "success"
            )

            self.importer.finish_log(
                sync_log,
                status=final_status,
                message=(
                    "CSV catalog synchronization "
                    f"completed. Processed: {processed}, "
                    f"succeeded: {succeeded}, "
                    f"failed: {failed}."
                ),
            )

            self._mark_supplier_synced()

            return SupplierCSVSyncResult(
                processed=processed,
                succeeded=succeeded,
                failed=failed,
                created=created,
                updated=updated,
                checkpoint={
                    "offset": current_offset,
                    "complete": True,
                },
                metadata={
                    "file_path": str(path),
                    "sync_log_id": sync_log.pk,
                    "mode": "csv",
                    "operation": "sync_catalog",
                },
            )

        except Exception as error:
            self.importer.finish_log(
                sync_log,
                status="failed",
                message=str(error),
            )

            raise

    def sync_inventory(
        self,
        *,
        checkpoint=None,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Update supplier price, quantity and discontinued state for
        products already imported into the marketplace.

        Catalog synchronization should run before this operation.
        """

        path = self.validate()

        checkpoint = dict(
            checkpoint or {}
        )

        start_offset = self._checkpoint_offset(
            checkpoint
        )

        sync_log = self.importer.start_log()

        processed = 0
        succeeded = 0
        failed = 0
        updated = 0
        skipped = 0
        current_offset = start_offset

        try:
            with path.open(
                newline="",
                encoding="utf-8-sig",
            ) as csvfile:
                reader = csv.DictReader(
                    csvfile
                )

                self.csv_importer.validate_columns(
                    reader.fieldnames
                )

                for row_index, row in enumerate(
                    reader
                ):
                    if row_index < start_offset:
                        continue

                    normalized = (
                        self.csv_importer
                        .normalize_row(row)
                    )

                    processed += 1
                    current_offset = (
                        row_index + 1
                    )

                    product = self._resolve_product(
                        normalized
                    )

                    if product is None:
                        skipped += 1

                        self._notify_progress(
                            progress_callback,
                            processed=1,
                            succeeded=0,
                            failed=0,
                            skipped=1,
                            checkpoint={
                                "offset": current_offset,
                            },
                        )

                        continue

                    try:
                        supplier_price = (
                            self._supplier_price(
                                normalized
                            )
                        )

                        supplier_inventory = (
                            self._supplier_inventory(
                                normalized
                            )
                        )

                        discontinued = (
                            self._is_discontinued(
                                normalized
                            )
                        )

                        with transaction.atomic():
                            update_supplier_product(
                                product,
                                supplier_price=(
                                    supplier_price
                                ),
                                supplier_inventory=(
                                    supplier_inventory
                                ),
                                discontinued=(
                                    discontinued
                                ),
                            )

                        succeeded += 1
                        updated += 1

                        sync_log.products_updated += 1

                        sync_log.save(
                            update_fields=[
                                "products_updated",
                            ]
                        )

                        self._notify_progress(
                            progress_callback,
                            processed=1,
                            succeeded=1,
                            failed=0,
                            skipped=0,
                            checkpoint={
                                "offset": current_offset,
                            },
                        )

                    except Exception:
                        failed += 1

                        sync_log.products_failed += 1

                        sync_log.save(
                            update_fields=[
                                "products_failed",
                            ]
                        )

                        self._notify_progress(
                            progress_callback,
                            processed=1,
                            succeeded=0,
                            failed=1,
                            skipped=0,
                            checkpoint={
                                "offset": current_offset,
                            },
                        )

            final_status = (
                "partial"
                if failed
                else "success"
            )

            self.importer.finish_log(
                sync_log,
                status=final_status,
                message=(
                    "CSV inventory synchronization "
                    f"completed. Processed: {processed}, "
                    f"updated: {updated}, "
                    f"skipped: {skipped}, "
                    f"failed: {failed}."
                ),
            )

            self._mark_supplier_synced()

            return SupplierCSVSyncResult(
                processed=processed,
                succeeded=succeeded,
                failed=failed,
                updated=updated,
                skipped=skipped,
                checkpoint={
                    "offset": current_offset,
                    "complete": True,
                },
                metadata={
                    "file_path": str(path),
                    "sync_log_id": sync_log.pk,
                    "mode": "csv",
                    "operation": "sync_inventory",
                },
            )

        except Exception as error:
            self.importer.finish_log(
                sync_log,
                status="failed",
                message=str(error),
            )

            raise

    def _resolve_product(
        self,
        row,
    ):
        """
        Resolve an existing supplier product using the strongest
        available supplier identifier.
        """

        queryset = Product.objects.filter(
            supplier_record=self.supplier
        )

        supplier_product_id = str(
            row.get(
                "supplier_product_id",
                "",
            )
            or ""
        ).strip()

        supplier_sku = str(
            row.get("supplier_sku")
            or row.get("sku")
            or ""
        ).strip()

        sku = str(
            row.get("sku")
            or ""
        ).strip()

        if supplier_product_id:
            product = queryset.filter(
                supplier_product_id=(
                    supplier_product_id
                )
            ).first()

            if product is not None:
                return product

        if supplier_sku:
            product = queryset.filter(
                supplier_sku=supplier_sku
            ).first()

            if product is not None:
                return product

        if sku:
            return queryset.filter(
                sku=sku
            ).first()

        return None

    def _supplier_price(
        self,
        row,
    ):
        return (
            row.get("supplier_price")
            or row.get("wholesale_price")
            or row.get("starting_price")
        )

    def _supplier_inventory(
        self,
        row,
    ):
        """
        Preserve zero inventory values instead of losing them through
        Python's truth-value fallback behavior.
        """

        for field_name in (
            "supplier_inventory",
            "inventory",
            "stock",
            "quantity_available",
        ):
            value = row.get(field_name)

            if value not in (
                None,
                "",
            ):
                return value

        return None

    def _is_discontinued(
        self,
        row,
    ):
        value = str(
            row.get(
                "discontinued",
                "",
            )
            or ""
        ).strip().lower()

        return value in {
            "true",
            "1",
            "yes",
            "y",
        }

    def _checkpoint_offset(
        self,
        checkpoint,
    ):
        try:
            return max(
                int(
                    checkpoint.get(
                        "offset",
                        0,
                    )
                    or 0
                ),
                0,
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    def _mark_supplier_synced(self):
        self.supplier.last_synced_at = (
            timezone.now()
        )

        self.supplier.save(
            update_fields=[
                "last_synced_at",
            ]
        )

    def _notify_progress(
        self,
        callback,
        **payload,
    ):
        if callback is None:
            return

        callback(**payload)