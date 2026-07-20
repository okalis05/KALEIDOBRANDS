import os
import stripe
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login

from django.http import FileResponse, Http404

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404

from products.models import (
    Product,
    Quote,
    SupplierPurchaseOrder,
    SupplierSyncLog,
)
from customers.services.marketplace import (
    select_supplier_listing,
)
from .forms import ShipmentTrackingForm, ShipmentForm, ShipmentItemSelectionForm, CustomerAddressForm, CustomerProfileForm, CustomerRegistrationForm, BrandAssetForm, ArtworkProofForm, CheckoutForm
from .models import  Shipment, CustomerAddress, BrandAsset, ArtworkProof, Order, CustomerLead, CustomerLead, CRMActivity, Cart, CartItem,  OrderItem

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Avg, Q

from django.http import JsonResponse,  HttpResponse
from products.services.recommendations import RecommendationEngine
from .services.shipping import create_shipment_from_order

from django.utils.crypto import get_random_string
from django.core.mail import EmailMessage

from django.views.decorators.csrf import csrf_exempt
from products.services.purchase_orders import (create_purchase_orders_from_order)
from products.services.purchase_order_delivery import (deliver_purchase_order)
from customers.services.shipping import (
    create_default_shipment_for_paid_order,
)
from .services.shipment_tracking import (
    assign_tracking,
    update_shipment_status,
)
from customers.services.packing_slip_pdf import (
    generate_packing_slip_pdf,
)
from customers.services.support_notifications import (
    notify_customer_staff_replied,
    notify_customer_ticket_created,
    notify_customer_ticket_status,
    notify_staff_customer_replied,
    notify_staff_ticket_created,
)

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.shortcuts import get_object_or_404, redirect, render
from customers.forms import (
    ReturnItemFormSet,
    ReturnMessageForm,
    ReturnRequestForm,
    StaffReturnItemForm,
    StaffReturnMessageForm,
    StaffReturnUpdateForm,
    SupportTicketForm,
    SupportTicketReplyForm,
    StaffTicketReplyForm,
    SupportTicketUpdateForm,
)

from customers.models import (
    ReturnRequest,
    ReturnRequestActivity,
    ReturnRequestAttachment,
    ReturnRequestItem,
    ReturnRequestMessage,
    RefundActivity,
    SupportTicket,
    SupportTicketMessage,
    RefundRequest,
    RefundTransaction,
    StripeWebhookEvent,
)

from customers.services.return_notifications import (
    notify_return_created,
    notify_return_message,
    notify_return_status_changed,
)

from customers.services.returns import (
    approve_return_request,
    complete_return_request,
    create_replacement_shipment,
    issue_rma,
    log_return_activity,
    reject_return_request,
)
from customers.services.refund_reporting import (
    dashboard_summary,
    refunds_by_day,
    refunds_by_status,
    refunds_by_reason,
)
from datetime import datetime, time

from django.contrib.admin.views.decorators import (
    staff_member_required,
)


from customers.services.refund_exports import (
    export_refund_requests_csv,
    export_refund_transactions_csv,
    export_webhook_events_csv,
)
from django.core.paginator import Paginator





def signup(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            login(request, user)

            messages.success(request, "Your KaleidoBrands account has been created.")
            return redirect("customers:dashboard")
    else:
        form = CustomerRegistrationForm()

    return render(
        request,
        "customers/signup.html",
        {
            "form": form,
        },
    )


@login_required
def dashboard(request):
    profile = request.user.customer_profile

    quotes = Quote.objects.filter(
        email__iexact=request.user.email
    ).order_by("-created_at")[:5]

    recommended_products = RecommendationEngine.customer_recommendations(request.user)
    RecommendationEngine.log_recommendations(
    recommended_products,
    context="customer_dashboard",
    user=request.user,
)

    return render(
        request,
        "customers/dashboard.html",
        {
            "profile": profile,
            "quotes": quotes,
            "recommended_products": recommended_products,
        },
    )


@login_required
def profile_settings(request):
    profile = request.user.customer_profile

    if request.method == "POST":
        form = CustomerProfileForm(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("customers:profile_settings")
    else:
        form = CustomerProfileForm(instance=profile)

    return render(
        request,
        "customers/profile_settings.html",
        {
            "form": form,
        },
    )


@login_required
def asset_library(request):
    if request.method == "POST":
        form = BrandAssetForm(request.POST, request.FILES)

        if form.is_valid():
            asset = form.save(commit=False)
            asset.user = request.user
            asset.save()

            messages.success(request, "Brand asset uploaded successfully.")
            return redirect("customers:asset_library")
    else:
        form = BrandAssetForm()

    assets = BrandAsset.objects.filter(user=request.user)

    return render(
        request,
        "customers/asset_library.html",
        {
            "form": form,
            "assets": assets,
        },
    )

@login_required
def order_list(request):
    orders = Order.objects.filter(
        customer=request.user
    ).order_by("-created_at")

    return render(
        request,
        "customers/order_list.html",
        {
            "orders": orders,
        },
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    status_steps = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("artwork", "Artwork Approval"),
        ("production", "In Production"),
        ("quality", "Quality Control"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
    ]

    current_index = next(
        (
            index
            for index, step in enumerate(status_steps)
            if step[0] == order.status
        ),
        0,
    )

    return render(
        request,
        "customers/order_detail.html",
        {
            "order": order,
            "status_steps": status_steps,
            "current_index": current_index,
        },
    )

@login_required
def upload_artwork(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    if request.method == "POST":
        form = ArtworkProofForm(request.POST, request.FILES)

        if form.is_valid():
            proof = form.save(commit=False)
            proof.order = order
            proof.uploaded_by = request.user
            proof.save()

            messages.success(request, "Artwork file uploaded successfully.")
            return redirect("customers:order_detail", order_id=order.id)
    else:
        form = ArtworkProofForm()

    return render(
        request,
        "customers/upload_artwork.html",
        {
            "form": form,
            "order": order,
        },
    )


@login_required
def approve_artwork(request, proof_id):
    proof = get_object_or_404(
        ArtworkProof,
        id=proof_id,
        order__customer=request.user,
    )

    if request.method == "POST":
        proof.status = "approved"
        proof.customer_notes = request.POST.get("customer_notes", "").strip()
        proof.save()

        messages.success(request, "Artwork proof approved.")
        return redirect("customers:order_detail", order_id=proof.order.id)

    return redirect("customers:order_detail", order_id=proof.order.id)


@login_required
def request_artwork_changes(request, proof_id):
    proof = get_object_or_404(
        ArtworkProof,
        id=proof_id,
        order__customer=request.user,
    )

    if request.method == "POST":
        proof.status = "changes"
        proof.customer_notes = request.POST.get("customer_notes", "").strip()
        proof.save()

        messages.success(request, "Artwork change request submitted.")
        return redirect("customers:order_detail", order_id=proof.order.id)

    return redirect("customers:order_detail", order_id=proof.order.id)


@login_required
def reorder_order(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    return render(
        request,
        "customers/reorder_order.html",
        {
            "order": order,
        },
    )

@staff_member_required
def order_analytics(request):
    orders = Order.objects.all()

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum("total"))["total"] or 0
    average_order_value = orders.aggregate(avg=Avg("total"))["avg"] or 0

    status_counts = (
        orders.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    recent_orders = orders.select_related("customer").order_by("-created_at")[:10]

    return render(
        request,
        "customers/order_analytics.html",
        {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "average_order_value": average_order_value,
            "status_counts": status_counts,
            "recent_orders": recent_orders,
        },
    )

@staff_member_required
def crm_dashboard(request):
    leads = CustomerLead.objects.select_related(
        "customer",
        "assigned_to",
    ).order_by("-created_at")

    statuses = CustomerLead.STATUS_CHOICES

    total_pipeline_value = sum(lead.estimated_value for lead in leads)
    won_count = leads.filter(status="won").count()
    lost_count = leads.filter(status="lost").count()

    upcoming_activities = CRMActivity.objects.filter(
        completed=False,
        activity_date__gte=timezone.now(),
    ).select_related("lead").order_by("activity_date")[:10]

    return render(
        request,
        "customers/crm_dashboard.html",
        {
            "leads": leads,
            "statuses": statuses,
            "total_pipeline_value": total_pipeline_value,
            "won_count": won_count,
            "lost_count": lost_count,
            "upcoming_activities": upcoming_activities,
        },
    )

@staff_member_required
def crm_lead_detail(request, lead_id):
    lead = get_object_or_404(
        CustomerLead.objects.select_related("customer", "assigned_to"),
        id=lead_id,
    )

    activities = lead.activities.order_by("-activity_date")

    return render(
        request,
        "customers/crm_lead_detail.html",
        {
            "lead": lead,
            "activities": activities,
        },
    )


@staff_member_required
def complete_crm_activity(request, activity_id):
    activity = get_object_or_404(CRMActivity, id=activity_id)

    if request.method == "POST":
        activity.completed = True
        activity.save(update_fields=["completed"])
        messages.success(request, "Activity marked complete.")

    return redirect("customers:crm_lead_detail", lead_id=activity.lead.id)


@staff_member_required
def crm_analytics(request):
    leads = CustomerLead.objects.all()

    total_leads = leads.count()
    open_pipeline_value = leads.exclude(status__in=["won", "lost"]).aggregate(
        total=Sum("estimated_value")
    )["total"] or 0

    won_value = leads.filter(status="won").aggregate(
        total=Sum("estimated_value")
    )["total"] or 0

    lost_value = leads.filter(status="lost").aggregate(
        total=Sum("estimated_value")
    )["total"] or 0

    leads_by_status = (
        leads.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    top_opportunities = leads.exclude(status__in=["won", "lost"]).order_by(
        "-estimated_value"
    )[:10]

    upcoming_activities = CRMActivity.objects.filter(
        completed=False,
        activity_date__gte=timezone.now(),
    ).select_related("lead").order_by("activity_date")[:10]

    return render(
        request,
        "customers/crm_analytics.html",
        {
            "total_leads": total_leads,
            "open_pipeline_value": open_pipeline_value,
            "won_value": won_value,
            "lost_value": lost_value,
            "leads_by_status": leads_by_status,
            "top_opportunities": top_opportunities,
            "upcoming_activities": upcoming_activities,
        },
    )

@staff_member_required
def executive_dashboard(request):
    total_quotes = Quote.objects.count()
    total_orders = Order.objects.count()
    total_leads = CustomerLead.objects.count()

    total_revenue = Order.objects.aggregate(
        total=Sum("total")
    )["total"] or 0

    open_pipeline_value = CustomerLead.objects.exclude(
        status__in=["won", "lost"]
    ).aggregate(
        total=Sum("estimated_value")
    )["total"] or 0

    total_purchase_orders = SupplierPurchaseOrder.objects.count()
    draft_purchase_orders = SupplierPurchaseOrder.objects.filter(
        status="draft"
    ).count()

    sent_purchase_orders = SupplierPurchaseOrder.objects.filter(
        status="sent"
    ).count()

    recent_quotes = Quote.objects.order_by("-created_at")[:5]
    recent_orders = Order.objects.select_related("customer").order_by("-created_at")[:5]
    recent_leads = CustomerLead.objects.order_by("-created_at")[:5]
    recent_sync_logs = SupplierSyncLog.objects.select_related("supplier").order_by("-started_at")[:5]

    return render(
        request,
        "customers/executive_dashboard.html",
        {
            "total_quotes": total_quotes,
            "total_orders": total_orders,
            "total_leads": total_leads,
            "total_revenue": total_revenue,
            "open_pipeline_value": open_pipeline_value,
            "recent_quotes": recent_quotes,
            "recent_orders": recent_orders,
            "recent_leads": recent_leads,
            "recent_sync_logs": recent_sync_logs,
            "total_purchase_orders": total_purchase_orders,
            "draft_purchase_orders": draft_purchase_orders,
            "sent_purchase_orders": sent_purchase_orders,
        },
    )

@staff_member_required
def executive_summary_api(request):
    data = {
        "total_quotes": Quote.objects.count(),
        "total_orders": Order.objects.count(),
        "total_leads": CustomerLead.objects.count(),
        "total_revenue": float(Order.objects.aggregate(total=Sum("total"))["total"] or 0),
        "open_pipeline_value": float(
            CustomerLead.objects.exclude(status__in=["won", "lost"]).aggregate(
                total=Sum("estimated_value")
            )["total"] or 0
        ),
    }

    return JsonResponse(data)


@staff_member_required
def executive_order_status_api(request):
    rows = (
        Order.objects.values("status")
        .annotate(order_count=Count("id"), revenue_total=Sum("total"))
        .order_by("status")
    )

    data = {
        "labels": [row["status"].title() for row in rows],
        "counts": [row["order_count"] for row in rows],
        "revenue": [float(row["revenue_total"] or 0) for row in rows],
    }

    return JsonResponse(data)


@staff_member_required
def executive_crm_pipeline_api(request):
    rows = (
        CustomerLead.objects.values("status")
        .annotate(total=Count("id"), value=Sum("estimated_value"))
        .order_by("status")
    )

    data = {
        "labels": [row["status"].title() for row in rows],
        "counts": [row["total"] for row in rows],
        "values": [float(row["value"] or 0) for row in rows],
    }

    return JsonResponse(data)


@staff_member_required
def executive_supplier_sync_api(request):
    logs = SupplierSyncLog.objects.select_related("supplier").order_by("-started_at")[:10]

    data = {
        "labels": [
            log.started_at.strftime("%m/%d %H:%M")
            for log in reversed(logs)
        ],
        "created": [
            log.products_created
            for log in reversed(logs)
        ],
        "updated": [
            log.products_updated
            for log in reversed(logs)
        ],
        "failed": [
            log.products_failed
            for log in reversed(logs)
        ],
    }

    return JsonResponse(data)


def get_active_cart(user):
    cart, _ = Cart.objects.get_or_create(
        user=user,
        status="active",
    )
    return cart


@login_required
def add_to_cart(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    cart = get_active_cart(request.user)

    price = product.starting_price or Decimal("0.00")

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={
            "product_name": product.name,
            "quantity": 1,
            "unit_price": price,
        },
    )

    if not created:
        item.quantity += 1
        item.save(update_fields=["quantity"])

    messages.success(request, f"{product.name} added to your cart.")
    return redirect("customers:cart_detail")


@login_required
def cart_detail(request):
    cart = get_active_cart(request.user)

    return render(
        request,
        "customers/cart_detail.html",
        {
            "cart": cart,
        },
    )


@login_required
def update_cart_item(request, item_id):
    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user,
        cart__status="active",
    )

    if request.method == "POST":
        quantity = request.POST.get("quantity", "1")

        try:
            quantity = int(quantity)
        except ValueError:
            quantity = 1

        if quantity <= 0:
            item.delete()
            messages.success(request, "Item removed from cart.")
        else:
            item.quantity = quantity
            item.save(update_fields=["quantity"])
            messages.success(request, "Cart updated.")

    return redirect("customers:cart_detail")


@login_required
def remove_cart_item(request, item_id):
    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user,
        cart__status="active",
    )

    item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect("customers:cart_detail")


def generate_order_number():
    return f"KB-{get_random_string(8).upper()}"



@login_required
@transaction.atomic
def checkout(request):
    cart = get_active_cart(request.user)

    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("customers:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)

        if form.is_valid():
            saved_address = form.cleaned_data.get("saved_address")
            shipping_method = form.cleaned_data["shipping_method"]
            if saved_address:
                company = saved_address.company
                shipping_name = saved_address.name
                shipping_address = saved_address.address
                shipping_city = saved_address.city
                shipping_state = saved_address.state
                shipping_postal_code = saved_address.postal_code
            else:
                company = form.cleaned_data.get("company", "")
                shipping_name = form.cleaned_data.get("shipping_name", "")
                shipping_address = form.cleaned_data.get("shipping_address", "")
                shipping_city = form.cleaned_data.get("shipping_city", "")
                shipping_state = form.cleaned_data.get("shipping_state", "")
                shipping_postal_code = form.cleaned_data.get("shipping_postal_code", "")

            if form.cleaned_data.get("save_address") and not saved_address:
                CustomerAddress.objects.create(
                    user=request.user,
                    label="Checkout Address",
                    name=shipping_name,
                    company=company,
                    address=shipping_address,
                    city=shipping_city,
                    state=shipping_state,
                    postal_code=shipping_postal_code,
                )


            subtotal = cart.subtotal()
            shipping = shipping_method.base_price
            tax = Decimal("0.00")
            total = subtotal + shipping + tax

            order = Order.objects.create(
                customer=request.user,
                order_number=generate_order_number(),
                company=company,
                shipping_name=shipping_name,
                shipping_address=shipping_address,
                shipping_city=shipping_city,
                shipping_state=shipping_state,
                shipping_postal_code=shipping_postal_code,
                status="pending",
                subtotal=subtotal,
                shipping_method=shipping_method,
                shipping_method_name=shipping_method.name,
                shipping=shipping,
                tax=tax,
                total=total,

                
            )

            for item in (
                cart.items
                .select_related("product")
                .all()
            ):
                product = item.product

                supplier_listing = select_supplier_listing(
                    product
                )

                order_item = OrderItem(
                    order=order,
                    product=product,
                    supplier_listing=supplier_listing,
                    product_name=item.product_name,
                    sku=product.sku if product else "",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total(),
                    decoration=item.notes,
                )

                if supplier_listing:
                    order_item.apply_supplier_listing_snapshot(
                        supplier_listing
                    )

                order_item.save()

            cart.status = "converted"
            cart.save(update_fields=["status"])

            customer_body = f"""
            Thank you for your KaleidoBrands order.

            Order Number: {order.order_number}
            Subtotal: ${order.subtotal}
            Shipping Method: {order.shipping_method_name}
            Shipping Cost: ${order.shipping}
            Total: ${order.total}

            We received your order and will review the details shortly.
            """

            staff_body = f"""
            New KaleidoBrands Checkout Order

            Order Number: {order.order_number}
            Customer: {request.user.get_full_name() or request.user.username}
            Email: {request.user.email}
            Company: {order.company}
            Subtotal: ${order.subtotal}
            Shipping Method: {order.shipping_method_name}
            Shipping Cost: ${order.shipping}
            Total: ${order.total}

            Review in admin:
            {request.build_absolute_uri("/admin/customers/order/")}
            """

            try:
                EmailMessage(
                    subject=f"Order Received - {order.order_number}",
                    body=customer_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[request.user.email],
                ).send(fail_silently=False)

                EmailMessage(
                    subject=f"New Checkout Order - {order.order_number}",
                    body=staff_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=["sales@kaleidobrands.com"],
                ).send(fail_silently=False)

            except Exception as error:
                messages.warning(
                    request,
                    f"Order created, but confirmation email failed: {error}"
                )

            messages.success(request, "Your order has been created.")
            return redirect("customers:checkout_success", order_id=order.id)

    else:
        form = CheckoutForm(user=request.user)

    return render(
        request,
        "customers/checkout.html",
        {
            "form": form,
            "cart": cart,
        },
    )


@login_required
def address_list(request):
    if request.method == "POST":
        form = CustomerAddressForm(request.POST)

        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user

            if address.is_default:
                CustomerAddress.objects.filter(user=request.user).update(is_default=False)

            address.save()
            messages.success(request, "Address saved.")
            return redirect("customers:address_list")
    else:
        form = CustomerAddressForm()

    addresses = CustomerAddress.objects.filter(user=request.user)

    return render(
        request,
        "customers/address_list.html",
        {
            "form": form,
            "addresses": addresses,
        },
    )


@login_required
def checkout_success(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    return render(
        request,
        "customers/checkout_success.html",
        {
            "order": order,
        },
    )


@login_required
def start_payment(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    if order.total <= 0:
        messages.error(request, "This order does not have a payable balance.")
        return redirect("customers:order_detail", order_id=order.id)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    success_url = request.build_absolute_uri(
        reverse("customers:payment_success", kwargs={"order_id": order.id})
    )

    cancel_url = request.build_absolute_uri(
        reverse("customers:payment_cancel", kwargs={"order_id": order.id})
    )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        customer_email=request.user.email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"KaleidoBrands Order {order.order_number}",
                    },
                    "unit_amount": int(order.total * 100),
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "order_id": str(order.id),
            "order_number": order.order_number,
        },
    )

    order.payment_status = "pending"
    order.stripe_checkout_session_id = session.id
    order.save(update_fields=["payment_status", "stripe_checkout_session_id"])

    return redirect(session.url)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    messages.success(
        request,
        "Payment submitted. Stripe will confirm your payment shortly."
    )

    return render(
        request,
        "customers/payment_success.html",
        {
            "order": order,
        },
    )


@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    messages.warning(request, "Payment was cancelled.")
    return render(request, "customers/payment_cancel.html", {"order": order})


def send_paid_order_emails(order):
    customer_body = f"""
Payment received for your KaleidoBrands order.

Order Number: {order.order_number}
Total Paid: ${order.total}

Thank you. Our team will now review your order and begin the next production steps.
"""

    sales_body = f"""
New Paid KaleidoBrands Order

Order Number: {order.order_number}
Customer: {order.customer.get_full_name() or order.customer.username}
Email: {order.customer.email}
Company: {order.company}
Total Paid: ${order.total}
Payment Intent: {order.stripe_payment_intent_id}

Review order:
"""

    EmailMessage(
        subject=f"Payment Received - {order.order_number}",
        body=customer_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.customer.email],
    ).send(fail_silently=False)

    EmailMessage(
        subject=f"New Paid Order - {order.order_number}",
        body=sales_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=["sales@kaleidobrands.com"],
    ).send(fail_silently=False)



@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                endpoint_secret,
            )
        else:
            event = stripe.Event.construct_from(
                stripe.util.json.loads(payload),
                stripe.api_key,
            )

    except ValueError:
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        order_id = session.get("metadata", {}).get("order_id")

        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                was_already_paid = order.payment_status == "paid"
                order.payment_status = "paid"


                order.stripe_checkout_session_id = session.get("id", "")
                order.stripe_payment_intent_id = session.get("payment_intent", "")
                order.paid_at = timezone.now()
                order.save(
                    update_fields=[
                        "payment_status",
                        "stripe_checkout_session_id",
                        "stripe_payment_intent_id",
                        "paid_at",
                    ]
                )
                

                try:
                    purchase_orders = create_purchase_orders_from_order(
                        order
                    )

                    delivery_failures = []
                
                    for purchase_order in purchase_orders:
                        success, result_message = deliver_purchase_order(
                            purchase_order
                        )

                        if not success:
                            delivery_failures.append(
                                (
                                    f"{purchase_order.po_number}: "
                                    f"{result_message}"
                                )
                            )

                    if delivery_failures:
                        EmailMessage(
                            subject=(
                                f"Supplier PO Delivery Review - "
                                f"{order.order_number}"
                            ),
                            body=(
                                "Payment was confirmed and supplier purchase "
                                "orders were created, but one or more purchase "
                                "orders require staff review.\n\n"
                                + "\n".join(delivery_failures)
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=["sales@kaleidobrands.com"],
                        ).send(fail_silently=True)

                except Exception as error:
                    EmailMessage(
                        subject=(
                            f"Purchase Order Automation Failed - "
                            f"{order.order_number}"
                        ),
                        body=(
                            f"Payment was confirmed for order "
                            f"{order.order_number}, but the supplier purchase "
                            f"order workflow failed.\n\n"
                            f"Error: {error}"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=["sales@kaleidobrands.com"],
                    ).send(fail_silently=True)
                
                try:
                    shipment, shipment_created = (
                        create_default_shipment_for_paid_order(order)
                    )

                except Exception as error:
                    EmailMessage(
                        subject=(
                            f"Shipment Creation Failed - "
                            f"{order.order_number}"
                        ),
                        body=(
                            f"Payment was confirmed for order "
                            f"{order.order_number}, but the initial "
                            f"shipment could not be created.\n\n"
                            f"Error: {error}"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=["sales@kaleidobrands.com"],
                    ).send(fail_silently=True)


                if not was_already_paid:
                    send_paid_order_emails(order)

            except Order.DoesNotExist:
                return HttpResponse(status=404)

    return HttpResponse(status=200)


@staff_member_required
def shipment_list(request):
    shipments = (
        Shipment.objects
        .select_related(
            "order",
            "order__customer",
            "shipping_method",
            "supplier_purchase_order",
        )
        .prefetch_related("items")
        .order_by("-created_at")
    )

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    if selected_status:
        shipments = shipments.filter(
            status=selected_status,
        )

    today = timezone.localdate()

    late_shipments = Shipment.objects.filter(
        status__in=[
            "pending",
            "label_created",
            "ready",
            "in_transit",
            "out_for_delivery",
        ],
        estimated_delivery_date__lt=today,
    ).count()

    missing_tracking = Shipment.objects.filter(
        status__in=[
            "label_created",
            "ready",
            "in_transit",
            "out_for_delivery",
        ],
        tracking_number="",
    ).count()

    paid_orders_without_shipments = (
        Order.objects
        .filter(
            payment_status="paid",
            shipments__isnull=True,
        )
        .distinct()
        .count()
    )

    shipment_totals = Shipment.objects.aggregate(
        total=Count("id"),
        pending=Count(
            "id",
            filter=models.Q(status="pending"),
        ),
        ready=Count(
            "id",
            filter=models.Q(status="ready"),
        ),
        in_transit=Count(
            "id",
            filter=models.Q(
                status__in=[
                    "in_transit",
                    "out_for_delivery",
                ]
            ),
        ),
        delivered=Count(
            "id",
            filter=models.Q(status="delivered"),
        ),
        exceptions=Count(
            "id",
            filter=models.Q(status="exception"),
        ),
        today=Count(
            "id",
            filter=models.Q(
                created_at__date=today,
            ),
        ),
    )

    return render(
        request,
        "customers/shipment_list.html",
        {
            "shipments": shipments,
            "status_choices": Shipment.STATUS_CHOICES,
            "selected_status": selected_status,
            "shipment_totals": shipment_totals,
            "late_shipments": late_shipments,
            "missing_tracking": missing_tracking,
            "paid_orders_without_shipments": paid_orders_without_shipments,
        },
    )

@staff_member_required
def create_shipment(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        id=order_id,
    )

    if request.method == "POST":
        shipment_form = ShipmentForm(request.POST)
        item_form = ShipmentItemSelectionForm(
            request.POST,
            order=order,
        )

        if shipment_form.is_valid() and item_form.is_valid():
            item_quantities = {}

            for order_item in order.items.all():
                item_quantities[order_item.id] = (
                    item_form.cleaned_data.get(
                        f"item_{order_item.id}",
                        0,
                    )
                )

            try:
                shipment = create_shipment_from_order(
                    order,
                    shipment_data=shipment_form.cleaned_data,
                    item_quantities=item_quantities,
                    user=request.user,
                )
            except ValueError as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    f"Shipment {shipment.shipment_number} created.",
                )

                return redirect(
                    "customers:shipment_detail",
                    shipment_id=shipment.id,
                )
    else:
        shipment_form = ShipmentForm(
            initial={
                "shipping_method": order.shipping_method,
                "shipping_cost": order.shipping,
            }
        )

        item_form = ShipmentItemSelectionForm(order=order)

    return render(
        request,
        "customers/create_shipment.html",
        {
            "order": order,
            "shipment_form": shipment_form,
            "item_form": item_form,
        },
    )

@login_required
def shipment_detail(request, shipment_id):
    shipment_query = (
        Shipment.objects
        .select_related(
            "order",
            "shipping_method",
            "supplier_purchase_order",
        )
        .prefetch_related(
            "items",
            "status_history__created_by",
        )
    )

    if request.user.is_staff:
        shipment = get_object_or_404(
            shipment_query,
            id=shipment_id,
        )
    else:
        shipment = get_object_or_404(
            shipment_query,
            id=shipment_id,
            order__customer=request.user,
        )

    return render(
        request,
        "customers/shipment_detail.html",
        {
            "shipment": shipment,
        },
    )

@staff_member_required
def update_shipment(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related(
            "order",
            "order__customer",
            "shipping_method",
        ),
        id=shipment_id,
    )

    if request.method == "POST":
        form = ShipmentTrackingForm(
            request.POST
        )

        if form.is_valid():
            carrier = form.cleaned_data.get(
                "carrier",
                "",
            )

            tracking_number = form.cleaned_data.get(
                "tracking_number",
                "",
            )

            estimated_delivery_date = (
                form.cleaned_data.get(
                    "estimated_delivery_date"
                )
            )

            shipment.estimated_delivery_date = (
                estimated_delivery_date
            )

            shipment.save(
                update_fields=[
                    "estimated_delivery_date",
                    "updated_at",
                ]
            )

            assign_tracking(
                shipment,
                carrier=carrier,
                tracking_number=tracking_number,
            )

            try:
                update_shipment_status(
                    shipment,
                    form.cleaned_data["status"],
                    user=request.user,
                    message=form.cleaned_data.get(
                        "message",
                        "",
                    ),
                )

            except ValueError as error:
                messages.error(
                    request,
                    str(error),
                )

            else:
                messages.success(
                    request,
                    (
                        f"Shipment "
                        f"{shipment.shipment_number} "
                        f"updated successfully."
                    ),
                )

                return redirect(
                    "customers:shipment_detail",
                    shipment_id=shipment.id,
                )

    else:
        form = ShipmentTrackingForm(
            initial={
                "carrier": shipment.carrier,
                "tracking_number": (
                    shipment.tracking_number
                ),
                "status": shipment.status,
                "estimated_delivery_date": (
                    shipment.estimated_delivery_date
                ),
            }
        )

    return render(
        request,
        "customers/update_shipment.html",
        {
            "shipment": shipment,
            "form": form,
        },
    )




@staff_member_required
def generate_packing_slip(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects
        .select_related(
            "order",
            "order__customer",
            "shipping_method",
        )
        .prefetch_related("items"),
        id=shipment_id,
    )

    try:
        generate_packing_slip_pdf(shipment)

    except Exception as error:
        messages.error(
            request,
            (
                "Packing slip could not be generated: "
                f"{error}"
            ),
        )

    else:
        messages.success(
            request,
            (
                "Packing slip generated for "
                f"{shipment.shipment_number}."
            ),
        )

    return redirect(
        "customers:shipment_detail",
        shipment_id=shipment.id,
    )


@login_required
def download_packing_slip(request, shipment_id):
    shipment_query = Shipment.objects.select_related(
        "order",
        "order__customer",
    )

    if request.user.is_staff:
        shipment = get_object_or_404(
            shipment_query,
            id=shipment_id,
        )
    else:
        shipment = get_object_or_404(
            shipment_query,
            id=shipment_id,
            order__customer=request.user,
        )

    if not shipment.packing_slip:
        raise Http404(
            "Packing slip has not been generated."
        )

    file_path = shipment.packing_slip.path

    if not os.path.exists(file_path):
        raise Http404(
            "Packing-slip file was not found."
        )

    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=os.path.basename(file_path),
        content_type="application/pdf",
    )


@login_required
def support_ticket_list(request):
    tickets = (
        SupportTicket.objects
        .filter(customer=request.user)
        .select_related(
            "order",
            "shipment",
            "assigned_to",
        )
        .order_by("-updated_at")
    )

    selected_status = request.GET.get("status", "").strip()

    if selected_status:
        tickets = tickets.filter(status=selected_status)

    return render(
        request,
        "customers/support_ticket_list.html",
        {
            "tickets": tickets,
            "status_choices": SupportTicket.STATUS_CHOICES,
            "selected_status": selected_status,
        },
    )

@login_required
def support_ticket_create(request):
    if request.method == "POST":
        form = SupportTicketForm(
            request.POST,
            user=request.user,
        )

        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.customer = request.user
            ticket.status = "open"
            ticket.save()

            SupportTicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                message=ticket.description,
                is_internal=False,
            )

            notify_customer_ticket_created(
                ticket,
                request=request,
            )

            notify_staff_ticket_created(
                ticket,
                request=request,
            )

            messages.success(
                request,
                f"Support ticket {ticket.ticket_number} was created.",
            )

            return redirect(
                "customers:support_ticket_detail",
                ticket_id=ticket.id,
            )

    else:
        form = SupportTicketForm(user=request.user)

    return render(
        request,
        "customers/support_ticket_create.html",
        {
            "form": form,
        },
    )

@login_required
def support_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        SupportTicket.objects
        .select_related(
            "customer",
            "assigned_to",
            "order",
            "shipment",
        )
        .prefetch_related(
            "messages__author",
        ),
        id=ticket_id,
        customer=request.user,
    )

    visible_messages = ticket.messages.filter(
        is_internal=False
    )

    if request.method == "POST":
        reply_form = SupportTicketReplyForm(
            request.POST,
            request.FILES,
        )

        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.ticket = ticket
            reply.author = request.user
            reply.is_internal = False
            reply.save()

            ticket.status = "waiting_staff"
            ticket.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )
            notify_staff_customer_replied(
                ticket,
                reply,
                request=request,
            )

            messages.success(
                request,
                "Your reply was added.",
            )

            return redirect(
                "customers:support_ticket_detail",
                ticket_id=ticket.id,
            )

    else:
        reply_form = SupportTicketReplyForm()

    return render(
        request,
        "customers/support_ticket_detail.html",
        {
            "ticket": ticket,
            "visible_messages": visible_messages,
            "reply_form": reply_form,
        },
    )

@staff_member_required
def staff_ticket_list(request):
    base_tickets = (
        SupportTicket.objects
        .select_related(
            "customer",
            "assigned_to",
            "order",
            "shipment",
        )
        .order_by("-updated_at")
    )

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    selected_priority = request.GET.get(
        "priority",
        "",
    ).strip()

    selected_category = request.GET.get(
        "category",
        "",
    ).strip()

    tickets = base_tickets

    if selected_status:
        tickets = tickets.filter(
            status=selected_status,
        )

    if selected_priority:
        tickets = tickets.filter(
            priority=selected_priority,
        )

    if selected_category:
        tickets = tickets.filter(
            category=selected_category,
        )

    ticket_totals = {
        "total": base_tickets.count(),
        "open": base_tickets.filter(
            status="open"
        ).count(),
        "waiting_customer": base_tickets.filter(
            status="waiting_customer"
        ).count(),
        "waiting_staff": base_tickets.filter(
            status="waiting_staff"
        ).count(),
        "in_progress": base_tickets.filter(
            status="in_progress"
        ).count(),
        "resolved": base_tickets.filter(
            status="resolved"
        ).count(),
        "closed": base_tickets.filter(
            status="closed"
        ).count(),
        "urgent": base_tickets.filter(
            priority="urgent"
        ).count(),
        "high": base_tickets.filter(
            priority="high"
        ).count(),
        "unassigned": base_tickets.filter(
            assigned_to__isnull=True
        ).count(),
    }

    return render(
        request,
        "customers/staff_ticket_list.html",
        {
            "tickets": tickets,
            "ticket_totals": ticket_totals,
            "status_choices": SupportTicket.STATUS_CHOICES,
            "priority_choices": SupportTicket.PRIORITY_CHOICES,
            "category_choices": SupportTicket.CATEGORY_CHOICES,
            "selected_status": selected_status,
            "selected_priority": selected_priority,
            "selected_category": selected_category,
        },
    ) 

@staff_member_required
def staff_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        SupportTicket.objects
        .select_related(
            "customer",
            "assigned_to",
            "order",
            "shipment",
        )
        .prefetch_related(
            "messages__author",
        ),
        id=ticket_id,
    )

    update_form = SupportTicketUpdateForm(
        instance=ticket,
    )

    reply_form = StaffTicketReplyForm()

    if request.method == "POST":
        if "update_ticket" in request.POST:
            previous_status = ticket.status
            update_form = SupportTicketUpdateForm(
                request.POST,
                instance=ticket,
            )
            
            if update_form.is_valid():
                updated_ticket = update_form.save(
                    commit=False
                )

                if (
                    updated_ticket.status == "resolved"
                    and not updated_ticket.resolved_at
                ):
                    updated_ticket.resolved_at = timezone.now()

                elif updated_ticket.status not in {
                    "resolved",
                    "closed",
                }:
                    updated_ticket.resolved_at = None

                updated_ticket.save()
                if previous_status != updated_ticket.status:
                    notify_customer_ticket_status(
                        updated_ticket,
                        previous_status=previous_status,
                        request=request,
                    )

                messages.success(
                    request,
                    (
                        f"{ticket.ticket_number} "
                        "was updated successfully."
                    ),
                )

                return redirect(
                    "customers:staff_ticket_detail",
                    ticket_id=ticket.id,
                )

        elif "reply_ticket" in request.POST:
            reply_form = StaffTicketReplyForm(
                request.POST,
                request.FILES,
            )

            if reply_form.is_valid():
                reply = reply_form.save(
                    commit=False
                )

                reply.ticket = ticket
                reply.author = request.user
                reply.save()

                if reply.is_internal:
                    messages.success(
                        request,
                        "Internal staff note added.",
                    )

                else:
                    ticket.status = "waiting_customer"
                    ticket.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

                    notify_customer_staff_replied(
                        ticket,
                        reply,
                        request=request,
                    )

                    messages.success(
                        request,
                        "Customer-visible reply added.",
                    )
                    ticket.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

                    messages.success(
                        request,
                        "Customer-visible reply added.",
                    )

                return redirect(
                    "customers:staff_ticket_detail",
                    ticket_id=ticket.id,
                )

    messages_list = ticket.messages.select_related(
        "author"
    ).order_by("created_at")

    return render(
        request,
        "customers/staff_ticket_detail.html",
        {
            "ticket": ticket,
            "update_form": update_form,
            "reply_form": reply_form,
            "messages_list": messages_list,
        },
    )


@login_required
def return_request_list(request):
    return_requests = (
        ReturnRequest.objects
        .filter(customer=request.user)
        .select_related(
            "order",
            "assigned_to",
            "replacement_shipment",
        )
        .prefetch_related("items")
        .order_by("-requested_at")
    )

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    if selected_status:
        return_requests = return_requests.filter(
            status=selected_status
        )

    return render(
        request,
        "customers/return_request_list.html",
        {
            "return_requests": return_requests,
            "status_choices": ReturnRequest.STATUS_CHOICES,
            "selected_status": selected_status,
        },
    )


@login_required
@transaction.atomic
def return_request_create(request):
    selected_order = None

    order_id = (
        request.POST.get("order")
        or request.GET.get("order")
    )

    if order_id:
        selected_order = get_object_or_404(
            request.user.orders.prefetch_related("items"),
            id=order_id,
        )

    if request.method == "POST":
        form = ReturnRequestForm(
            request.POST,
            user=request.user,
        )

        item_formset = ReturnItemFormSet(
            request.POST,
            prefix="items",
            form_kwargs={
                "order": selected_order,
            },
        )

        if form.is_valid():
            selected_order = form.cleaned_data["order"]

            item_formset = ReturnItemFormSet(
                request.POST,
                prefix="items",
                form_kwargs={
                    "order": selected_order,
                },
            )

            if item_formset.is_valid():
                return_request = form.save(commit=False)
                return_request.customer = request.user
                return_request.status = "submitted"
                return_request.save()

                selected_item_ids = set()

                for item_form in item_formset:
                    if not item_form.cleaned_data:
                        continue

                    if item_form.cleaned_data.get("DELETE"):
                        continue

                    order_item = item_form.cleaned_data.get(
                        "order_item"
                    )

                    quantity = item_form.cleaned_data.get(
                        "quantity_requested"
                    )

                    if not order_item or not quantity:
                        continue

                    if order_item.id in selected_item_ids:
                        item_form.add_error(
                            "order_item",
                            "This item was selected more than once.",
                        )
                        continue

                    selected_item_ids.add(order_item.id)

                    ReturnRequestItem.objects.create(
                        return_request=return_request,
                        order_item=order_item,
                        product_name=order_item.product_name,
                        sku=order_item.sku,
                        quantity_requested=quantity,
                        condition=item_form.cleaned_data[
                            "condition"
                        ],
                        customer_item_notes=(
                            item_form.cleaned_data.get(
                                "customer_item_notes",
                                "",
                            )
                        ),
                    )

                if not return_request.items.exists():
                    return_request.delete()

                    messages.error(
                        request,
                        "Select at least one order item.",
                    )
                else:
                    ReturnRequestMessage.objects.create(
                        return_request=return_request,
                        author=request.user,
                        message=return_request.customer_notes,
                        is_internal=False,
                    )

                    log_return_activity(
                        return_request,
                        action="created",
                        message=(
                            f"Request created for order "
                            f"{return_request.order.order_number}."
                        ),
                        user=request.user,
                    )

                    notify_return_created(
                        return_request,
                        request=request,
                    )

                    messages.success(
                        request,
                        (
                            f"Request "
                            f"{return_request.request_number} "
                            "was submitted."
                        ),
                    )

                    return redirect(
                        "customers:return_request_detail",
                        return_id=return_request.id,
                    )
    else:
        initial = {}

        if selected_order:
            initial["order"] = selected_order

        form = ReturnRequestForm(
            user=request.user,
            initial=initial,
        )

        item_formset = ReturnItemFormSet(
            prefix="items",
            form_kwargs={
                "order": selected_order,
            },
        )

    return render(
        request,
        "customers/return_request_create.html",
        {
            "form": form,
            "item_formset": item_formset,
            "selected_order": selected_order,
        },
    )

@login_required
def return_request_detail(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects
        .select_related(
            "customer",
            "order",
            "assigned_to",
            "replacement_shipment",
            "support_ticket",
        )
        .prefetch_related(
            "items__order_item",
            "messages__author",
            "messages__attachments",
            "attachments",
            "activities__created_by",
        ),
        id=return_id,
        customer=request.user,
    )

    visible_messages = return_request.messages.filter(
        is_internal=False
    )

    if request.method == "POST":
        form = ReturnMessageForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            return_message = form.save(commit=False)
            return_message.return_request = return_request
            return_message.author = request.user
            return_message.is_internal = False
            return_message.save()

            attachment = form.cleaned_data.get("attachment")

            if attachment:
                ReturnRequestAttachment.objects.create(
                    return_request=return_request,
                    message=return_message,
                    uploaded_by=request.user,
                    file=attachment,
                    description=(
                        form.cleaned_data.get(
                            "attachment_description",
                            "",
                        )
                    ),
                )

            if return_request.status not in {
                "completed",
                "cancelled",
                "rejected",
            }:
                return_request.status = "under_review"
                return_request.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            log_return_activity(
                return_request,
                action="message_added",
                message="Customer added a message.",
                user=request.user,
            )

            notify_return_message(
                return_request,
                return_message,
                to_customer=False,
                request=request,
            )

            messages.success(
                request,
                "Your message was added.",
            )

            return redirect(
                "customers:return_request_detail",
                return_id=return_request.id,
            )
    else:
        form = ReturnMessageForm()

    return render(
        request,
        "customers/return_request_detail.html",
        {
            "return_request": return_request,
            "visible_messages": visible_messages,
            "message_form": form,
        },
    )


@staff_member_required
def staff_return_list(request):
    base_requests = (
        ReturnRequest.objects
        .select_related(
            "customer",
            "order",
            "assigned_to",
            "replacement_shipment",
        )
        .prefetch_related("items")
        .order_by("-updated_at")
    )

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    selected_type = request.GET.get(
        "request_type",
        "",
    ).strip()

    selected_assignee = request.GET.get(
        "assigned",
        "",
    ).strip()

    return_requests = base_requests

    if selected_status:
        return_requests = return_requests.filter(
            status=selected_status
        )

    if selected_type:
        return_requests = return_requests.filter(
            request_type=selected_type
        )

    if selected_assignee == "unassigned":
        return_requests = return_requests.filter(
            assigned_to__isnull=True
        )

    totals = {
        "total": base_requests.count(),
        "submitted": base_requests.filter(
            status="submitted"
        ).count(),
        "under_review": base_requests.filter(
            status="under_review"
        ).count(),
        "approved": base_requests.filter(
            status="approved"
        ).count(),
        "awaiting_return": base_requests.filter(
            status="awaiting_return"
        ).count(),
        "item_received": base_requests.filter(
            status="item_received"
        ).count(),
        "replacement_processing": base_requests.filter(
            status="replacement_processing"
        ).count(),
        "completed": base_requests.filter(
            status="completed"
        ).count(),
        "unassigned": base_requests.filter(
            assigned_to__isnull=True
        ).exclude(
            status__in=[
                "completed",
                "cancelled",
                "rejected",
            ]
        ).count(),
    }

    return render(
        request,
        "customers/staff_return_list.html",
        {
            "return_requests": return_requests,
            "totals": totals,
            "status_choices": ReturnRequest.STATUS_CHOICES,
            "type_choices": ReturnRequest.REQUEST_TYPE_CHOICES,
            "selected_status": selected_status,
            "selected_type": selected_type,
            "selected_assignee": selected_assignee,
        },
    )


@staff_member_required
@transaction.atomic
def staff_return_detail(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects
        .select_related(
            "customer",
            "order",
            "assigned_to",
            "replacement_shipment",
            "support_ticket",
        )
        .prefetch_related(
            "items__order_item",
            "messages__author",
            "messages__attachments",
            "attachments",
            "activities__created_by",
        ),
        id=return_id,
    )

    update_form = StaffReturnUpdateForm(
        instance=return_request,
    )

    message_form = StaffReturnMessageForm()

    item_forms = [
        (
            item,
            StaffReturnItemForm(
                instance=item,
                prefix=f"item-{item.id}",
            ),
        )
        for item in return_request.items.all()
    ]

    if request.method == "POST":
        if "update_request" in request.POST:
            previous_status = return_request.status
            previous_assignee = return_request.assigned_to

            update_form = StaffReturnUpdateForm(
                request.POST,
                instance=return_request,
            )

            if update_form.is_valid():
                updated_request = update_form.save(
                    commit=False
                )

                now = timezone.now()

                if (
                    updated_request.status == "under_review"
                    and not updated_request.reviewed_at
                ):
                    updated_request.reviewed_at = now

                if (
                    updated_request.status == "approved"
                    and not updated_request.approved_at
                ):
                    updated_request.approved_at = now

                if (
                    updated_request.status == "rejected"
                    and not updated_request.rejected_at
                ):
                    updated_request.rejected_at = now

                if (
                    updated_request.status == "item_received"
                    and not updated_request.received_at
                ):
                    updated_request.received_at = now

                if (
                    updated_request.status == "completed"
                    and not updated_request.completed_at
                ):
                    updated_request.completed_at = now

                updated_request.save()

                if previous_status != updated_request.status:
                    log_return_activity(
                        updated_request,
                        action="status_changed",
                        message="Request status updated.",
                        previous_value=previous_status,
                        new_value=updated_request.status,
                        user=request.user,
                    )

                    notify_return_status_changed(
                        updated_request,
                        previous_status=previous_status,
                        request=request,
                    )

                if previous_assignee != updated_request.assigned_to:
                    log_return_activity(
                        updated_request,
                        action="assigned",
                        message="Request assignment updated.",
                        previous_value=(
                            previous_assignee.username
                            if previous_assignee
                            else "Unassigned"
                        ),
                        new_value=(
                            updated_request.assigned_to.username
                            if updated_request.assigned_to
                            else "Unassigned"
                        ),
                        user=request.user,
                    )

                messages.success(
                    request,
                    "Return request updated.",
                )

                return redirect(
                    "customers:staff_return_detail",
                    return_id=return_request.id,
                )

        elif "update_item" in request.POST:
            item_id = request.POST.get("item_id")

            return_item = get_object_or_404(
                return_request.items,
                id=item_id,
            )

            item_form = StaffReturnItemForm(
                request.POST,
                instance=return_item,
                prefix=f"item-{return_item.id}",
            )

            if item_form.is_valid():
                item_form.save()

                messages.success(
                    request,
                    f"{return_item.product_name} was updated.",
                )

                return redirect(
                    "customers:staff_return_detail",
                    return_id=return_request.id,
                )

        elif "add_message" in request.POST:
            message_form = StaffReturnMessageForm(
                request.POST,
                request.FILES,
            )

            if message_form.is_valid():
                return_message = message_form.save(
                    commit=False
                )

                return_message.return_request = return_request
                return_message.author = request.user
                return_message.save()

                attachment = message_form.cleaned_data.get(
                    "attachment"
                )

                if attachment:
                    ReturnRequestAttachment.objects.create(
                        return_request=return_request,
                        message=return_message,
                        uploaded_by=request.user,
                        file=attachment,
                        description=(
                            message_form.cleaned_data.get(
                                "attachment_description",
                                "",
                            )
                        ),
                    )

                log_return_activity(
                    return_request,
                    action="message_added",
                    message=(
                        "Staff added an internal note."
                        if return_message.is_internal
                        else "Staff added a customer-visible message."
                    ),
                    user=request.user,
                )

                if not return_message.is_internal:
                    notify_return_message(
                        return_request,
                        return_message,
                        to_customer=True,
                        request=request,
                    )

                messages.success(
                    request,
                    (
                        "Internal note added."
                        if return_message.is_internal
                        else "Customer-visible message added."
                    ),
                )

                return redirect(
                    "customers:staff_return_detail",
                    return_id=return_request.id,
                )

        elif "approve_request" in request.POST:
            previous_status = return_request.status

            approve_return_request(
                return_request,
                user=request.user,
            )

            notify_return_status_changed(
                return_request,
                previous_status=previous_status,
                request=request,
            )

            messages.success(
                request,
                "Return request approved.",
            )

            return redirect(
                "customers:staff_return_detail",
                return_id=return_request.id,
            )

        elif "reject_request" in request.POST:
            previous_status = return_request.status

            reject_return_request(
                return_request,
                user=request.user,
            )

            notify_return_status_changed(
                return_request,
                previous_status=previous_status,
                request=request,
            )

            messages.success(
                request,
                "Return request rejected.",
            )

            return redirect(
                "customers:staff_return_detail",
                return_id=return_request.id,
            )

        elif "issue_rma" in request.POST:
            previous_status = return_request.status

            issue_rma(
                return_request,
                user=request.user,
            )

            notify_return_status_changed(
                return_request,
                previous_status=previous_status,
                request=request,
            )

            messages.success(
                request,
                f"RMA {return_request.rma_number} issued.",
            )

            return redirect(
                "customers:staff_return_detail",
                return_id=return_request.id,
            )

        elif "create_replacement" in request.POST:
            try:
                shipment, was_created = (
                    create_replacement_shipment(
                        return_request,
                        user=request.user,
                    )
                )

            except ValueError as error:
                messages.error(
                    request,
                    str(error),
                )

            else:
                if was_created:
                    messages.success(
                        request,
                        (
                            f"Replacement shipment "
                            f"{shipment.shipment_number} created."
                        ),
                    )
                else:
                    messages.info(
                        request,
                        "A replacement shipment already exists.",
                    )

            return redirect(
                "customers:staff_return_detail",
                return_id=return_request.id,
            )

        elif "complete_request" in request.POST:
            previous_status = return_request.status

            complete_return_request(
                return_request,
                user=request.user,
            )

            notify_return_status_changed(
                return_request,
                previous_status=previous_status,
                request=request,
            )

            messages.success(
                request,
                "Return request completed.",
            )

            return redirect(
                "customers:staff_return_detail",
                return_id=return_request.id,
            )

    return render(
        request,
        "customers/staff_return_detail.html",
        {
            "return_request": return_request,
            "update_form": update_form,
            "message_form": message_form,
            "item_forms": item_forms,
            "messages_list": (
                return_request.messages
                .select_related("author")
                .prefetch_related("attachments")
                .order_by("created_at")
            ),
        },
    )

@login_required
def download_return_attachment(request, attachment_id):
    attachment = get_object_or_404(
        ReturnRequestAttachment.objects
        .select_related(
            "return_request",
            "return_request__customer",
        ),
        id=attachment_id,
    )

    if (
        not request.user.is_staff
        and attachment.return_request.customer_id
        != request.user.id
    ):
        raise Http404(
            "Attachment not found."
        )

    file_path = attachment.file.path

    if not os.path.exists(file_path):
        raise Http404(
            "Attachment file not found."
        )

    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=os.path.basename(file_path),
    )




@staff_member_required
def refund_dashboard(request):
    refunds = RefundRequest.objects.select_related(
        "customer",
        "order",
        "assigned_to",
    ).order_by("-requested_at")

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    selected_reason = request.GET.get(
        "reason",
        "",
    ).strip()

    start_date_value = request.GET.get(
        "start_date",
        "",
    ).strip()

    end_date_value = request.GET.get(
        "end_date",
        "",
    ).strip()

    if search_query:
        refunds = refunds.filter(
            Q(
                refund_number__icontains=search_query
            )
            | Q(
                customer__username__icontains=search_query
            )
            | Q(
                customer__first_name__icontains=search_query
            )
            | Q(
                customer__last_name__icontains=search_query
            )
            | Q(
                customer__email__icontains=search_query
            )
            | Q(
                order__order_number__icontains=search_query
            )
            | Q(
                stripe_payment_intent_id__icontains=search_query
            )
            | Q(
                stripe_refund_id__icontains=search_query
            )
        )

    if selected_status:
        refunds = refunds.filter(
            status=selected_status
        )

    if selected_reason:
        refunds = refunds.filter(
            reason=selected_reason
        )

    start_date = parse_report_date(
        start_date_value
    )

    end_date = parse_report_date(
        end_date_value,
        end_of_day=True,
    )

    if start_date:
        refunds = refunds.filter(
            requested_at__gte=start_date
        )

    if end_date:
        refunds = refunds.filter(
            requested_at__lte=end_date
        )

    filtered_totals = refunds.aggregate(
        amount_requested=Sum(
            "amount_requested"
        ),
        amount_approved=Sum(
            "amount_approved"
        ),
        amount_refunded=Sum(
            "amount_refunded"
        ),
    )

    filtered_summary = {
        "count": refunds.count(),
        "requested": (
            filtered_totals["amount_requested"]
            or Decimal("0.00")
        ),
        "approved": (
            filtered_totals["amount_approved"]
            or Decimal("0.00")
        ),
        "refunded": (
            filtered_totals["amount_refunded"]
            or Decimal("0.00")
        ),
        "completed": refunds.filter(
            status="completed"
        ).count(),
        "pending": refunds.filter(
            status__in=[
                "requested",
                "approved",
                "processing",
            ]
        ).count(),
        "failed": refunds.filter(
            status="failed"
        ).count(),
    }

    paginator = Paginator(
        refunds,
        25,
    )

    page_number = request.GET.get(
        "page"
    )

    refund_page = paginator.get_page(
        page_number
    )

    summary = dashboard_summary(
        start=start_date,
        end=end_date,
    )

    context = {
    "summary": summary,
    "filtered_summary": filtered_summary,
    "refund_page": refund_page,
    "status_choices": RefundRequest.STATUS_CHOICES,
    "reason_choices": RefundRequest.REASON_CHOICES,
    "search_query": search_query,
    "selected_status": selected_status,
    "selected_reason": selected_reason,
    "start_date": start_date_value,
    "end_date": end_date_value,
    "daily": list(refunds_by_day()),
    "status": list(refunds_by_status()),
    "reasons": list(refunds_by_reason()),
    "monthly": summary["monthly"],
    "top_customers": summary["top_customers"],
    "average_days": summary["average_days"],
    "approval_rate": summary["approval_rate"],
    "failure_rate": summary["failure_rate"],
}
    return render(
        request,
        "customers/refund_dashboard.html",
        context,
    )



def parse_report_date(value, end_of_day=False):
    """
    Convert a YYYY-MM-DD query-string value into an aware datetime.
    """

    if not value:
        return None

    try:
        parsed_date = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None

    selected_time = (
        time.max
        if end_of_day
        else time.min
    )

    parsed_datetime = datetime.combine(
        parsed_date,
        selected_time,
    )

    if timezone.is_naive(parsed_datetime):
        parsed_datetime = timezone.make_aware(
            parsed_datetime
        )

    return parsed_datetime



def filter_refunds_by_date(
    queryset,
    request,
):
    """
    Apply optional start and end date filters.
    """

    start_value = request.GET.get(
        "start_date",
        "",
    )

    end_value = request.GET.get(
        "end_date",
        "",
    )

    start_date = parse_report_date(
        start_value,
    )

    end_date = parse_report_date(
        end_value,
        end_of_day=True,
    )

    if start_date:
        queryset = queryset.filter(
            requested_at__gte=start_date
        )

    if end_date:
        queryset = queryset.filter(
            requested_at__lte=end_date
        )

    return queryset



@staff_member_required
def export_all_refunds(request):
    queryset = RefundRequest.objects.all()

    queryset = filter_refunds_by_date(
        queryset,
        request,
    )

    return export_refund_requests_csv(
        queryset,
        filename="all_refund_requests.csv",
    )



@staff_member_required
def export_pending_refunds(request):
    queryset = RefundRequest.objects.filter(
        status__in=[
            "requested",
            "approved",
            "processing",
        ]
    )

    queryset = filter_refunds_by_date(
        queryset,
        request,
    )

    return export_refund_requests_csv(
        queryset,
        filename="pending_refunds.csv",
    )


@staff_member_required
def export_failed_refunds(request):
    queryset = RefundRequest.objects.filter(
        status="failed"
    )

    queryset = filter_refunds_by_date(
        queryset,
        request,
    )

    return export_refund_requests_csv(
        queryset,
        filename="failed_refunds.csv",
    )


@staff_member_required
def export_completed_refunds(request):
    queryset = RefundRequest.objects.filter(
        status="completed"
    )

    queryset = filter_refunds_by_date(
        queryset,
        request,
    )

    return export_refund_requests_csv(
        queryset,
        filename="completed_refunds.csv",
    )


@staff_member_required
def export_refund_transactions(request):
    queryset = RefundTransaction.objects.all()

    start_date = parse_report_date(
        request.GET.get("start_date")
    )

    end_date = parse_report_date(
        request.GET.get("end_date"),
        end_of_day=True,
    )

    if start_date:
        queryset = queryset.filter(
            created_at__gte=start_date
        )

    if end_date:
        queryset = queryset.filter(
            created_at__lte=end_date
        )

    return export_refund_transactions_csv(
        queryset,
        filename="refund_transactions.csv",
    )



@staff_member_required
def export_stripe_webhooks(request):
    queryset = StripeWebhookEvent.objects.all()

    start_date = parse_report_date(
        request.GET.get("start_date")
    )

    end_date = parse_report_date(
        request.GET.get("end_date"),
        end_of_day=True,
    )

    if start_date:
        queryset = queryset.filter(
            received_at__gte=start_date
        )

    if end_date:
        queryset = queryset.filter(
            received_at__lte=end_date
        )

    return export_webhook_events_csv(
        queryset,
        filename="stripe_webhook_events.csv",
    )



@staff_member_required
def printable_refund_report(request):
    refunds = RefundRequest.objects.select_related(
        "customer",
        "order",
    ).order_by("-requested_at")

    refunds = filter_refunds_by_date(
        refunds,
        request,
    )

    selected_status = request.GET.get(
        "status",
        "",
    ).strip()

    if selected_status:
        refunds = refunds.filter(
            status=selected_status
        )

    totals = {
        "count": refunds.count(),
        "requested": sum(
            (
                refund.amount_requested
                for refund in refunds
            ),
            start=0,
        ),
        "approved": sum(
            (
                refund.amount_approved
                for refund in refunds
            ),
            start=0,
        ),
        "refunded": sum(
            (
                refund.amount_refunded
                for refund in refunds
            ),
            start=0,
        ),
    }

    context = {
        "refunds": refunds,
        "totals": totals,
        "summary": dashboard_summary(),
        "start_date": request.GET.get(
            "start_date",
            "",
        ),
        "end_date": request.GET.get(
            "end_date",
            "",
        ),
        "selected_status": selected_status,
        "generated_at": timezone.now(),
    }

    return render(
        request,
        "customers/printable_refund_report.html",
        context,
    )



@staff_member_required
def refund_detail(request, refund_id):
    refund = get_object_or_404(
        RefundRequest.objects.select_related(
            "customer",
            "order",
            "assigned_to",
            "return_request",
        ),
        pk=refund_id,
    )

    transactions = (
        RefundTransaction.objects.filter(
            refund_request=refund
        )
        .select_related("created_by")
        .order_by("-created_at")
    )

    activities = (
        RefundActivity.objects.filter(
            refund_request=refund
        )
        .select_related("created_by")
        .order_by("-created_at")
    )

    duration = None

    if refund.completed_at:
        duration = (
            refund.completed_at
            - refund.requested_at
        )

    context = {
        "refund": refund,
        "transactions": transactions,
        "activities": activities,
        "processing_duration": duration,
    }

    return render(
        request,
        "customers/refund_detail.html",
        context,
    )