from django.contrib import admin

from .models import (
    Category,
    HomepageProductRail,
    ImprintMethod,
    Industry,
    Product,
    ProductCollection,
    ProductImage,
    ProductSpecification,
    ProductVariant,
    Quote,
    QuoteItem,
    RecommendationEvent,
    Supplier,
    SupplierCatalog,
    SupplierIntegrationAuditLog,
    SupplierInventoryHistory,
    SupplierListing,
    SupplierPriceHistory,
    SupplierPurchaseOrder,
    SupplierPurchaseOrderActivity,
    SupplierPurchaseOrderItem,
    SupplierSyncBatch,
    SupplierSyncCheckpoint,
    SupplierSyncJob,
    SupplierSyncLog,
)


# ============================================================
# PRODUCT INLINES
# ============================================================


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

    fields = (
        "image",
        "external_image_url",
        "alt_text",
        "order",
    )

    ordering = (
        "order",
        "id",
    )


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0

    fields = (
        "name",
        "sku",
        "supplier_sku",
        "color",
        "size",
        "material",
        "price_adjustment",
        "inventory_status",
        "inventory_quantity",
        "is_default",
        "is_active",
        "order",
    )

    ordering = (
        "order",
        "name",
    )

    show_change_link = True


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0

    fields = (
        "name",
        "value",
        "unit",
        "is_highlighted",
        "order",
    )

    ordering = (
        "order",
        "name",
    )

    show_change_link = True


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


# ============================================================
# CATEGORY ADMIN
# ============================================================


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "parent",
        "slug",
        "icon",
        "is_root_category",
        "is_active",
        "order",
    )

    list_filter = (
        "is_active",
        "parent",
    )

    search_fields = (
        "name",
        "description",
        "parent__name",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    autocomplete_fields = (
        "parent",
    )

    ordering = (
        "order",
        "name",
    )

    fieldsets = (
        (
            "Category",
            {
                "fields": (
                    "name",
                    "slug",
                    "parent",
                    "description",
                ),
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "icon",
                    "banner_image",
                    "order",
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "is_active",
                ),
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Root category",
    )
    def is_root_category(self, obj):
        return obj.is_root


# ============================================================
# INDUSTRY ADMIN
# ============================================================


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_featured",
        "is_active",
        "order",
        "product_count",
        "updated_at",
    )

    list_filter = (
        "is_featured",
        "is_active",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "slug",
        "description",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "order",
        "name",
    )

    fieldsets = (
        (
            "Industry",
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                ),
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "icon",
                    "image",
                    "order",
                ),
            },
        ),
        (
            "Marketplace visibility",
            {
                "fields": (
                    "is_featured",
                    "is_active",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Products",
        ordering="products__count",
    )
    def product_count(self, obj):
        return obj.products.count()


# ============================================================
# PRODUCT COLLECTION ADMIN
# ============================================================


@admin.register(ProductCollection)
class ProductCollectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_featured",
        "is_active",
        "is_current_collection",
        "starts_at",
        "ends_at",
        "order",
        "product_count",
    )

    list_filter = (
        "is_featured",
        "is_active",
        "starts_at",
        "ends_at",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "description",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
        "is_current_collection",
    )

    ordering = (
        "order",
        "name",
    )

    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Collection",
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "image",
                ),
            },
        ),
        (
            "Scheduling",
            {
                "fields": (
                    "starts_at",
                    "ends_at",
                    "is_current_collection",
                ),
            },
        ),
        (
            "Marketplace visibility",
            {
                "fields": (
                    "is_featured",
                    "is_active",
                    "order",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Currently visible",
    )
    def is_current_collection(self, obj):
        if not obj:
            return False

        return obj.is_current

    @admin.display(
        description="Products",
        ordering="products__count",
    )
    def product_count(self, obj):
        return obj.products.count()


# ============================================================
# IMPRINT METHOD ADMIN
# ============================================================


@admin.register(ImprintMethod)
class ImprintMethodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "setup_fee",
        "price_adjustment",
        "is_active",
        "order",
        "product_count",
        "updated_at",
    )

    list_filter = (
        "is_active",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "slug",
        "description",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "order",
        "name",
    )

    fieldsets = (
        (
            "Imprint method",
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                ),
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "setup_fee",
                    "price_adjustment",
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "is_active",
                    "order",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Products",
        ordering="products__count",
    )
    def product_count(self, obj):
        return obj.products.count()


# ============================================================
# SUPPLIER ADMIN
# ============================================================


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

    list_filter = (
        "api_enabled",
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "website",
        "email",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    ordering = (
        "name",
    )


# ============================================================
# SUPPLIER CATALOG ADMIN
# ============================================================


@admin.register(SupplierCatalog)
class SupplierCatalogAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "supplier",
        "external_id",
        "year",
        "source_type",
        "valid_from",
        "valid_until",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "supplier",
        "source_type",
        "year",
        "is_active",
        "valid_from",
        "valid_until",
        "created_at",
    )

    search_fields = (
        "name",
        "external_id",
        "description",
        "catalog_url",
        "supplier__name",
        "supplier__slug",
    )

    autocomplete_fields = (
        "supplier",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "supplier__name",
        "name",
    )

    fieldsets = (
        (
            "Catalog",
            {
                "fields": (
                    "supplier",
                    "name",
                    "external_id",
                    "description",
                    "catalog_url",
                    "cover_image",
                ),
            },
        ),
        (
            "Catalog period",
            {
                "fields": (
                    "year",
                    "valid_from",
                    "valid_until",
                ),
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "source_type",
                    "metadata",
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "is_active",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# ============================================================
# PRODUCT ADMIN
# ============================================================


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
        "updated_at",
    )

    list_filter = (
        "category",
        "supplier",
        "supplier_record",
        "catalog",
        "industry_groups",
        "collections",
        "imprint_methods",
        "source",
        "is_featured",
        "is_active",
        "inventory_status",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "slug",
        "sku",
        "supplier_sku",
        "supplier_product_id",
        "short_description",
        "description",
        "colors",
        "decoration_methods",
        "industries",
        "industry_groups__name",
        "collections__name",
        "imprint_methods__name",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        ),
    }

    autocomplete_fields = (
        "category",
        "supplier_record",
        "catalog",
    )

    filter_horizontal = (
        "industry_groups",
        "collections",
        "imprint_methods",
    )

    ordering = (
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_synced_at",
        "supplier_last_synced_at",
    )

    inlines = [
        ProductImageInline,
        ProductVariantInline,
        ProductSpecificationInline,
        SupplierListingInline,
    ]

    fieldsets = (
        (
            "Product identity",
            {
                "fields": (
                    "name",
                    "slug",
                    "category",
                    "short_description",
                    "description",
                ),
            },
        ),
        (
            "Marketplace organization",
            {
                "fields": (
                    "industry_groups",
                    "collections",
                    "imprint_methods",
                    "is_featured",
                    "is_active",
                ),
            },
        ),
        (
            "Product media",
            {
                "fields": (
                    "image",
                    "external_image_url",
                ),
            },
        ),
        (
            "Customer pricing",
            {
                "fields": (
                    "starting_price",
                    "min_quantity",
                    "setup_fee",
                    "lead_time",
                ),
            },
        ),
        (
            "Product attributes",
            {
                "fields": (
                    "colors",
                    "material",
                    "dimensions",
                ),
            },
        ),
        (
            "Legacy marketplace fields",
            {
                "fields": (
                    "decoration_methods",
                    "industries",
                ),
                "description": (
                    "These text fields are retained for existing "
                    "supplier imports and backwards compatibility."
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Supplier relationship",
            {
                "fields": (
                    "supplier",
                    "supplier_record",
                    "catalog",
                    "supplier_product_id",
                    "supplier_sku",
                    "supplier_url",
                ),
            },
        ),
        (
            "Supplier pricing and inventory",
            {
                "fields": (
                    "supplier_price",
                    "supplier_inventory",
                    "inventory_status",
                    "supplier_last_synced_at",
                ),
            },
        ),
        (
            "Synchronization",
            {
                "fields": (
                    "source",
                    "last_synced_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# ============================================================
# PRODUCT VARIANT ADMIN
# ============================================================


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "product",
        "sku",
        "supplier_sku",
        "color",
        "size",
        "effective_price_display",
        "inventory_status",
        "inventory_quantity",
        "is_default",
        "is_active",
        "order",
    )

    list_filter = (
        "inventory_status",
        "is_default",
        "is_active",
        "color",
        "size",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "sku",
        "supplier_sku",
        "product__name",
        "product__sku",
        "color",
        "size",
        "material",
    )

    autocomplete_fields = (
        "product",
    )

    readonly_fields = (
        "effective_price_display",
        "created_at",
        "updated_at",
    )

    ordering = (
        "product__name",
        "order",
        "name",
    )

    fieldsets = (
        (
            "Variant",
            {
                "fields": (
                    "product",
                    "name",
                    "sku",
                    "supplier_sku",
                ),
            },
        ),
        (
            "Attributes",
            {
                "fields": (
                    "color",
                    "size",
                    "material",
                ),
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price_adjustment",
                    "effective_price_display",
                ),
            },
        ),
        (
            "Inventory",
            {
                "fields": (
                    "inventory_status",
                    "inventory_quantity",
                ),
            },
        ),
        (
            "Display and availability",
            {
                "fields": (
                    "is_default",
                    "is_active",
                    "order",
                ),
            },
        ),
        (
            "Supplier data",
            {
                "fields": (
                    "source_payload",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Effective price",
    )
    def effective_price_display(self, obj):
        if not obj or obj.effective_price is None:
            return "Not set"

        return f"${obj.effective_price:,.2f}"


# ============================================================
# PRODUCT SPECIFICATION ADMIN
# ============================================================


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "name",
        "value",
        "unit",
        "is_highlighted",
        "order",
        "updated_at",
    )

    list_filter = (
        "is_highlighted",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "name",
        "value",
        "unit",
    )

    autocomplete_fields = (
        "product",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "product__name",
        "order",
        "name",
    )

    fieldsets = (
        (
            "Specification",
            {
                "fields": (
                    "product",
                    "name",
                    "value",
                    "unit",
                ),
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "is_highlighted",
                    "order",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# ============================================================
# HOMEPAGE PRODUCT RAIL ADMIN
# ============================================================


@admin.register(HomepageProductRail)
class HomepageProductRailAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "rail_type",
        "selected_target",
        "max_products",
        "is_active",
        "is_current_rail",
        "starts_at",
        "ends_at",
        "order",
        "updated_at",
    )

    list_filter = (
        "rail_type",
        "is_active",
        "starts_at",
        "ends_at",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "slug",
        "subtitle",
        "category__name",
        "industry__name",
        "collection__name",
        "products__name",
    )

    prepopulated_fields = {
        "slug": (
            "title",
        ),
    }

    autocomplete_fields = (
        "category",
        "industry",
        "collection",
    )

    filter_horizontal = (
        "products",
    )

    readonly_fields = (
        "is_current_rail",
        "created_at",
        "updated_at",
    )

    ordering = (
        "order",
        "title",
    )

    fieldsets = (
        (
            "Homepage section",
            {
                "fields": (
                    "title",
                    "slug",
                    "subtitle",
                    "rail_type",
                ),
            },
        ),
        (
            "Automatic product source",
            {
                "fields": (
                    "category",
                    "industry",
                    "collection",
                ),
                "description": (
                    "Select only the source that matches the chosen "
                    "rail type. Manual rails use the Products field below."
                ),
            },
        ),
        (
            "Manual products",
            {
                "fields": (
                    "products",
                ),
            },
        ),
        (
            "Display settings",
            {
                "fields": (
                    "max_products",
                    "order",
                    "is_active",
                ),
            },
        ),
        (
            "Scheduling",
            {
                "fields": (
                    "starts_at",
                    "ends_at",
                    "is_current_rail",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(
        description="Target",
    )
    def selected_target(self, obj):
        if obj.rail_type == "category":
            return obj.category or "Category not selected"

        if obj.rail_type == "industry":
            return obj.industry or "Industry not selected"

        if obj.rail_type == "collection":
            return obj.collection or "Collection not selected"

        if obj.rail_type == "manual":
            return f"{obj.products.count()} manual products"

        return obj.get_rail_type_display()

    @admin.display(
        boolean=True,
        description="Currently visible",
    )
    def is_current_rail(self, obj):
        if not obj:
            return False

        return obj.is_current


# ============================================================
# SUPPLIER SYNC LOG ADMIN
# ============================================================


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

    list_filter = (
        "supplier",
        "status",
    )

    search_fields = (
        "message",
    )

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


# ============================================================
# QUOTE ADMIN
# ============================================================


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

    list_filter = (
        "deadline",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "pdf_file",
    )

    inlines = [
        QuoteItemInline,
    ]


# ============================================================
# RECOMMENDATION ADMIN
# ============================================================


@admin.register(RecommendationEvent)
class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = (
        "product_name",
        "context",
        "user",
        "created_at",
    )

    list_filter = (
        "context",
        "created_at",
    )

    search_fields = (
        "product_name",
        "product_slug",
        "user__username",
        "user__email",
    )

    readonly_fields = (
        "product_name",
        "product_slug",
        "context",
        "user",
        "created_at",
    )


# ============================================================
# SUPPLIER HISTORY ADMIN
# ============================================================


@admin.register(SupplierPriceHistory)
class SupplierPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "supplier",
        "previous_price",
        "new_price",
        "recorded_at",
    )

    list_filter = (
        "supplier",
        "recorded_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
    )

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

    list_filter = (
        "supplier",
        "new_status",
        "recorded_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
    )

    readonly_fields = (
        "product",
        "supplier",
        "previous_quantity",
        "new_quantity",
        "previous_status",
        "new_status",
        "recorded_at",
    )


# ============================================================
# SUPPLIER PURCHASE ORDER ADMIN
# ============================================================


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

    inlines = [
        SupplierPurchaseOrderItemInline,
    ]


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


# ============================================================
# SUPPLIER LISTING ADMIN
# ============================================================


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


# ============================================================
# SUPPLIER INTEGRATION AUDIT ADMIN
# ============================================================


@admin.register(SupplierIntegrationAuditLog)
class SupplierIntegrationAuditLogAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


# ============================================================
# SUPPLIER SYNC ADMIN
# ============================================================


class SupplierSyncJobInline(admin.TabularInline):
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
class SupplierSyncBatchAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupplierSyncJob)
class SupplierSyncJobAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupplierSyncCheckpoint)
class SupplierSyncCheckpointAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False