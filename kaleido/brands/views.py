from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import render, redirect

from .models import ContactMessage, QuoteRequest


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


def send_business_email(subject, body, reply_to_email=None, receiver=None):
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[receiver or settings.CONTACT_RECEIVER_EMAIL],
        fail_silently=False,
        reply_to=[reply_to_email] if reply_to_email else None,
    )


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

    return render(
        request,
        "brands/home.html",
        {
            "catalog_categories": CATALOG_CATEGORIES,
            "featured_products": FEATURED_PRODUCTS,
        },
    )