from pathlib import Path

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
from products.services.kaeser_blair import (
    KaeserBlairImporter,
)
from products.services.purchase_order_delivery import (
    deliver_purchase_order,
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