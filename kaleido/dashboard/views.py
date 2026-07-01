from datetime import timedelta
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from brands.models import ContactMessage, QuoteRequest
from .serializers import (
    ContactMessageSerializer,
    QuoteRequestSerializer,
    QuoteStatusUpdateSerializer,
)


def get_dashboard_context():
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    month_start = today.replace(day=1)
    next_30_days = today + timedelta(days=30)

    total_contacts = ContactMessage.objects.count()
    total_quotes = QuoteRequest.objects.count()

    quotes_this_month = QuoteRequest.objects.filter(
        created_at__date__gte=month_start
    ).count()

    contacts_this_month = ContactMessage.objects.filter(
        created_at__date__gte=month_start
    ).count()

    recent_contacts = ContactMessage.objects.filter(
        created_at__date__gte=last_7_days
    ).count()

    recent_quotes = QuoteRequest.objects.filter(
        created_at__date__gte=last_7_days
    ).count()

    estimated_revenue = (
        QuoteRequest.objects.aggregate(total=Sum("estimated_value"))["total"] or 0
    )

    average_order_value = (
        QuoteRequest.objects.aggregate(avg=Avg("estimated_value"))["avg"] or 0
    )

    conversion_rate = round((total_quotes / total_contacts) * 100, 1) if total_contacts else 0

    returning_customers = QuoteRequest.objects.filter(
        is_returning_customer=True
    ).count()

    orders_in_production = QuoteRequest.objects.filter(
        in_production=True
    ).count()

    pending_quotes = QuoteRequest.objects.filter(
        status__in=["new", "reviewing"]
    ).count()

    latest_contacts = ContactMessage.objects.all().order_by("-created_at")[:8]
    latest_quotes = QuoteRequest.objects.all().order_by("-created_at")[:8]

    upcoming_deadlines = QuoteRequest.objects.filter(
        deadline__gte=today,
        deadline__lte=next_30_days,
    ).order_by("deadline")[:8]

    hot_prospects = QuoteRequest.objects.filter(
        quantity__gte=100
    ).order_by("-created_at")[:8]

    quotes_with_files = QuoteRequest.objects.filter(
        logo__isnull=False
    ).exclude(logo="")[:8]

    quotes_with_logos = QuoteRequest.objects.exclude(
        logo=""
    ).exclude(
        logo__isnull=True
    )

    logo_count = quotes_with_logos.count()

    production_jobs = QuoteRequest.objects.exclude(
        status="new"
    ).order_by("deadline")

    pipeline = {
        "new": QuoteRequest.objects.filter(status="new").order_by("-created_at")[:6],
        "reviewing": QuoteRequest.objects.filter(status="reviewing").order_by("-created_at")[:6],
        "quoted": QuoteRequest.objects.filter(status="quoted").order_by("-created_at")[:6],
        "ordered": QuoteRequest.objects.filter(status="ordered").order_by("-created_at")[:6],
        "shipped": QuoteRequest.objects.filter(status="shipped").order_by("-created_at")[:6],
    }

    pipeline_counts = {
        "new": QuoteRequest.objects.filter(status="new").count(),
        "reviewing": QuoteRequest.objects.filter(status="reviewing").count(),
        "quoted": QuoteRequest.objects.filter(status="quoted").count(),
        "ordered": QuoteRequest.objects.filter(status="ordered").count(),
        "shipped": QuoteRequest.objects.filter(status="shipped").count(),
    }

    quote_trend = (
        QuoteRequest.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    contact_trend = (
        ContactMessage.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    lead_sources = (
        QuoteRequest.objects.values("lead_source")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    quote_labels = [item["day"].strftime("%b %d") for item in quote_trend]
    quote_values = [item["total"] for item in quote_trend]

    contact_labels = [item["day"].strftime("%b %d") for item in contact_trend]
    contact_values = [item["total"] for item in contact_trend]

    lead_source_labels = [
        (item["lead_source"] or "Unknown").title()
        for item in lead_sources
    ]

    lead_source_values = [
        item["total"]
        for item in lead_sources
    ]

    return {
        "total_contacts": total_contacts,
        "total_messages": total_contacts,
        "total_quotes": total_quotes,
        "quotes_this_month": quotes_this_month,
        "contacts_this_month": contacts_this_month,
        "recent_contacts": recent_contacts,
        "recent_quotes": recent_quotes,
        "estimated_revenue": estimated_revenue,
        "total_revenue": estimated_revenue,
        "average_order_value": average_order_value,
        "conversion_rate": conversion_rate,
        "returning_customers": returning_customers,
        "orders_in_production": orders_in_production,
        "production_quotes": orders_in_production,
        "pending_quotes": pending_quotes,
        "latest_contacts": latest_contacts,
        "latest_quotes": latest_quotes,
        "upcoming_deadlines": upcoming_deadlines,
        "hot_prospects": hot_prospects,
        "quotes_with_files": quotes_with_files,
        "quotes_with_logos": quotes_with_logos,
        "logo_count": logo_count,
        "production_jobs": production_jobs,
        "pipeline": pipeline,
        "pipeline_counts": pipeline_counts,
        "lead_sources": lead_sources,
        "quote_labels": json.dumps(quote_labels),
        "quote_values": json.dumps(quote_values),
        "contact_labels": json.dumps(contact_labels),
        "contact_values": json.dumps(contact_values),
        "lead_source_labels": json.dumps(lead_source_labels),
        "lead_source_values": json.dumps(lead_source_values),
    }


@staff_member_required
def dashboard_home(request):
    context = get_dashboard_context()
    return render(request, "dashboard/home.html", context)


@staff_member_required
def analytics_page(request):
    context = get_dashboard_context()
    return render(request, "dashboard/analytics.html", context)


@staff_member_required
def crm_page(request):
    context = get_dashboard_context()
    return render(request, "dashboard/crm.html", context)


class ContactMessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContactMessage.objects.all().order_by("-created_at")
    serializer_class = ContactMessageSerializer
    permission_classes = [IsAdminUser]


class QuoteRequestViewSet(viewsets.ModelViewSet):
    queryset = QuoteRequest.objects.all().order_by("-created_at")
    serializer_class = QuoteRequestSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["patch"])
    def update_status(self, request, pk=None):
        quote = self.get_object()

        serializer = QuoteStatusUpdateSerializer(
            quote,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "success": True,
                    "id": quote.id,
                    "status": quote.status,
                }
            )

        return Response(serializer.errors, status=400)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_stats_api(request):
    total_quotes = QuoteRequest.objects.count()
    total_contacts = ContactMessage.objects.count()

    pending_quotes = QuoteRequest.objects.filter(
        status__in=["new", "reviewing"]
    ).count()

    orders_in_production = QuoteRequest.objects.filter(
        in_production=True
    ).count()

    estimated_revenue = (
        QuoteRequest.objects.aggregate(total=Sum("estimated_value"))["total"] or 0
    )

    return Response(
        {
            "total_quotes": total_quotes,
            "total_contacts": total_contacts,
            "pending_quotes": pending_quotes,
            "orders_in_production": orders_in_production,
            "estimated_revenue": float(estimated_revenue),
        }
    )


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_charts_api(request):
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)

    quote_trend = (
        QuoteRequest.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    contact_trend = (
        ContactMessage.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    lead_sources = (
        QuoteRequest.objects.values("lead_source")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return Response(
        {
            "quote_labels": [item["day"].strftime("%b %d") for item in quote_trend],
            "quote_values": [item["total"] for item in quote_trend],
            "contact_labels": [item["day"].strftime("%b %d") for item in contact_trend],
            "contact_values": [item["total"] for item in contact_trend],
            "lead_source_labels": [
                (item["lead_source"] or "Unknown").title()
                for item in lead_sources
            ],
            "lead_source_values": [item["total"] for item in lead_sources],
        }
    )