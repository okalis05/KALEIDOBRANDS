from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.http import HttpResponse
from django.utils import timezone

from customers.models import (
    RefundRequest,
    RefundTransaction,
    StripeWebhookEvent,
)


def safe_value(value) -> str:
    """
    Convert database values into CSV-safe strings.
    """

    if value is None:
        return ""

    if isinstance(value, Decimal):
        return f"{value:.2f}"

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)

        return value.strftime("%Y-%m-%d %H:%M:%S")

    return str(value)


def create_csv_response(
    filename: str,
    headers: list[str],
    rows: Iterable[Iterable],
) -> HttpResponse:
    """
    Create a downloadable CSV response.
    """

    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    # Helps Excel recognize UTF-8 correctly.
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(headers)

    for row in rows:
        writer.writerow(
            [
                safe_value(value)
                for value in row
            ]
        )

    return response


def export_refund_requests_csv(
    queryset,
    filename: str = "refund_requests.csv",
) -> HttpResponse:
    """
    Export refund requests.
    """

    queryset = queryset.select_related(
        "customer",
        "order",
        "return_request",
    ).order_by("-requested_at")

    headers = [
        "Refund Number",
        "Status",
        "Reason",
        "Customer Name",
        "Customer Email",
        "Order Number",
        "Amount Requested",
        "Amount Approved",
        "Amount Refunded",
        "Stripe Payment Intent",
        "Stripe Refund ID",
        "Requested At",
        "Reviewed At",
        "Approved At",
        "Processed At",
        "Completed At",
        "Failed At",
        "Rejected At",
        "Cancelled At",
        "Customer Notes",
        "Staff Notes",
        "Failure Message",
    ]

    rows = []

    for refund in queryset:
        customer = refund.customer
        order = refund.order

        customer_name = ""

        if customer:
            customer_name = (
                customer.get_full_name()
                or customer.get_username()
            )

        order_number = ""

        if order:
            order_number = getattr(
                order,
                "order_number",
                str(order.pk),
            )

        reason_display = refund.reason

        if hasattr(refund, "get_reason_display"):
            reason_display = (
                refund.get_reason_display()
            )

        status_display = refund.status

        if hasattr(refund, "get_status_display"):
            status_display = (
                refund.get_status_display()
            )

        rows.append(
            [
                refund.refund_number,
                status_display,
                reason_display,
                customer_name,
                getattr(customer, "email", ""),
                order_number,
                refund.amount_requested,
                refund.amount_approved,
                refund.amount_refunded,
                refund.stripe_payment_intent_id,
                refund.stripe_refund_id,
                refund.requested_at,
                refund.reviewed_at,
                refund.approved_at,
                refund.processed_at,
                refund.completed_at,
                refund.failed_at,
                refund.rejected_at,
                refund.cancelled_at,
                refund.customer_notes,
                refund.staff_notes,
                refund.failure_message,
            ]
        )

    return create_csv_response(
        filename,
        headers,
        rows,
    )


def export_refund_transactions_csv(
    queryset,
    filename: str = "refund_transactions.csv",
) -> HttpResponse:
    """
    Export individual refund transactions.
    """

    queryset = queryset.select_related(
        "refund_request",
        "refund_request__customer",
        "refund_request__order",
        "created_by",
    ).order_by("-created_at")

    headers = [
        "Transaction ID",
        "Refund Number",
        "Transaction Status",
        "Stripe Status",
        "Amount",
        "Stripe Refund ID",
        "Stripe Payment Intent",
        "Idempotency Key",
        "Customer Email",
        "Order Number",
        "Created By",
        "Created At",
        "Processed At",
        "Completed At",
        "Failed At",
        "Failure Message",
    ]

    rows = []

    for transaction in queryset:
        refund = transaction.refund_request
        customer = refund.customer
        order = refund.order
        created_by = transaction.created_by

        order_number = ""

        if order:
            order_number = getattr(
                order,
                "order_number",
                str(order.pk),
            )

        creator = ""

        if created_by:
            creator = (
                created_by.get_full_name()
                or created_by.get_username()
            )

        status_display = transaction.status

        if hasattr(
            transaction,
            "get_status_display",
        ):
            status_display = (
                transaction.get_status_display()
            )

        rows.append(
            [
                transaction.pk,
                refund.refund_number,
                status_display,
                transaction.stripe_status,
                transaction.amount,
                transaction.stripe_refund_id,
                transaction.stripe_payment_intent_id,
                transaction.idempotency_key,
                getattr(customer, "email", ""),
                order_number,
                creator,
                transaction.created_at,
                transaction.processed_at,
                transaction.completed_at,
                transaction.failed_at,
                transaction.failure_message,
            ]
        )

    return create_csv_response(
        filename,
        headers,
        rows,
    )


def export_webhook_events_csv(
    queryset,
    filename: str = "stripe_webhook_events.csv",
) -> HttpResponse:
    """
    Export persisted Stripe webhook events.
    """

    queryset = queryset.order_by("-received_at")

    headers = [
        "Event ID",
        "Event Type",
        "Status",
        "Retry Count",
        "Received At",
        "Processed At",
        "Last Retried At",
        "Error Message",
    ]

    rows = []

    for event in queryset:
        rows.append(
            [
                event.event_id,
                event.event_type,
                event.status,
                event.retry_count,
                event.received_at,
                event.processed_at,
                getattr(
                    event,
                    "last_retried_at",
                    None,
                ),
                event.error_message,
                event.last_retried_at,
            ]
        )

    return create_csv_response(
        filename,
        headers,
        rows,
    )