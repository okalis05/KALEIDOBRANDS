from django.db import models
from django.urls import reverse




class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    website = models.URLField(blank=True)
    api_base_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    api_enabled = models.BooleanField(default=False)
    api_key_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Environment variable name containing the supplier API key.",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_frequency_hours = models.PositiveIntegerField(default=24)
    email = models.EmailField(blank=True, help_text="Supplier email address used for purchase orders.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierCatalog(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="catalogs",
    )
    name = models.CharField(max_length=180)
    catalog_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.supplier.name} - {self.name}"

class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    supplier = models.CharField(
        max_length=120,
        blank=True,
        default="Kaeser & Blair",
    )

    supplier_record = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    catalog = models.ForeignKey(
        SupplierCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    supplier_sku = models.CharField(
        max_length=120,
        blank=True,
    )

    supplier_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    supplier_inventory = models.IntegerField(
        null=True,
        blank=True,
    )

    inventory_status = models.CharField(
        max_length=30,
        choices=[
            ("unknown", "Unknown"),
            ("in_stock", "In Stock"),
            ("low_stock", "Low Stock"),
            ("out_of_stock", "Out of Stock"),
            ("discontinued", "Discontinued"),
        ],
        default="unknown",
    )

    supplier_last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    sku = models.CharField(max_length=80, blank=True)
    supplier_product_id = models.CharField(max_length=120, blank=True)
    supplier_url = models.URLField(blank=True)
    external_image_url = models.URLField(blank=True)

    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
    )

    min_quantity = models.PositiveIntegerField(default=1)

    starting_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    colors = models.CharField(max_length=255, blank=True)
    decoration_methods = models.CharField(max_length=255, blank=True)
    industries = models.CharField(max_length=255, blank=True)

    lead_time = models.CharField(
        max_length=80,
        blank=True,
        default="Varies by product",
    )

    setup_fee = models.CharField(
        max_length=80,
        blank=True,
        default="Varies",
    )

    material = models.CharField(max_length=120, blank=True)
    dimensions = models.CharField(max_length=120, blank=True)

    source = models.CharField(
        max_length=80,
        blank=True,
        default="manual",
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["supplier_product_id"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "products:detail",
            kwargs={"slug": self.slug},
        )

    def color_list(self):
        if not self.colors:
            return []

        return [
            color.strip()
            for color in self.colors.split(",")
            if color.strip()
        ]

    def decoration_list(self):
        if not self.decoration_methods:
            return []

        return [
            method.strip()
            for method in self.decoration_methods.split(",")
            if method.strip()
        ]

    def industry_list(self):
        if not self.industries:
            return []

        return [
            industry.strip()
            for industry in self.industries.split(",")
            if industry.strip()
        ]

    def display_image_url(self):
        if self.image:
            return self.image.url

        if self.external_image_url:
            return self.external_image_url

        return ""


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to="products/gallery/", blank=True, null=True)
    external_image_url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.product.name} image"

    @property
    def display_url(self):
        if self.image:
            return self.image.url
        return self.external_image_url


class SupplierSyncLog(models.Model):
    STATUS_CHOICES = [
        ("started", "Started"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("partial", "Partial"),
    ]

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="started")
    message = models.TextField(blank=True)
    products_created = models.PositiveIntegerField(default=0)
    products_updated = models.PositiveIntegerField(default=0)
    products_failed = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "Unknown Supplier"
        return f"{supplier_name} sync - {self.status}"
    
from .models_recommendations import *
from .models_supplier_history import *
from .models_purchase_orders import *
from .models_purchase_order_activity import *
from .models_quote import *
from .models_marketplace import *