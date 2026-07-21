from unittest.mock import MagicMock

from django.test import SimpleTestCase

from products.integrations.operation_dispatch import (
    SupplierOperationCapabilityError,
    invoke_adapter_operation,
    normalize_operation_result,
    resolve_adapter_operation,
)
from products.integrations.registered_operations import (
    register_default_supplier_operations,
)
from products.integrations.sync_context import (
    SupplierSyncResult,
)
from products.integrations.sync_operations import (
    clear_sync_operations,
    get_sync_operation,
)


class ExampleContext:
    def __init__(self, adapter):
        self.adapter = adapter
        self.job = MagicMock()
        self.supplier = MagicMock()
        self.correlation_id = "test-correlation-id"

    def checkpoint_data(self):
        return {
            "cursor": "cursor-1",
            "page": 2,
            "offset": 50,
            "last_external_id": "product-50",
            "state": {
                "complete": False,
            },
        }


class SupplierOperationRegistrationTests(
    SimpleTestCase
):
    def tearDown(self):
        clear_sync_operations()
        register_default_supplier_operations()

    def test_default_operations_are_registered(
        self,
    ):
        clear_sync_operations()

        register_default_supplier_operations()

        expected_operations = {
            "sync_catalog",
            "sync_inventory",
            "sync_pricing",
            "sync_images",
            "sync_discontinued",
        }

        for operation_name in expected_operations:
            self.assertIsNotNone(
                get_sync_operation(
                    operation_name
                )
            )

    def test_catalog_has_no_dependency(
        self,
    ):
        clear_sync_operations()

        register_default_supplier_operations()

        operation = get_sync_operation(
            "sync_catalog"
        )

        self.assertEqual(
            operation.sequence,
            10,
        )

        self.assertEqual(
            operation.depends_on,
            "",
        )

    def test_inventory_depends_on_catalog(
        self,
    ):
        clear_sync_operations()

        register_default_supplier_operations()

        operation = get_sync_operation(
            "sync_inventory"
        )

        self.assertEqual(
            operation.sequence,
            30,
        )

        self.assertEqual(
            operation.depends_on,
            "sync_catalog",
        )


class SupplierOperationDispatchTests(
    SimpleTestCase
):
    def test_exact_adapter_method_is_resolved(
        self,
    ):
        adapter = MagicMock()

        adapter.sync_catalog = MagicMock(
            return_value={
                "processed": 5,
                "succeeded": 5,
            }
        )

        handler = resolve_adapter_operation(
            adapter,
            "sync_catalog",
        )

        self.assertEqual(
            handler,
            adapter.sync_catalog,
        )

    def test_catalog_fallback_method_is_resolved(
        self,
    ):
        class Adapter:
            def fetch_catalog(self):
                return []

        adapter = Adapter()

        handler = resolve_adapter_operation(
            adapter,
            "sync_catalog",
        )

        self.assertEqual(
            handler.__name__,
            "fetch_catalog",
        )

    def test_missing_capability_raises_error(
        self,
    ):
        class Adapter:
            pass

        with self.assertRaises(
            SupplierOperationCapabilityError
        ):
            resolve_adapter_operation(
                Adapter(),
                "sync_inventory",
            )

    def test_context_and_checkpoint_are_forwarded(
        self,
    ):
        class Adapter:
            def sync_catalog(
                self,
                context,
                checkpoint,
                correlation_id,
            ):
                return {
                    "processed": 3,
                    "succeeded": 3,
                    "checkpoint": {
                        "cursor": (
                            checkpoint["cursor"]
                        ),
                    },
                    "metadata": {
                        "correlation_id": (
                            correlation_id
                        ),
                    },
                }

        context = ExampleContext(
            Adapter()
        )

        result = invoke_adapter_operation(
            adapter=context.adapter,
            operation="sync_catalog",
            context=context,
        )

        self.assertEqual(
            result.records_processed,
            3,
        )

        self.assertEqual(
            result.records_succeeded,
            3,
        )

        self.assertEqual(
            result.checkpoint,
            {
                "cursor": "cursor-1",
            },
        )

        self.assertEqual(
            result.metadata[
                "correlation_id"
            ],
            "test-correlation-id",
        )

    def test_list_result_is_normalized(
        self,
    ):
        result = normalize_operation_result(
            [
                {"sku": "ONE"},
                {"sku": "TWO"},
            ]
        )

        self.assertEqual(
            result.records_processed,
            2,
        )

        self.assertEqual(
            result.records_succeeded,
            2,
        )

    def test_dictionary_result_is_normalized(
        self,
    ):
        result = normalize_operation_result(
            {
                "processed": 12,
                "succeeded": 10,
                "failed": 2,
                "checkpoint": {
                    "page": 4,
                },
            }
        )

        self.assertEqual(
            result.records_processed,
            12,
        )

        self.assertEqual(
            result.records_succeeded,
            10,
        )

        self.assertEqual(
            result.records_failed,
            2,
        )

        self.assertEqual(
            result.checkpoint,
            {
                "page": 4,
            },
        )

    def test_supplier_sync_result_is_preserved(
        self,
    ):
        original = SupplierSyncResult(
            records_processed=8,
            records_succeeded=8,
        )

        normalized = (
            normalize_operation_result(
                original
            )
        )

        self.assertIs(
            normalized,
            original,
        )