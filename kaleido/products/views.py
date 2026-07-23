from django.conf import settings
import json
from django.shortcuts import get_object_or_404, render , redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib import messages 
from django.core.mail import send_mail, EmailMessage
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Min, Max, Q, Sum
from django.http import QueryDict
from .models import (
    Category,
    HomepageProductRail,
    ImprintMethod,
    Industry,
    Product,
    ProductCollection,
    Quote,
    QuoteItem,
    RecommendationEvent,
    Supplier,
    SupplierInventoryHistory,
    SupplierPriceHistory,
    SupplierPurchaseOrder,
    SupplierSyncLog,
)
from django.views.decorators.http import require_POST
import csv
import tempfile
from datetime import timedelta
from products.services.quote_pdf import generate_quote_pdf
from django.core.files.storage import FileSystemStorage
from products.services.csv_importer import ProductCSVImporter
from .forms import (
    ProductSearchForm,
    QuoteBuilderForm,
)
from customers.models import CustomerLead
from products.services.recommendations import RecommendationEngine
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




# ============================================================
# MARKETPLACE QUERY HELPERS
# ============================================================


def _active_products():
    return (
        Product.objects
        .filter(is_active=True)
        .select_related(
            "category",
            "supplier_record",
            "catalog",
        )
        .prefetch_related(
            "industry_groups",
            "collections",
            "imprint_methods",
        )
    )


def _active_window_filter(queryset, now=None):
    """
    Restrict scheduled marketplace content to records whose active
    date window includes the current time.

    A null start date means the object is available immediately.
    A null end date means the object does not automatically expire.
    """
    now = now or timezone.now()

    return queryset.filter(
        Q(starts_at__isnull=True)
        | Q(starts_at__lte=now),
    ).filter(
        Q(ends_at__isnull=True)
        | Q(ends_at__gte=now),
    )


def _products_for_homepage_rail(rail):
    """
    Resolve the products displayed by one HomepageProductRail.

    Supported rail types include manual, category, industry,
    collection, featured, newest, and supplier-backed rails.
    Unknown rail types safely return no products.
    """
    products = _active_products()

    if rail.rail_type == "manual":
        products = rail.products.filter(
            is_active=True,
        ).select_related(
            "category",
            "supplier_record",
            "catalog",
        ).prefetch_related(
            "gallery_images",
            "variants",
            "specifications",
            "industry_groups",
            "collections",
            "imprint_methods",
            "supplier_listings",
        )

    elif rail.rail_type == "category":
        if not rail.category_id:
            return Product.objects.none()

        category_ids = [
            rail.category_id,
            *rail.category.children.filter(
                is_active=True,
            ).values_list(
                "id",
                flat=True,
            ),
        ]

        products = products.filter(
            category_id__in=category_ids,
        )

    elif rail.rail_type == "industry":
        if not rail.industry_id:
            return Product.objects.none()

        products = products.filter(
            industry_groups=rail.industry,
        )

    elif rail.rail_type == "collection":
        if not rail.collection_id:
            return Product.objects.none()

        products = products.filter(
            collections=rail.collection,
        )

    elif rail.rail_type == "featured":
        products = products.filter(
            is_featured=True,
        )

    elif rail.rail_type == "newest":
        products = products.order_by(
            "-created_at",
        )

    elif rail.rail_type == "supplier":
        products = products.filter(
            supplier_record__isnull=False,
        ).order_by(
            "-supplier_last_synced_at",
            "-created_at",
        )

    else:
        return Product.objects.none()

    return products.distinct()[:rail.max_products]


def _safe_decimal_filter(queryset, field_name, raw_value):
    """
    Apply a decimal-compatible filter without allowing malformed
    query-string values to trigger a database validation error.
    """
    if not raw_value:
        return queryset

    try:
        numeric_value = float(raw_value)
    except (TypeError, ValueError):
        return queryset

    if numeric_value < 0:
        return queryset

    return queryset.filter(
        **{
            field_name: numeric_value,
        }
    )


def _safe_integer_filter(queryset, field_name, raw_value):
    """
    Apply a nonnegative integer filter from a query-string value.
    """
    if not raw_value:
        return queryset

    try:
        numeric_value = int(raw_value)
    except (TypeError, ValueError):
        return queryset

    if numeric_value < 0:
        return queryset

    return queryset.filter(
        **{
            field_name: numeric_value,
        }
    )
def _active_marketplace_collections(now=None):
    now = now or timezone.now()

    return (
        ProductCollection.objects
        .filter(
            is_active=True,
        )
        .filter(
            Q(starts_at__isnull=True)
            | Q(starts_at__lte=now),
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gte=now),
        )
        .order_by(
            "order",
            "name",
        )
    )


def _normalize_legacy_search_parameters(query_dict):
    """
    Preserve compatibility with earlier single-value marketplace URLs.

    Previous URLs used category, industry, collection, and imprint.
    Package 1.3A uses plural multi-value parameters.
    """
    normalized = query_dict.copy()

    legacy_parameters = {
        "category": "categories",
        "industry": "industries",
        "collection": "collections",
        "imprint": "imprints",
        "supplier": "suppliers",
    }

    for old_name, new_name in legacy_parameters.items():
        if normalized.getlist(new_name):
            continue

        old_values = normalized.getlist(old_name)

        if old_values:
            normalized.setlist(
                new_name,
                old_values,
            )

    return normalized


def _query_string_without(request, *excluded_keys):
    query = request.GET.copy()

    for key in (
        *excluded_keys,
        "page",
    ):
        if key in query:
            del query[key]

    return query.urlencode()


def _build_active_filter_chips(form, request):
    chips = []

    model_filter_fields = (
        (
            "categories",
            "Category",
        ),
        (
            "industries",
            "Industry",
        ),
        (
            "collections",
            "Collection",
        ),
        (
            "imprints",
            "Imprint",
        ),
        (
            "suppliers",
            "Supplier",
        ),
    )

    for field_name, label in model_filter_fields:
        selected_objects = form.cleaned_data.get(
            field_name,
        )

        if not selected_objects:
            continue

        for selected_object in selected_objects:
            query = request.GET.copy()

            remaining_values = [
                value
                for value in query.getlist(field_name)
                if value != str(selected_object.pk)
            ]

            query.setlist(
                field_name,
                remaining_values,
            )

            query.pop("page", None)

            chips.append(
                {
                    "label": label,
                    "value": str(selected_object),
                    "url": (
                        f"{request.path}?{query.urlencode()}"
                        if query
                        else request.path
                    ),
                },
            )

    simple_multi_fields = (
        (
            "colors",
            "Color",
        ),
        (
            "materials",
            "Material",
        ),
        (
            "inventory",
            "Availability",
        ),
    )

    for field_name, label in simple_multi_fields:
        selected_values = form.cleaned_data.get(
            field_name,
        ) or []

        for selected_value in selected_values:
            query = request.GET.copy()

            remaining_values = [
                value
                for value in query.getlist(field_name)
                if value != selected_value
            ]

            query.setlist(
                field_name,
                remaining_values,
            )

            query.pop("page", None)

            display_value = selected_value.replace(
                "_",
                " ",
            ).title()

            chips.append(
                {
                    "label": label,
                    "value": display_value,
                    "url": (
                        f"{request.path}?{query.urlencode()}"
                        if query
                        else request.path
                    ),
                },
            )

    single_fields = (
        (
            "q",
            "Search",
        ),
        (
            "max_price",
            "Maximum price",
        ),
        (
            "min_quantity",
            "Minimum order",
        ),
    )

    for field_name, label in single_fields:
        value = form.cleaned_data.get(
            field_name,
        )

        if value in (
            None,
            "",
        ):
            continue

        query = request.GET.copy()
        query.pop(
            field_name,
            None,
        )
        query.pop(
            "page",
            None,
        )

        chips.append(
            {
                "label": label,
                "value": str(value),
                "url": (
                    f"{request.path}?{query.urlencode()}"
                    if query
                    else request.path
                ),
            },
        )

    return chips

# ============================================================
# MARKETPLACE HOME
# ============================================================


def product_home(request):
    now = timezone.now()

    categories = (
        Category.objects
        .filter(
            is_active=True,
            parent__isnull=True,
        )
        .prefetch_related(
            "children",
        )
        .order_by(
            "order",
            "name",
        )
    )

    featured_products = (
        _active_products()
        .filter(
            is_featured=True,
        )
        .order_by(
            "-created_at",
        )[:12]
    )

    newest_products = (
        _active_products()
        .order_by(
            "-created_at",
        )[:12]
    )

    industries = (
        Industry.objects
        .filter(
            is_active=True,
            is_featured=True,
        )
        .order_by(
            "order",
            "name",
        )[:12]
    )

    collections = _active_window_filter(
        ProductCollection.objects.filter(
            is_active=True,
            is_featured=True,
        ),
        now=now,
    ).order_by(
        "order",
        "name",
    )[:12]

    homepage_rails = (
        _active_window_filter(
            HomepageProductRail.objects.filter(
                is_active=True,
            ),
            now=now,
        )
        .select_related(
            "category",
            "industry",
            "collection",
        )
        .prefetch_related(
            "products",
        )
        .order_by(
            "order",
            "title",
        )
    )

    resolved_rails = []

    for rail in homepage_rails:
        rail.resolved_products = _products_for_homepage_rail(
            rail,
        )

        if rail.resolved_products:
            resolved_rails.append(rail)

    context = {
        "categories": categories,
        "featured": featured_products,
        "featured_products": featured_products,
        "newest_products": newest_products,
        "industries": industries,
        "collections": collections,
        "homepage_rails": resolved_rails,
    }

    return render(
        request,
        "products/home.html",
        context,
    )


# ============================================================
# CATEGORY DETAIL
# ============================================================


def category_detail(request, slug):
    category = get_object_or_404(
        Category.objects.prefetch_related(
            "children",
        ),
        slug=slug,
        is_active=True,
    )

    child_categories = (
        category.children
        .filter(
            is_active=True,
        )
        .order_by(
            "order",
            "name",
        )
    )

    category_ids = [
        category.id,
        *child_categories.values_list(
            "id",
            flat=True,
        ),
    ]

    products = (
        _active_products()
        .filter(
            category_id__in=category_ids,
        )
        .distinct()
        .order_by(
            "-is_featured",
            "name",
        )
    )

    query = request.GET.get(
        "q",
        "",
    ).strip()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(colors__icontains=query)
            | Q(material__icontains=query)
            | Q(industry_groups__name__icontains=query)
            | Q(imprint_methods__name__icontains=query)
        ).distinct()

    paginator = Paginator(
        products,
        24,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    context = {
        "category": category,
        "child_categories": child_categories,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "query": query,
    }

    return render(
        request,
        "products/category.html",
        context,
    )


# ============================================================
# INDUSTRY DETAIL
# ============================================================


def industry_detail(request, slug):
    industry = get_object_or_404(
        Industry,
        slug=slug,
        is_active=True,
    )

    products = (
        _active_products()
        .filter(
            industry_groups=industry,
        )
        .distinct()
        .order_by(
            "-is_featured",
            "name",
        )
    )

    query = request.GET.get(
        "q",
        "",
    ).strip()

    category_slug = request.GET.get(
        "category",
        "",
    ).strip()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(colors__icontains=query)
            | Q(material__icontains=query)
            | Q(imprint_methods__name__icontains=query)
        ).distinct()

    if category_slug:
        products = products.filter(
            category__slug=category_slug,
        )

    categories = (
        Category.objects
        .filter(
            is_active=True,
            products__industry_groups=industry,
            products__is_active=True,
        )
        .distinct()
        .order_by(
            "order",
            "name",
        )
    )

    paginator = Paginator(
        products,
        24,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    context = {
        "industry": industry,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "categories": categories,
        "query": query,
        "category_slug": category_slug,
    }

    return render(
        request,
        "products/industry.html",
        context,
    )


# ============================================================
# COLLECTION DETAIL
# ============================================================


def collection_detail(request, slug):
    now = timezone.now()

    collection = get_object_or_404(
        ProductCollection.objects.filter(
            is_active=True,
        ).filter(
            Q(starts_at__isnull=True)
            | Q(starts_at__lte=now),
        ).filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gte=now),
        ),
        slug=slug,
    )

    products = (
        _active_products()
        .filter(
            collections=collection,
        )
        .distinct()
        .order_by(
            "-is_featured",
            "name",
        )
    )

    query = request.GET.get(
        "q",
        "",
    ).strip()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(colors__icontains=query)
            | Q(material__icontains=query)
            | Q(industry_groups__name__icontains=query)
            | Q(imprint_methods__name__icontains=query)
        ).distinct()

    paginator = Paginator(
        products,
        24,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    context = {
        "collection": collection,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "query": query,
    }

    return render(
        request,
        "products/collection.html",
        context,
    )


# ============================================================
# PRODUCT DETAIL
# ============================================================


def product_detail(request, slug):
    product = get_object_or_404(
        _active_products(),
        slug=slug,
    )

    active_variants = (
        product.variants
        .filter(
            is_active=True,
        )
        .order_by(
            "-is_default",
            "order",
            "name",
        )
    )

    specifications = (
        product.specifications
        .all()
        .order_by(
            "-is_highlighted",
            "order",
            "name",
        )
    )

    supplier_listings = (
        product.supplier_listings
        .filter(
            is_active=True,
        )
        .select_related(
            "supplier",
            "catalog",
        )
        .order_by(
            "-is_preferred",
            "unit_cost",
            "supplier__name",
        )
    )

    related_products = _active_products().exclude(
        id=product.id,
    )

    if product.category_id:
        related_products = related_products.filter(
            category=product.category,
        )
    elif product.industry_groups.exists():
        related_products = related_products.filter(
            industry_groups__in=product.industry_groups.all(),
        )
    else:
        related_products = related_products.none()

    related_products = (
        related_products
        .distinct()
        .order_by(
            "-is_featured",
            "name",
        )[:8]
    )

    recommendations = RecommendationEngine.recommendations(
        product,
    )

    RecommendationEngine.log_recommendations(
        recommendations,
        context="product_detail",
        user=request.user,
    )

    context = {
        "product": product,
        "active_variants": active_variants,
        "variants": active_variants,
        "specifications": specifications,
        "supplier_listings": supplier_listings,
        "related_products": related_products,
        "recommendations": recommendations,
    }

    return render(
        request,
        "products/detail.html",
        context,
    )


# ============================================================
# MARKETPLACE SEARCH
# ============================================================


def product_search(request):
    now = timezone.now()


    compare_ids = _get_compare_ids(request)
    active_collections = _active_marketplace_collections(
        now=now,
    )

    normalized_query = _normalize_legacy_search_parameters(
        request.GET,
    )

    form = ProductSearchForm(
        normalized_query or None,
        active_collections=active_collections,
    )

    products = _active_products()

    sort = "featured"

    if form.is_valid():
        query = form.cleaned_data.get(
            "q",
            "",
        ).strip()

        categories = form.cleaned_data.get(
            "categories",
        )

        industries = form.cleaned_data.get(
            "industries",
        )

        collections = form.cleaned_data.get(
            "collections",
        )

        imprints = form.cleaned_data.get(
            "imprints",
        )

        suppliers = form.cleaned_data.get(
            "suppliers",
        )

        colors = form.cleaned_data.get(
            "colors",
        ) or []

        materials = form.cleaned_data.get(
            "materials",
        ) or []

        inventory_statuses = form.cleaned_data.get(
            "inventory",
        ) or []

        max_price = form.cleaned_data.get(
            "max_price",
        )

        min_quantity = form.cleaned_data.get(
            "min_quantity",
        )

        sort = (
            form.cleaned_data.get(
                "sort",
            )
            or "featured"
        )
        

        if query:
            products = products.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(supplier_sku__icontains=query)
                | Q(description__icontains=query)
                | Q(short_description__icontains=query)
                | Q(industries__icontains=query)
                | Q(colors__icontains=query)
                | Q(material__icontains=query)
                | Q(decoration_methods__icontains=query)
                | Q(category__name__icontains=query)
                | Q(industry_groups__name__icontains=query)
                | Q(collections__name__icontains=query)
                | Q(imprint_methods__name__icontains=query)
                | Q(specifications__name__icontains=query)
                | Q(specifications__value__icontains=query)
            )

        if categories:
            products = products.filter(
                category__in=categories,
            )

        if industries:
            products = products.filter(
                industry_groups__in=industries,
            )

        if collections:
            products = products.filter(
                collections__in=collections,
            )

        if imprints:
            products = products.filter(
                imprint_methods__in=imprints,
            )

        if suppliers:
            products = products.filter(
                supplier_record__in=suppliers,
            )

        if colors:
            color_query = Q()

            for color in colors:
                color_query |= Q(
                    colors__icontains=color,
                )

            products = products.filter(
                color_query,
            )

        if materials:
            material_query = Q()

            for material in materials:
                material_query |= Q(
                    material__iexact=material,
                )

            products = products.filter(
                material_query,
            )

        if inventory_statuses:
            products = products.filter(
                inventory_status__in=inventory_statuses,
            )

        if max_price is not None:
            products = products.filter(
                starting_price__lte=max_price,
            )

        if min_quantity is not None:
            products = products.filter(
                min_quantity__lte=min_quantity,
            )

    sort_options = {
        "featured": (
            "-is_featured",
            "name",
        ),
        "newest": (
            "-created_at",
            "name",
        ),
        "price-low": (
            "starting_price",
            "name",
        ),
        "price-high": (
            "-starting_price",
            "name",
        ),
        "name": (
            "name",
        ),
    }
    
    products = (
        products
        .order_by(
            *sort_options.get(
                sort,
                sort_options["featured"],
            )
        )
        .distinct()
    )

    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    total_results = paginator.count
    result_start = 0
    result_end = 0

    if total_results:
        result_start = page_obj.start_index()
        result_end = page_obj.end_index()


    # Build active filter chips first.
    active_filter_chips = []

    if form.is_valid():
        cleaned_data = form.cleaned_data

        if cleaned_data.get("q"):
            active_filter_chips.append(
                {
                    "label": "Search",
                    "value": cleaned_data["q"],
                    "url": _query_string_without(request, "q"),
                }
            )

        for category in cleaned_data.get("categories", []):
            active_filter_chips.append(
                {
                    "label": "Category",
                    "value": category.name,
                    "url": _query_string_without(
                        request,
                        "categories",
                    ),
                }
            )

        for industry in cleaned_data.get("industries", []):
            active_filter_chips.append(
                {
                    "label": "Industry",
                    "value": industry.name,
                    "url": _query_string_without(
                        request,
                        "industries",
                    ),
                }
            )


    # Calculate this only after active_filter_chips exists.
    active_filter_count = len(active_filter_chips)



    context = {
        "form": form,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "result_count": total_results,
        "total_results": total_results,
        "result_start": result_start,
        "result_end": result_end,
        "active_filter_chips": active_filter_chips,
        "active_filter_count": active_filter_count,
        "pagination_query": _query_string_without(
            request,
            "page",
        ),
        "sort": sort,
        "compare_ids": compare_ids,
    }

    return render(
        request,
        "products/search.html",
        context,
    )

# ============================================================
# LIVE SEARCH API
# ============================================================


def live_search(request):
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse(
            {
                "results": [],
                "count": 0,
            }
        )

    products = (
        _active_products()
        .filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(sku__icontains=query)
            | Q(category__name__icontains=query)
            | Q(supplier_record__name__icontains=query)
        )
        
        .distinct()[:8]
    )

    results = []

    for product in products:
        image_url = ""

        if product.image:
            try:
                image_url = product.image.url
            except ValueError:
                image_url = ""
        elif product.external_image_url:
            image_url = product.external_image_url

        if product.starting_price is not None:
            price = f"${product.starting_price:.2f}"
        else:
            price = "Request quote"

        inventory_label = (
            product.get_inventory_status_display()
            if product.inventory_status
            else ""
        )

        results.append(
            {
                "name": product.name,
                "url": product.get_absolute_url(),
                "image": image_url,
                "category": (
                    product.category.name
                    if product.category
                    else "Promotional Product"
                ),
                "supplier": (
                    product.supplier_record.name
                    if product.supplier_record
                    else ""
                ),
                "price": price,
                "minimum_quantity": product.min_quantity,
                "inventory_status": product.inventory_status or "",
                "inventory_label": inventory_label,
            }
        )

    return JsonResponse(
        {
            "results": results,
            "count": len(results),
        }
    )


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

COMPARE_SESSION_KEY = "product_compare_ids"
MAX_COMPARE_PRODUCTS = 4


def _get_compare_ids(request):
    raw_ids = request.session.get(COMPARE_SESSION_KEY, [])

    compare_ids = []

    for value in raw_ids:
        try:
            product_id = int(value)
        except (TypeError, ValueError):
            continue

        if product_id not in compare_ids:
            compare_ids.append(product_id)

    compare_ids = compare_ids[:MAX_COMPARE_PRODUCTS]

    if compare_ids != raw_ids:
        request.session[COMPARE_SESSION_KEY] = compare_ids
        request.session.modified = True

    return compare_ids


def _compare_response(request, *, message="", status=200):
    compare_ids = _get_compare_ids(request)

    return JsonResponse(
        {
            "success": status < 400,
            "message": message,
            "compare_ids": compare_ids,
            "compare_count": len(compare_ids),
            "maximum": MAX_COMPARE_PRODUCTS,
        },
        status=status,
    )

@require_POST
def compare_add(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(is_active=True),
        pk=product_id,
    )

    compare_ids = _get_compare_ids(request)

    if product.pk in compare_ids:
        return _compare_response(
            request,
            message=f"{product.name} is already in your comparison.",
        )

    if len(compare_ids) >= MAX_COMPARE_PRODUCTS:
        return _compare_response(
            request,
            message=(
                f"You may compare up to "
                f"{MAX_COMPARE_PRODUCTS} products at a time."
            ),
            status=400,
        )

    compare_ids.append(product.pk)

    request.session[COMPARE_SESSION_KEY] = compare_ids
    request.session.modified = True

    return _compare_response(
        request,
        message=f"{product.name} was added to comparison.",
    )


@require_POST
def compare_remove(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    compare_ids = _get_compare_ids(request)

    if product.pk in compare_ids:
        compare_ids.remove(product.pk)

        request.session[COMPARE_SESSION_KEY] = compare_ids
        request.session.modified = True

        message = f"{product.name} was removed from comparison."
    else:
        message = f"{product.name} was not in your comparison."

    return _compare_response(
        request,
        message=message,
    )


@require_POST
def compare_clear(request):
    request.session.pop(COMPARE_SESSION_KEY, None)
    request.session.modified = True

    return JsonResponse(
        {
            "success": True,
            "message": "The comparison list was cleared.",
            "compare_ids": [],
            "compare_count": 0,
            "maximum": MAX_COMPARE_PRODUCTS,
        }
    )

def product_compare(request):
    compare_ids = _get_compare_ids(request)

    products_by_id = {
        product.pk: product
        for product in (
            _active_products()
            .filter(pk__in=compare_ids)
        )
    }

    products = [
        products_by_id[product_id]
        for product_id in compare_ids
        if product_id in products_by_id
    ]

    valid_ids = [product.pk for product in products]

    if valid_ids != compare_ids:
        request.session[COMPARE_SESSION_KEY] = valid_ids
        request.session.modified = True

    return render(
        request,
        "products/compare.html",
        {
            "products": products,
            "compare_ids": valid_ids,
            "compare_count": len(valid_ids),
            "maximum_compare_products": MAX_COMPARE_PRODUCTS,
        },
    )