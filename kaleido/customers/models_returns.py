from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class ReturnRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ("return", "Return"),
        ("replacement", "Replacement"),
        ("damaged", "Damaged Item"),
        ("wrong_item", "Wrong Item"),
        ("missing_item", "Missing Item"),
    ]

    REASON_CHOICES = [
        ("damaged", "Product arrived damaged"),
        ("defective", "Product is defective"),
        ("wrong_item", "Wrong product received"),
        ("missing_item", "Product or quantity missing"),
        ("not_as_expected", "Product not as expected"),
        ("quality", "Quality concern"),
        ("shipping_damage", "Shipping damage"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("information_requested", "Information Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("awaiting_return", "Awaiting Return"),
        ("item_received", "Item Received"),
        ("replacement_processing", "Replacement Processing"),
        ("refund_processing", "Refund Processing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    RESOLUTION_CHOICES = [
        ("", "Not Determined"),
        ("refund", "Refund"),
        ("replacement", "Replacement"),
        ("store_credit", "Store Credit"),
        ("repair", "Repair"),
        ("no_action", "No Action"),
    ]

    request_number = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_requests",
    )

    order = models.ForeignKey(
        "customers.Order",
        on_delete=models.CASCADE,
        related_name="return_requests",
    )

    support_ticket = models.ForeignKey(
        "customers.SupportTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_requests",
    )

    replacement_shipment = models.ForeignKey(
        "customers.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_return_requests",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_return_requests",
    )

    request_type = models.CharField(
        max_length=30,
        choices=REQUEST_TYPE_CHOICES,
    )

    reason = models.CharField(
        max_length=40,
        choices=REASON_CHOICES,
    )

    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default="submitted",
    )

    resolution = models.CharField(
        max_length=30,
        choices=RESOLUTION_CHOICES,
        blank=True,
    )

    customer_notes = models.TextField()

    staff_notes = models.TextField(
        blank=True,
    )

    rma_number = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
    )

    return_tracking_number = models.CharField(
        max_length=160,
        blank=True,
    )

    return_tracking_url = models.URLField(
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

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    received_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["request_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["request_type"]),
            models.Index(fields=["requested_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.request_number:
            from customers.services.returns import (
                generate_return_request_number,
            )

            self.request_number = generate_return_request_number()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.request_number


class ReturnRequestItem(models.Model):
    CONDITION_CHOICES = [
        ("unopened", "Unopened"),
        ("opened", "Opened"),
        ("damaged", "Damaged"),
        ("defective", "Defective"),
        ("missing", "Missing"),
        ("wrong_item", "Wrong Item"),
        ("other", "Other"),
    ]

    ITEM_RESOLUTION_CHOICES = [
        ("", "Not Determined"),
        ("refund", "Refund"),
        ("replacement", "Replacement"),
        ("store_credit", "Store Credit"),
        ("no_action", "No Action"),
    ]

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )

    order_item = models.ForeignKey(
        "customers.OrderItem",
        on_delete=models.CASCADE,
        related_name="return_request_items",
    )

    product_name = models.CharField(
        max_length=200,
    )

    sku = models.CharField(
        max_length=120,
        blank=True,
    )

    quantity_requested = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    quantity_approved = models.PositiveIntegerField(
        default=0,
    )

    quantity_received = models.PositiveIntegerField(
        default=0,
    )

    condition = models.CharField(
        max_length=30,
        choices=CONDITION_CHOICES,
        default="other",
    )

    resolution = models.CharField(
        max_length=30,
        choices=ITEM_RESOLUTION_CHOICES,
        blank=True,
    )

    customer_item_notes = models.TextField(
        blank=True,
    )

    staff_item_notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.order_item_id:
            if (
                self.return_request_id
                and self.order_item.order_id
                != self.return_request.order_id
            ):
                raise ValidationError(
                    "The selected order item does not belong to this order."
                )

            if self.quantity_requested > self.order_item.quantity:
                raise ValidationError(
                    "Requested quantity cannot exceed the ordered quantity."
                )

        if self.quantity_approved > self.quantity_requested:
            raise ValidationError(
                "Approved quantity cannot exceed requested quantity."
            )

        if self.quantity_received > self.quantity_approved:
            raise ValidationError(
                "Received quantity cannot exceed approved quantity."
            )

    def save(self, *args, **kwargs):
        if self.order_item_id:
            self.product_name = self.order_item.product_name
            self.sku = self.order_item.sku or ""

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.return_request.request_number} - "
            f"{self.product_name}"
        )


class ReturnRequestMessage(models.Model):
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_request_messages",
    )

    message = models.TextField()

    is_internal = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.return_request.request_number} - "
            f"{self.author}"
        )


class ReturnRequestAttachment(models.Model):
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    message = models.ForeignKey(
        ReturnRequestMessage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_attachments",
    )

    file = models.FileField(
        upload_to="returns/evidence/",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.file.name


class ReturnRequestActivity(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("status_changed", "Status Changed"),
        ("assigned", "Assigned"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("rma_created", "RMA Created"),
        ("message_added", "Message Added"),
        ("attachment_added", "Attachment Added"),
        ("item_received", "Item Received"),
        ("replacement_created", "Replacement Created"),
        ("completed", "Completed"),
    ]

    return_request = models.ForeignKey(
        ReturnRequest,
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
        related_name="return_activities",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.return_request.request_number} - "
            f"{self.get_action_display()}"
        )