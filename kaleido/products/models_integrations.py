import uuid

from django.db import models


class SupplierIntegrationAuditLog(models.Model):
    """
    Persistent audit record for a supplier integration request.

    The model stores operational metadata only. Authentication secrets and
    complete request payloads must never be persisted here.
    """

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_audit_logs",
    )

    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )

    operation = models.CharField(
        max_length=100,
        blank=True,
    )

    method = models.CharField(
        max_length=10,
        blank=True,
    )

    url = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    success = models.BooleanField(
        default=False,
        db_index=True,
    )

    status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    attempt_count = models.PositiveIntegerField(
        default=0,
    )

    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    request_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    response_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    error_type = models.CharField(
        max_length=255,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-started_at",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "supplier",
                    "operation",
                    "status",
                ],
                name="supplier_audit_lookup_idx",
            ),
            models.Index(
                fields=[
                    "correlation_id",
                    "started_at",
                ],
                name="supplier_corr_time_idx",
            ),
        ]

    def __str__(self):
        supplier_name = (
            self.supplier.name
            if self.supplier
            else "Unknown supplier"
        )

        return (
            f"{supplier_name}: "
            f"{self.operation or self.method} "
            f"[{self.status}]"
        )
    
class SupplierSyncBatch(models.Model):
    """
    Groups one or more supplier synchronization jobs into a single
    orchestrated execution.
    """

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_PARTIAL, "Partially completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    requested_operations = models.JSONField(
        default=list,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    total_jobs = models.PositiveIntegerField(
        default=0,
    )

    completed_jobs = models.PositiveIntegerField(
        default=0,
    )

    successful_jobs = models.PositiveIntegerField(
        default=0,
    )

    failed_jobs = models.PositiveIntegerField(
        default=0,
    )

    skipped_jobs = models.PositiveIntegerField(
        default=0,
    )

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_sync_batches",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "created_at",
                ],
                name="supplier_batch_status_idx",
            ),
            models.Index(
                fields=[
                    "correlation_id",
                ],
                name="supplier_batch_corr_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Supplier sync batch {self.pk} "
            f"[{self.status}]"
        )

    @property
    def progress_percentage(self):
        if not self.total_jobs:
            return 0

        return round(
            (
                self.completed_jobs
                / self.total_jobs
            )
            * 100,
            2,
        )

    @property
    def is_finished(self):
        return self.status in {
            self.STATUS_COMPLETED,
            self.STATUS_PARTIAL,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED,
        }


class SupplierSyncJob(models.Model):
    """
    Represents one supplier operation within a synchronization batch.
    """

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    batch = models.ForeignKey(
        SupplierSyncBatch,
        on_delete=models.CASCADE,
        related_name="jobs",
    )

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )

    operation = models.CharField(
        max_length=100,
        db_index=True,
    )

    sequence = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    depends_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependent_jobs",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    attempt_count = models.PositiveIntegerField(
        default=0,
    )

    max_attempts = models.PositiveIntegerField(
        default=3,
    )

    records_processed = models.PositiveIntegerField(
        default=0,
    )

    records_succeeded = models.PositiveIntegerField(
        default=0,
    )

    records_failed = models.PositiveIntegerField(
        default=0,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    result_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    error_type = models.CharField(
        max_length=255,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "sequence",
            "created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batch",
                    "supplier",
                    "operation",
                ],
                name=(
                    "unique_supplier_operation_per_batch"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "batch",
                    "status",
                    "sequence",
                ],
                name="supplier_job_batch_idx",
            ),
            models.Index(
                fields=[
                    "supplier",
                    "operation",
                    "status",
                ],
                name="supplier_job_lookup_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.supplier}: "
            f"{self.operation} "
            f"[{self.status}]"
        )

    @property
    def can_retry(self):
        return (
            self.status == self.STATUS_FAILED
            and self.attempt_count < self.max_attempts
        )

    @property
    def is_finished(self):
        return self.status in {
            self.STATUS_COMPLETED,
            self.STATUS_FAILED,
            self.STATUS_SKIPPED,
            self.STATUS_CANCELLED,
        }


class SupplierSyncCheckpoint(models.Model):
    """
    Persistent resume state for an individual supplier sync job.
    """

    job = models.OneToOneField(
        SupplierSyncJob,
        on_delete=models.CASCADE,
        related_name="checkpoint",
    )

    cursor = models.CharField(
        max_length=500,
        blank=True,
    )

    page = models.PositiveIntegerField(
        default=0,
    )

    offset = models.PositiveIntegerField(
        default=0,
    )

    last_external_id = models.CharField(
        max_length=255,
        blank=True,
    )

    state = models.JSONField(
        default=dict,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-updated_at",
        ]

    def __str__(self):
        return (
            f"Checkpoint for "
            f"{self.job.operation}: "
            f"{self.job.supplier}"
        )