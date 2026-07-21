import csv
import tempfile
from pathlib import Path

from django.test import TestCase

from products.models import (
    Product,
    SupplierInventoryHistory,
    SupplierPriceHistory,
)
from products.services.supplier_sync import (
    KaeserBlairCSVSyncService,
)


class KaeserBlairCSVSyncServiceTests(
    TestCase
):
    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.file_path = (
            Path(
                self.temp_directory.name
            )
            / "supplier.csv"
        )

        self.fieldnames = [
            "name",
            "sku",
            "supplier_sku",
            "category",
            "starting_price",
            "supplier_price",
            "supplier_inventory",
            "discontinued",
            "image_url",
        ]

        self.write_rows(
            [
                {
                    "name": "Executive Pen",
                    "sku": "KB-PEN-1",
                    "supplier_sku": "KB-PEN-1",
                    "category": "Pens",
                    "starting_price": "2.25",
                    "supplier_price": "1.50",
                    "supplier_inventory": "100",
                    "discontinued": "false",
                    "image_url": (
                        "https://example.com/pen.jpg"
                    ),
                }
            ]
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def write_rows(
        self,
        rows,
    ):
        with self.file_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=self.fieldnames,
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(row)

    def test_catalog_sync_creates_product(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        result = service.sync_catalog()

        self.assertEqual(
            result.processed,
            1,
        )

        self.assertEqual(
            result.succeeded,
            1,
        )

        self.assertEqual(
            result.failed,
            0,
        )

        self.assertEqual(
            result.created,
            1,
        )

        product = Product.objects.get(
            sku="KB-PEN-1"
        )

        self.assertEqual(
            product.supplier_sku,
            "KB-PEN-1",
        )

        self.assertEqual(
            product.supplier_inventory,
            100,
        )

        self.assertEqual(
            str(product.supplier_price),
            "1.50",
        )

        self.assertEqual(
            product.inventory_status,
            "in_stock",
        )

    def test_catalog_sync_updates_existing_product(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        first_result = (
            service.sync_catalog()
        )

        second_result = (
            service.sync_catalog()
        )

        self.assertEqual(
            first_result.created,
            1,
        )

        self.assertEqual(
            second_result.updated,
            1,
        )

        self.assertEqual(
            Product.objects.filter(
                sku="KB-PEN-1"
            ).count(),
            1,
        )

    def test_inventory_sync_updates_existing_product(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        service.sync_catalog()

        self.write_rows(
            [
                {
                    "name": "Executive Pen",
                    "sku": "KB-PEN-1",
                    "supplier_sku": "KB-PEN-1",
                    "category": "Pens",
                    "starting_price": "2.25",
                    "supplier_price": "1.75",
                    "supplier_inventory": "10",
                    "discontinued": "false",
                    "image_url": (
                        "https://example.com/pen.jpg"
                    ),
                }
            ]
        )

        result = (
            service.sync_inventory()
        )

        product = Product.objects.get(
            sku="KB-PEN-1"
        )

        self.assertEqual(
            result.updated,
            1,
        )

        self.assertEqual(
            product.supplier_inventory,
            10,
        )

        self.assertEqual(
            product.inventory_status,
            "low_stock",
        )

        self.assertEqual(
            str(product.supplier_price),
            "1.75",
        )

        self.assertTrue(
            SupplierPriceHistory.objects.filter(
                product=product
            ).exists()
        )

        self.assertTrue(
            SupplierInventoryHistory.objects.filter(
                product=product
            ).exists()
        )

    def test_discontinued_product_is_updated(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        service.sync_catalog()

        self.write_rows(
            [
                {
                    "name": "Executive Pen",
                    "sku": "KB-PEN-1",
                    "supplier_sku": "KB-PEN-1",
                    "category": "Pens",
                    "starting_price": "2.25",
                    "supplier_price": "1.50",
                    "supplier_inventory": "0",
                    "discontinued": "true",
                    "image_url": (
                        "https://example.com/pen.jpg"
                    ),
                }
            ]
        )

        service.sync_inventory()

        product = Product.objects.get(
            sku="KB-PEN-1"
        )

        self.assertEqual(
            product.supplier_inventory,
            0,
        )

        self.assertEqual(
            product.inventory_status,
            "discontinued",
        )

    def test_inventory_sync_skips_unknown_product(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        result = (
            service.sync_inventory()
        )

        self.assertEqual(
            result.processed,
            1,
        )

        self.assertEqual(
            result.skipped,
            1,
        )

        self.assertEqual(
            result.failed,
            0,
        )

        self.assertEqual(
            Product.objects.count(),
            0,
        )

    def test_checkpoint_skips_completed_rows(
        self,
    ):
        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        result = service.sync_catalog(
            checkpoint={
                "offset": 1,
            }
        )

        self.assertEqual(
            result.processed,
            0,
        )

        self.assertEqual(
            result.created,
            0,
        )

        self.assertEqual(
            Product.objects.count(),
            0,
        )

    def test_progress_callback_receives_checkpoint(
        self,
    ):
        checkpoints = []

        def callback(
            **payload,
        ):
            checkpoints.append(
                payload["checkpoint"]
            )

        service = (
            KaeserBlairCSVSyncService(
                file_path=self.file_path
            )
        )

        service.sync_catalog(
            progress_callback=callback
        )

        self.assertEqual(
            checkpoints,
            [
                {
                    "offset": 1,
                }
            ],
        )