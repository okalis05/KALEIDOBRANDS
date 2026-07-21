from dataclasses import dataclass, field

from django.db import transaction

from products.models import (
    SupplierSyncCheckpoint,
    SupplierSyncJob,
)


@dataclass
class SupplierSyncResult:
    """
    Normalized result returned by supplier synchronization operations.
    """

    records_processed: int = 0
    records_succeeded: int = 0
    records_failed: int = 0
    checkpoint: dict = field(
        default_factory=dict
    )
    metadata: dict = field(
        default_factory=dict
    )


class SupplierSyncExecutionContext:
    """
    Runtime context passed to registered supplier sync handlers.
    """

    def __init__(
        self,
        *,
        job,
        adapter,
        correlation_id,
    ):
        self.job = job
        self.adapter = adapter
        self.correlation_id = correlation_id

    @property
    def supplier(self):
        return self.job.supplier

    def get_checkpoint(self):
        checkpoint, _ = (
            SupplierSyncCheckpoint
            .objects.get_or_create(
                job=self.job
            )
        )

        return checkpoint

    def checkpoint_data(self):
        checkpoint = self.get_checkpoint()

        return {
            "cursor": checkpoint.cursor,
            "page": checkpoint.page,
            "offset": checkpoint.offset,
            "last_external_id": (
                checkpoint.last_external_id
            ),
            "state": dict(
                checkpoint.state or {}
            ),
        }

    @transaction.atomic
    def save_checkpoint(
        self,
        *,
        cursor=None,
        page=None,
        offset=None,
        last_external_id=None,
        state=None,
        records_processed=None,
        records_succeeded=None,
        records_failed=None,
    ):
        checkpoint = (
            SupplierSyncCheckpoint
            .objects.select_for_update()
            .get_or_create(
                job=self.job
            )[0]
        )

        update_fields = [
            "updated_at",
        ]

        if cursor is not None:
            checkpoint.cursor = str(cursor)
            update_fields.append("cursor")

        if page is not None:
            checkpoint.page = max(
                int(page),
                0,
            )
            update_fields.append("page")

        if offset is not None:
            checkpoint.offset = max(
                int(offset),
                0,
            )
            update_fields.append("offset")

        if last_external_id is not None:
            checkpoint.last_external_id = str(
                last_external_id
            )
            update_fields.append(
                "last_external_id"
            )

        if state is not None:
            checkpoint.state = dict(
                state or {}
            )
            update_fields.append("state")

        checkpoint.save(
            update_fields=list(
                dict.fromkeys(update_fields)
            )
        )

        job_update_fields = []

        if records_processed is not None:
            self.job.records_processed = max(
                int(records_processed),
                0,
            )
            job_update_fields.append(
                "records_processed"
            )

        if records_succeeded is not None:
            self.job.records_succeeded = max(
                int(records_succeeded),
                0,
            )
            job_update_fields.append(
                "records_succeeded"
            )

        if records_failed is not None:
            self.job.records_failed = max(
                int(records_failed),
                0,
            )
            job_update_fields.append(
                "records_failed"
            )

        if job_update_fields:
            self.job.save(
                update_fields=job_update_fields
            )

        return checkpoint

    def increment_progress(
        self,
        *,
        processed=0,
        succeeded=0,
        failed=0,
    ):
        from django.db.models import F

        SupplierSyncJob.objects.filter(
            pk=self.job.pk
        ).update(
            records_processed=(
                F("records_processed")
                + max(int(processed), 0)
            ),
            records_succeeded=(
                F("records_succeeded")
                + max(int(succeeded), 0)
            ),
            records_failed=(
                F("records_failed")
                + max(int(failed), 0)
            ),
        )

        self.job.refresh_from_db(
            fields=[
                "records_processed",
                "records_succeeded",
                "records_failed",
            ]
        )

        return self.job