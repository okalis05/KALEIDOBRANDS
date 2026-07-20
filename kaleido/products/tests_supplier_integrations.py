import os
from unittest.mock import patch

from django.test import TestCase

from products.integrations import (
    BaseSupplierAdapter,
    SupplierOperationResult,
    get_adapter_class,
    get_supplier_adapter,
    register_adapter,
    registered_adapters,
)
from products.integrations.auth import (
    SupplierCredentials,
)
from products.integrations.exceptions import (
    SupplierAdapterNotFoundError,
    SupplierAuthenticationError,
    SupplierOperationNotSupportedError,
)
from products.integrations.registry import (
    unregister_adapter,
)
from products.models import Supplier


class SupplierIntegrationRegistryTests(
    TestCase
):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Kaeser & Blair",
            slug="kaeser-blair",
            website=(
                "https://www.kaeser-blair.com/"
            ),
            is_active=True,
        )

    def test_kaeser_blair_adapter_is_registered(
        self,
    ):
        adapter_class = get_adapter_class(
            "kaeser-blair"
        )

        self.assertEqual(
            adapter_class.supplier_slug,
            "kaeser-blair",
        )

    def test_adapter_can_be_resolved_from_supplier(
        self,
    ):
        adapter = get_supplier_adapter(
            self.supplier
        )

        self.assertEqual(
            adapter.supplier,
            self.supplier,
        )

        self.assertEqual(
            adapter.supplier_slug,
            "kaeser-blair",
        )

    def test_unknown_supplier_adapter_is_rejected(
        self,
    ):
        unknown_supplier = Supplier.objects.create(
            name="Unknown Supplier",
            slug="unknown-supplier",
        )

        with self.assertRaises(
            SupplierAdapterNotFoundError
        ):
            get_supplier_adapter(
                unknown_supplier
            )

    def test_duplicate_adapter_registration_is_rejected(
        self,
    ):
        class DuplicateAdapter(
            BaseSupplierAdapter
        ):
            supplier_slug = "kaeser-blair"

        with self.assertRaises(ValueError):
            register_adapter(
                DuplicateAdapter
            )

    def test_custom_adapter_can_be_registered(
        self,
    ):
        class TemporaryAdapter(
            BaseSupplierAdapter
        ):
            supplier_slug = (
                "temporary-supplier"
            )

        try:
            register_adapter(
                TemporaryAdapter
            )

            self.assertIs(
                get_adapter_class(
                    "temporary-supplier"
                ),
                TemporaryAdapter,
            )

        finally:
            unregister_adapter(
                "temporary-supplier"
            )


class SupplierCredentialsTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Credential Supplier",
            slug="credential-supplier",
            api_base_url=(
                "https://api.example.com/"
            ),
            api_key_name=(
                "TEST_SUPPLIER_API_KEY"
            ),
            api_enabled=True,
        )

    @patch.dict(
        os.environ,
        {
            "TEST_SUPPLIER_API_KEY": (
                "secret-test-key"
            )
        },
        clear=False,
    )
    def test_credentials_are_loaded_from_environment(
        self,
    ):
        credentials = (
            SupplierCredentials.from_supplier(
                self.supplier,
                required=True,
            )
        )

        self.assertEqual(
            credentials.api_key,
            "secret-test-key",
        )

        self.assertEqual(
            credentials.api_base_url,
            "https://api.example.com",
        )

        self.assertTrue(
            credentials.is_configured
        )

    @patch.dict(
        os.environ,
        {},
        clear=True,
    )
    def test_required_missing_credentials_raise_error(
        self,
    ):
        with self.assertRaises(
            SupplierAuthenticationError
        ):
            SupplierCredentials.from_supplier(
                self.supplier,
                required=True,
            )

    @patch.dict(
        os.environ,
        {
            "TEST_SUPPLIER_API_KEY": (
                "secret-test-key"
            )
        },
        clear=False,
    )
    def test_authorization_headers_are_generated(
        self,
    ):
        credentials = (
            SupplierCredentials.from_supplier(
                self.supplier,
                required=True,
            )
        )

        self.assertEqual(
            credentials.authorization_headers(),
            {
                "Authorization": (
                    "Bearer secret-test-key"
                )
            },
        )


class BaseSupplierAdapterTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Base Supplier",
            slug="base-supplier",
        )

        self.adapter = BaseSupplierAdapter(
            self.supplier
        )

    def test_default_connection_result_is_standardized(
        self,
    ):
        result = self.adapter.test_connection()

        self.assertIsInstance(
            result,
            SupplierOperationResult,
        )

        self.assertTrue(result.success)

        self.assertEqual(
            result.operation,
            "test_connection",
        )

    def test_unsupported_operation_raises_consistent_error(
        self,
    ):
        with self.assertRaises(
            SupplierOperationNotSupportedError
        ):
            self.adapter.fetch_inventory()


class KaeserBlairAdapterTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Kaeser & Blair",
            slug="kaeser-blair",
            is_active=True,
            api_enabled=False,
        )

        self.adapter = get_supplier_adapter(
            self.supplier
        )

    def test_connection_supports_csv_and_email_mode(
        self,
    ):
        result = self.adapter.test_connection()

        self.assertTrue(result.success)

        self.assertEqual(
            result.metadata["mode"],
            "csv-and-email",
        )

        self.assertTrue(
            result.metadata["supports_csv"]
        )

        self.assertTrue(
            result.metadata[
                "supports_purchase_orders"
            ]
        )

    def test_product_payload_is_normalized(
        self,
    ):
        normalized = (
            self.adapter.normalize_product(
                {
                    "name": "Executive Pen",
                    "supplier_sku": "KB-PEN-1",
                    "price": "3.50",
                    "minimum_quantity": 100,
                    "inventory": 250,
                    "id": "SUP-100",
                }
            )
        )

        self.assertEqual(
            normalized["name"],
            "Executive Pen",
        )

        self.assertEqual(
            normalized["sku"],
            "KB-PEN-1",
        )

        self.assertEqual(
            normalized["starting_price"],
            "3.50",
        )

        self.assertEqual(
            normalized["min_quantity"],
            100,
        )

        self.assertEqual(
            normalized["supplier_inventory"],
            250,
        )

        self.assertEqual(
            normalized[
                "supplier_product_id"
            ],
            "SUP-100",
        )