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


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    sku = models.CharField(max_length=80, blank=True)
    supplier = models.CharField(max_length=120, blank=True, default="Kaeser & Blair")
    supplier_product_id = models.CharField(max_length=120, blank=True)
    supplier_url = models.URLField(blank=True)

    image = models.ImageField(upload_to="products/", blank=True, null=True)

    min_quantity = models.PositiveIntegerField(default=1)
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    colors = models.CharField(max_length=255, blank=True)
    decoration_methods = models.CharField(max_length=255, blank=True)
    industries = models.CharField(max_length=255, blank=True)

    lead_time = models.CharField(max_length=80, blank=True, default="Varies by product")
    setup_fee = models.CharField(max_length=80, blank=True, default="Varies")
    material = models.CharField(max_length=120, blank=True)
    dimensions = models.CharField(max_length=120, blank=True)

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    def color_list(self):
        if not self.colors:
            return []
        return [color.strip() for color in self.colors.split(",") if color.strip()]

    def decoration_list(self):
        if not self.decoration_methods:
            return []
        return [method.strip() for method in self.decoration_methods.split(",") if method.strip()]

    def industry_list(self):
        if not self.industries:
            return []
        return [industry.strip() for industry in self.industries.split(",") if industry.strip()]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.product.name} image"