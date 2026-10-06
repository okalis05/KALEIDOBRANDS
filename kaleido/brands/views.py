from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.core.mail import EmailMessage
from .models import ContactMessage, QuoteRequest
from products.models import Product


CATALOG_CATEGORIES = [
    {
        "title": "Apparel",
        "icon": "👕",
        "description": "Polos, t-shirts, hats, scrubs, uniforms, jackets, and team apparel.",
        "keywords": "apparel shirts polos hats scrubs uniforms tshirts",
        "links": [
            {"label": "Healthcare Scrubs", "url": "https://online.flippingbook.com/view/440891710/"},
            {"label": "Polo Shirts", "url": "https://online.flippingbook.com/view/440744366/"},
            {"label": "Hats", "url": "https://online.flippingbook.com/view/440842574/"},
        ],
    },
    {
        "title": "Drinkware",
        "icon": "🥤",
        "description": "Tumblers, mugs, bottles, insulated cups, and employee hydration gifts.",
        "keywords": "drinkware tumblers mugs bottles cups",
        "links": [],
    },
    {
        "title": "Corporate Gifts",
        "icon": "🎁",
        "description": "Elegant appreciation gifts for clients, teams, milestones, and holidays.",
        "keywords": "corporate gifts employee appreciation client gifts",
        "links": [],
    },
    {
        "title": "Events",
        "icon": "🎪",
        "description": "Trade show giveaways, booth items, bags, badges, pens, and event essentials.",
        "keywords": "events trade shows giveaways booth bags pens",
        "links": [],
    },
    {
        "title": "Office",
        "icon": "🖊️",
        "description": "Notebooks, pens, desk items, folders, calendars, and workplace essentials.",
        "keywords": "office pens notebooks desk folders",
        "links": [],
    },
    {
        "title": "Tech",
        "icon": "🔌",
        "description": "Chargers, cables, speakers, tech accessories, and modern branded gifts.",
        "keywords": "tech chargers speakers cables accessories",
        "links": [],
    },
]


FEATURED_PRODUCTS = [
    {"title": "Healthcare Scrubs", "icon": "🩺", "description": "Practical branded apparel for clinics, healthcare teams, and wellness events."},
    {"title": "Custom Polos", "icon": "👔", "description": "Professional apparel for teams, offices, sales staff, and conferences."},
    {"title": "Branded Hats", "icon": "🧢", "description": "High-visibility headwear for crews, events, teams, and giveaways."},
    {"title": "Tumblers", "icon": "🥤", "description": "Useful drinkware gifts with strong everyday brand exposure."},
    {"title": "Tote Bags", "icon": "🛍️", "description": "Event-ready bags for trade shows, onboarding, and conferences."},
    {"title": "Pens", "icon": "🖊️", "description": "Affordable, practical promotional items for high-volume campaigns."},
    {"title": "Corporate Gift Sets", "icon": "🎁", "description": "Premium kits for appreciation, onboarding, and client retention."},
    {"title": "Tech Accessories", "icon": "🔌", "description": "Modern branded items people use at work, travel, and events."},
]


HOME_INDUSTRIES = [
    {
        "name": "Healthcare",
        "icon": "bi-hospital",
        "description": "Uniforms, wellness campaigns and employee essentials",
        "product_ids": [1056],
        "category_slugs": ["healthcare"],
    },
    {
        "name": "Corporate",
        "icon": "bi-buildings",
        "description": "Employee kits, executive gifts and client appreciation",
        "product_ids": [2023, 280, 148],
        "category_slugs": ["corporate-gifts", "food-candy", "office"],
    },
    {
        "name": "Education",
        "icon": "bi-mortarboard",
        "description": "Campus events, student programs and school spirit",
        "product_ids": [148],
        "category_slugs": ["office", "apparel", "bags"],
    },
    {
        "name": "Hospitality",
        "icon": "bi-building",
        "description": "Guest experiences, uniforms and branded amenities",
        "product_ids": [585, 74],
        "category_slugs": ["drinkware", "apparel", "bags"],
    },
    {
        "name": "Events",
        "icon": "bi-calendar-event",
        "description": "Trade shows, conferences and memorable giveaways",
        "product_ids": [311, 599],
        "category_slugs": ["trade-shows", "bags"],
    },
    {
        "name": "Teams",
        "icon": "bi-trophy",
        "description": "Polos, hats, shirts, spirit wear and recognition",
        "product_ids": [13083],
        "category_slugs": ["apparel"],
    },
    {
        "name": "Nonprofits",
        "icon": "bi-people",
        "description": "Fundraisers, volunteer programs and community events",
        "product_ids": [599, 148],
        "category_slugs": ["bags", "office", "drinkware"],
    },
    {
        "name": "Construction",
        "icon": "bi-tools",
        "description": "Worksite apparel, safety campaigns and durable giveaways",
        "product_ids": [13082, 13083],
        "category_slugs": ["apparel"],
    },
]


def build_home_industry_cards():
    """
    Build the Brands homepage industry cards using real active
    marketplace products.

    Read-only: no Product records are modified.
    """

    cards = []

    for config in HOME_INDUSTRIES:

        products = (
            Product.objects
            .filter(
                is_active=True,
                category__slug__in=config["category_slugs"],
            )
            .filter(
                image__isnull=False
            )
            .select_related(
                "category",
                "catalog",
            )
            .distinct()
        )

        # Also allow externally hosted supplier imagery.
        external_products = (
            Product.objects
            .filter(
                is_active=True,
                category__slug__in=config["category_slugs"],
            )
            .exclude(external_image_url="")
            .select_related(
                "category",
                "catalog",
            )
            .distinct()
        )

        # Prefer our deliberately selected representative product.
        representative = None

        for product_id in config["product_ids"]:
            representative = (
                Product.objects
                .filter(
                    pk=product_id,
                    is_active=True,
                )
                .filter(
                    category__slug__in=config["category_slugs"],
                )
                .first()
            )

            if representative and (
                representative.image
                or representative.external_image_url
            ):
                break

            representative = None

        # Safe database fallback.
        if representative is None:
            representative = products.first()

        if representative is None:
            representative = external_products.first()

        cards.append(
            {
                **config,
                "product": representative,
                "product_count": (
                    Product.objects
                    .filter(
                        is_active=True,
                        category__slug__in=config["category_slugs"],
                    )
                    .distinct()
                    .count()
                ),
            }
        )

    return cards


def send_business_email(subject, body, reply_to_email=None, receiver=None):
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[receiver or settings.CONTACT_RECEIVER_EMAIL],
    )

    if reply_to_email:
        email.reply_to = [reply_to_email]

    email.send(fail_silently=False)


def home(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type", "contact")

        if form_type == "contact":
            contact = ContactMessage.objects.create(
                name=request.POST.get("name", "").strip(),
                email=request.POST.get("email", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                company=request.POST.get("company", "").strip(),
                subject=request.POST.get("subject", "").strip(),
                message=request.POST.get("message", "").strip(),
            )

            body = f"""
New KaleidoBrands Contact Message

Name: {contact.name}
Email: {contact.email}
Phone: {contact.phone}
Company: {contact.company}
Subject: {contact.subject}

Message:
{contact.message}
"""

            send_business_email(
                subject="New Website Contact - KaleidoBrands",
                body=body,
                reply_to_email=contact.email,
                receiver="helpdesk@kaleidobrands.com",
            )

            messages.success(request, "Thank you. Your message has been sent.")
            return redirect("brands:home")

        if form_type == "quote":
            saved_products = request.POST.get("saved_products", "").strip()
            message = request.POST.get("message", "").strip()

            if saved_products:
                message = f"{message}\n\nSaved Product Ideas:\n{saved_products}"

            quote = QuoteRequest.objects.create(
                name=request.POST.get("name", "").strip(),
                email=request.POST.get("email", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                company=request.POST.get("company", "").strip(),
                product_interest=request.POST.get("product_interest", "").strip(),
                quantity=request.POST.get("quantity") or None,
                budget=request.POST.get("budget", "").strip(),
                deadline=request.POST.get("deadline") or None,
                colors=request.POST.get("colors", "").strip(),
                decoration=request.POST.get("decoration", "").strip(),
                logo=request.FILES.get("logo"),
                artwork=request.FILES.get("artwork"),
                message=message,
            )

            body = f"""
New KaleidoBrands Quote Request

Name: {quote.name}
Email: {quote.email}
Phone: {quote.phone}
Company: {quote.company}
Product Interest: {quote.product_interest}
Quantity: {quote.quantity}
Budget: {quote.budget}
Deadline: {quote.deadline}
Colors: {quote.colors}
Decoration: {quote.decoration}
Logo Uploaded: {"Yes" if quote.logo else "No"}
Artwork Uploaded: {"Yes" if quote.artwork else "No"}

Project Details:
{quote.message}
"""

            send_business_email(
                subject="New Quote Request - KaleidoBrands",
                body=body,
                reply_to_email=quote.email,
                receiver="sales@kaleidobrands.com",
            )

            messages.success(request, "Thank you. Your quote request has been sent.")
            return redirect("brands:home")





    featured_marketplace_products = (
        Product.objects
        .filter(
            is_active=True,
            is_featured=True,
        )
        .select_related(
            "category",
            "supplier_record",
        )
        .prefetch_related(
            "gallery_images",
        )
        .order_by("-updated_at")[:8]
    )

    newest_marketplace_products = (
        Product.objects
        .filter(
            is_active=True,
        )
        .select_related(
            "category",
            "supplier_record",
        )
        .prefetch_related(
            "gallery_images",
        )
        .order_by("-created_at")[:8]
)






    return render(
        request,
        "brands/home.html",
        {
            "catalog_categories": CATALOG_CATEGORIES,
            "featured_products": FEATURED_PRODUCTS,
            "featured_marketplace_products": featured_marketplace_products,
            "newest_marketplace_products": newest_marketplace_products,
            "home_industry_cards": build_home_industry_cards(),
            
        },
    )