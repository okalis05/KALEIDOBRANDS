from django.conf import settings
from django.db import models
from products.models import Quote


class Order(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("artwork", "Artwork Approval"),
        ("production", "In Production"),
        ("quality", "Quality Control"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    quote = models.ForeignKey(
        Quote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    order_number = models.CharField(
        max_length=30,
        unique=True,
    )

    company = models.CharField(
        max_length=200,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    shipping = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    invoice_pdf = models.FileField(
        upload_to="orders/invoices/",
        blank=True,
        null=True,
    )

    tracking_number = models.CharField(
        max_length=100,
        blank=True,
    )

    carrier = models.CharField(
        max_length=80,
        blank=True,
    )

    estimated_delivery = models.DateField(
        null=True,
        blank=True,
    )

    shipping_email_sent = models.BooleanField(
        default=False
    
    )
    shipping_email_sent_at = models.DateTimeField(
        null=True, 
        blank=True
    )


    PAYMENT_STATUS_CHOICES = [
    ("unpaid", "Unpaid"),
    ("pending", "Pending"),
    ("paid", "Paid"),
    ("partially_refunded", "Partially Refunded"),
    ("refunded", "Refunded"),
    ("failed", "Failed"),
]
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
    )

    shipping_method = models.ForeignKey(
        "customers.ShippingMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    shipping_method_name = models.CharField(
        max_length=120,
        blank=True,
    )

    shipping_name = models.CharField(
        max_length=200,
        blank=True,
    )

    shipping_address = models.TextField(
        blank=True,
    )

    shipping_city = models.CharField(
        max_length=100,
        blank=True,
    )

    shipping_state = models.CharField(
        max_length=100,
        blank=True,
    )

    shipping_postal_code = models.CharField(
        max_length=20,
        blank=True,
    )

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    tracking_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number
    
    
    
class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    supplier_listing = models.ForeignKey(
        "products.SupplierListing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    product_name = models.CharField(
        max_length=200,
    )

    sku = models.CharField(
        max_length=80,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    decoration = models.CharField(
        max_length=150,
        blank=True,
    )

    color = models.CharField(
        max_length=100,
        blank=True,
    )

    # Supplier snapshots preserve the original sourcing details even if the
    # SupplierListing record changes or is deleted later.

    supplier_name_snapshot = models.CharField(
        max_length=150,
        blank=True,
    )

    supplier_sku_snapshot = models.CharField(
        max_length=160,
        blank=True,
    )

    supplier_product_id_snapshot = models.CharField(
        max_length=160,
        blank=True,
    )

    supplier_product_name_snapshot = models.CharField(
        max_length=220,
        blank=True,
    )

    supplier_catalog_snapshot = models.CharField(
        max_length=180,
        blank=True,
    )

    supplier_unit_cost_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    supplier_setup_cost_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    supplier_minimum_quantity_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    supplier_source_snapshot = models.CharField(
        max_length=30,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

        indexes = [
            models.Index(
                fields=["supplier_listing"],
                name="orderitem_listing_idx",
            ),
            models.Index(
                fields=["supplier_name_snapshot"],
                name="orderitem_supplier_idx",
            ),
            models.Index(
                fields=["supplier_sku_snapshot"],
                name="orderitem_supplier_sku_idx",
            ),
        ]

    def __str__(self):
        return self.product_name

    def apply_supplier_listing_snapshot(self, listing=None):
        """
        Attach a supplier listing and copy its current sourcing details.

        Snapshot values must not be refreshed automatically after the initial
        order-item creation because historical order sourcing must remain fixed.
        """

        listing = listing or self.supplier_listing

        if listing is None:
            return

        self.supplier_listing = listing
        self.supplier_name_snapshot = listing.supplier.name
        self.supplier_sku_snapshot = listing.supplier_sku
        self.supplier_product_id_snapshot = listing.supplier_product_id
        self.supplier_product_name_snapshot = (
            listing.supplier_product_name
            or listing.product.name
        )
        self.supplier_catalog_snapshot = (
            listing.catalog.name
            if listing.catalog_id
            else ""
        )
        self.supplier_unit_cost_snapshot = listing.unit_cost
        self.supplier_setup_cost_snapshot = listing.setup_cost
        self.supplier_minimum_quantity_snapshot = (
            listing.minimum_order_quantity
        )
        self.supplier_source_snapshot = listing.source

    @property
    def supplier_line_cost(self):
        if self.supplier_unit_cost_snapshot is None:
            return None

        return (
            self.supplier_unit_cost_snapshot
            * self.quantity
        )