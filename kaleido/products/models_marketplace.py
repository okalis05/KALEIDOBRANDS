from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class SupplierListing(models.Model):
    """
    Represents one supplier's offer for a KaleidoBrands product.

    Product is the customer-facing catalog identity.
    SupplierListing is the supplier-specific sourcing record.
    """

    INVENTORY_STATUS_CHOICES = [
        ("unknown", "Unknown"),
        ("in_stock", "In Stock"),
        ("low_stock", "Low Stock"),
        ("out_of_stock", "Out of Stock"),
        ("discontinued", "Discontinued"),
    ]

    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("api", "Supplier API"),
        ("csv", "CSV Import"),
        ("catalog", "Supplier Catalog"),
        ("sync", "Automated Sync"),
        ("other", "Other"),
    ]

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="supplier_listings",
    )

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.PROTECT,
        related_name="product_listings",
    )

    catalog = models.ForeignKey(
        "products.SupplierCatalog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_listings",
    )

    supplier_product_id = models.CharField(
        max_length=160,
        blank=True,
        help_text="Supplier-side product identifier.",
    )

    supplier_sku = models.CharField(
        max_length=160,
        blank=True,
        help_text="Supplier-specific SKU.",
    )

    supplier_product_name = models.CharField(
        max_length=220,
        blank=True,
        help_text="Product name as shown by the supplier.",
    )

    supplier_url = models.URLField(
        blank=True,
    )

    external_image_url = models.URLField(
        blank=True,
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    setup_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    minimum_order_quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
        ],
    )

    inventory_quantity = models.IntegerField(
        null=True,
        blank=True,
    )

    inventory_status = models.CharField(
        max_length=30,
        choices=INVENTORY_STATUS_CHOICES,
        default="unknown",
    )

    production_lead_time_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    decoration_methods = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated supplier decoration methods.",
    )

    available_colors = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated supplier color options.",
    )

    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="manual",
    )

    source_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw normalized supplier data used to create this listing.",
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_preferred = models.BooleanField(
        default=False,
        help_text="Marks the preferred supplier offer for this product.",
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "product__name",
            "-is_preferred",
            "supplier__name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "supplier",
                    "supplier_sku",
                ],
                condition=~Q(supplier_sku=""),
                name="uniq_supplier_listing_sku",
            ),
            models.UniqueConstraint(
                fields=[
                    "supplier",
                    "supplier_product_id",
                ],
                condition=~Q(supplier_product_id=""),
                name="uniq_supplier_listing_product_id",
            ),
            models.UniqueConstraint(
                fields=[
                    "product",
                ],
                condition=Q(is_preferred=True),
                name="uniq_preferred_listing_per_product",
            ),
            models.CheckConstraint(
                check=(
                    Q(inventory_quantity__isnull=True)
                    | Q(inventory_quantity__gte=0)
                ),
                name="supplier_listing_inventory_nonnegative",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "is_active",
                ],
                name="listing_product_active_idx",
            ),
            models.Index(
                fields=[
                    "supplier",
                    "is_active",
                ],
                name="listing_supplier_active_idx",
            ),
            models.Index(
                fields=[
                    "inventory_status",
                ],
                name="listing_inventory_idx",
            ),
            models.Index(
                fields=[
                    "source",
                ],
                name="listing_source_idx",
            ),
            models.Index(
                fields=[
                    "last_synced_at",
                ],
                name="listing_last_sync_idx",
            ),
        ]

        verbose_name = "Supplier listing"
        verbose_name_plural = "Supplier listings"

    def clean(self):
        errors = {}

        if (
            self.catalog_id
            and self.supplier_id
            and self.catalog.supplier_id != self.supplier_id
        ):
            errors["catalog"] = (
                "The selected catalog does not belong to this supplier."
            )

        if (
            self.inventory_quantity is not None
            and self.inventory_quantity < 0
        ):
            errors["inventory_quantity"] = (
                "Inventory quantity cannot be negative."
            )

        if (
            self.inventory_status == "out_of_stock"
            and self.inventory_quantity not in (None, 0)
        ):
            errors["inventory_quantity"] = (
                "An out-of-stock listing cannot have positive inventory."
            )

        if (
            self.inventory_status == "in_stock"
            and self.inventory_quantity == 0
        ):
            errors["inventory_status"] = (
                "A listing with zero inventory cannot be marked in stock."
            )

        if (
            self.inventory_status == "discontinued"
            and self.is_active
        ):
            errors["is_active"] = (
                "A discontinued listing must be inactive."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        identifier = (
            self.supplier_sku
            or self.supplier_product_id
            or str(self.pk or "new")
        )

        return (
            f"{self.product.name} — "
            f"{self.supplier.name} ({identifier})"
        )

    @property
    def display_name(self):
        return self.supplier_product_name or self.product.name

    @property
    def display_image_url(self):
        if self.external_image_url:
            return self.external_image_url

        return self.product.display_image_url()

    def decoration_list(self):
        if not self.decoration_methods:
            return []

        return [
            method.strip()
            for method in self.decoration_methods.split(",")
            if method.strip()
        ]

    def color_list(self):
        if not self.available_colors:
            return []

        return [
            color.strip()
            for color in self.available_colors.split(",")
            if color.strip()
        ]