from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse

from .models import Category, Product


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

    return render(
        request,
        "products/detail.html",
        {
            "product": product,
            "related_products": related_products,
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