from datetime import timedelta
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from brands.models import ContactMessage, QuoteRequest


@staff_member_required
def dashboard_home(request):
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    next_30_days = today + timedelta(days=30)

    contacts = ContactMessage.objects.all()[:8]
    quotes = QuoteRequest.objects.all()[:8]

    recent_contacts = ContactMessage.objects.filter(created_at__date__gte=last_7_days).count()
    recent_quotes = QuoteRequest.objects.filter(created_at__date__gte=last_7_days).count()

    total_contacts = ContactMessage.objects.count()
    total_quotes = QuoteRequest.objects.count()

    upcoming_deadlines = QuoteRequest.objects.filter(
        deadline__gte=today,
        deadline__lte=next_30_days
    ).order_by("deadline")[:8]

    hot_prospects = QuoteRequest.objects.filter(
        quantity__gte=100
    ).order_by("-created_at")[:6]

    quotes_with_files = QuoteRequest.objects.filter(
        logo__isnull=False
    ).exclude(logo="")[:6]

    status_counts = QuoteRequest.objects.values("status").annotate(total=Count("id"))
    pipeline = {
        "new": 0,
        "reviewing": 0,
        "quoted": 0,
        "ordered": 0,
        "shipped": 0,
    }

    for item in status_counts:
        pipeline[item["status"]] = item["total"]

    quote_trend = (
        QuoteRequest.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    chart_labels = []
    chart_values = []

    for item in quote_trend:
        chart_labels.append(item["day"].strftime("%b %d"))
        chart_values.append(item["total"])

    context = {
        "contact_count": total_contacts,
        "quote_count": total_quotes,
        "recent_contacts": recent_contacts,
        "recent_quotes": recent_quotes,
        "latest_contacts": contacts,
        "latest_quotes": quotes,
        "upcoming_deadlines": upcoming_deadlines,
        "hot_prospects": hot_prospects,
        "quotes_with_files": quotes_with_files,
        "pipeline": pipeline,
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
    }

    return render(request, "dashboard/home.html", context)