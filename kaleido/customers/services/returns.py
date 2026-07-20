from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from customers.models import (
    ReturnRequest,
    ReturnRequestActivity,
    ReturnRequestItem,
    Shipment,
    ShipmentItem,
    ShipmentStatusHistory,
)


def generate_return_request_number():
    while True:
        value = f"KB-RET-{get_random_string(8).upper()}"

        if not ReturnRequest.objects.filter(
            request_number=value
        ).exists():
            return value


def generate_rma_number():
    while True:
        value = f"KB-RMA-{get_random_string(8).upper()}"

        if not ReturnRequest.objects.filter(
            rma_number=value
        ).exists():
            return value


def log_return_activity(
    return_request,
    *,
    action,
    message="",
    previous_value="",
    new_value="",
    user=None,
):
    return ReturnRequestActivity.objects.create(
        return_request=return_request,
        action=action,
        message=message,
        previous_value=str(previous_value or ""),
        new_value=str(new_value or ""),
        created_by=(
            user
            if user and getattr(user, "is_authenticated", False)
            else None
        ),
    )


def issue_rma(return_request, *, user=None):
    if not return_request.rma_number:
        return_request.rma_number = generate_rma_number()

    if return_request.status in {
        "submitted",
        "under_review",
        "information_requested",
        "approved",
    }:
        return_request.status = "awaiting_return"

    return_request.approved_at = (
        return_request.approved_at
        or timezone.now()
    )

    return_request.save(
        update_fields=[
            "rma_number",
            "status",
            "approved_at",
            "updated_at",
        ]
    )

    log_return_activity(
        return_request,
        action="rma_created",
        message=f"RMA {return_request.rma_number} was issued.",
        user=user,
    )

    return return_request


def approve_return_request(return_request, *, user=None):
    previous_status = return_request.status

    return_request.status = "approved"
    return_request.approved_at = timezone.now()
    return_request.rejected_at = None

    return_request.save(
        update_fields=[
            "status",
            "approved_at",
            "rejected_at",
            "updated_at",
        ]
    )

    log_return_activity(
        return_request,
        action="approved",
        message="Return request approved.",
        previous_value=previous_status,
        new_value="approved",
        user=user,
    )

    return return_request


def reject_return_request(return_request, *, user=None):
    previous_status = return_request.status

    return_request.status = "rejected"
    return_request.rejected_at = timezone.now()
    return_request.approved_at = None

    return_request.save(
        update_fields=[
            "status",
            "rejected_at",
            "approved_at",
            "updated_at",
        ]
    )

    log_return_activity(
        return_request,
        action="rejected",
        message="Return request rejected.",
        previous_value=previous_status,
        new_value="rejected",
        user=user,
    )

    return return_request


def complete_return_request(return_request, *, user=None):
    previous_status = return_request.status

    return_request.status = "completed"
    return_request.completed_at = timezone.now()

    return_request.save(
        update_fields=[
            "status",
            "completed_at",
            "updated_at",
        ]
    )

    log_return_activity(
        return_request,
        action="completed",
        message="Return request completed.",
        previous_value=previous_status,
        new_value="completed",
        user=user,
    )

    return return_request


@transaction.atomic
def create_replacement_shipment(
    return_request,
    *,
    user=None,
):
    if return_request.replacement_shipment:
        return return_request.replacement_shipment, False

    approved_items = return_request.items.filter(
        quantity_approved__gt=0,
        resolution="replacement",
    )

    if not approved_items.exists():
        raise ValueError(
            "No approved replacement quantities were found."
        )

    shipment = Shipment.objects.create(
        order=return_request.order,
        shipment_number=(
            f"KB-RPL-{get_random_string(8).upper()}"
        ),
        shipping_method=return_request.order.shipping_method,
        carrier="",
        service_level="Replacement Shipment",
        shipping_cost=0,
        status="pending",
        notes=(
            f"Replacement shipment for "
            f"{return_request.request_number}"
        ),
    )

    for return_item in approved_items:
        ShipmentItem.objects.create(
            shipment=shipment,
            order_item=return_item.order_item,
            product_name=return_item.product_name,
            sku=return_item.sku,
            quantity=return_item.quantity_approved,
        )

    ShipmentStatusHistory.objects.create(
        shipment=shipment,
        previous_status="",
        new_status="pending",
        message=(
            f"Replacement shipment created from "
            f"{return_request.request_number}."
        ),
        created_by=(
            user
            if user and user.is_authenticated
            else None
        ),
    )

    return_request.replacement_shipment = shipment
    return_request.status = "replacement_processing"
    return_request.resolution = "replacement"

    return_request.save(
        update_fields=[
            "replacement_shipment",
            "status",
            "resolution",
            "updated_at",
        ]
    )

    log_return_activity(
        return_request,
        action="replacement_created",
        message=(
            f"Replacement shipment "
            f"{shipment.shipment_number} created."
        ),
        user=user,
    )

    return shipment, True