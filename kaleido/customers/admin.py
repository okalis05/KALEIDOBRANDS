from django.contrib import admin

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
    ShippingMethod,
    Shipment,
    ShipmentItem,
    ShipmentStatusHistory,

    
)
from customers.models import (
    ReturnRequest,
    ReturnRequestActivity,
    ReturnRequestAttachment,
    ReturnRequestItem,
    ReturnRequestMessage,
    RefundActivity,
    RefundRequest,
    RefundTransaction,
    StripeWebhookEvent
)


from customers.webhooks.refunds import (
    process_failed_webhook,
)
from customers.services.refund_exports import (
    export_refund_requests_csv,
    export_refund_transactions_csv,
    export_webhook_events_csv,
)


@admin.action(
    description="Export selected refunds to CSV"
)
def export_selected_refunds(
    modeladmin,
    request,
    queryset,
):
    return export_refund_requests_csv(
        queryset,
        filename="selected_refunds.csv",
    )


@admin.action(
    description="Export selected refund transactions to CSV"
)
def export_selected_refund_transactions(
    modeladmin,
    request,
    queryset,
):
    return export_refund_transactions_csv(
        queryset,
        filename="selected_refund_transactions.csv",
    )



@admin.action(
    description="Export selected Stripe webhooks to CSV"
)
def export_selected_webhooks(
    modeladmin,
    request,
    queryset,
):
    return export_webhook_events_csv(
        queryset,
        filename="selected_webhooks.csv",
    )



@admin.action(
    description="Retry selected Stripe webhooks"
)
def retry_selected_webhooks(
    modeladmin,
    request,
    queryset,
):
    success = 0

    for webhook in queryset:

        try:

            process_failed_webhook(
                webhook
            )

            success += 1

        except Exception:
            pass

    modeladmin.message_user(
        request,
        f"{success} webhook(s) retried.",
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

    fields = (
        "product_name",
        "sku",
        "quantity",
        "unit_price",
        "line_total",
        "supplier_listing",
        "supplier_name_snapshot",
        "supplier_sku_snapshot",
        "supplier_unit_cost_snapshot",
    )

    readonly_fields = (
        "product_name",
        "sku",
        "quantity",
        "unit_price",
        "line_total",
        "supplier_name_snapshot",
        "supplier_sku_snapshot",
        "supplier_unit_cost_snapshot",
    )

    autocomplete_fields = (
        "supplier_listing",
    )

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
        "shipping_method_name",
        "shipping",
    )

    list_filter = (
        "status",
        "carrier",
        "shipping_method",
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


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0


class ShipmentStatusHistoryInline(admin.TabularInline):
    model = ShipmentStatusHistory
    extra = 0
    readonly_fields = (
        "previous_status",
        "new_status",
        "message",
        "created_by",
        "created_at",
    )


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "method_type",
        "carrier",
        "base_price",
        "is_active",
    )

    list_filter = (
        "method_type",
        "carrier",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
        "carrier",
    )


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "shipment_number",
        "order",
        "carrier",
        "status",
        "tracking_number",
        "packing_slip",
        "estimated_delivery_date",
        "created_at",
    )

    list_filter = (
        "status",
        "carrier",
        "shipping_method",
        "created_at",
    )

    search_fields = (
        "shipment_number",
        "tracking_number",
        "order__order_number",
        "carrier",
    )

    readonly_fields = (
        "packing_slip",
        "created_at",
        "updated_at",
        "shipped_at",
        "delivered_at",
    )

    inlines = [
        ShipmentItemInline,
        ShipmentStatusHistoryInline,
    ]


@admin.register(ShipmentStatusHistory)
class ShipmentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "shipment",
        "previous_status",
        "new_status",
        "created_by",
        "created_at",
    )

    list_filter = (
        "new_status",
        "created_at",
    )

    search_fields = (
        "shipment__shipment_number",
        "message",
    )

    readonly_fields = (
        "shipment",
        "previous_status",
        "new_status",
        "message",
        "created_by",
        "created_at",
    )

class ReturnRequestItemInline(admin.TabularInline):
    model = ReturnRequestItem
    extra = 0


class ReturnRequestMessageInline(admin.TabularInline):
    model = ReturnRequestMessage
    extra = 0


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "customer",
        "order",
        "request_type",
        "status",
        "resolution",
        "assigned_to",
        "requested_at",
    )

    list_filter = (
        "request_type",
        "reason",
        "status",
        "resolution",
        "requested_at",
    )

    search_fields = (
        "request_number",
        "rma_number",
        "customer__username",
        "customer__email",
        "order__order_number",
    )

    readonly_fields = (
        "request_number",
        "requested_at",
        "updated_at",
        "reviewed_at",
        "approved_at",
        "rejected_at",
        "received_at",
        "completed_at",
    )

    inlines = [
        ReturnRequestItemInline,
        ReturnRequestMessageInline,
    ]


@admin.register(ReturnRequestAttachment)
class ReturnRequestAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "return_request",
        "uploaded_by",
        "file",
        "created_at",
    )

    search_fields = (
        "return_request__request_number",
        "uploaded_by__username",
    )


@admin.register(ReturnRequestActivity)
class ReturnRequestActivityAdmin(admin.ModelAdmin):
    list_display = (
        "return_request",
        "action",
        "created_by",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    readonly_fields = (
        "return_request",
        "action",
        "message",
        "previous_value",
        "new_value",
        "created_by",
        "created_at",
    )


class RefundTransactionInline(
    admin.TabularInline
):
    model = RefundTransaction
    extra = 0

    fields = (
        "amount",
        "status",
        "stripe_refund_id",
        "stripe_status",
        "created_by",
        "created_at",
    )

    readonly_fields = (
        "amount",
        "status",
        "stripe_refund_id",
        "stripe_status",
        "created_by",
        "created_at",
    )

    can_delete = False


class RefundActivityInline(
    admin.TabularInline
):
    model = RefundActivity
    extra = 0

    fields = (
        "action",
        "message",
        "previous_value",
        "new_value",
        "created_by",
        "created_at",
    )

    readonly_fields = fields
    can_delete = False


@admin.register(RefundRequest)
class RefundRequestAdmin(
    admin.ModelAdmin
):
    list_display = (
        "refund_number",
        "customer",
        "order",
        "status",
        "amount_requested",
        "amount_approved",
        "amount_refunded",
        "assigned_to",
        "requested_at",
    )

    list_filter = (
        "status",
        "reason",
        "requested_at",
        "approved_at",
        "completed_at",
    )

    search_fields = (
        "refund_number",
        "customer__username",
        "customer__email",
        "order__order_number",
        "stripe_payment_intent_id",
        "stripe_refund_id",
    )

    readonly_fields = (
        "refund_number",
        "amount_refunded",
        "stripe_payment_intent_id",
        "stripe_refund_id",
        "idempotency_key",
        "requested_at",
        "updated_at",
        "reviewed_at",
        "approved_at",
        "processed_at",
        "completed_at",
        "failed_at",
        "rejected_at",
        "cancelled_at",
    )

    fieldsets = (
        (
            "Refund Request",
            {
                "fields": (
                    "refund_number",
                    "customer",
                    "order",
                    "return_request",
                    "assigned_to",
                    "reason",
                    "status",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "amount_requested",
                    "amount_approved",
                    "amount_refunded",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "customer_notes",
                    "staff_notes",
                    "failure_message",
                )
            },
        ),
        (
            "Stripe",
            {
                "fields": (
                    "stripe_payment_intent_id",
                    "stripe_refund_id",
                    "idempotency_key",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "requested_at",
                    "updated_at",
                    "reviewed_at",
                    "approved_at",
                    "processed_at",
                    "completed_at",
                    "failed_at",
                    "rejected_at",
                    "cancelled_at",
                )
            },
        ),
    )

    inlines = [
        RefundTransactionInline,
        RefundActivityInline,
    ]

    actions = [
        export_selected_refunds,
    ]


@admin.register(RefundTransaction)
class RefundTransactionAdmin(
    admin.ModelAdmin
):
    list_display = (
        "refund_request",
        "amount",
        "status",
        "stripe_refund_id",
        "stripe_status",
        "created_by",
        "created_at",
    )

    list_filter = (
        "status",
        "stripe_status",
        "created_at",
    )

    search_fields = (
        "refund_request__refund_number",
        "refund_request__order__order_number",
        "stripe_refund_id",
        "stripe_payment_intent_id",
        "idempotency_key",
    )

    readonly_fields = (
        "refund_request",
        "amount",
        "status",
        "stripe_refund_id",
        "stripe_payment_intent_id",
        "idempotency_key",
        "stripe_status",
        "stripe_response",
        "failure_message",
        "created_by",
        "created_at",
        "updated_at",
        "processed_at",
        "completed_at",
        "failed_at",
    )
    actions = [
        export_selected_refund_transactions,
    ]

@admin.register(RefundActivity)
class RefundActivityAdmin(
    admin.ModelAdmin
):
    list_display = (
        "refund_request",
        "action",
        "created_by",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "refund_request__refund_number",
        "refund_request__order__order_number",
        "message",
    )

    readonly_fields = (
        "refund_request",
        "action",
        "message",
        "previous_value",
        "new_value",
        "created_by",
        "created_at",
    )




@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):

    list_display = (
        "stripe_event_id",
        "event_type",
        "status",
        "received_at",
        "processed_at",
    )

    list_filter = (
        "status",
        "event_type",
    )

    search_fields = (
        "stripe_event_id",
    )

    actions = [
        retry_selected_webhooks,
        export_selected_webhooks,
    ]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "product_name",
        "order",
        "quantity",
        "unit_price",
        "supplier_name_snapshot",
        "supplier_sku_snapshot",
        "supplier_unit_cost_snapshot",
    )

    list_filter = (
        "supplier_name_snapshot",
    )

    search_fields = (
        "product_name",
        "sku",
        "order__order_number",
        "supplier_name_snapshot",
        "supplier_sku_snapshot",
        "supplier_product_id_snapshot",
    )

    autocomplete_fields = (
        "product",
        "supplier_listing",
    )

    readonly_fields = (
        "supplier_name_snapshot",
        "supplier_sku_snapshot",
        "supplier_product_id_snapshot",
        "supplier_product_name_snapshot",
        "supplier_catalog_snapshot",
        "supplier_unit_cost_snapshot",
        "supplier_setup_cost_snapshot",
        "supplier_minimum_quantity_snapshot",
        "supplier_source_snapshot",
    )