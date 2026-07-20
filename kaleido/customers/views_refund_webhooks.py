from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from customers.webhooks.refunds import (
    dispatch_refund_event,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_refund_webhook(
    request: HttpRequest,
) -> HttpResponse:
    """
    Receive and verify Stripe refund webhook events.

    Stripe signature verification requires the original raw body.
    Do not decode, parse, or modify request.body before calling
    stripe.Webhook.construct_event().
    """

    webhook_secret = getattr(
        settings,
        "STRIPE_WEBHOOK_SECRET",
        "",
    )

    if not webhook_secret:
        logger.error(
            "STRIPE_WEBHOOK_SECRET is not configured."
        )

        return JsonResponse(
            {
                "detail": (
                    "Stripe webhook is not configured."
                )
            },
            status=503,
        )

    signature = request.headers.get(
        "Stripe-Signature",
        "",
    )

    if not signature:
        return JsonResponse(
            {
                "detail": (
                    "Missing Stripe-Signature header."
                )
            },
            status=400,
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=request.body,
            sig_header=signature,
            secret=webhook_secret,
        )

    except ValueError:
        logger.warning(
            "Stripe webhook received an invalid payload."
        )

        return JsonResponse(
            {"detail": "Invalid payload."},
            status=400,
        )

    except stripe.error.SignatureVerificationError:
        logger.warning(
            "Stripe webhook signature verification failed."
        )

        return JsonResponse(
            {"detail": "Invalid signature."},
            status=400,
        )

    try:
        result = dispatch_refund_event(event)

    except Exception:
        logger.exception(
            "Stripe refund webhook processing failed."
        )

        # Returning a non-2xx response tells Stripe to retry.
        return JsonResponse(
            {
                "detail": (
                    "Webhook processing failed."
                )
            },
            status=500,
        )

    return JsonResponse(
        {
            "received": True,
            "result": result,
        },
        status=200,
    )