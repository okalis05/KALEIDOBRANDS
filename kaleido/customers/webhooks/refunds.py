from __future__ import annotations

import logging
from typing import Any


from django.db import transaction
from django.utils import timezone


from customers.models import (
    StripeWebhookEvent,
    RefundTransaction,
)

from customers.services.refunds import (
    fail_transaction,
    complete_transaction,
    money,
)


logger = logging.getLogger(__name__)


SUPPORTED_REFUND_EVENTS = {
    "refund.created",
    "refund.updated",
    "refund.failed",
    "charge.refunded",
}


def stripe_object_to_dict(value: Any) -> dict:
    """
    Convert a Stripe object into a regular dictionary.
    """

    if value is None:
        return {}

    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()

    if isinstance(value, dict):
        return value

    return {"value": str(value)}





def handle_refund_created(
    refund_data,
    event,
):
    """
    Synchronize newly-created Stripe refunds.
    """

    transaction = get_transaction_from_metadata(
        refund_data
    )

    if not transaction:

        logger.warning(
            "No local refund transaction found "
            "for Stripe refund %s",
            refund_data.get("id"),
        )

        return

    transaction.stripe_refund_id = (
        refund_data.get("id", "")
    )

    transaction.stripe_status = (
        str(
            refund_data.get("status", "")
        )
    )

    transaction.stripe_response = refund_data

    transaction.save(
        update_fields=[
            "stripe_refund_id",
            "stripe_status",
            "stripe_response",
            "updated_at",
        ]
    )

    logger.info(
        "Linked Stripe refund %s.",
        transaction.stripe_refund_id,
    )



def handle_refund_failed(
    refund_data,
    event,
):
    """
    Synchronize failed Stripe refunds.
    """

    transaction = get_transaction_from_metadata(
        refund_data
    )

    if not transaction:
        logger.warning(
            "Failed refund ignored because "
            "no matching transaction exists."
        )
        return

    if transaction.status == "completed":
        logger.warning(
            "Ignoring failed webhook because "
            "transaction %s is already completed.",
            transaction.pk,
        )
        return

    transaction.stripe_status = str(
        refund_data.get("status", "failed")
    )
    transaction.stripe_response = refund_data

    transaction.save(
        update_fields=[
            "stripe_status",
            "stripe_response",
            "updated_at",
        ]
    )

    fail_transaction(
        transaction,
        error_message=get_failure_reason(
            refund_data
        ),
        stripe_response=refund_data,
    )

    logger.error(
        "Refund transaction %s failed.",
        transaction.pk,
    )


def get_charge_refunds(
    charge_data: dict,
) -> list[dict]:
    """
    Extract Stripe refund objects from a charge.refunded payload.
    """

    refunds = charge_data.get("refunds") or {}

    if isinstance(refunds, dict):
        refund_items = refunds.get("data") or []
    else:
        refund_items = []

    return [
        stripe_object_to_dict(refund)
        for refund in refund_items
    ]




def handle_charge_refunded(
    charge_data,
    event,
):
    """
    Reconcile all refunds contained in a Stripe charge.
    """

    stripe_charge_id = str(
        charge_data.get("id", "")
    )

    refund_items = get_charge_refunds(
        charge_data
    )

    if not refund_items:
        logger.warning(
            "Stripe charge %s reports a refund, "
            "but no refund objects were included.",
            stripe_charge_id,
        )
        return

    synchronized_count = 0

    for refund_data in refund_items:
        refund_transaction = (
            get_transaction_from_metadata(
                refund_data
            )
        )

        if not refund_transaction:
            logger.warning(
                "No local transaction found for "
                "Stripe refund %s on charge %s.",
                refund_data.get("id"),
                stripe_charge_id,
            )
            continue

        stripe_status = str(
            refund_data.get("status", "")
        ).lower()

        if stripe_status == "succeeded":
            if refund_transaction.status != "completed":
                complete_transaction(
                        refund_transaction,
                        refund_data,
                    )
               

            synchronized_count += 1
            continue

        if stripe_status == "failed":
            if refund_transaction.status == "completed":
                logger.warning(
                    "Ignoring failed Stripe state for "
                    "completed transaction %s.",
                    refund_transaction.pk,
                )
                continue

            fail_transaction(
                refund_transaction,
                error_message=get_failure_reason(
                    refund_data
                ),
                stripe_response=refund_data,
            )

            synchronized_count += 1
            continue

        if stripe_status == "pending":
            if refund_transaction.status != "completed":
                synchronize_pending_transaction(
                    refund_transaction,
                    refund_data,
                )

            synchronized_count += 1
            continue

        logger.warning(
            "Unsupported Stripe refund status '%s' "
            "for refund %s.",
            stripe_status or "unknown",
            refund_data.get("id"),
        )

    logger.info(
        "Reconciled %s refund transaction(s) "
        "for Stripe charge %s.",
        synchronized_count,
        stripe_charge_id,
    )



def dispatch_refund_event(event: Any) -> str:
    """
    Dispatch a verified Stripe event.

    Returns:
        processed
        duplicate
        ignored
    """

    event_data = stripe_object_to_dict(event)

    event_id = str(event_data.get("id", ""))
    event_type = str(event_data.get("type", ""))

    webhook_event, created = register_webhook_event(event_data)

    if not created:
        logger.info(
            "Duplicate Stripe event %s ignored.",
            event_id,
        )
        return "duplicate"

    webhook_event.status = "processing"
    webhook_event.save(update_fields=["status"])


    if event_type not in SUPPORTED_REFUND_EVENTS:
        logger.info(
            "Ignoring unsupported Stripe event %s.",
            event_type,
        )

        webhook_event.status = "ignored"
        webhook_event.processed_at = timezone.now()

        webhook_event.save(
            update_fields=[
                "status",
                "processed_at",
            ]
        )

        return "ignored"

    data = event_data.get("data") or {}
    stripe_object = stripe_object_to_dict(
        data.get("object")
    )
  

    handler = EVENT_HANDLERS[event_type]

    try:

        with transaction.atomic():

            handler(
                stripe_object,
                event_data,
            )

    except Exception as exc:

        webhook_event.status = "failed"

        webhook_event.error_message = str(exc)

        webhook_event.retry_count += 1
        if webhook_event.retry_count >= 10:

            webhook_event.status = "permanent_failure"

            webhook_event.save(
                update_fields=[
                    "status",
                ]
            )

            return "failed"

        webhook_event.save(
            update_fields=[
                "status",
                "error_message",
                "retry_count",
            ]
        )

        raise

    webhook_event.status = "processed"
    webhook_event.processed_at = timezone.now()

    webhook_event.save(
        update_fields=[
            "status",
            "processed_at",
        ]
    )

    return "processed"


def get_transaction_by_stripe_refund(
    stripe_refund_id: str,
):
    """
    Locate the matching RefundTransaction.
    """

    if not stripe_refund_id:
        return None

    return (
        RefundTransaction.objects
        .select_related(
            "refund_request",
            "refund_request__order",
            "refund_request__return_request",
        )
        .filter(
            stripe_refund_id=stripe_refund_id,
        )
        .first()
    )


def get_transaction_from_metadata(
    refund_data: dict,
):
    """
    Stripe metadata is our preferred lookup.
    """

    metadata = refund_data.get("metadata") or {}

    transaction_id = metadata.get(
        "refund_transaction_id"
    )

    if transaction_id:

        try:

            return (
                RefundTransaction.objects
                .select_related(
                    "refund_request",
                    "refund_request__order",
                    "refund_request__return_request",
                )
                .get(
                    pk=transaction_id
                )
            )

        except RefundTransaction.DoesNotExist:
            pass

    return get_transaction_by_stripe_refund(
        refund_data.get("id", "")
    )



def get_failure_reason(
    refund_data: dict,
) -> str:
    """
    Return the best available Stripe failure message.
    """

    return (
        refund_data.get("failure_reason")
        or refund_data.get("failure_balance_transaction")
        or refund_data.get("failure_message")
        or "Stripe reported that the refund failed."
    )



@transaction.atomic
def register_webhook_event(event: dict):
    """
    Persist the webhook.

    Returns:
        (event_object, created)
    """

    event_object, created = (
        StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event["id"],
            defaults={
                "event_type": event["type"],
                "api_version": event.get("api_version", ""),
                "livemode": event.get("livemode", False),
                "payload": event,
                "status": "received",
            },
        )
    )

    return event_object, created


def handle_refund_updated(
    refund_data,
    event,
):
    transaction = get_transaction_from_metadata(
        refund_data
    )

    if not transaction:
        logger.warning(
            "Refund update ignored because no transaction exists."
        )
        return

    stripe_status = str(
        refund_data.get("status", "")
    )

    transaction.stripe_status = stripe_status
    transaction.stripe_response = refund_data

    transaction.save(
        update_fields=[
            "stripe_status",
            "stripe_response",
            "updated_at",
        ]
    )

    if (
        stripe_status == "succeeded"
        and transaction.status != "completed"
    ):
        complete_transaction(
            transaction,
            refund_data,
        )
        return


    if stripe_status == "pending":
        logger.info(
            "Refund %s is still pending.",
            refund_data.get("id"),
        )
        return

    logger.info(
        "Refund %s updated with Stripe status %s.",
        refund_data.get("id"),
        stripe_status,
    )

def synchronize_pending_transaction(
    refund_transaction: RefundTransaction,
    refund_data: dict,
) -> None:
    """
    Keep a pending local transaction synchronized with Stripe.
    """

    refund_transaction.status = "processing"
    refund_transaction.stripe_refund_id = str(
        refund_data.get("id", "")
    )
    refund_transaction.stripe_status = str(
        refund_data.get("status", "pending")
    )
    refund_transaction.stripe_response = refund_data

    refund_transaction.save(
        update_fields=[
            "status",
            "stripe_refund_id",
            "stripe_status",
            "stripe_response",
            "updated_at",
        ]
    )



def synchronize_request_amounts(
    refund_request,
):
    """
    Refresh amount_refunded from completed refund transactions.
    """

    total = money(
        refund_request.completed_transactions_total()
    )

    if total != refund_request.amount_refunded:
        refund_request.amount_refunded = total

        refund_request.save(
            update_fields=[
                "amount_refunded",
                "updated_at",
            ]
        )



    
EVENT_HANDLERS = {
    "refund.created": handle_refund_created,
    "refund.updated": handle_refund_updated,
    "refund.failed": handle_refund_failed,
    "charge.refunded": handle_charge_refunded,
}



def process_failed_webhook(
    webhook_event: StripeWebhookEvent,
):
    """
    Retry processing a previously failed webhook.
    """

    event = webhook_event.payload

    dispatch_refund_event(event)




def retry_failed_webhooks(
    limit: int = 100,
):
    """
    Retry failed Stripe webhook events.
    """

    failed_events = (
        StripeWebhookEvent.objects
        .filter(
            status="failed",
        )
        .order_by(
            "received_at",
        )[:limit]
    )

    processed = 0

    for event in failed_events:

        try:

            process_failed_webhook(event)

            processed += 1

        except Exception:

            logger.exception(
                "Webhook retry failed."
            )

    return processed