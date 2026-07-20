from __future__ import annotations

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from customers.models import (
    RefundActivity,
    RefundRequest,
    RefundTransaction,
)

logger = logging.getLogger(__name__)


class RefundServiceError(Exception):
    """Base exception for refund service failures."""


class RefundValidationError(RefundServiceError):
    """Raised when a refund does not pass business validation."""


class RefundProcessingError(RefundServiceError):
    """Raised when Stripe cannot process a refund."""


class DuplicateRefundError(RefundServiceError):
    """Raised when a duplicate refund attempt is detected."""


def generate_refund_number() -> str:
    """
    Generate a readable refund number.

    Example:
        KB-RFD-20260717-A1B2C3D4
    """

    date_part = timezone.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:8].upper()

    return f"KB-RFD-{date_part}-{random_part}"


def generate_idempotency_key() -> str:
    """
    Generate a unique Stripe idempotency key.
    """

    return uuid.uuid4().hex


def money(value: Any) -> Decimal:
    """
    Normalize a value to a two-decimal Decimal.
    """

    if value is None:
        value = Decimal("0.00")

    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def amount_to_minor_units(amount: Decimal) -> int:
    """
    Convert a dollar amount to the smallest currency unit.

    Example:
        Decimal("10.25") -> 1025
    """

    normalized = money(amount)

    if normalized <= Decimal("0.00"):
        raise RefundValidationError(
            "Refund amount must be greater than zero."
        )

    return int(
        (
            normalized * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def stripe_object_to_dict(
    stripe_object: Any,
) -> dict:
    """
    Safely convert a Stripe object to a serializable dictionary.
    """

    if stripe_object is None:
        return {}

    if hasattr(stripe_object, "to_dict_recursive"):
        return stripe_object.to_dict_recursive()

    if isinstance(stripe_object, dict):
        return stripe_object

    return {
        "value": str(stripe_object),
    }


def completed_refund_total(order) -> Decimal:
    """
    Return the total of successful refund transactions for an order.
    """

    result = (
        RefundTransaction.objects.filter(
            refund_request__order=order,
            status="completed",
        ).aggregate(
            total=Sum("amount"),
        )
    )

    return money(
        result["total"] or Decimal("0.00")
    )


def pending_refund_total(order) -> Decimal:
    """
    Return refund amounts that have been created or are processing.

    This prevents two staff members from processing overlapping
    refunds at the same time.
    """

    result = (
        RefundTransaction.objects.filter(
            refund_request__order=order,
            status__in=[
                "created",
                "processing",
            ],
        ).aggregate(
            total=Sum("amount"),
        )
    )

    return money(
        result["total"] or Decimal("0.00")
    )


def remaining_refundable(
    order,
    include_pending: bool = False,
) -> Decimal:
    """
    Calculate the remaining refundable balance for an order.
    """

    order_total = money(order.total)
    completed_total = completed_refund_total(order)

    reserved_total = Decimal("0.00")

    if include_pending:
        reserved_total = pending_refund_total(order)

    remaining = (
        order_total
        - completed_total
        - reserved_total
    )

    return max(
        money(remaining),
        Decimal("0.00"),
    )


def log_refund_activity(
    refund_request: RefundRequest,
    action: str,
    message: str = "",
    user=None,
    previous_value: str = "",
    new_value: str = "",
) -> RefundActivity:
    """
    Write an immutable refund audit activity.
    """

    return RefundActivity.objects.create(
        refund_request=refund_request,
        action=action,
        message=message,
        previous_value=str(
            previous_value or ""
        ),
        new_value=str(
            new_value or ""
        ),
        created_by=user,
    )


def send_notification(
    notification_name: str,
    refund_request: RefundRequest,
    **kwargs,
) -> None:
    """
    Safely call a notification function when the notifications
    module is available.

    Notification failures must not roll back a completed refund.
    """

    try:
        from customers.services import (
            refund_notifications,
        )

        notification_function = getattr(
            refund_notifications,
            notification_name,
            None,
        )

        if notification_function:
            notification_function(
                refund_request,
                **kwargs,
            )

    except Exception:
        logger.exception(
            "Refund notification '%s' failed for %s.",
            notification_name,
            refund_request.refund_number,
        )


def get_payment_intent_id(
    refund_request: RefundRequest,
) -> str:
    """
    Resolve the Stripe PaymentIntent from the refund or order.
    """

    payment_intent_id = (
        refund_request.stripe_payment_intent_id
        or getattr(
            refund_request.order,
            "stripe_payment_intent_id",
            "",
        )
        or ""
    ).strip()

    return payment_intent_id


def validate_order_is_refundable(order) -> None:
    """
    Confirm that the order is eligible for a refund.
    """

    valid_statuses = {
        "paid",
        "partially_refunded",
    }

    if order.payment_status not in valid_statuses:
        raise RefundValidationError(
            "Only paid or partially refunded orders can be refunded."
        )

    order_total = money(order.total)

    if order_total <= Decimal("0.00"):
        raise RefundValidationError(
            "The order total must be greater than zero."
        )


def validate_refund_request(
    refund_request: RefundRequest,
    amount: Optional[Decimal] = None,
) -> Decimal:
    """
    Run all checks required before creating a Stripe refund.
    """

    if not refund_request.pk:
        raise RefundValidationError(
            "The refund request must be saved before processing."
        )

    if refund_request.status not in {
        "approved",
        "failed",
    }:
        raise RefundValidationError(
            "Only approved or failed refund requests can be processed."
        )

    validate_order_is_refundable(
        refund_request.order
    )

    payment_intent_id = get_payment_intent_id(
        refund_request
    )

    if not payment_intent_id:
        raise RefundValidationError(
            "No Stripe PaymentIntent is associated with this order."
        )

    approved_amount = money(
        refund_request.amount_approved
    )

    if approved_amount <= Decimal("0.00"):
        raise RefundValidationError(
            "The refund must have an approved amount."
        )

    already_completed = money(
        refund_request.completed_transactions_total()
    )

    remaining_approved = money(
        approved_amount - already_completed
    )

    if remaining_approved <= Decimal("0.00"):
        raise DuplicateRefundError(
            "This refund request has already been fully processed."
        )

    requested_amount = money(
        amount
        if amount is not None
        else remaining_approved
    )

    if requested_amount <= Decimal("0.00"):
        raise RefundValidationError(
            "Refund amount must be greater than zero."
        )

    if requested_amount > remaining_approved:
        raise RefundValidationError(
            (
                "Refund amount exceeds the remaining approved "
                f"balance of ${remaining_approved:.2f}."
            )
        )

    remaining_order_amount = remaining_refundable(
        refund_request.order,
        include_pending=True,
    )

    if requested_amount > remaining_order_amount:
        raise RefundValidationError(
            (
                "Refund amount exceeds the remaining refundable "
                f"order balance of ${remaining_order_amount:.2f}."
            )
        )

    active_duplicate = (
        RefundTransaction.objects.filter(
            refund_request=refund_request,
            amount=requested_amount,
            status__in=[
                "created",
                "processing",
            ],
        ).exists()
    )

    if active_duplicate:
        raise DuplicateRefundError(
            "An identical refund transaction is already being processed."
        )

    return requested_amount


@transaction.atomic
def approve_refund(
    refund_request: RefundRequest,
    amount: Decimal,
    user=None,
    staff_notes: str = "",
) -> RefundRequest:
    """
    Approve a refund request.
    """

    locked_refund = (
        RefundRequest.objects.select_for_update()
        .select_related("order")
        .get(pk=refund_request.pk)
    )

    amount = money(amount)

    if amount <= Decimal("0.00"):
        raise RefundValidationError(
            "Approved amount must be greater than zero."
        )

    if amount > money(
        locked_refund.amount_requested
    ):
        raise RefundValidationError(
            "Approved amount cannot exceed the requested amount."
        )

    remaining_order_amount = remaining_refundable(
        locked_refund.order,
        include_pending=True,
    )

    already_completed_for_request = money(
        locked_refund.completed_transactions_total()
    )

    maximum_available = money(
        remaining_order_amount
        + already_completed_for_request
    )

    if amount > maximum_available:
        raise RefundValidationError(
            (
                "Approved amount exceeds the available refundable "
                f"balance of ${maximum_available:.2f}."
            )
        )

    previous_status = locked_refund.status
    previous_amount = locked_refund.amount_approved

    locked_refund.amount_approved = amount
    locked_refund.status = "approved"
    locked_refund.approved_at = timezone.now()
    locked_refund.reviewed_at = timezone.now()
    locked_refund.failure_message = ""

    if staff_notes:
        locked_refund.staff_notes = staff_notes

    locked_refund.save()

    log_refund_activity(
        locked_refund,
        action="approved",
        message=(
            f"Refund approved for ${amount:.2f}."
        ),
        user=user,
        previous_value=previous_status,
        new_value="approved",
    )

    if money(previous_amount) != amount:
        log_refund_activity(
            locked_refund,
            action="amount_changed",
            message="Approved refund amount updated.",
            user=user,
            previous_value=money(previous_amount),
            new_value=amount,
        )

    transaction.on_commit(
        lambda: send_notification(
            "send_refund_approved_notification",
            locked_refund,
        )
    )

    return locked_refund


@transaction.atomic
def reject_refund(
    refund_request: RefundRequest,
    reason: str,
    user=None,
) -> RefundRequest:
    """
    Reject a refund request.
    """

    reason = str(reason or "").strip()

    if not reason:
        raise RefundValidationError(
            "A rejection reason is required."
        )

    locked_refund = (
        RefundRequest.objects.select_for_update()
        .get(pk=refund_request.pk)
    )

    if locked_refund.status in {
        "processing",
        "completed",
    }:
        raise RefundValidationError(
            "A processing or completed refund cannot be rejected."
        )

    previous_status = locked_refund.status

    locked_refund.status = "rejected"
    locked_refund.staff_notes = reason
    locked_refund.rejected_at = timezone.now()
    locked_refund.reviewed_at = timezone.now()
    locked_refund.save()

    log_refund_activity(
        locked_refund,
        action="rejected",
        message=reason,
        user=user,
        previous_value=previous_status,
        new_value="rejected",
    )

    transaction.on_commit(
        lambda: send_notification(
            "send_refund_rejected_notification",
            locked_refund,
        )
    )

    return locked_refund


@transaction.atomic
def cancel_refund(
    refund_request: RefundRequest,
    user=None,
    reason: str = "",
) -> RefundRequest:
    """
    Cancel an unprocessed refund request.
    """

    locked_refund = (
        RefundRequest.objects.select_for_update()
        .get(pk=refund_request.pk)
    )

    if locked_refund.status in {
        "processing",
        "completed",
    }:
        raise RefundValidationError(
            "A processing or completed refund cannot be cancelled."
        )

    previous_status = locked_refund.status

    locked_refund.status = "cancelled"
    locked_refund.cancelled_at = timezone.now()

    if reason:
        locked_refund.staff_notes = reason

    locked_refund.save()

    log_refund_activity(
        locked_refund,
        action="cancelled",
        message=reason or "Refund request cancelled.",
        user=user,
        previous_value=previous_status,
        new_value="cancelled",
    )

    return locked_refund


@transaction.atomic
def create_refund_transaction(
    refund_request: RefundRequest,
    amount: Optional[Decimal] = None,
    user=None,
) -> RefundTransaction:
    """
    Reserve a refund amount and create the local transaction.

    This database transaction finishes before Stripe is called.
    That is important for SQLite because an external API call should
    not keep the database write lock open.
    """

    locked_refund = (
        RefundRequest.objects.select_for_update()
        .select_related("order")
        .get(pk=refund_request.pk)
    )

    validated_amount = validate_refund_request(
        locked_refund,
        amount=amount,
    )

    payment_intent_id = get_payment_intent_id(
        locked_refund
    )

    idempotency_key = generate_idempotency_key()

    transaction_record = (
        RefundTransaction.objects.create(
            refund_request=locked_refund,
            amount=validated_amount,
            status="created",
            stripe_payment_intent_id=(
                payment_intent_id
            ),
            idempotency_key=idempotency_key,
            created_by=user,
        )
    )

    previous_status = locked_refund.status

    locked_refund.status = "processing"
    locked_refund.processed_at = timezone.now()
    locked_refund.failure_message = ""
    locked_refund.idempotency_key = (
        idempotency_key
    )
    locked_refund.save()

    log_refund_activity(
        locked_refund,
        action="processing_started",
        message=(
            "Stripe refund transaction created for "
            f"${validated_amount:.2f}."
        ),
        user=user,
        previous_value=previous_status,
        new_value="processing",
    )

    return transaction_record


@transaction.atomic
def mark_transaction_processing(
    refund_transaction: RefundTransaction,
) -> RefundTransaction:
    """
    Mark a local transaction as actively processing.
    """

    locked_transaction = (
        RefundTransaction.objects.select_for_update()
        .get(pk=refund_transaction.pk)
    )

    locked_transaction.status = "processing"
    locked_transaction.processed_at = timezone.now()
    locked_transaction.save(
        update_fields=[
            "status",
            "processed_at",
            "updated_at",
        ]
    )

    return locked_transaction


@transaction.atomic
def complete_transaction(
    refund_transaction: RefundTransaction,
    stripe_refund: Any,
    user=None,
) -> RefundTransaction:
    """
    Save a successful Stripe refund result.
    """

    locked_transaction = (
        RefundTransaction.objects.select_for_update()
        .select_related(
            "refund_request",
            "refund_request__order",
            "refund_request__return_request",
        )
        .get(pk=refund_transaction.pk)
    )

    refund_request = locked_transaction.refund_request
    stripe_data = stripe_object_to_dict(
        stripe_refund
    )

    stripe_refund_id = str(
        stripe_data.get("id", "")
    )

    stripe_status = str(
        stripe_data.get("status", "succeeded")
    )

    now = timezone.now()

    locked_transaction.status = "completed"
    locked_transaction.stripe_refund_id = (
        stripe_refund_id
    )
    locked_transaction.stripe_status = (
        stripe_status
    )
    locked_transaction.stripe_response = (
        stripe_data
    )
    locked_transaction.failure_message = ""
    locked_transaction.processed_at = (
        locked_transaction.processed_at
        or now
    )
    locked_transaction.completed_at = now
    locked_transaction.save()

    total_refunded_for_request = money(
        refund_request.completed_transactions_total()
    )

    refund_request.amount_refunded = (
        total_refunded_for_request
    )
    refund_request.stripe_refund_id = (
        stripe_refund_id
    )
    refund_request.failure_message = ""
    refund_request.failed_at = None

    if (
        total_refunded_for_request
        >= money(refund_request.amount_approved)
    ):
        previous_status = refund_request.status
        refund_request.status = "completed"
        refund_request.completed_at = now
    else:
        previous_status = refund_request.status
        refund_request.status = "approved"

    refund_request.save()

    synchronize_order_payment_status(
        refund_request.order
    )

    synchronize_return_request(
        refund_request
    )

    log_refund_activity(
        refund_request,
        action="processed",
        message=(
            f"Stripe refund {stripe_refund_id} completed "
            f"for ${locked_transaction.amount:.2f}."
        ),
        user=user,
        previous_value=previous_status,
        new_value=refund_request.status,
    )

    transaction.on_commit(
        lambda: send_notification(
            "send_refund_completed_notification",
            refund_request,
            refund_transaction=locked_transaction,
        )
    )

    return locked_transaction


@transaction.atomic
def fail_transaction(
    refund_transaction: RefundTransaction,
    error_message: str,
    stripe_response: Optional[dict] = None,
    user=None,
) -> RefundTransaction:
    """
    Save a failed Stripe refund result.
    """

    error_message = str(
        error_message or "Unknown refund error."
    )

    locked_transaction = (
        RefundTransaction.objects.select_for_update()
        .select_related("refund_request")
        .get(pk=refund_transaction.pk)
    )

    now = timezone.now()

    locked_transaction.status = "failed"
    locked_transaction.failure_message = (
        error_message
    )
    locked_transaction.failed_at = now
    locked_transaction.stripe_response = (
        stripe_response or {}
    )
    locked_transaction.save()

    refund_request = (
        locked_transaction.refund_request
    )
    previous_status = refund_request.status

    refund_request.status = "failed"
    refund_request.failure_message = (
        error_message
    )
    refund_request.failed_at = now
    refund_request.save()

    log_refund_activity(
        refund_request,
        action="failed",
        message=error_message,
        user=user,
        previous_value=previous_status,
        new_value="failed",
    )

    transaction.on_commit(
        lambda: send_notification(
            "send_refund_failed_notification",
            refund_request,
            error_message=error_message,
        )
    )

    return locked_transaction


def synchronize_order_payment_status(order) -> str:
    """
    Update the order payment status from completed refunds.
    """

    order_total = money(order.total)
    refunded_total = completed_refund_total(order)

    if refunded_total <= Decimal("0.00"):
        new_status = "paid"

    elif refunded_total >= order_total:
        new_status = "refunded"

    else:
        new_status = "partially_refunded"

    if order.payment_status != new_status:
        order.payment_status = new_status
        order.save(
            update_fields=[
                "payment_status",
            ]
        )

    return new_status


def synchronize_return_request(
    refund_request: RefundRequest,
) -> None:
    """
    Synchronize the connected return request when one exists.

    This uses only statuses that are expected from Phase 8.5.
    Adjust the final status name if your ReturnRequest model uses
    different values.
    """

    return_request = (
        refund_request.return_request
    )

    if not return_request:
        return

    update_fields = []

    if refund_request.status == "processing":
        if hasattr(return_request, "status"):
            return_request.status = (
                "refund_processing"
            )
            update_fields.append("status")

    elif refund_request.status == "completed":
        if hasattr(return_request, "status"):
            return_request.status = "completed"
            update_fields.append("status")

    if update_fields:
        try:
            return_request.save(
                update_fields=update_fields
            )
        except ValidationError:
            logger.warning(
                (
                    "Return request %s could not be synchronized "
                    "because its status choices differ."
                ),
                return_request.pk,
            )


def configure_stripe() -> None:
    """
    Configure the Stripe SDK using Django settings.
    """

    secret_key = getattr(
        settings,
        "STRIPE_SECRET_KEY",
        "",
    )

    if not secret_key:
        raise RefundProcessingError(
            "STRIPE_SECRET_KEY is not configured."
        )

    stripe.api_key = secret_key


def create_stripe_refund(
    refund_transaction: RefundTransaction,
) -> Any:
    """
    Send the refund request to Stripe.

    The Stripe request is deliberately executed outside a Django
    atomic block to avoid holding SQLite write locks while waiting
    for the network.
    """

    configure_stripe()

    amount_in_minor_units = (
        amount_to_minor_units(
            refund_transaction.amount
        )
    )

    metadata = {
        "refund_request_id": str(
            refund_transaction.refund_request_id
        ),
        "refund_number": (
            refund_transaction
            .refund_request
            .refund_number
        ),
        "refund_transaction_id": str(
            refund_transaction.pk
        ),
        "order_id": str(
            refund_transaction
            .refund_request
            .order_id
        ),
    }

    return stripe.Refund.create(
        payment_intent=(
            refund_transaction
            .stripe_payment_intent_id
        ),
        amount=amount_in_minor_units,
        reason="requested_by_customer",
        metadata=metadata,
        idempotency_key=(
            refund_transaction.idempotency_key
        ),
    )


def process_refund(
    refund_request: RefundRequest,
    amount: Optional[Decimal] = None,
    user=None,
) -> RefundTransaction:
    """
    Complete refund-processing workflow.

    Workflow:
        1. Validate and reserve locally.
        2. Commit the local transaction.
        3. Call Stripe without holding a database lock.
        4. Save the Stripe result.
    """

    refund_transaction = (
        create_refund_transaction(
            refund_request=refund_request,
            amount=amount,
            user=user,
        )
    )

    mark_transaction_processing(
        refund_transaction
    )

    try:
        stripe_refund = create_stripe_refund(
            refund_transaction
        )

    except stripe.error.StripeError as exc:
        error_message = (
            getattr(exc, "user_message", None)
            or str(exc)
            or "Stripe rejected the refund."
        )

        error_body = getattr(
            exc,
            "json_body",
            None,
        )

        fail_transaction(
            refund_transaction,
            error_message=error_message,
            stripe_response=(
                error_body
                if isinstance(error_body, dict)
                else {}
            ),
            user=user,
        )

        raise RefundProcessingError(
            error_message
        ) from exc

    except Exception as exc:
        error_message = (
            "Unexpected refund-processing error: "
            f"{exc}"
        )

        fail_transaction(
            refund_transaction,
            error_message=error_message,
            user=user,
        )

        raise RefundProcessingError(
            error_message
        ) from exc

    stripe_status = str(
        getattr(
            stripe_refund,
            "status",
            "",
        )
        or ""
    )

    if stripe_status not in {
        "succeeded",
        "pending",
    }:
        error_message = (
            "Stripe returned refund status "
            f"'{stripe_status or 'unknown'}'."
        )

        fail_transaction(
            refund_transaction,
            error_message=error_message,
            stripe_response=(
                stripe_object_to_dict(
                    stripe_refund
                )
            ),
            user=user,
        )

        raise RefundProcessingError(
            error_message
        )

    if stripe_status == "pending":
        return save_pending_stripe_refund(
            refund_transaction,
            stripe_refund,
            user=user,
        )

    return complete_transaction(
        refund_transaction,
        stripe_refund,
        user=user,
    )


@transaction.atomic
def save_pending_stripe_refund(
    refund_transaction: RefundTransaction,
    stripe_refund: Any,
    user=None,
) -> RefundTransaction:
    """
    Save a Stripe refund whose status is still pending.

    A later webhook will mark it completed or failed.
    """

    locked_transaction = (
        RefundTransaction.objects.select_for_update()
        .select_related("refund_request")
        .get(pk=refund_transaction.pk)
    )

    stripe_data = stripe_object_to_dict(
        stripe_refund
    )

    locked_transaction.status = "processing"
    locked_transaction.stripe_refund_id = str(
        stripe_data.get("id", "")
    )
    locked_transaction.stripe_status = "pending"
    locked_transaction.stripe_response = (
        stripe_data
    )
    locked_transaction.processed_at = (
        timezone.now()
    )
    locked_transaction.save()

    refund_request = (
        locked_transaction.refund_request
    )

    refund_request.status = "processing"
    refund_request.stripe_refund_id = (
        locked_transaction.stripe_refund_id
    )
    refund_request.save()

    log_refund_activity(
        refund_request,
        action="processing_started",
        message=(
            "Stripe accepted the refund and marked it pending."
        ),
        user=user,
        previous_value="processing",
        new_value="processing",
    )

    return locked_transaction


def retry_failed_refund(
    refund_request: RefundRequest,
    user=None,
) -> RefundTransaction:
    """
    Retry a failed refund with a new local transaction and a new
    Stripe idempotency key.

    A new key is necessary because Stripe returns the original
    response when the same key is reused.
    """

    if refund_request.status != "failed":
        raise RefundValidationError(
            "Only failed refund requests can be retried."
        )

    remaining_amount = money(
        refund_request.remaining_approved_amount()
    )

    if remaining_amount <= Decimal("0.00"):
        raise DuplicateRefundError(
            "There is no approved refund balance remaining."
        )

    log_refund_activity(
        refund_request,
        action="retry_started",
        message=(
            f"Refund retry started for "
            f"${remaining_amount:.2f}."
        ),
        user=user,
    )

    return process_refund(
        refund_request=refund_request,
        amount=remaining_amount,
        user=user,
    )


@transaction.atomic
def add_refund_note(
    refund_request: RefundRequest,
    note: str,
    user=None,
) -> RefundActivity:
    """
    Add an internal audit note.
    """

    note = str(note or "").strip()

    if not note:
        raise RefundValidationError(
            "A refund note cannot be empty."
        )

    locked_refund = (
        RefundRequest.objects.select_for_update()
        .get(pk=refund_request.pk)
    )

    if locked_refund.staff_notes:
        locked_refund.staff_notes = (
            f"{locked_refund.staff_notes}\n\n"
            f"{note}"
        )
    else:
        locked_refund.staff_notes = note

    locked_refund.save(
        update_fields=[
            "staff_notes",
            "updated_at",
        ]
    )

    return log_refund_activity(
        locked_refund,
        action="note_added",
        message=note,
        user=user,
    )