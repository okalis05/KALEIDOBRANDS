import inspect
import logging
from dataclasses import asdict
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from products.integrations.context import (
    supplier_correlation_context,
)
from products.integrations.registry import (
    get_supplier_adapter,
)
from products.integrations.sync_context import (
    SupplierSyncExecutionContext,
    SupplierSyncResult,
)
from products.integrations.sync_operations import (
    SupplierSyncOperationNotRegistered,
    get_sync_operation,
)
from products.models import (
    SupplierSyncBatch,
    SupplierSyncCheckpoint,
    SupplierSyncJob,
)


logger = logging.getLogger(__name__)


class SupplierSyncBatchError(Exception):
    """
    Base error for supplier sync batch orchestration.
    """


class SupplierSyncBatchAlreadyRunning(
    SupplierSyncBatchError
):
    """
    Raised when an already-running batch is executed again.
    """


class SupplierSyncJobDependencyError(
    SupplierSyncBatchError
):
    """
    Raised when a job dependency cannot be satisfied.
    """


class SupplierSyncOrchestrator:
    """
    Creates and executes persistent supplier synchronization batches.
    """

    FINISHED_JOB_STATUSES = {
        SupplierSyncJob.STATUS_COMPLETED,
        SupplierSyncJob.STATUS_FAILED,
        SupplierSyncJob.STATUS_SKIPPED,
        SupplierSyncJob.STATUS_CANCELLED,
    }

    @classmethod
    @transaction.atomic
    def create_batch(
        cls,
        *,
        suppliers,
        operations,
        created_by=None,
        metadata=None,
        max_attempts=3,
        operation_dependencies=None,
    ):
        suppliers = list(suppliers)
        operations = cls._normalize_operations(
            operations
        )

        if not suppliers:
            raise ValueError(
                "At least one supplier is required."
            )

        if not operations:
            raise ValueError(
                "At least one sync operation is required."
            )

        operation_dependencies = dict(
            operation_dependencies or {}
        )

        batch = SupplierSyncBatch.objects.create(
            status=SupplierSyncBatch.STATUS_PENDING,
            requested_operations=operations,
            metadata=dict(metadata or {}),
            created_by=created_by,
        )

        jobs_by_supplier = {}
        sequence = 0

        for supplier in suppliers:
            supplier_jobs = {}

            for operation_name in operations:
                registered_operation = (
                    get_sync_operation(
                        operation_name
                    )
                )

                operation_sequence = sequence
                dependency_name = (
                    operation_dependencies.get(
                        operation_name,
                        "",
                    )
                )
                operation_max_attempts = max(
                    int(max_attempts),
                    1,
                )

                if registered_operation:
                    operation_sequence = (
                        registered_operation.sequence
                    )

                    dependency_name = (
                        dependency_name
                        or registered_operation.depends_on
                    )

                    operation_max_attempts = (
                        registered_operation.max_attempts
                    )

                job = SupplierSyncJob.objects.create(
                    batch=batch,
                    supplier=supplier,
                    operation=operation_name,
                    sequence=operation_sequence,
                    max_attempts=operation_max_attempts,
                )

                supplier_jobs[
                    operation_name
                ] = job

                sequence += 1

            jobs_by_supplier[
                supplier.pk
            ] = supplier_jobs

        for supplier_jobs in (
            jobs_by_supplier.values()
        ):
            for operation_name, job in (
                supplier_jobs.items()
            ):
                registered_operation = (
                    get_sync_operation(
                        operation_name
                    )
                )

                dependency_name = (
                    operation_dependencies.get(
                        operation_name,
                        "",
                    )
                )

                if (
                    not dependency_name
                    and registered_operation
                ):
                    dependency_name = (
                        registered_operation.depends_on
                    )

                if not dependency_name:
                    continue

                dependency = supplier_jobs.get(
                    dependency_name
                )

                if dependency is None:
                    raise (
                        SupplierSyncJobDependencyError(
                            (
                                f"Operation "
                                f"'{operation_name}' "
                                f"depends on "
                                f"'{dependency_name}', "
                                "but that operation is not "
                                "included in the batch."
                            )
                        )
                    )

                job.depends_on = dependency
                job.save(
                    update_fields=[
                        "depends_on",
                    ]
                )

        batch.total_jobs = (
            batch.jobs.count()
        )

        batch.save(
            update_fields=[
                "total_jobs",
            ]
        )

        return batch

    @classmethod
    def execute_batch(
        cls,
        batch,
        *,
        stop_on_error=False,
        resume=False,
    ):
        batch_id = getattr(
            batch,
            "pk",
            batch,
        )

        batch = cls._claim_batch(
            batch_id,
            resume=resume,
        )

        try:
            with supplier_correlation_context(
                batch.correlation_id
            ):
                jobs = (
                    SupplierSyncJob.objects
                    .filter(batch=batch)
                    .select_related(
                        "supplier",
                        "depends_on",
                    )
                    .order_by(
                        "sequence",
                        "created_at",
                    )
                )

                for job in jobs:
                    if (
                        batch.status
                        == SupplierSyncBatch
                        .STATUS_CANCELLED
                    ):
                        break

                    if (
                        job.status
                        == SupplierSyncJob
                        .STATUS_COMPLETED
                    ):
                        continue

                    if (
                        job.status
                        == SupplierSyncJob
                        .STATUS_CANCELLED
                    ):
                        continue

                    if (
                        job.status
                        == SupplierSyncJob
                        .STATUS_FAILED
                        and not resume
                    ):
                        continue

                    if (
                        job.status
                        == SupplierSyncJob
                        .STATUS_FAILED
                        and not job.can_retry
                    ):
                        continue

                    if not cls._dependency_satisfied(
                        job
                    ):
                        cls._skip_job_for_dependency(
                            job
                        )
                        continue

                    try:
                        cls.execute_job(
                            job,
                            correlation_id=(
                                batch.correlation_id
                            ),
                        )

                    except Exception:
                        logger.exception(
                            (
                                "Supplier sync job "
                                "%s failed."
                            ),
                            job.pk,
                        )

                        if stop_on_error:
                            break

            return cls.refresh_batch_status(
                batch
            )

        except Exception:
            cls.refresh_batch_status(batch)
            raise

    @classmethod
    def execute_job(
        cls,
        job,
        *,
        correlation_id=None,
    ):
        job_id = getattr(
            job,
            "pk",
            job,
        )

        job = cls._claim_job(job_id)

        try:
            adapter = get_supplier_adapter(
                job.supplier
            )

            execution_context = (
                SupplierSyncExecutionContext(
                    job=job,
                    adapter=adapter,
                    correlation_id=correlation_id,
                )
            )

            handler = cls._resolve_handler(
                adapter,
                job.operation,
            )

            raw_result = cls._invoke_handler(
                handler,
                execution_context,
            )

            result = cls._normalize_result(
                raw_result
            )

            cls._complete_job(
                job,
                result,
                execution_context,
            )

            return job

        except Exception as error:
            cls._fail_job(
                job,
                error,
            )
            raise

    @classmethod
    @transaction.atomic
    def cancel_batch(cls, batch):
        batch_id = getattr(
            batch,
            "pk",
            batch,
        )

        batch = (
            SupplierSyncBatch.objects
            .select_for_update()
            .get(pk=batch_id)
        )

        if batch.is_finished:
            return batch

        now = timezone.now()

        batch.status = (
            SupplierSyncBatch.STATUS_CANCELLED
        )
        batch.completed_at = now

        batch.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

        batch.jobs.filter(
            status__in=[
                SupplierSyncJob.STATUS_PENDING,
                SupplierSyncJob.STATUS_RUNNING,
            ]
        ).update(
            status=(
                SupplierSyncJob.STATUS_CANCELLED
            ),
            completed_at=now,
        )

        return cls.refresh_batch_status(
            batch
        )

    @classmethod
    @transaction.atomic
    def reset_failed_jobs(cls, batch):
        batch_id = getattr(
            batch,
            "pk",
            batch,
        )

        batch = (
            SupplierSyncBatch.objects
            .select_for_update()
            .get(pk=batch_id)
        )

        retryable_jobs = batch.jobs.filter(
            status=SupplierSyncJob.STATUS_FAILED,
            attempt_count__lt=F(
                "max_attempts"
            ),
        )

        retryable_jobs.update(
            status=SupplierSyncJob.STATUS_PENDING,
            error_type="",
            error_message="",
            started_at=None,
            completed_at=None,
        )

        batch.status = (
            SupplierSyncBatch.STATUS_PENDING
        )
        batch.completed_at = None

        batch.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

        return cls.refresh_batch_status(
            batch
        )

    @classmethod
    @transaction.atomic
    def refresh_batch_status(cls, batch):
        batch_id = getattr(
            batch,
            "pk",
            batch,
        )

        batch = (
            SupplierSyncBatch.objects
            .select_for_update()
            .get(pk=batch_id)
        )

        statistics = batch.jobs.aggregate(
            total=Count("id"),
            completed=Count(
                "id",
                filter=Q(
                    status__in=(
                        cls.FINISHED_JOB_STATUSES
                    )
                ),
            ),
            successful=Count(
                "id",
                filter=Q(
                    status=(
                        SupplierSyncJob
                        .STATUS_COMPLETED
                    )
                ),
            ),
            failed=Count(
                "id",
                filter=Q(
                    status=(
                        SupplierSyncJob
                        .STATUS_FAILED
                    )
                ),
            ),
            skipped=Count(
                "id",
                filter=Q(
                    status=(
                        SupplierSyncJob
                        .STATUS_SKIPPED
                    )
                ),
            ),
            running=Count(
                "id",
                filter=Q(
                    status=(
                        SupplierSyncJob
                        .STATUS_RUNNING
                    )
                ),
            ),
            pending=Count(
                "id",
                filter=Q(
                    status=(
                        SupplierSyncJob
                        .STATUS_PENDING
                    )
                ),
            ),
        )

        batch.total_jobs = statistics[
            "total"
        ]
        batch.completed_jobs = statistics[
            "completed"
        ]
        batch.successful_jobs = statistics[
            "successful"
        ]
        batch.failed_jobs = statistics[
            "failed"
        ]
        batch.skipped_jobs = statistics[
            "skipped"
        ]

        if (
            batch.status
            == SupplierSyncBatch.STATUS_CANCELLED
        ):
            if not batch.completed_at:
                batch.completed_at = timezone.now()

        elif statistics["running"]:
            batch.status = (
                SupplierSyncBatch.STATUS_RUNNING
            )

        elif statistics["pending"]:
            batch.status = (
                SupplierSyncBatch.STATUS_PENDING
            )

        elif (
            statistics["successful"]
            == statistics["total"]
            and statistics["total"] > 0
        ):
            batch.status = (
                SupplierSyncBatch.STATUS_COMPLETED
            )
            batch.completed_at = timezone.now()

        elif statistics["successful"] > 0:
            batch.status = (
                SupplierSyncBatch.STATUS_PARTIAL
            )
            batch.completed_at = timezone.now()

        elif statistics["failed"] > 0:
            batch.status = (
                SupplierSyncBatch.STATUS_FAILED
            )
            batch.completed_at = timezone.now()

        elif statistics["total"] == 0:
            batch.status = (
                SupplierSyncBatch.STATUS_COMPLETED
            )
            batch.completed_at = timezone.now()

        update_fields = [
            "status",
            "total_jobs",
            "completed_jobs",
            "successful_jobs",
            "failed_jobs",
            "skipped_jobs",
            "completed_at",
        ]

        batch.save(
            update_fields=update_fields
        )

        return batch

    @classmethod
    @transaction.atomic
    def _claim_batch(
        cls,
        batch_id,
        *,
        resume=False,
    ):
        batch = (
            SupplierSyncBatch.objects
            .select_for_update()
            .get(pk=batch_id)
        )

        if (
            batch.status
            == SupplierSyncBatch.STATUS_RUNNING
        ):
            raise SupplierSyncBatchAlreadyRunning(
                (
                    f"Supplier sync batch "
                    f"{batch.pk} is already running."
                )
            )

        if (
            batch.is_finished
            and not resume
        ):
            return batch

        batch.status = (
            SupplierSyncBatch.STATUS_RUNNING
        )

        if batch.started_at is None:
            batch.started_at = timezone.now()

        batch.completed_at = None

        batch.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
            ]
        )

        return batch

    @classmethod
    @transaction.atomic
    def _claim_job(cls, job_id):
        job = (
            SupplierSyncJob.objects
            .select_for_update()
            .select_related(
                "batch",
                "supplier",
                "depends_on",
            )
            .get(pk=job_id)
        )

        if (
            job.status
            == SupplierSyncJob.STATUS_RUNNING
        ):
            raise SupplierSyncBatchAlreadyRunning(
                (
                    f"Supplier sync job "
                    f"{job.pk} is already running."
                )
            )

        if (
            job.status
            == SupplierSyncJob.STATUS_COMPLETED
        ):
            return job

        if (
            job.attempt_count
            >= job.max_attempts
        ):
            raise SupplierSyncBatchError(
                (
                    f"Supplier sync job "
                    f"{job.pk} has reached its "
                    "maximum number of attempts."
                )
            )

        job.status = (
            SupplierSyncJob.STATUS_RUNNING
        )
        job.attempt_count += 1
        job.started_at = timezone.now()
        job.completed_at = None
        job.error_type = ""
        job.error_message = ""

        job.save(
            update_fields=[
                "status",
                "attempt_count",
                "started_at",
                "completed_at",
                "error_type",
                "error_message",
            ]
        )

        return job

    @classmethod
    def _resolve_handler(
        cls,
        adapter,
        operation_name,
    ):
        registered_operation = (
            get_sync_operation(
                operation_name
            )
        )

        if registered_operation is None:
            from products.integrations.registered_operations import (
                register_default_supplier_operations,
            )

            register_default_supplier_operations()

            registered_operation = (
                get_sync_operation(
                    operation_name
                )
            )

        if registered_operation:
            return registered_operation.handler

        handler = getattr(
            adapter,
            operation_name,
            None,
        )

        if callable(handler):
            return handler

        raise SupplierSyncOperationNotRegistered(
            (
                f"No supplier sync operation "
                f"or adapter method is registered "
                f"for '{operation_name}'."
            )
        )

    @classmethod
    def _invoke_handler(
        cls,
        handler,
        execution_context,
    ):
        signature = inspect.signature(
            handler
        )

        available_arguments = {
            "context": execution_context,
            "sync_context": execution_context,
            "job": execution_context.job,
            "supplier": (
                execution_context.supplier
            ),
            "adapter": execution_context.adapter,
            "checkpoint": (
                execution_context
                .checkpoint_data()
            ),
            "correlation_id": (
                execution_context.correlation_id
            ),
        }

        kwargs = {}

        for parameter_name, parameter in (
            signature.parameters.items()
        ):
            if (
                parameter_name
                in available_arguments
            ):
                kwargs[parameter_name] = (
                    available_arguments[
                        parameter_name
                    ]
                )

            elif (
                parameter.default
                is inspect.Parameter.empty
                and parameter.kind
                in {
                    inspect.Parameter
                    .POSITIONAL_OR_KEYWORD,
                    inspect.Parameter
                    .KEYWORD_ONLY,
                }
            ):
                raise TypeError(
                    (
                        f"Supplier sync handler "
                        f"'{handler.__name__}' requires "
                        f"unsupported argument "
                        f"'{parameter_name}'."
                    )
                )

        return handler(**kwargs)

    @classmethod
    def _normalize_result(
        cls,
        raw_result,
    ):
        if raw_result is None:
            return SupplierSyncResult()

        if isinstance(
            raw_result,
            SupplierSyncResult,
        ):
            return raw_result

        if isinstance(raw_result, dict):
            return SupplierSyncResult(
                records_processed=max(
                    int(
                        raw_result.get(
                            "records_processed",
                            raw_result.get(
                                "processed",
                                0,
                            ),
                        )
                        or 0
                    ),
                    0,
                ),
                records_succeeded=max(
                    int(
                        raw_result.get(
                            "records_succeeded",
                            raw_result.get(
                                "succeeded",
                                0,
                            ),
                        )
                        or 0
                    ),
                    0,
                ),
                records_failed=max(
                    int(
                        raw_result.get(
                            "records_failed",
                            raw_result.get(
                                "failed",
                                0,
                            ),
                        )
                        or 0
                    ),
                    0,
                ),
                checkpoint=dict(
                    raw_result.get(
                        "checkpoint",
                        {},
                    )
                    or {}
                ),
                metadata=dict(
                    raw_result.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
            )

        if isinstance(raw_result, int):
            count = max(
                raw_result,
                0,
            )

            return SupplierSyncResult(
                records_processed=count,
                records_succeeded=count,
            )

        return SupplierSyncResult(
            metadata={
                "result": str(raw_result),
            }
        )

    @classmethod
    @transaction.atomic
    def _complete_job(
        cls,
        job,
        result,
        execution_context,
    ):
        job = (
            SupplierSyncJob.objects
            .select_for_update()
            .get(pk=job.pk)
        )

        job.status = (
            SupplierSyncJob.STATUS_COMPLETED
        )
        job.records_processed = (
            result.records_processed
        )
        job.records_succeeded = (
            result.records_succeeded
        )
        job.records_failed = (
            result.records_failed
        )
        job.result_metadata = dict(
            result.metadata or {}
        )
        job.error_type = ""
        job.error_message = ""
        job.completed_at = timezone.now()

        job.save(
            update_fields=[
                "status",
                "records_processed",
                "records_succeeded",
                "records_failed",
                "result_metadata",
                "error_type",
                "error_message",
                "completed_at",
            ]
        )

        if result.checkpoint:
            execution_context.job = job

            execution_context.save_checkpoint(
                cursor=result.checkpoint.get(
                    "cursor"
                ),
                page=result.checkpoint.get(
                    "page"
                ),
                offset=result.checkpoint.get(
                    "offset"
                ),
                last_external_id=(
                    result.checkpoint.get(
                        "last_external_id"
                    )
                ),
                state=result.checkpoint.get(
                    "state"
                ),
            )

        cls.refresh_batch_status(
            job.batch_id
        )

    @classmethod
    @transaction.atomic
    def _fail_job(
        cls,
        job,
        error,
    ):
        job = (
            SupplierSyncJob.objects
            .select_for_update()
            .get(pk=job.pk)
        )

        job.status = (
            SupplierSyncJob.STATUS_FAILED
        )
        job.error_type = (
            error.__class__.__name__
        )
        job.error_message = str(error)[:4000]
        job.completed_at = timezone.now()

        job.save(
            update_fields=[
                "status",
                "error_type",
                "error_message",
                "completed_at",
            ]
        )

        cls.refresh_batch_status(
            job.batch_id
        )

    @classmethod
    def _dependency_satisfied(
        cls,
        job,
    ):
        if not job.depends_on_id:
            return True

        dependency_status = (
            SupplierSyncJob.objects
            .filter(pk=job.depends_on_id)
            .values_list(
                "status",
                flat=True,
            )
            .first()
        )

        return (
            dependency_status
            == SupplierSyncJob.STATUS_COMPLETED
        )

    @classmethod
    @transaction.atomic
    def _skip_job_for_dependency(
        cls,
        job,
    ):
        job = (
            SupplierSyncJob.objects
            .select_for_update()
            .get(pk=job.pk)
        )

        job.status = (
            SupplierSyncJob.STATUS_SKIPPED
        )
        job.error_type = (
            "SupplierSyncJobDependencyError"
        )
        job.error_message = (
            "Required dependency did not "
            "complete successfully."
        )
        job.completed_at = timezone.now()

        job.save(
            update_fields=[
                "status",
                "error_type",
                "error_message",
                "completed_at",
            ]
        )

        cls.refresh_batch_status(
            job.batch_id
        )

    @staticmethod
    def _normalize_operations(
        operations,
    ):
        normalized = []

        for operation in operations:
            name = str(
                operation or ""
            ).strip()

            if (
                name
                and name not in normalized
            ):
                normalized.append(name)

        return normalized