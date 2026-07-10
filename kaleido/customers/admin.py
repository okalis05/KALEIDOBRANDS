from django.contrib import admin
from .models import CustomerProfile, BrandAsset
from .models import (
    CustomerProfile,
    BrandAsset,
    Order,
    OrderItem,
    ArtworkProof,
    CustomerLead,
    CRMActivity,
    Cart,
    CartItem,
    CustomerAddress,
    
)


# Register your models here.
@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "phone", "city", "state", "created_at")
    search_fields = ("user__username", "user__email", "company", "phone")
    list_filter = ("state", "country")


@admin.register(BrandAsset)
class BrandAssetAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "asset_type", "uploaded_at")
    search_fields = ("title", "user__username", "user__email", "notes")
    list_filter = ("asset_type", "uploaded_at")

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class ArtworkProofInline(admin.TabularInline):
    model = ArtworkProof
    extra = 0
    readonly_fields = ("created_at", "updated_at")

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "order_number",
        "customer",
        "company",
        "status",
        "total",
        "estimated_delivery",
        "shipping_email_sent",
        "created_at",
        "payment_status",
        "paid_at",
    )

    list_filter = (
        "status",
        "carrier",
    )

    search_fields = (
        "order_number",
        "customer__username",
        "customer__email",
        "company",
        "tracking_number",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "shipping_email_sent_at",
        "invoice_pdf",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "paid_at",
    )

    inlines = [OrderItemInline, ArtworkProofInline]


class ArtworkProofInline(admin.TabularInline):
    model = ArtworkProof
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(ArtworkProof)
class ArtworkProofAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "order",
        "status",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "title",
        "order__order_number",
        "customer_notes",
        "staff_notes",
    )
    readonly_fields = ("created_at", "updated_at")


class CRMActivityInline(admin.TabularInline):
    model = CRMActivity
    extra = 0


@admin.register(CustomerLead)
class CustomerLeadAdmin(admin.ModelAdmin):

    list_display = (
        "company",
        "contact_name",
        "status",
        "estimated_value",
        "assigned_to",
        "created_at",
    )

    list_filter = (
        "status",
        "assigned_to",
    )

    search_fields = (
        "company",
        "contact_name",
        "email",
    )

    inlines = [CRMActivityInline]


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email")
    inlines = [CartItemInline]


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "city", "state", "is_default", "created_at")
    list_filter = ("state", "is_default", "created_at")
    search_fields = ("label", "user__email", "name", "company", "city")