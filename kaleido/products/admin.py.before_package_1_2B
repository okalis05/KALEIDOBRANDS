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
    RecommendationEvent,
    SupplierPriceHistory,
    SupplierInventoryHistory,
    SupplierPurchaseOrder,
    SupplierPurchaseOrderItem,
    SupplierPurchaseOrderActivity,
    SupplierListing,
)
from products.models import (
    SupplierIntegrationAuditLog,
    SupplierSyncBatch,
    SupplierSyncCheckpoint,
    SupplierSyncJob,
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
    list_display = (
    "name",
    "slug",
    "website",
    "email",
    "api_enabled",
    "is_active",
    "last_synced_at",
    )   
    list_filter = ("is_active",)
    search_fields = ("name", "website")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SupplierCatalog)
class SupplierCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "supplier", "is_active", "created_at")
    list_filter = ("supplier", "is_active")
    search_fields = ("name", "description", "catalog_url")


class SupplierListingInline(admin.TabularInline):
    model = SupplierListing
    extra = 0
    fields = (
        "supplier",
        "supplier_sku",
        "unit_cost",
        "minimum_order_quantity",
        "inventory_status",
        "inventory_quantity",
        "is_preferred",
        "is_active",
    )
    autocomplete_fields = (
        "supplier",
    )
    show_change_link = True


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
        "supplier_price",
        "supplier_inventory",
        "inventory_status",
        "supplier_last_synced_at",
    )
    list_filter = (
        "category",
        "supplier",
        "supplier_record",
        "catalog",
        "source",
        "is_featured",
        "is_active",
        "inventory_status",
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
    inlines = [
    ProductImageInline,
    SupplierListingInline,
    ]
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

@admin.register(RecommendationEvent)
class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = ("product_name", "context", "user", "created_at")
    list_filter = ("context", "created_at")
    search_fields = ("product_name", "product_slug", "user__username", "user__email")
    readonly_fields = ("product_name", "product_slug", "context", "user", "created_at")



@admin.register(SupplierPriceHistory)
class SupplierPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "supplier",
        "previous_price",
        "new_price",
        "recorded_at",
    )
    list_filter = ("supplier", "recorded_at")
    search_fields = ("product__name", "product__sku")
    readonly_fields = (
        "product",
        "supplier",
        "previous_price",
        "new_price",
        "recorded_at",
    )


@admin.register(SupplierInventoryHistory)
class SupplierInventoryHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "supplier",
        "previous_quantity",
        "new_quantity",
        "new_status",
        "recorded_at",
    )
    list_filter = ("supplier", "new_status", "recorded_at")
    search_fields = ("product__name", "product__sku")
    readonly_fields = (
        "product",
        "supplier",
        "previous_quantity",
        "new_quantity",
        "previous_status",
        "new_status",
        "recorded_at",
    )

class SupplierPurchaseOrderItemInline(admin.TabularInline):
    model = SupplierPurchaseOrderItem
    extra = 0


@admin.register(SupplierPurchaseOrder)
class SupplierPurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "po_number",
        "supplier",
        "customer_order",
        "status",
        "supplier_reference",
        "created_at",
        "tracking_number",
        "estimated_ship_date",
    )

    list_filter = (
        "status",
        "supplier",
        "created_at",
    )

    search_fields = (
        "po_number",
        "supplier_reference",
        "customer_order__order_number",
        "supplier__name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "sent_at",
        "pdf_file",
        "confirmed_at",
        "production_started_at",
        "shipped_at",
        "received_at",
    )

    inlines = [SupplierPurchaseOrderItemInline]

@admin.register(SupplierPurchaseOrderActivity)
class SupplierPurchaseOrderActivityAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_order",
        "action",
        "created_by",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "purchase_order__po_number",
        "message",
        "created_by__username",
        "created_by__email",
    )

    readonly_fields = (
        "purchase_order",
        "action",
        "message",
        "previous_value",
        "new_value",
        "created_by",
        "created_at",
    )


@admin.register(SupplierListing)
class SupplierListingAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "supplier",
        "supplier_sku",
        "unit_cost",
        "minimum_order_quantity",
        "inventory_status",
        "inventory_quantity",
        "is_preferred",
        "is_active",
        "last_synced_at",
    )

    list_filter = (
        "supplier",
        "inventory_status",
        "source",
        "is_preferred",
        "is_active",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "supplier__name",
        "supplier_sku",
        "supplier_product_id",
        "supplier_product_name",
    )

    autocomplete_fields = (
        "product",
        "supplier",
        "catalog",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_synced_at",
    )

    fieldsets = (
        (
            "Marketplace relationship",
            {
                "fields": (
                    "product",
                    "supplier",
                    "catalog",
                    "is_preferred",
                    "is_active",
                ),
            },
        ),
        (
            "Supplier product identity",
            {
                "fields": (
                    "supplier_product_id",
                    "supplier_sku",
                    "supplier_product_name",
                    "supplier_url",
                    "external_image_url",
                ),
            },
        ),
        (
            "Supplier commercial terms",
            {
                "fields": (
                    "unit_cost",
                    "setup_cost",
                    "minimum_order_quantity",
                    "production_lead_time_days",
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "inventory_status",
                    "inventory_quantity",
                    "available_colors",
                    "decoration_methods",
                ),
            },
        ),
        (
            "Synchronization",
            {
                "fields": (
                    "source",
                    "source_payload",
                    "last_synced_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

@admin.register(
    SupplierIntegrationAuditLog
)
class SupplierIntegrationAuditLogAdmin(
    admin.ModelAdmin
):
    list_display = (
        "request_id",
        "supplier",
        "operation",
        "method",
        "status",
        "status_code",
        "attempt_count",
        "duration_ms",
        "started_at",
    )

    list_filter = (
        "status",
        "success",
        "method",
        "supplier",
        "started_at",
    )

    search_fields = (
        "request_id",
        "correlation_id",
        "operation",
        "url",
        "error_type",
        "error_message",
    )

    readonly_fields = (
        "request_id",
        "correlation_id",
        "supplier",
        "operation",
        "method",
        "url",
        "status",
        "success",
        "status_code",
        "attempt_count",
        "duration_ms",
        "request_metadata",
        "response_metadata",
        "error_type",
        "error_message",
        "started_at",
        "completed_at",
    )

    ordering = (
        "-started_at",
    )

    date_hierarchy = "started_at"

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False
    

class SupplierSyncJobInline(
    admin.TabularInline
):
    model = SupplierSyncJob
    extra = 0

    fields = (
        "supplier",
        "operation",
        "sequence",
        "status",
        "attempt_count",
        "records_processed",
        "records_succeeded",
        "records_failed",
        "started_at",
        "completed_at",
    )

    readonly_fields = fields
    ordering = (
        "sequence",
        "created_at",
    )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupplierSyncBatch)
class SupplierSyncBatchAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "status",
        "progress_percentage",
        "total_jobs",
        "successful_jobs",
        "failed_jobs",
        "skipped_jobs",
        "created_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "created_at",
        "completed_at",
    )

    search_fields = (
        "id",
        "correlation_id",
    )

    readonly_fields = (
        "id",
        "correlation_id",
        "status",
        "requested_operations",
        "metadata",
        "total_jobs",
        "completed_jobs",
        "successful_jobs",
        "failed_jobs",
        "skipped_jobs",
        "created_by",
        "created_at",
        "started_at",
        "completed_at",
    )

    inlines = [
        SupplierSyncJobInline,
    ]

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupplierSyncJob)
class SupplierSyncJobAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "batch",
        "supplier",
        "operation",
        "sequence",
        "status",
        "attempt_count",
        "records_processed",
        "records_succeeded",
        "records_failed",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "operation",
        "supplier",
        "created_at",
    )

    search_fields = (
        "id",
        "batch__id",
        "supplier__name",
        "supplier__slug",
        "operation",
        "error_type",
        "error_message",
    )

    readonly_fields = (
        "id",
        "batch",
        "supplier",
        "operation",
        "sequence",
        "depends_on",
        "status",
        "attempt_count",
        "max_attempts",
        "records_processed",
        "records_succeeded",
        "records_failed",
        "metadata",
        "result_metadata",
        "error_type",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
    )

    ordering = (
        "-created_at",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupplierSyncCheckpoint)
class SupplierSyncCheckpointAdmin(
    admin.ModelAdmin
):
    list_display = (
        "job",
        "cursor",
        "page",
        "offset",
        "last_external_id",
        "updated_at",
    )

    search_fields = (
        "job__id",
        "job__operation",
        "job__supplier__name",
        "cursor",
        "last_external_id",
    )

    readonly_fields = (
        "job",
        "cursor",
        "page",
        "offset",
        "last_external_id",
        "state",
        "updated_at",
    )

    ordering = (
        "-updated_at",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False