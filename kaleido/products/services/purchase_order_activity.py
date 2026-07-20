from products.models import SupplierPurchaseOrderActivity


def log_purchase_order_activity(
    purchase_order,
    *,
    action,
    message="",
    previous_value="",
    new_value="",
    user=None,
):
    return SupplierPurchaseOrderActivity.objects.create(
        purchase_order=purchase_order,
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