from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from products.models import Quote, SupplierSyncLog, Product

from .forms import CustomerAddressForm, CustomerProfileForm, CustomerRegistrationForm, BrandAssetForm, ArtworkProofForm, CheckoutForm
from .models import  CustomerAddress, BrandAsset, ArtworkProof, Order, CustomerLead, CustomerLead, CRMActivity, Cart, CartItem,  OrderItem
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse,  HttpResponse
from products.services.recommendations import RecommendationEngine

import stripe
from decimal import Decimal
from django.utils.crypto import get_random_string
from django.core.mail import EmailMessage
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt






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
def checkout(request):
    cart = get_active_cart(request.user)

    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("customers:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)

        if form.is_valid():
            saved_address = form.cleaned_data.get("saved_address")

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
            shipping = Decimal("0.00")
            tax = Decimal("0.00")
            total = subtotal + shipping + tax

            order = Order.objects.create(
                customer=request.user,
                order_number=generate_order_number(),
                company=company,
                status="pending",
                subtotal=subtotal,
                shipping=shipping,
                tax=tax,
                total=total,
            )

            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product_name=item.product_name,
                    sku=item.product.sku if item.product else "",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total(),
                    decoration=item.notes,
                )

            cart.status = "converted"
            cart.save(update_fields=["status"])

            customer_body = f"""
            Thank you for your KaleidoBrands order.

            Order Number: {order.order_number}
            Subtotal: ${order.subtotal}
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

                send_paid_order_emails(order)

            except Order.DoesNotExist:
                return HttpResponse(status=404)

    return HttpResponse(status=200)