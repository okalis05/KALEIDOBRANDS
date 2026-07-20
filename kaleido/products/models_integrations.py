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