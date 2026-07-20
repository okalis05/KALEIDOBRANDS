from django.db import models


class ShippingMethod(models.Model):
    METHOD_TYPES = [
        ("ground", "Ground"),
        ("two_day", "2-Day"),
        ("overnight", "Overnight"),
        ("pickup", "Local Pickup"),
        ("supplier", "Supplier Shipping"),
    ]

    name = models.CharField(max_length=120)
    code = models.SlugField(unique=True)

    method_type = models.CharField(
        max_length=30,
        choices=METHOD_TYPES,
        default="ground",
    )

    carrier = models.CharField(
        max_length=80,
        blank=True,
    )

    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    estimated_days_min = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    estimated_days_max = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["base_price", "name"]

    def __str__(self):
        return self.name


class Shipment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("label_created", "Label Created"),
        ("ready", "Ready for Pickup"),
        ("in_transit", "In Transit"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("exception", "Delivery Exception"),
        ("cancelled", "Cancelled"),
    ]

    order = models.ForeignKey(
        "customers.Order",
        on_delete=models.CASCADE,
        related_name="shipments",
    )

    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )

    supplier_purchase_order = models.ForeignKey(
        "products.SupplierPurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )

    shipment_number = models.CharField(
        max_length=40,
        unique=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
    )

    packing_slip = models.FileField(
        upload_to="shipments/packing_slips/",
        blank=True,
        null=True,
    )

    carrier = models.CharField(max_length=80, blank=True)
    service_level = models.CharField(max_length=100, blank=True)

    tracking_number = models.CharField(
        max_length=160,
        blank=True,
    )

    tracking_url = models.URLField(blank=True)

    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    estimated_ship_date = models.DateField(
        null=True,
        blank=True,
    )

    estimated_delivery_date = models.DateField(
        null=True,
        blank=True,
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.shipment_number


class ShipmentItem(models.Model):
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="items",
    )

    order_item = models.ForeignKey(
        "customers.OrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipment_items",
    )

    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=120, blank=True)

    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class ShipmentStatusHistory(models.Model):
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    previous_status = models.CharField(
        max_length=30,
        blank=True,
    )

    new_status = models.CharField(
        max_length=30,
    )

    message = models.TextField(blank=True)

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipment_status_updates",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shipment.shipment_number}: {self.new_status}"