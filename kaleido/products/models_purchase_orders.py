from django.conf import settings
from django.db import models


class SupplierPurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready to Send"),
        ("sent", "Sent to Supplier"),
        ("confirmed", "Confirmed"),
        ("in_production", "In Production"),
        ("shipped", "Shipped"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )

    customer_order = models.ForeignKey(
        "customers.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_purchase_orders",
    )

    po_number = models.CharField(
        max_length=40,
        unique=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
    )

    supplier_reference = models.CharField(
        max_length=120,
        blank=True,
    )

    tracking_number = models.CharField(
        max_length=120,
        blank=True,
    )

    tracking_url = models.URLField(blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_supplier_purchase_orders",
    )

    pdf_file = models.FileField(
        upload_to="supplier_purchase_orders/",
        blank=True,
        null=True,
    )

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    production_started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    received_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    estimated_ship_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.po_number

    def total_cost(self):
        return sum(
            (item.line_total for item in self.items.all()),
            start=0,
        )


class SupplierPurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        SupplierPurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    order_item = models.ForeignKey(
        "customers.OrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_purchase_order_items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    supplier_listing = models.ForeignKey(
        "products.SupplierListing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )

    product_name = models.CharField(max_length=200)
    supplier_sku = models.CharField(max_length=120, blank=True)

    supplier_product_id_snapshot = models.CharField(
        max_length=160,
        blank=True,
    )

    supplier_product_name_snapshot = models.CharField(
        max_length=255,
        blank=True,
    )

    supplier_catalog_snapshot = models.CharField(
        max_length=160,
        blank=True,
    )

    supplier_source_snapshot = models.CharField(
        max_length=160,
        blank=True,
    )

    setup_cost_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    minimum_quantity_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    decoration = models.CharField(max_length=180, blank=True)
    color = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product_name