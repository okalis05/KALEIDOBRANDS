from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class Industry(models.Model):
    """
    Represents a customer-facing industry used to organize products.

    Examples:
    Healthcare, Education, Construction, Hospitality, and Technology.
    """

    name = models.CharField(
        max_length=140,
    )

    slug = models.SlugField(
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    icon = models.CharField(
        max_length=80,
        blank=True,
    )

    image = models.ImageField(
        upload_to="marketplace/industries/",
        blank=True,
        null=True,
    )

    is_featured = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "name",
        ]

        verbose_name_plural = "Industries"

        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "is_featured",
                    "order",
                ],
                name="industry_active_feature_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "products:industry",
            kwargs={
                "slug": self.slug,
            },
        )


class ProductCollection(models.Model):
    """
    Represents a curated collection of marketplace products.

    Examples:
    Summer Essentials, Healthcare Favorites, New Arrivals, and Staff Picks.
    """

    name = models.CharField(
        max_length=160,
    )

    slug = models.SlugField(
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    image = models.ImageField(
        upload_to="marketplace/collections/",
        blank=True,
        null=True,
    )

    is_featured = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "name",
        ]

        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "is_featured",
                    "order",
                ],
                name="collection_active_feat_idx",
            ),
            models.Index(
                fields=[
                    "starts_at",
                    "ends_at",
                ],
                name="collection_window_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}

        if (
            self.starts_at
            and self.ends_at
            and self.ends_at <= self.starts_at
        ):
            errors["ends_at"] = (
                "The collection end date must be later than "
                "the collection start date."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def is_current(self):
        now = timezone.now()

        if not self.is_active:
            return False

        if self.starts_at and self.starts_at > now:
            return False

        if self.ends_at and self.ends_at <= now:
            return False

        return True

    def get_absolute_url(self):
        return reverse(
            "products:collection",
            kwargs={
                "slug": self.slug,
            },
        )


class ImprintMethod(models.Model):
    """
    Represents a structured product decoration or imprint method.

    The existing comma-separated Product.decoration_methods field remains
    available for existing supplier imports and backwards compatibility.
    """

    name = models.CharField(
        max_length=140,
    )

    slug = models.SlugField(
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    setup_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0.00"),
            ),
        ],
    )

    price_adjustment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    is_active = models.BooleanField(
        default=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "name",
        ]

        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "order",
                ],
                name="imprint_active_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    """
    Represents a variation of a marketplace product.

    Examples:
    - Blue / Large
    - Red / Medium
    - 16 GB
    - Stainless Steel
    """

    INVENTORY_STATUS_CHOICES = [
        (
            "unknown",
            "Unknown",
        ),
        (
            "in_stock",
            "In Stock",
        ),
        (
            "low_stock",
            "Low Stock",
        ),
        (
            "out_of_stock",
            "Out of Stock",
        ),
        (
            "discontinued",
            "Discontinued",
        ),
    ]

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="variants",
    )

    name = models.CharField(
        max_length=180,
    )

    sku = models.CharField(
        max_length=120,
        blank=True,
    )

    supplier_sku = models.CharField(
        max_length=160,
        blank=True,
    )

    color = models.CharField(
        max_length=120,
        blank=True,
    )

    size = models.CharField(
        max_length=120,
        blank=True,
    )

    material = models.CharField(
        max_length=120,
        blank=True,
    )

    price_adjustment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
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

    is_default = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    source_payload = models.JSONField(
        default=dict,
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
            "order",
            "name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "product",
                    "sku",
                ],
                condition=~Q(
                    sku="",
                ),
                name="uniq_product_variant_sku",
            ),
            models.UniqueConstraint(
                fields=[
                    "product",
                ],
                condition=Q(
                    is_default=True,
                ),
                name="uniq_default_variant_per_product",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        inventory_quantity__isnull=True,
                    )
                    | Q(
                        inventory_quantity__gte=0,
                    )
                ),
                name="product_variant_inventory_nonnegative",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "is_active",
                    "order",
                ],
                name="variant_product_active_idx",
            ),
            models.Index(
                fields=[
                    "sku",
                ],
                name="variant_sku_idx",
            ),
            models.Index(
                fields=[
                    "supplier_sku",
                ],
                name="variant_supplier_sku_idx",
            ),
            models.Index(
                fields=[
                    "inventory_status",
                ],
                name="variant_inventory_idx",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.name}"

    def clean(self):
        errors = {}

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
                "An out-of-stock variant cannot have positive inventory."
            )

        if (
            self.inventory_status == "in_stock"
            and self.inventory_quantity == 0
        ):
            errors["inventory_status"] = (
                "A variant with zero inventory cannot be marked in stock."
            )

        if (
            self.inventory_status == "discontinued"
            and self.is_active
        ):
            errors["is_active"] = (
                "A discontinued variant must be inactive."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    @property
    def effective_price(self):
        if self.product.starting_price is None:
            return None

        return (
            self.product.starting_price
            + self.price_adjustment
        )


class ProductSpecification(models.Model):
    """
    Represents a structured product specification.

    Examples:
    Material: Polyester
    Capacity: 20 ounces
    Dimensions: 12 x 8 inches
    """

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="specifications",
    )

    name = models.CharField(
        max_length=140,
    )

    value = models.CharField(
        max_length=500,
    )

    unit = models.CharField(
        max_length=60,
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    is_highlighted = models.BooleanField(
        default=False,
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
            "order",
            "name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "product",
                    "name",
                ],
                name="uniq_product_specification_name",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "order",
                ],
                name="spec_product_order_idx",
            ),
        ]

    def __str__(self):
        suffix = (
            f" {self.unit}"
            if self.unit
            else ""
        )

        return (
            f"{self.product.name}: "
            f"{self.name} = "
            f"{self.value}{suffix}"
        )


class HomepageProductRail(models.Model):
    """
    Represents one product section on the marketplace homepage.

    Examples:
    - Featured Products
    - Healthcare Essentials
    - New Arrivals
    - Staff Favorites
    """

    RAIL_TYPE_CHOICES = [
        (
            "manual",
            "Manual Products",
        ),
        (
            "featured",
            "Featured Products",
        ),
        (
            "newest",
            "Newest Products",
        ),
        (
            "category",
            "Category",
        ),
        (
            "industry",
            "Industry",
        ),
        (
            "collection",
            "Collection",
        ),
    ]

    title = models.CharField(
        max_length=180,
    )

    slug = models.SlugField(
        unique=True,
    )

    subtitle = models.CharField(
        max_length=255,
        blank=True,
    )

    rail_type = models.CharField(
        max_length=30,
        choices=RAIL_TYPE_CHOICES,
        default="manual",
    )

    category = models.ForeignKey(
        "products.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homepage_product_rails",
    )

    industry = models.ForeignKey(
        "products.Industry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homepage_product_rails",
    )

    collection = models.ForeignKey(
        "products.ProductCollection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homepage_product_rails",
    )

    products = models.ManyToManyField(
        "products.Product",
        blank=True,
        related_name="homepage_rails",
    )

    max_products = models.PositiveIntegerField(
        default=12,
    )

    is_active = models.BooleanField(
        default=True,
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "title",
        ]

        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "order",
                ],
                name="homepage_rail_active_idx",
            ),
            models.Index(
                fields=[
                    "starts_at",
                    "ends_at",
                ],
                name="homepage_rail_window_idx",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}

        if self.max_products < 1:
            errors["max_products"] = (
                "A homepage product rail must display "
                "at least one product."
            )

        if (
            self.starts_at
            and self.ends_at
            and self.ends_at <= self.starts_at
        ):
            errors["ends_at"] = (
                "The rail end date must be later than "
                "the rail start date."
            )

        if (
            self.rail_type == "category"
            and not self.category_id
        ):
            errors["category"] = (
                "Select a category for a category rail."
            )

        if (
            self.rail_type == "industry"
            and not self.industry_id
        ):
            errors["industry"] = (
                "Select an industry for an industry rail."
            )

        if (
            self.rail_type == "collection"
            and not self.collection_id
        ):
            errors["collection"] = (
                "Select a collection for a collection rail."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def is_current(self):
        now = timezone.now()

        if not self.is_active:
            return False

        if self.starts_at and self.starts_at > now:
            return False

        if self.ends_at and self.ends_at <= now:
            return False

        return True


class SupplierListing(models.Model):
    """
    Represents one supplier's offer for a KaleidoBrands product.

    Product is the customer-facing marketplace identity.
    SupplierListing is the supplier-specific sourcing record.
    """

    INVENTORY_STATUS_CHOICES = [
        (
            "unknown",
            "Unknown",
        ),
        (
            "in_stock",
            "In Stock",
        ),
        (
            "low_stock",
            "Low Stock",
        ),
        (
            "out_of_stock",
            "Out of Stock",
        ),
        (
            "discontinued",
            "Discontinued",
        ),
    ]

    SOURCE_CHOICES = [
        (
            "manual",
            "Manual",
        ),
        (
            "api",
            "Supplier API",
        ),
        (
            "csv",
            "CSV Import",
        ),
        (
            "catalog",
            "Supplier Catalog",
        ),
        (
            "sync",
            "Automated Sync",
        ),
        (
            "other",
            "Other",
        ),
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
            MinValueValidator(
                Decimal("0.00"),
            ),
        ],
    )

    setup_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0.00"),
            ),
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
        help_text=(
            "Comma-separated supplier decoration methods."
        ),
    )

    available_colors = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Comma-separated supplier color options."
        ),
    )

    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="manual",
    )

    source_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Raw normalized supplier data used to create this listing."
        ),
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_preferred = models.BooleanField(
        default=False,
        help_text=(
            "Marks the preferred supplier offer for this product."
        ),
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
                condition=~Q(
                    supplier_sku="",
                ),
                name="uniq_supplier_listing_sku",
            ),
            models.UniqueConstraint(
                fields=[
                    "supplier",
                    "supplier_product_id",
                ],
                condition=~Q(
                    supplier_product_id="",
                ),
                name="uniq_supplier_listing_product_id",
            ),
            models.UniqueConstraint(
                fields=[
                    "product",
                ],
                condition=Q(
                    is_preferred=True,
                ),
                name="uniq_preferred_listing_per_product",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        inventory_quantity__isnull=True,
                    )
                    | Q(
                        inventory_quantity__gte=0,
                    )
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
                "The selected catalog does not belong "
                "to this supplier."
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

        super().save(
            *args,
            **kwargs,
        )

    def __str__(self):
        identifier = (
            self.supplier_sku
            or self.supplier_product_id
            or str(
                self.pk
                or "new"
            )
        )

        return (
            f"{self.product.name} — "
            f"{self.supplier.name} "
            f"({identifier})"
        )

    @property
    def display_name(self):
        return (
            self.supplier_product_name
            or self.product.name
        )

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