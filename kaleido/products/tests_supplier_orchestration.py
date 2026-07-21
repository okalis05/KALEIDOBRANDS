from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from products.integrations.orchestration import (
    SupplierSyncOrchestrator,
)
from products.integrations.sync_context import (
    SupplierSyncResult,
)
from products.integrations.registered_operations import (
    register_default_supplier_operations,
)
from products.integrations.sync_operations import (
    clear_sync_operations,
    register_sync_operation,
)
from products.models import (
    Supplier,
    SupplierSyncBatch,
    SupplierSyncCheckpoint,
    SupplierSyncJob,
)


User = get_user_model()


class SupplierSyncOrchestratorTests(
    TestCase
):
    def setUp(self):
        clear_sync_operations()

        self.supplier = Supplier.objects.create(
            name="Orchestration Supplier",
            slug="orchestration-supplier",
            api_base_url=(
                "https://supplier.example.com"
            ),
            api_enabled=True,
        )

        self.second_supplier = (
            Supplier.objects.create(
                name="Second Supplier",
                slug="second-supplier",
                api_base_url=(
                    "https://second.example.com"
                ),
                api_enabled=True,
            )
        )

        self.adapter = MagicMock()

    def tearDown(self):
        clear_sync_operations()
        register_default_supplier_operations()

    def test_create_batch_creates_jobs_for_each_supplier_and_operation(
        self,
    ):
        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                    self.second_supplier,
                ],
                operations=[
                    "sync_catalog",
                    "sync_inventory",
                ],
            )
        )

        self.assertEqual(
            batch.status,
            SupplierSyncBatch.STATUS_PENDING,
        )

        self.assertEqual(
            batch.total_jobs,
            4,
        )

        self.assertEqual(
            batch.jobs.count(),
            4,
        )

        self.assertEqual(
            set(
                batch.jobs.values_list(
                    "operation",
                    flat=True,
                )
            ),
            {
                "sync_catalog",
                "sync_inventory",
            },
        )

    def test_duplicate_operations_are_removed(
        self,
    ):
        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                    "sync_catalog",
                ],
            )
        )

        self.assertEqual(
            batch.total_jobs,
            1,
        )

    def test_registered_operation_executes_successfully(
        self,
    ):
        @register_sync_operation(
            "sync_catalog"
        )
        def sync_catalog(context):
            self.assertEqual(
                context.supplier,
                self.supplier,
            )

            return SupplierSyncResult(
                records_processed=10,
                records_succeeded=9,
                records_failed=1,
                checkpoint={
                    "page": 2,
                    "cursor": "next-cursor",
                    "state": {
                        "finished": True,
                    },
                },
                metadata={
                    "source": "test",
                },
            )

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            completed_batch = (
                SupplierSyncOrchestrator
                .execute_batch(batch)
            )

        job = batch.jobs.get()

        self.assertEqual(
            job.status,
            SupplierSyncJob.STATUS_COMPLETED,
        )

        self.assertEqual(
            job.records_processed,
            10,
        )

        self.assertEqual(
            job.records_succeeded,
            9,
        )

        self.assertEqual(
            job.records_failed,
            1,
        )

        self.assertEqual(
            job.result_metadata,
            {
                "source": "test",
            },
        )

        checkpoint = (
            SupplierSyncCheckpoint
            .objects.get(job=job)
        )

        self.assertEqual(
            checkpoint.page,
            2,
        )

        self.assertEqual(
            checkpoint.cursor,
            "next-cursor",
        )

        self.assertEqual(
            checkpoint.state,
            {
                "finished": True,
            },
        )

        self.assertEqual(
            completed_batch.status,
            SupplierSyncBatch
            .STATUS_COMPLETED,
        )

    def test_adapter_method_is_used_when_operation_is_not_registered(
        self,
    ):
        self.adapter.sync_inventory.return_value = {
            "records_processed": 4,
            "records_succeeded": 4,
        }

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_inventory",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            SupplierSyncOrchestrator.execute_batch(
                batch
            )

        job = batch.jobs.get()

        self.assertEqual(
            job.status,
            SupplierSyncJob.STATUS_COMPLETED,
        )

        self.assertEqual(
            job.records_processed,
            4,
        )

        self.adapter.sync_inventory.assert_called_once()

    def test_failed_operation_records_error(
        self,
    ):
        @register_sync_operation(
            "sync_catalog"
        )
        def sync_catalog(context):
            raise RuntimeError(
                "Supplier catalog unavailable."
            )

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            completed_batch = (
                SupplierSyncOrchestrator
                .execute_batch(batch)
            )

        job = batch.jobs.get()

        self.assertEqual(
            job.status,
            SupplierSyncJob.STATUS_FAILED,
        )

        self.assertEqual(
            job.error_type,
            "RuntimeError",
        )

        self.assertIn(
            "catalog unavailable",
            job.error_message,
        )

        self.assertEqual(
            job.attempt_count,
            1,
        )

        self.assertEqual(
            completed_batch.status,
            SupplierSyncBatch.STATUS_FAILED,
        )

    def test_batch_continues_after_job_failure(
        self,
    ):
        @register_sync_operation(
            "sync_catalog"
        )
        def sync_catalog(context):
            raise RuntimeError(
                "Catalog failed."
            )

        @register_sync_operation(
            "sync_inventory"
        )
        def sync_inventory(context):
            return {
                "processed": 2,
                "succeeded": 2,
            }

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                    "sync_inventory",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            completed_batch = (
                SupplierSyncOrchestrator
                .execute_batch(
                    batch,
                    stop_on_error=False,
                )
            )

        self.assertEqual(
            completed_batch.status,
            SupplierSyncBatch.STATUS_PARTIAL,
        )

        self.assertEqual(
            completed_batch.successful_jobs,
            1,
        )

        self.assertEqual(
            completed_batch.failed_jobs,
            1,
        )

    def test_dependency_failure_skips_dependent_job(
        self,
    ):
        @register_sync_operation(
            "sync_catalog"
        )
        def sync_catalog(context):
            raise RuntimeError(
                "Catalog failed."
            )

        @register_sync_operation(
            "sync_inventory",
            depends_on="sync_catalog",
        )
        def sync_inventory(context):
            return {
                "processed": 1,
                "succeeded": 1,
            }

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                    "sync_inventory",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            completed_batch = (
                SupplierSyncOrchestrator
                .execute_batch(batch)
            )

        inventory_job = batch.jobs.get(
            operation="sync_inventory"
        )

        self.assertEqual(
            inventory_job.status,
            SupplierSyncJob.STATUS_SKIPPED,
        )

        self.assertEqual(
            completed_batch.failed_jobs,
            1,
        )

        self.assertEqual(
            completed_batch.skipped_jobs,
            1,
        )

    def test_failed_job_can_resume(
        self,
    ):
        call_count = {
            "value": 0,
        }

        @register_sync_operation(
            "sync_catalog",
            max_attempts=2,
        )
        def sync_catalog(context):
            call_count["value"] += 1

            if call_count["value"] == 1:
                context.save_checkpoint(
                    page=3,
                    cursor="resume-token",
                )

                raise RuntimeError(
                    "Temporary supplier failure."
                )

            checkpoint = (
                context.checkpoint_data()
            )

            self.assertEqual(
                checkpoint["page"],
                3,
            )

            self.assertEqual(
                checkpoint["cursor"],
                "resume-token",
            )

            return {
                "processed": 5,
                "succeeded": 5,
            }

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            first_result = (
                SupplierSyncOrchestrator
                .execute_batch(batch)
            )

            self.assertEqual(
                first_result.status,
                SupplierSyncBatch.STATUS_FAILED,
            )

            second_result = (
                SupplierSyncOrchestrator
                .execute_batch(
                    batch,
                    resume=True,
                )
            )

        job = batch.jobs.get()

        self.assertEqual(
            job.status,
            SupplierSyncJob.STATUS_COMPLETED,
        )

        self.assertEqual(
            job.attempt_count,
            2,
        )

        self.assertEqual(
            second_result.status,
            SupplierSyncBatch
            .STATUS_COMPLETED,
        )

    def test_batch_uses_one_correlation_id(
        self,
    ):
        observed_correlation_ids = []

        @register_sync_operation(
            "sync_catalog"
        )
        def sync_catalog(context):
            observed_correlation_ids.append(
                context.correlation_id
            )

            return {
                "processed": 1,
                "succeeded": 1,
            }

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                    self.second_supplier,
                ],
                operations=[
                    "sync_catalog",
                ],
            )
        )

        with patch(
            (
                "products.integrations."
                "orchestration."
                "get_supplier_adapter"
            ),
            return_value=self.adapter,
        ):
            SupplierSyncOrchestrator.execute_batch(
                batch
            )

        self.assertEqual(
            len(observed_correlation_ids),
            2,
        )

        self.assertEqual(
            set(observed_correlation_ids),
            {
                batch.correlation_id,
            },
        )

    def test_cancel_batch_cancels_pending_jobs(
        self,
    ):
        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=[
                    self.supplier,
                ],
                operations=[
                    "sync_catalog",
                    "sync_inventory",
                ],
            )
        )

        cancelled_batch = (
            SupplierSyncOrchestrator
            .cancel_batch(batch)
        )

        self.assertEqual(
            cancelled_batch.status,
            SupplierSyncBatch
            .STATUS_CANCELLED,
        )

        self.assertFalse(
            cancelled_batch.jobs.exclude(
                status=(
                    SupplierSyncJob
                    .STATUS_CANCELLED
                )
            ).exists()
        )