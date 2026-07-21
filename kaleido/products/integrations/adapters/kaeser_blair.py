
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from products.integrations.base import (
    BaseSupplierAdapter,
    SupplierOperationResult,
)
from products.integrations.registry import (
    register_adapter,
)
from products.services.csv_importer import (
    ProductCSVImporter,
)
from products.integrations.kaeser_blair import (
    KaeserBlairImporter,
)
from products.services.purchase_order_delivery import (
    deliver_purchase_order,
)
from products.services.supplier_sync import (
    KaeserBlairCSVSyncService,
)


@register_adapter
class KaeserBlairAdapter(BaseSupplierAdapter):
    """
    Kaeser & Blair integration adapter.

    Current supported transport:
    - CSV and normalized dictionary catalog imports
    - Email-based purchase-order delivery

    API-specific synchronization can be added later without changing the
    adapter contract.
    """

    supplier_slug = "kaeser-blair"
    display_name = "Kaeser & Blair"

    supports_api = False
    supports_csv = True
    supports_purchase_orders = True
    supports_tracking = False

    def test_connection(self):
        mode = (
            "api"
            if self.supplier.api_enabled
            else "csv-and-email"
        )

        return SupplierOperationResult.succeeded(
            "test_connection",
            message=(
                "Kaeser & Blair integration is available."
            ),
            metadata={
                "mode": mode,
                "supplier_active": (
                    self.supplier.is_active
                ),
                "api_enabled": (
                    self.supplier.api_enabled
                ),
                "api_configured": (
                    self.credentials.is_configured
                ),
                "supports_csv": (
                    self.supports_csv
                ),
                "supports_purchase_orders": (
                    self.supports_purchase_orders
                ),
            },
        )

    def fetch_catalog(
        self,
        *,
        file_path=None,
        records=None,
        **kwargs,
    ):
        """
        Import a CSV file or a sequence of normalized product dictionaries.
        """

        if file_path:
            sync_log = (
                ProductCSVImporter().import_csv(
                    file_path
                )
            )

            return SupplierOperationResult.succeeded(
                "fetch_catalog",
                message=(
                    "Kaeser & Blair CSV catalog imported."
                ),
                data={
                    "sync_log_id": sync_log.pk,
                    "products_created": (
                        sync_log.products_created
                    ),
                    "products_updated": (
                        sync_log.products_updated
                    ),
                    "products_failed": (
                        sync_log.products_failed
                    ),
                },
            )

        if records is None:
            raise ValueError(
                (
                    "fetch_catalog requires either "
                    "file_path or records."
                )
            )

        importer = KaeserBlairImporter()
        sync_log = importer.start_log()

        try:
            for record in records:
                normalized = self.normalize_product(
                    record
                )

                importer.import_product_dict(
                    normalized,
                    sync_log=sync_log,
                )

            importer.finish_log(
                sync_log,
                status="success",
                message=(
                    "Supplier product records imported."
                ),
            )

        except Exception as error:
            importer.finish_log(
                sync_log,
                status="failed",
                message=str(error),
            )
            raise

        return SupplierOperationResult.succeeded(
            "fetch_catalog",
            message=(
                "Kaeser & Blair product records imported."
            ),
            data={
                "sync_log_id": sync_log.pk,
                "products_created": (
                    sync_log.products_created
                ),
                "products_updated": (
                    sync_log.products_updated
                ),
                "products_failed": (
                    sync_log.products_failed
                ),
            },
        )
    def sync_catalog(
        self,
        *,
        context=None,
        checkpoint=None,
        correlation_id="",
        file_path=None,
        **kwargs,
    ):
        """
        Synchronize Kaeser & Blair catalog data from the configured CSV
        source.
        """

        file_path = self._resolve_sync_file_path(
            context=context,
            file_path=file_path,
        )

        service = KaeserBlairCSVSyncService(
            file_path=file_path
        )

        result = service.sync_catalog(
            checkpoint=checkpoint,
            progress_callback=(
                self._build_progress_callback(
                    context
                )
            ),
        )

        return {
            "processed": int(result.processed),
            "succeeded": int(result.succeeded),
            "failed": int(result.failed),
            "skipped": int(result.skipped),
            "checkpoint": _json_safe(
                result.checkpoint or {}
            ),
            "metadata": _json_safe(
                {
                **dict(result.metadata or {}),
                "created": int(result.created),
                "updated": int(result.updated),
                "supplier_slug": str(
                    self.supplier.slug
                ),
                "correlation_id": str(
                    correlation_id or ""
                ),
            },
            )
        }


    def sync_inventory(
        self,
        *,
        context=None,
        checkpoint=None,
        correlation_id="",
        file_path=None,
        **kwargs,
    ):
        """
        Synchronize inventory, price and discontinued state from CSV.
        """

        file_path = self._resolve_sync_file_path(
            context=context,
            file_path=file_path,
        )

        service = KaeserBlairCSVSyncService(
            file_path=file_path
        )

        result = service.sync_inventory(
            checkpoint=checkpoint,
            progress_callback=(
                self._build_progress_callback(
                    context
                )
            ),
        )

        return {
            "processed": int(result.processed),
            "succeeded": int(result.succeeded),
            "failed": int(result.failed),
            "skipped": int(result.skipped),
            "checkpoint": dict(
                result.checkpoint or {}
            ),
            "metadata": {
                **dict(result.metadata or {}
                ),
                "updated": int(result.updated),
                "supplier_slug": str(
                    self.supplier.slug
                ),
                "correlation_id": str(
                    correlation_id or ""
                ),
            },
        }


    def fetch_catalog(
        self,
        **kwargs,
    ):
        """
        Backward-compatible alias.
        """

        return self.sync_catalog(
            **kwargs
        )


    def fetch_inventory(
        self,
        **kwargs,
    ):
        """
        Backward-compatible alias.
        """

        return self.sync_inventory(
            **kwargs
        )


    def _resolve_sync_file_path(
        self,
        *,
        context=None,
        file_path=None,
    ):
        if file_path:
            return file_path

        if context is None:
            return None

        job = getattr(
            context,
            "job",
            None,
        )

        batch = getattr(
            job,
            "batch",
            None,
        )

        metadata = getattr(
            batch,
            "metadata",
            None,
        ) or {}

        return metadata.get(
            "file_path"
        )


    def _build_progress_callback(
        self,
        context,
    ):
        """
        Save resumable checkpoints during execution.

        Final job counters should be written from the returned operation
        result by the orchestrator. This prevents double-counting.
        """

        if context is None:
            return None

        def callback(
            *,
            checkpoint=None,
            **kwargs,
        ):
            if not checkpoint:
                return

            save_checkpoint = getattr(
                context,
                "save_checkpoint",
                None,
            )

            if callable(save_checkpoint):
                save_checkpoint(
                    **checkpoint
                )

        return callback

    def submit_purchase_order(
        self,
        purchase_order,
        *,
        user=None,
        **kwargs,
    ):
        success, message = deliver_purchase_order(
            purchase_order,
            user=user,
        )

        if success:
            purchase_order.refresh_from_db()

            return SupplierOperationResult.succeeded(
                "submit_purchase_order",
                message=message,
                external_reference=(
                    purchase_order.supplier_reference
                    or purchase_order.po_number
                ),
                data={
                    "purchase_order_id": (
                        purchase_order.pk
                    ),
                    "po_number": (
                        purchase_order.po_number
                    ),
                    "status": (
                        purchase_order.status
                    ),
                },
            )

        return SupplierOperationResult.failed(
            "submit_purchase_order",
            message=message,
            data={
                "purchase_order_id": (
                    purchase_order.pk
                ),
                "po_number": (
                    purchase_order.po_number
                ),
            },
        )

    def normalize_product(self, payload):
        """
        Normalize a supplier product record for KaeserBlairImporter.
        """

        payload = dict(payload or {})

        return {
            "name": str(
                payload.get("name", "")
            ).strip(),
            "sku": str(
                payload.get(
                    "sku",
                    payload.get(
                        "supplier_sku",
                        "",
                    ),
                )
            ).strip(),
            "category": str(
                payload.get(
                    "category",
                    "Promotional Products",
                )
            ).strip(),
            "short_description": str(
                payload.get(
                    "short_description",
                    "",
                )
            ).strip(),
            "description": str(
                payload.get(
                    "description",
                    "",
                )
            ).strip(),
            "starting_price": payload.get(
                "starting_price",
                payload.get("price"),
            ),
            "supplier_price": payload.get(
                "supplier_price",
                payload.get(
                    "wholesale_price",
                ),
            ),
            "min_quantity": payload.get(
                "min_quantity",
                payload.get(
                    "minimum_quantity",
                    1,
                ),
            ),
            "supplier_inventory": payload.get(
                "supplier_inventory",
                payload.get(
                    "inventory",
                ),
            ),
            "discontinued": payload.get(
                "discontinued",
                False,
            ),
            "colors": payload.get(
                "colors",
                "",
            ),
            "decoration_methods": payload.get(
                "decoration_methods",
                "",
            ),
            "industries": payload.get(
                "industries",
                "",
            ),
            "material": payload.get(
                "material",
                "",
            ),
            "dimensions": payload.get(
                "dimensions",
                "",
            ),
            "lead_time": payload.get(
                "lead_time",
                "Varies by product",
            ),
            "setup_fee": payload.get(
                "setup_fee",
                "Varies",
            ),
            "supplier_product_id": str(
                payload.get(
                    "supplier_product_id",
                    payload.get("id", ""),
                )
            ).strip(),
            "supplier_url": str(
                payload.get(
                    "supplier_url",
                    payload.get("url", ""),
                )
            ).strip(),
            "image_url": str(
                payload.get(
                    "image_url",
                    "",
                )
            ).strip(),
            "gallery_urls": payload.get(
                "gallery_urls",
                [],
            ),
            "catalog_name": str(
                payload.get(
                    "catalog_name",
                    "",
                )
            ).strip(),
            "catalog_url": str(
                payload.get(
                    "catalog_url",
                    "",
                )
            ).strip(),
        }
    def test_kaeser_blair_reports_catalog_sync_support(
        self,
    ):
        adapter = KaeserBlairAdapter(
            self.supplier
        )

        self.assertIn(
            "sync_catalog",
            adapter.supported_sync_operations(),
        )


    def test_kaeser_blair_reports_inventory_sync_support(
        self,
    ):
        adapter = KaeserBlairAdapter(
            self.supplier
        )

        self.assertIn(
            "sync_inventory",
            adapter.supported_sync_operations(),
        )


    def test_kaeser_blair_does_not_report_unimplemented_sync_support(
        self,
    ):
        adapter = KaeserBlairAdapter(
            self.supplier
        )

        supported = (
            adapter.supported_sync_operations()
        )

        self.assertNotIn(
            "sync_pricing",
            supported,
        )

        self.assertNotIn(
            "sync_images",
            supported,
        )

        self.assertNotIn(
            "sync_discontinued",
            supported,
        )


def _json_safe(value):
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    if isinstance(
        value,
        (
            Path,
            UUID,
        ),
    ):
        return str(value)

    if isinstance(
        value,
        (
            datetime,
            date,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    return str(value)