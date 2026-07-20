from django.conf import settings
from django.db import models


class SupplierPurchaseOrderActivity(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("pdf_generated", "PDF Generated"),
        ("sent", "Sent"),
        ("status_changed", "Status Changed"),
        ("tracking_updated", "Tracking Updated"),
        ("supplier_reference_updated", "Supplier Reference Updated"),
        ("notes_updated", "Notes Updated"),
        ("sync", "Fulfillment Synchronized"),
        ("error", "Error"),
    ]

    purchase_order = models.ForeignKey(
        "products.SupplierPurchaseOrder",
        on_delete=models.CASCADE,
        related_name="activities",
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
    )

    message = models.TextField(blank=True)

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
        related_name="supplier_po_activities",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.get_action_display()}"