from django.contrib import admin

from .models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "supplier",
        "min_quantity",
        "starting_price",
        "is_featured",
        "is_active",
    )
    list_filter = ("category", "supplier", "is_featured", "is_active")
    search_fields = (
        "name",
        "sku",
        "supplier_product_id",
        "short_description",
        "description",
        "colors",
        "decoration_methods",
        "industries",
    )
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    inlines = [ProductImageInline]