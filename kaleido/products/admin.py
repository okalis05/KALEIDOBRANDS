from django.contrib import admin

from .models import (
    Category,
    Product,
    ProductImage,
    Supplier,
    SupplierCatalog,
    SupplierSyncLog,
    Quote,
    QuoteItem,
)


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


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "website", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "website")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SupplierCatalog)
class SupplierCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "supplier", "is_active", "created_at")
    list_filter = ("supplier", "is_active")
    search_fields = ("name", "description", "catalog_url")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "supplier",
        "supplier_record",
        "sku",
        "min_quantity",
        "starting_price",
        "source",
        "is_featured",
        "is_active",
    )
    list_filter = (
        "category",
        "supplier",
        "supplier_record",
        "catalog",
        "source",
        "is_featured",
        "is_active",
    )
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
    readonly_fields = ("created_at", "last_synced_at")


@admin.register(SupplierSyncLog)
class SupplierSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "status",
        "products_created",
        "products_updated",
        "products_failed",
        "started_at",
        "completed_at",
    )
    list_filter = ("supplier", "status")
    search_fields = ("message",)
    readonly_fields = (
        "supplier",
        "status",
        "message",
        "products_created",
        "products_updated",
        "products_failed",
        "started_at",
        "completed_at",
    )

class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name",
        "company",
        "email",
        "phone",
        "project_name",
        "deadline",
        "created_at",
    )
    search_fields = (
        "customer_name",
        "company",
        "email",
        "phone",
        "project_name",
        "notes",
    )
    list_filter = ("deadline", "created_at")
    readonly_fields = ("created_at","pdf_file")
    inlines = [QuoteItemInline]