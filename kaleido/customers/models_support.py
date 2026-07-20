from django.conf import settings
from django.db import models


class SupportTicket(models.Model):

    CATEGORY_CHOICES = [
        ("order", "Order"),
        ("shipping", "Shipping"),
        ("payment", "Payment"),
        ("product", "Product"),
        ("artwork", "Artwork"),
        ("return", "Return"),
        ("refund", "Refund"),
        ("replacement", "Replacement"),
        ("technical", "Technical"),
        ("other", "Other"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("waiting_customer", "Waiting for Customer"),
        ("waiting_staff", "Waiting for Staff"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    ticket_number = models.CharField(
        max_length=30,
        unique=True,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )

    order = models.ForeignKey(
        "customers.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )

    shipment = models.ForeignKey(
        "customers.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="other",
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="normal",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="open",
    )

    subject = models.CharField(
        max_length=250,
    )

    description = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):

        if not self.ticket_number:

            from customers.utils import generate_ticket_number

            self.ticket_number = generate_ticket_number()

        super().save(*args, **kwargs)
    def __str__(self):
        return self.ticket_number
    


class SupportTicketMessage(models.Model):

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    message = models.TextField()

    attachment = models.FileField(
        upload_to="support/",
        blank=True,
        null=True,
    )

    is_internal = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.ticket_number}"