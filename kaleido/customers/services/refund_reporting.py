from decimal import Decimal
from datetime import timedelta
from django.db.models.functions import TruncMonth ,TruncDate
from django.db.models import (
    Avg,
    Count,
    Sum,
    Max,
    F,
    ExpressionWrapper,
    DurationField,
)
from django.utils import timezone

from customers.models import (
    RefundRequest,
    RefundTransaction,
    StripeWebhookEvent,
)


def _date_filter(queryset, start=None, end=None):
    if start:
        queryset = queryset.filter(requested_at__gte=start)

    if end:
        queryset = queryset.filter(requested_at__lte=end)

    return queryset


def total_refunds(start=None, end=None):
    queryset = _date_filter(
        RefundRequest.objects.filter(status="completed"),
        start,
        end,
    )

    return (
        queryset.aggregate(
            total=Sum("amount_refunded")
        )["total"]
        or Decimal("0.00")
    )


def completed_refunds(start=None, end=None):
    queryset = _date_filter(
        RefundRequest.objects.filter(status="completed"),
        start,
        end,
    )

    return queryset.count()


def pending_refunds():
    return RefundRequest.objects.filter(
        status__in=[
            "requested",
            "approved",
            "processing",
        ]
    ).count()


def failed_refunds():
    return RefundRequest.objects.filter(
        status="failed"
    ).count()


def cancelled_refunds():
    return RefundRequest.objects.filter(
        status="cancelled"
    ).count()


def rejected_refunds():
    return RefundRequest.objects.filter(
        status="rejected"
    ).count()


def average_refund():
    return (
        RefundRequest.objects.filter(
            status="completed"
        ).aggregate(
            avg=Avg("amount_refunded")
        )["avg"]
        or Decimal("0.00")
    )


def largest_refund():
    return (
        RefundRequest.objects.filter(
            status="completed"
        ).aggregate(
            largest=Max("amount_refunded")
        )["largest"]
        or Decimal("0.00")
    )


def refunds_by_reason():
    return (
        RefundRequest.objects.values(
            "reason"
        )
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )


def refunds_by_status():
    return (
        RefundRequest.objects.values(
            "status"
        )
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )


def refunds_by_day(days=30):
    since = timezone.now() - timedelta(days=days)

    return (
        RefundRequest.objects.filter(
            requested_at__gte=since
        )
        .annotate(
            day=TruncDate("requested_at")
        )
        .values("day")
        .annotate(
            total=Count("id"),
            amount=Sum("amount_requested"),
        )
        .order_by("day")
    )


def average_processing_time():
    queryset = RefundRequest.objects.filter(
        completed_at__isnull=False,
        processed_at__isnull=False,
    )

    queryset = queryset.annotate(
        duration=ExpressionWrapper(
            F("completed_at") - F("processed_at"),
            output_field=DurationField(),
        )
    )

    return queryset.aggregate(
        avg=Avg("duration")
    )["avg"]


def webhook_health():
    total = StripeWebhookEvent.objects.count()

    processed = StripeWebhookEvent.objects.filter(
        status="processed"
    ).count()

    failed = StripeWebhookEvent.objects.filter(
        status="failed"
    ).count()

    permanent = StripeWebhookEvent.objects.filter(
        status="permanent_failure"
    ).count()

    ignored = StripeWebhookEvent.objects.filter(
        status="ignored"
    ).count()

    processing = StripeWebhookEvent.objects.filter(
        status="processing"
    ).count()

    received = StripeWebhookEvent.objects.filter(
        status="received"
    ).count()

    success_rate = 100

    if total:
        success_rate = round(
            processed / total * 100,
            2,
        )

    return {
        "total": total,
        "processed": processed,
        "failed": failed,
        "permanent": permanent,
        "ignored": ignored,
        "processing": processing,
        "received": received,
        "success_rate": success_rate,
    }


def refund_rate():
    orders = RefundRequest.objects.exclude(
        order=None
    ).values(
        "order"
    ).distinct().count()

    if not orders:
        return 0

    refunded = RefundRequest.objects.filter(
        status="completed"
    ).count()

    return round(
        refunded / orders * 100,
        2,
    )


def dashboard_summary(
    start=None,
    end=None,
):
    completed_queryset = _date_filter(
        RefundRequest.objects.filter(
            status="completed"
        ),
        start,
        end,
    )

    all_queryset = _date_filter(
        RefundRequest.objects.all(),
        start,
        end,
    )

    completed_count = completed_queryset.count()

    pending_count = all_queryset.filter(
        status__in=[
            "requested",
            "approved",
            "processing",
        ]
    ).count()

    failed_count = all_queryset.filter(
        status="failed"
    ).count()

    cancelled_count = all_queryset.filter(
        status="cancelled"
    ).count()

    rejected_count = all_queryset.filter(
        status="rejected"
    ).count()

    amounts = completed_queryset.aggregate(
        total=Sum("amount_refunded"),
        average=Avg("amount_refunded"),
        largest=Max("amount_refunded"),
    )

    summary = {
        "completed": completed_count,
        "pending": pending_count,
        "failed": failed_count,
        "cancelled": cancelled_count,
        "rejected": rejected_count,
        "total_amount": amounts["total"] or Decimal("0.00"),
        "average": amounts["average"] or Decimal("0.00"),
        "largest": amounts["largest"] or Decimal("0.00"),
        "refund_rate": refund_rate(),
        "processing_time": average_processing_time(),
        "webhooks": webhook_health(),
        "monthly": list(monthly_refunds()),
        "top_customers": list(top_refund_customers()),
        "average_days": average_processing_days(),
        "approval_rate": approval_rate(),
        "failure_rate": failure_rate(),
    }

    return summary

def monthly_refunds(start=None, end=None):
    queryset = _date_filter(
        RefundRequest.objects.filter(
            status="completed"
        ),
        start,
        end,
    )

    return (
        queryset
        .annotate(month=TruncMonth("completed_at"))
        .values("month")
        .annotate(
            total=Sum("amount_refunded"),
            refunds=Count("id"),
        )
        .order_by("month")
    )

def top_refund_customers(limit=10):
    return (
        RefundRequest.objects.filter(
            status="completed"
        )
        .values(
            "customer__username",
            "customer__email",
        )
        .annotate(
            refunds=Count("id"),
            total=Sum("amount_refunded"),
        )
        .order_by("-total")[:limit]
    )


def average_processing_days():
    refunds = RefundRequest.objects.filter(
        completed_at__isnull=False
    )

    if not refunds.exists():
        return 0

    total_days = 0

    for refund in refunds:
        total_days += (
            refund.completed_at
            - refund.requested_at
        ).days

    return round(
        total_days / refunds.count(),
        2,
    )


def approval_rate():
    total = RefundRequest.objects.count()

    if total == 0:
        return 0

    approved = RefundRequest.objects.filter(
        status="completed"
    ).count()

    return round(
        approved * 100 / total,
        2,
    )


def failure_rate():
    total = RefundRequest.objects.count()

    if total == 0:
        return 0

    failed = RefundRequest.objects.filter(
        status="failed"
    ).count()

    return round(
        failed * 100 / total,
        2,
    )