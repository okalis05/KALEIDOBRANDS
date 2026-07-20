from django.conf import settings
import json
from django.shortcuts import get_object_or_404, render , redirect
from django.http import JsonResponse

from django.contrib import messages 
from django.core.mail import send_mail, EmailMessage
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Min, Max, Q, Sum
from .models import Category, Product, Supplier, SupplierSyncLog, Quote, QuoteItem

import csv
import tempfile
from datetime import timedelta
from products.services.quote_pdf import generate_quote_pdf
from django.core.files.storage import FileSystemStorage
from products.services.csv_importer import ProductCSVImporter
from .forms import QuoteBuilderForm
from customers.models import CustomerLead
from products.services.recommendations import RecommendationEngine
from products.models import (
    RecommendationEvent, 
    Product, 
    Supplier, 
    SupplierInventoryHistory, 
    SupplierPriceHistory,
    SupplierSyncLog, 
    SupplierPurchaseOrder,
    SupplierSyncLog,
    )
from django.utils import timezone
from products.services.purchase_order_pdf import (generate_purchase_order_pdf,)
from products.services.purchase_order_delivery import (
    deliver_purchase_order,
)
from products.forms import SupplierPurchaseOrderStatusForm
from products.services.order_fulfillment import (
    synchronize_customer_order_from_purchase_orders,
)
from products.services.purchase_order_activity import (
    log_purchase_order_activity,
)

from django.core.exceptions import ValidationError

from products.services.purchase_order_status import (
    update_purchase_order_status as apply_purchase_order_status,
)




def product_home(request):
    categories = Category.objects.filter(is_active=True)
    featured = Product.objects.filter(
        is_active=True,
        is_featured=True,
    )[:12]

    return render(
        request,
        "products/home.html",
        {
            "categories": categories,
            "featured": featured,
        },
    )


def category_detail(request, slug):
    category = get_object_or_404(
        Category,
        slug=slug,
        is_active=True,
    )

    products = Product.objects.filter(
        category=category,
        is_active=True,
    )

    return render(
        request,
        "products/category.html",
        {
            "category": category,
            "products": products,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True,
    )

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
    ).exclude(
        id=product.id,
    )[:4]

    recommendations = RecommendationEngine.recommendations(product)
    RecommendationEngine.log_recommendations(
    recommendations,
    context="product_detail",
    user=request.user,
)

    return render(
        request,
        "products/detail.html",
        {
            "product": product,
            "related_products": related_products,
            "recommendations": recommendations,
        },
    )


def product_search(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    min_quantity = request.GET.get("min_quantity", "").strip()

    products = Product.objects.filter(is_active=True)
    categories = Category.objects.filter(is_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(industries__icontains=query)
            | Q(colors__icontains=query)
            | Q(decoration_methods__icontains=query)
        )

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if max_price:
        products = products.filter(starting_price__lte=max_price)

    if min_quantity:
        products = products.filter(min_quantity__lte=min_quantity)

    return render(
        request,
        "products/search.html",
        {
            "query": query,
            "products": products,
            "categories": categories,
            "category_slug": category_slug,
            "max_price": max_price,
            "min_quantity": min_quantity,
        },
    )


def live_search(request):
    query = request.GET.get("q", "").strip()

    products = Product.objects.filter(is_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(industries__icontains=query)
            | Q(colors__icontains=query)
            | Q(decoration_methods__icontains=query)
        )[:8]
    else:
        products = Product.objects.none()

    data = []

    for product in products:
        data.append({
            "name": product.name,
            "url": product.get_absolute_url(),
            "category": product.category.name if product.category else "",
            "price": str(product.starting_price or ""),
        })

    return JsonResponse(data, safe=False)

def quote_cart(request):
    return render(request, "products/quote_cart.html")


def supplier_detail(request, slug):
    supplier = get_object_or_404(
        Supplier,
        slug=slug,
        is_active=True,
    )

    products = Product.objects.filter(
        supplier_record=supplier,
        is_active=True,
    ).select_related(
        "category",
        "supplier_record",
        "catalog",
    )

    categories = Category.objects.filter(
        products__supplier_record=supplier,
        products__is_active=True,
    ).distinct()

    featured = products.filter(is_featured=True)[:8]

    return render(
        request,
        "products/supplier_detail.html",
        {
            "supplier": supplier,
            "products": products[:24],
            "categories": categories,
            "featured": featured,
        },
    )


def supplier_search(request, slug):
    supplier = get_object_or_404(
        Supplier,
        slug=slug,
        is_active=True,
    )

    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()

    products = Product.objects.filter(
        supplier_record=supplier,
        is_active=True,
    ).select_related(
        "category",
        "supplier_record",
        "catalog",
    )

    categories = Category.objects.filter(
        products__supplier_record=supplier,
        products__is_active=True,
    ).distinct()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(industries__icontains=query)
            | Q(colors__icontains=query)
            | Q(decoration_methods__icontains=query)
        )

    if category_slug:
        products = products.filter(category__slug=category_slug)

    return render(
        request,
        "products/supplier_search.html",
        {
            "supplier": supplier,
            "query": query,
            "products": products,
            "categories": categories,
            "category_slug": category_slug,
        },
    )

@staff_member_required
def supplier_sync_dashboard(request):
    suppliers = Supplier.objects.filter(is_active=True).annotate(
        product_count=Count("products")
    )

    logs = SupplierSyncLog.objects.select_related("supplier")[:20]

    total_supplier_products = Product.objects.filter(
        supplier_record__isnull=False
    ).count()

    kaeser_products = Product.objects.filter(
        supplier_record__slug="kaeser-blair"
    ).count()

    active_supplier_products = Product.objects.filter(
        supplier_record__isnull=False,
        is_active=True,
    ).count()

    context = {
        "suppliers": suppliers,
        "logs": logs,
        "total_supplier_products": total_supplier_products,
        "kaeser_products": kaeser_products,
        "active_supplier_products": active_supplier_products,
    }

    return render(
        request,
        "products/supplier_sync_dashboard.html",
        context,
    )

@staff_member_required
def supplier_csv_upload(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("csv_file")
        dry_run = request.POST.get("dry_run") == "1"

        if not uploaded_file:
            messages.error(request, "Please choose a CSV file.")
            return redirect("products:supplier_csv_upload")

        if not uploaded_file.name.lower().endswith(".csv"):
            messages.error(request, "Only CSV files are allowed.")
            return redirect("products:supplier_csv_upload")

        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".csv",
                mode="wb",
            ) as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)

                temp_path = temp_file.name

            importer = ProductCSVImporter()

            if dry_run:
                path = importer.validate_file_exists(temp_path)

                with path.open(newline="", encoding="utf-8-sig") as csvfile:
                    reader = csv.DictReader(csvfile)
                    importer.validate_columns(reader.fieldnames)

                messages.success(
                    request,
                    "CSV validation passed. No products were imported.",
                )

            else:
                sync_log = importer.import_csv(temp_path)

                messages.success(
                    request,
                    (
                        "CSV import complete. "
                        f"Created: {sync_log.products_created}, "
                        f"Updated: {sync_log.products_updated}, "
                        f"Failed: {sync_log.products_failed}."
                    ),
                )

        except Exception as error:
            messages.error(request, f"Import failed: {error}")

        return redirect("products:supplier_csv_upload")

    return render(request, "products/supplier_csv_upload.html")

@staff_member_required
def supplier_analytics(request):
    supplier_products = Product.objects.filter(
        supplier_record__isnull=False
    )

    total_supplier_products = supplier_products.count()

    active_supplier_products = supplier_products.filter(
        is_active=True
    ).count()

    featured_supplier_products = supplier_products.filter(
        is_featured=True
    ).count()

    average_price = supplier_products.exclude(
        starting_price__isnull=True
    ).aggregate(
        avg=Avg("starting_price")
    )["avg"] or 0

    min_price = supplier_products.exclude(
        starting_price__isnull=True
    ).aggregate(
        minimum=Min("starting_price")
    )["minimum"] or 0

    max_price = supplier_products.exclude(
        starting_price__isnull=True
    ).aggregate(
        maximum=Max("starting_price")
    )["maximum"] or 0

    average_min_quantity = supplier_products.aggregate(
        avg=Avg("min_quantity")
    )["avg"] or 0

    products_by_supplier = (
        supplier_products
        .values("supplier_record__name", "supplier_record__slug")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    products_by_category = (
        supplier_products
        .values("category__name", "category__slug")
        .annotate(total=Count("id"))
        .order_by("-total")[:12]
    )

    recent_supplier_products = (
        supplier_products
        .select_related("category", "supplier_record")
        .order_by("-last_synced_at", "-created_at")[:10]
    )

    context = {
        "total_supplier_products": total_supplier_products,
        "active_supplier_products": active_supplier_products,
        "featured_supplier_products": featured_supplier_products,
        "average_price": average_price,
        "min_price": min_price,
        "max_price": max_price,
        "average_min_quantity": average_min_quantity,
        "products_by_supplier": products_by_supplier,
        "products_by_category": products_by_category,
        "recent_supplier_products": recent_supplier_products,
    }

    return render(
        request,
        "products/supplier_analytics.html",
        context,
    )

@staff_member_required
def supplier_stats_api(request):
    supplier_products = Product.objects.filter(
        supplier_record__isnull=False
    )

    data = {
        "total_supplier_products": supplier_products.count(),
        "active_supplier_products": supplier_products.filter(is_active=True).count(),
        "featured_supplier_products": supplier_products.filter(is_featured=True).count(),
        "kaeser_blair_products": supplier_products.filter(
            supplier_record__slug="kaeser-blair"
        ).count(),
    }

    return JsonResponse(data)


@staff_member_required
def supplier_categories_api(request):
    supplier_products = Product.objects.filter(
        supplier_record__isnull=False
    )

    rows = (
        supplier_products
        .values("category__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    data = {
        "labels": [
            row["category__name"] or "Uncategorized"
            for row in rows
        ],
        "values": [
            row["total"]
            for row in rows
        ],
    }

    return JsonResponse(data)


@staff_member_required
def supplier_pricing_api(request):
    supplier_products = Product.objects.filter(
        supplier_record__isnull=False
    ).exclude(
        starting_price__isnull=True
    )

    data = {
        "average_price": float(
            supplier_products.aggregate(avg=Avg("starting_price"))["avg"] or 0
        ),
        "minimum_price": float(
            supplier_products.aggregate(minimum=Min("starting_price"))["minimum"] or 0
        ),
        "maximum_price": float(
            supplier_products.aggregate(maximum=Max("starting_price"))["maximum"] or 0
        ),
    }

    return JsonResponse(data)

def quote_builder(request):
    if request.method == "POST":
        form = QuoteBuilderForm(request.POST)

        if form.is_valid():
            raw_items = request.POST.get("quote_items", "[]")

            try:
                items = json.loads(raw_items)
            except json.JSONDecodeError:
                items = []

            if not items:
                messages.error(request, "Please save at least one product before submitting a quote.")
                return redirect("products:quote_builder")

            quote = Quote.objects.create(
                customer_name=form.cleaned_data["customer_name"],
                company=form.cleaned_data.get("company", ""),
                email=form.cleaned_data["email"],
                phone=form.cleaned_data.get("phone", ""),
                project_name=form.cleaned_data.get("project_name", ""),
                deadline=form.cleaned_data.get("deadline"),
                notes=form.cleaned_data.get("notes", ""),
            )
            user = request.user if request.user.is_authenticated else None

            if user:
                CustomerLead.objects.create(
                    customer=user,
                    company=quote.company or "Individual Customer",
                    contact_name=quote.customer_name,
                    email=quote.email,
                    phone=quote.phone,
                    estimated_value=0,
                    status="new",
                    source="Quote Builder",
                    notes=f"Auto-created from Quote Builder request: {quote.project_name or 'Quote Request'}",
                )
            pdf_file = generate_quote_pdf(quote)

            product_lines = []

            for item in items:
                quote_item = QuoteItem.objects.create(
                    quote=quote,
                    product_name=item.get("name", ""),
                    category=item.get("category", ""),
                    product_url=item.get("url", ""),
                    quantity=item.get("quantity") or 1,
                    notes=item.get("notes", ""),
                )

                product_lines.append(
                                    f"""
                Product: {quote_item.product_name}
                Category: {quote_item.category}
                Quantity: {quote_item.quantity}
                Notes: {quote_item.notes}
                URL: {quote_item.product_url}
                """
                                )

                body = f"""
                New KaleidoBrands Quote Builder Request

                Customer
                --------------------
                Name: {quote.customer_name}
                Company: {quote.company}
                Email: {quote.email}
                Phone: {quote.phone}

                Project
                --------------------
                Project Name: {quote.project_name}
                Deadline: {quote.deadline}
                Notes:
                {quote.notes}

                Products
                --------------------
                {''.join(product_lines)}
                """

            email = EmailMessage(
                subject="New Quote Builder Request - KaleidoBrands",
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["sales@kaleidobrands.com"],
                reply_to=[quote.email],
            )

            if pdf_file:
                email.attach_file(quote.pdf_file.path)

            email.send(fail_silently=False)

            return redirect("products:quote_success")

    else:
        form = QuoteBuilderForm()

    recommended_products = (
        RecommendationEngine.customer_recommendations(request.user)
        if request.user.is_authenticated
        else Product.objects.filter(is_active=True, is_featured=True)[:8]
    )

    RecommendationEngine.log_recommendations(
    recommended_products,
    context="quote_builder",
    user=request.user,
)

    return render(
        request,
        "products/quote_builder.html",
        {
            "form": form,
            "recommended_products": recommended_products,
        },
    )

def quote_success(request):
    return render(request, "products/quote_success.html")


def quote_history(request):
    email = request.GET.get("email", "").strip()

    quotes = Quote.objects.none()

    if request.user.is_staff:
        quotes = Quote.objects.all().order_by("-created_at")
    elif email:
        quotes = Quote.objects.filter(email__iexact=email).order_by("-created_at")

    return render(
        request,
        "products/quote_history.html",
        {
            "quotes": quotes,
            "email": email,
        },
    )


def quote_detail(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)

    if not request.user.is_staff:
        email = request.GET.get("email", "").strip()
        if quote.email.lower() != email.lower():
            messages.error(request, "Please enter the email used for this quote.")
            return redirect("products:quote_history")

    return render(
        request,
        "products/quote_detail.html",
        {
            "quote": quote,
        },
    )

@staff_member_required
def recommendation_analytics(request):
    top_products = (
        RecommendationEvent.objects.values("product_name", "product_slug")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    context_counts = (
        RecommendationEvent.objects.values("context")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    recent_events = RecommendationEvent.objects.select_related("user")[:25]

    return render(
        request,
        "products/recommendation_analytics.html",
        {
            "top_products": top_products,
            "context_counts": context_counts,
            "recent_events": recent_events,
        },
    )

@staff_member_required
def supplier_inventory_dashboard(request):
    products = Product.objects.select_related(
        "supplier_record",
        "category",
    ).filter(
        supplier_record__isnull=False,
    )

    suppliers = Supplier.objects.filter(
        is_active=True,
    ).order_by("name")

    selected_supplier = request.GET.get("supplier", "").strip()
    selected_status = request.GET.get("status", "").strip()

    if selected_supplier:
        products = products.filter(
            supplier_record__slug=selected_supplier,
        )

    if selected_status:
        products = products.filter(
            inventory_status=selected_status,
        )

    totals = {
        "all": products.count(),
        "in_stock": products.filter(
            inventory_status="in_stock",
        ).count(),
        "low_stock": products.filter(
            inventory_status="low_stock",
        ).count(),
        "out_of_stock": products.filter(
            inventory_status="out_of_stock",
        ).count(),
        "discontinued": products.filter(
            inventory_status="discontinued",
        ).count(),
        "unknown": products.filter(
            inventory_status="unknown",
        ).count(),
    }

    recent_price_changes = (
        SupplierPriceHistory.objects
        .select_related("product", "supplier")
        .order_by("-recorded_at")[:15]
    )

    recent_inventory_changes = (
        SupplierInventoryHistory.objects
        .select_related("product", "supplier")
        .order_by("-recorded_at")[:15]
    )

    recent_sync_logs = (
        SupplierSyncLog.objects
        .select_related("supplier")
        .order_by("-started_at")[:10]
    )

    products = products.order_by(
        "inventory_status",
        "name",
    )[:100]

    return render(
        request,
        "products/supplier_inventory_dashboard.html",
        {
            "products": products,
            "suppliers": suppliers,
            "selected_supplier": selected_supplier,
            "selected_status": selected_status,
            "totals": totals,
            "recent_price_changes": recent_price_changes,
            "recent_inventory_changes": recent_inventory_changes,
            "recent_sync_logs": recent_sync_logs,
        },
    )


@staff_member_required
def purchase_order_list(request):
    purchase_orders = (
        SupplierPurchaseOrder.objects
        .select_related(
            "supplier",
            "customer_order",
            "created_by",
        )
        .prefetch_related("items")
        .order_by("-created_at")
    )

    selected_status = request.GET.get("status", "").strip()
    selected_supplier = request.GET.get("supplier", "").strip()

    if selected_status:
        purchase_orders = purchase_orders.filter(
            status=selected_status,
        )

    if selected_supplier:
        purchase_orders = purchase_orders.filter(
            supplier__slug=selected_supplier,
        )

    suppliers = (
        Supplier.objects
        .filter(is_active=True)
        .order_by("name")
    )

    return render(
        request,
        "products/purchase_order_list.html",
        {
            "purchase_orders": purchase_orders,
            "suppliers": suppliers,
            "status_choices": SupplierPurchaseOrder.STATUS_CHOICES,
            "selected_status": selected_status,
            "selected_supplier": selected_supplier,
        },
    )


@staff_member_required
def purchase_order_detail(request, po_id):
    purchase_order = get_object_or_404(
        SupplierPurchaseOrder.objects
        .select_related(
            "supplier",
            "customer_order",
            "created_by",
        )
        .prefetch_related(
            "items",
            "activities__created_by",
        ),
        id=po_id,
    )
    status_form = SupplierPurchaseOrderStatusForm(
        instance=purchase_order
    )

    return render(
        request,
        "products/purchase_order_detail.html",
        {
            "purchase_order": purchase_order,
            "status_form": status_form,
        },
    )


@staff_member_required
def generate_purchase_order_pdf_view(request, po_id):
    purchase_order = get_object_or_404(
        SupplierPurchaseOrder,
        id=po_id,
    )

    generate_purchase_order_pdf(purchase_order)

    messages.success(
        request,
        f"PDF generated for {purchase_order.po_number}.",
    )

    return redirect(
        "products:purchase_order_detail",
        po_id=purchase_order.id,
    )

@staff_member_required
def send_purchase_order(request, po_id):
    purchase_order = get_object_or_404(
        SupplierPurchaseOrder.objects.select_related(
            "supplier",
            "customer_order",
        ),
        id=po_id,
    )

    if request.method != "POST":
        return redirect(
            "products:purchase_order_detail",
            po_id=purchase_order.id,
        )

    success, result_message = deliver_purchase_order(
        purchase_order,
        user=request.user,
    )

    if success:
        messages.success(
            request,
            result_message,
        )
    else:
        messages.error(
            request,
            f"Purchase order was not sent: {result_message}",
        )

    return redirect(
        "products:purchase_order_detail",
        po_id=purchase_order.id,
    )

@staff_member_required
def update_purchase_order_status(request, po_id):
    purchase_order = get_object_or_404(
        SupplierPurchaseOrder,
        id=po_id,
    )

    if request.method != "POST":
        return redirect(
            "products:purchase_order_detail",
            po_id=purchase_order.id,
        )

    previous_tracking_number = (
        purchase_order.tracking_number
    )
    previous_tracking_url = (
        purchase_order.tracking_url
    )
    previous_supplier_reference = (
        purchase_order.supplier_reference
    )
    previous_notes = purchase_order.notes

    form = SupplierPurchaseOrderStatusForm(
        request.POST,
        instance=purchase_order,
    )

    if not form.is_valid():
        messages.error(
            request,
            "Purchase order could not be updated.",
        )

        return redirect(
            "products:purchase_order_detail",
            po_id=purchase_order.id,
        )

    updated_purchase_order = form.save(
        commit=False
    )

    new_status = updated_purchase_order.status

    # Restore the persisted status so the service can
    # validate the real transition.
    purchase_order.refresh_from_db()

    purchase_order.tracking_number = (
        updated_purchase_order.tracking_number
    )
    purchase_order.tracking_url = (
        updated_purchase_order.tracking_url
    )
    purchase_order.supplier_reference = (
        updated_purchase_order.supplier_reference
    )
    purchase_order.notes = updated_purchase_order.notes
    purchase_order.estimated_ship_date = (
        updated_purchase_order.estimated_ship_date
    )

    try:
        apply_purchase_order_status(
            purchase_order,
            new_status,
            user=request.user,
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

        return redirect(
            "products:purchase_order_detail",
            po_id=purchase_order.id,
        )

    purchase_order.save(
        update_fields=[
            "tracking_number",
            "tracking_url",
            "supplier_reference",
            "notes",
            "estimated_ship_date",
            "updated_at",
        ]
    )

    if (
        previous_tracking_number
        != purchase_order.tracking_number
        or previous_tracking_url
        != purchase_order.tracking_url
    ):
        log_purchase_order_activity(
            purchase_order,
            action="tracking_updated",
            message="Tracking information updated.",
            previous_value=previous_tracking_number,
            new_value=purchase_order.tracking_number,
            user=request.user,
        )

    if (
        previous_supplier_reference
        != purchase_order.supplier_reference
    ):
        log_purchase_order_activity(
            purchase_order,
            action="supplier_reference_updated",
            message="Supplier reference updated.",
            previous_value=previous_supplier_reference,
            new_value=purchase_order.supplier_reference,
            user=request.user,
        )

    if previous_notes != purchase_order.notes:
        log_purchase_order_activity(
            purchase_order,
            action="notes_updated",
            message="Purchase order notes updated.",
            previous_value=previous_notes,
            new_value=purchase_order.notes,
            user=request.user,
        )

    messages.success(
        request,
        (
            f"{purchase_order.po_number} was updated "
            "successfully."
        ),
    )

    return redirect(
        "products:purchase_order_detail",
        po_id=purchase_order.id,
    )


@staff_member_required
def supplier_operations_dashboard(request):
    now = timezone.now()

    open_statuses = [
        "draft",
        "ready",
        "sent",
        "confirmed",
        "in_production",
        "shipped",
    ]

    open_purchase_orders = (
        SupplierPurchaseOrder.objects
        .filter(status__in=open_statuses)
        .select_related(
            "supplier",
            "customer_order",
        )
        .prefetch_related("items")
        .order_by("created_at")
    )

    total_suppliers = Supplier.objects.filter(
        is_active=True
    ).count()

    total_open_pos = open_purchase_orders.count()

    total_open_po_cost = (
        sum(
            purchase_order.total_cost()
            for purchase_order in open_purchase_orders
        )
    )

    draft_pos = open_purchase_orders.filter(
        status="draft"
    ).count()

    sent_pos = open_purchase_orders.filter(
        status="sent"
    ).count()

    production_pos = open_purchase_orders.filter(
        status="in_production"
    ).count()

    shipped_pos = open_purchase_orders.filter(
        status="shipped"
    ).count()

    low_stock_products = Product.objects.filter(
        is_active=True,
        inventory_status="low_stock",
    ).count()

    out_of_stock_products = Product.objects.filter(
        is_active=True,
        inventory_status="out_of_stock",
    ).count()

    discontinued_products = Product.objects.filter(
        inventory_status="discontinued",
    ).count()

    stale_sync_cutoff = now - timedelta(hours=48)

    stale_suppliers = Supplier.objects.filter(
        is_active=True,
    ).filter(
        last_synced_at__lt=stale_sync_cutoff
    ).order_by("last_synced_at")

    never_synced_suppliers = Supplier.objects.filter(
        is_active=True,
        last_synced_at__isnull=True,
    ).order_by("name")

    aging_cutoff = now - timedelta(days=7)

    aging_purchase_orders = (
        open_purchase_orders
        .filter(created_at__lt=aging_cutoff)
        .order_by("created_at")[:20]
    )

    recent_sync_logs = (
        SupplierSyncLog.objects
        .select_related("supplier")
        .order_by("-started_at")[:10]
    )

    supplier_summary = (
        Supplier.objects
        .filter(is_active=True)
        .annotate(
            product_count=Count(
                "products",
                distinct=True,
            ),
            purchase_order_count=Count(
                "purchase_orders",
                distinct=True,
            ),
        )
        .order_by("name")
    )

    return render(
        request,
        "products/supplier_operations_dashboard.html",
        {
            "total_suppliers": total_suppliers,
            "total_open_pos": total_open_pos,
            "total_open_po_cost": total_open_po_cost,
            "draft_pos": draft_pos,
            "sent_pos": sent_pos,
            "production_pos": production_pos,
            "shipped_pos": shipped_pos,
            "low_stock_products": low_stock_products,
            "out_of_stock_products": out_of_stock_products,
            "discontinued_products": discontinued_products,
            "stale_suppliers": stale_suppliers,
            "never_synced_suppliers": never_synced_suppliers,
            "aging_purchase_orders": aging_purchase_orders,
            "recent_sync_logs": recent_sync_logs,
            "supplier_summary": supplier_summary,
            "open_purchase_orders": open_purchase_orders[:20],
        },
    )