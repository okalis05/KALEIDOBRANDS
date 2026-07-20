from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class RefundRequest(models.Model):
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("under_review", "Under Review"),
        ("information_requested", "Information Requested"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    REASON_CHOICES = [
        ("returned_items", "Returned Items"),
        ("damaged_items", "Damaged Items"),
        ("missing_items", "Missing Items"),
        ("wrong_items", "Wrong Items"),
        ("duplicate_charge", "Duplicate Charge"),
        ("pricing_error", "Pricing Error"),
        ("service_issue", "Service Issue"),
        ("order_cancelled", "Order Cancelled"),
        ("other", "Other"),
    ]

    refund_number = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )

    order = models.ForeignKey(
        "customers.Order",
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )

    return_request = models.ForeignKey(
        "customers.ReturnRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_refund_requests",
    )

    reason = models.CharField(
        max_length=40,
        choices=REASON_CHOICES,
    )

    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default="requested",
    )

    amount_requested = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ],
    )

    amount_approved = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount_refunded = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    customer_notes = models.TextField()

    staff_notes = models.TextField(
        blank=True,
    )

    failure_message = models.TextField(
        blank=True,
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
    )

    stripe_refund_id = models.CharField(
        max_length=255,
        blank=True,
    )

    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    failed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-requested_at",
        ]

        indexes = [
            models.Index(
                fields=["refund_number"]
            ),
            models.Index(
                fields=["status"]
            ),
            models.Index(
                fields=["requested_at"]
            ),
            models.Index(
                fields=["stripe_refund_id"]
            ),
        ]

    def clean(self):
        errors = {}

        if self.order_id:
            if self.customer_id != self.order.customer_id:
                errors["customer"] = (
                    "The selected customer does not own this order."
                )

            if self.return_request_id:
                if self.return_request.order_id != self.order_id:
                    errors["return_request"] = (
                        "The selected return request does not belong "
                        "to this order."
                    )

                if (
                    self.return_request.customer_id
                    != self.customer_id
                ):
                    errors["return_request"] = (
                        "The selected return request does not belong "
                        "to this customer."
                    )

        if self.amount_requested <= Decimal("0.00"):
            errors["amount_requested"] = (
                "Requested amount must be greater than zero."
            )

        if self.amount_approved < Decimal("0.00"):
            errors["amount_approved"] = (
                "Approved amount cannot be negative."
            )

        if self.amount_refunded < Decimal("0.00"):
            errors["amount_refunded"] = (
                "Refunded amount cannot be negative."
            )

        if (
            self.amount_approved
            > self.amount_requested
        ):
            errors["amount_approved"] = (
                "Approved amount cannot exceed requested amount."
            )

        if (
            self.amount_refunded
            > self.amount_approved
        ):
            errors["amount_refunded"] = (
                "Refunded amount cannot exceed approved amount."
            )

        if self.order_id:
            order_total = self.order.total or Decimal("0.00")

            if self.amount_requested > order_total:
                errors["amount_requested"] = (
                    "Requested amount cannot exceed the order total."
                )

            if self.amount_approved > order_total:
                errors["amount_approved"] = (
                    "Approved amount cannot exceed the order total."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.refund_number:
            from customers.services.refunds import (
                generate_refund_number,
            )

            self.refund_number = (
                generate_refund_number()
            )

        if (
            self.order_id
            and not self.stripe_payment_intent_id
        ):
            self.stripe_payment_intent_id = (
                getattr(
                self.order,
                "stripe_payment_intent_id",
                "",
                )
                or ""
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def completed_transactions_total(self):
        result = (
            self.transactions
            .filter(status="completed")
            .aggregate(total=Sum("amount"))
        )

        return result["total"] or Decimal("0.00")

    def remaining_approved_amount(self):
        completed = self.completed_transactions_total()

        remaining = (
            self.amount_approved
            - completed
        )

        return max(
            remaining,
            Decimal("0.00"),
        )

    def __str__(self):
        return self.refund_number


class RefundTransaction(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ],
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="created",
    )

    stripe_refund_id = models.CharField(
        max_length=255,
        blank=True,
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
    )

    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
    )

    stripe_status = models.CharField(
        max_length=80,
        blank=True,
    )

    stripe_response = models.JSONField(
        default=dict,
        blank=True,
    )

    failure_message = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_refund_transactions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    failed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=["status"]
            ),
            models.Index(
                fields=["stripe_refund_id"]
            ),
            models.Index(
                fields=["created_at"]
            ),
        ]

    def clean(self):
        errors = {}

        if self.amount <= Decimal("0.00"):
            errors["amount"] = (
                "Refund transaction amount must be greater "
                "than zero."
            )

        if self.refund_request_id:
            if (
                self.amount
                > self.refund_request.amount_approved
            ):
                errors["amount"] = (
                    "Transaction amount cannot exceed the "
                    "approved refund amount."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if (
            self.refund_request_id
            and not self.stripe_payment_intent_id
        ):
            self.stripe_payment_intent_id = (
                self.refund_request
                .stripe_payment_intent_id
                or ""
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.refund_request.refund_number} "
            f"- ${self.amount}"
        )


class RefundActivity(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("assigned", "Assigned"),
        ("status_changed", "Status Changed"),
        ("amount_changed", "Amount Changed"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("processing_started", "Processing Started"),
        ("processed", "Processed"),
        ("failed", "Failed"),
        ("retry_started", "Retry Started"),
        ("cancelled", "Cancelled"),
        ("note_added", "Note Added"),
    ]

    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.CASCADE,
        related_name="activities",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

    message = models.TextField(
        blank=True,
    )

    previous_value = models.CharField(
        max_length=255,
        blank=True,
    )

    new_value = models.CharField(
        max_length=255,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_activities",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return (
            f"{self.refund_request.refund_number} "
            f"- {self.get_action_display()}"
        )
    
class StripeWebhookEvent(models.Model):
    """
    Persistent Stripe webhook event log.

    Prevents duplicate processing while providing a complete
    audit trail of every webhook received.
    """

    STATUS_CHOICES = [
        ("received", "Received"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("ignored", "Ignored"),
        ("failed", "Failed"),
    ]

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
    )

    event_type = models.CharField(
        max_length=120,
    )

    api_version = models.CharField(
        max_length=80,
        blank=True,
    )

    livemode = models.BooleanField(
        default=False,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="received",
    )

    payload = models.JSONField(
        default=dict,
    )

    error_message = models.TextField(
        blank=True,
    )

    retry_count = models.PositiveIntegerField(
        default=0,
    )

    received_at = models.DateTimeField(
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-received_at"]

        indexes = [
            models.Index(fields=["stripe_event_id"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["received_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.stripe_event_id})"