from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Sum

from customers.models import (
    Order,
    RefundRequest,
    RefundTransaction,
    ReturnRequest,
)

User = get_user_model()


def completed_refunds_for_order(order):
    """
    Return the total amount already successfully refunded
    across all completed refund transactions for the order.
    """

    result = (
        RefundTransaction.objects
        .filter(
            refund_request__order=order,
            status="completed",
        )
        .aggregate(total=Sum("amount"))
    )

    return result["total"] or Decimal("0.00")


def remaining_refundable_amount(order):
    """
    Calculate how much remains refundable on the order.
    """

    order_total = order.total or Decimal("0.00")
    refunded_total = completed_refunds_for_order(order)

    remaining = order_total - refunded_total

    return max(
        remaining,
        Decimal("0.00"),
    )


class RefundRequestForm(forms.ModelForm):
    """
    Customer-facing form for requesting a refund.
    """

    class Meta:
        model = RefundRequest

        fields = (
            "order",
            "return_request",
            "reason",
            "amount_requested",
            "customer_notes",
        )

        widgets = {
            "order": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "return_request": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "reason": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "amount_requested": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
            "customer_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Explain why you are requesting a refund."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.user = user

        if user and user.is_authenticated:
            self.fields["order"].queryset = (
                Order.objects
                .filter(
                    customer=user,
                    payment_status__in=[
                        "paid",
                        "partially_refunded",
                    ],
                )
                .order_by("-created_at")
            )

            self.fields["return_request"].queryset = (
                ReturnRequest.objects
                .filter(
                    customer=user,
                    status__in=[
                        "approved",
                        "awaiting_return",
                        "item_received",
                        "refund_processing",
                        "completed",
                    ],
                )
                .select_related("order")
                .order_by("-requested_at")
            )

        else:
            self.fields["order"].queryset = (
                Order.objects.none()
            )

            self.fields["return_request"].queryset = (
                ReturnRequest.objects.none()
            )

        self.fields["return_request"].required = False
        self.fields["return_request"].empty_label = (
            "No related return request"
        )

    def clean(self):
        cleaned_data = super().clean()

        order = cleaned_data.get("order")
        return_request = cleaned_data.get(
            "return_request"
        )
        amount_requested = cleaned_data.get(
            "amount_requested"
        )

        if not order:
            return cleaned_data

        if (
            self.user
            and order.customer_id != self.user.id
        ):
            self.add_error(
                "order",
                "You may only request refunds for your own orders.",
            )

        if order.payment_status not in {
            "paid",
            "partially_refunded",
        }:
            self.add_error(
                "order",
                "Only paid orders can be refunded.",
            )

        if return_request:
            if return_request.order_id != order.id:
                self.add_error(
                    "return_request",
                    (
                        "The selected return request does not "
                        "belong to the selected order."
                    ),
                )

            if (
                self.user
                and return_request.customer_id
                != self.user.id
            ):
                self.add_error(
                    "return_request",
                    (
                        "The selected return request does not "
                        "belong to your account."
                    ),
                )

        if amount_requested is not None:
            if amount_requested <= Decimal("0.00"):
                self.add_error(
                    "amount_requested",
                    (
                        "Requested amount must be greater "
                        "than zero."
                    ),
                )

            remaining = remaining_refundable_amount(
                order
            )

            if amount_requested > remaining:
                self.add_error(
                    "amount_requested",
                    (
                        "The requested amount exceeds the "
                        f"remaining refundable balance of "
                        f"${remaining:.2f}."
                    ),
                )

        return cleaned_data


class StaffRefundUpdateForm(forms.ModelForm):
    """
    Staff form for status, assignment, approved amount,
    and internal notes.
    """

    class Meta:
        model = RefundRequest

        fields = (
            "status",
            "assigned_to",
            "amount_approved",
            "staff_notes",
        )

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "assigned_to": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "amount_approved": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.00",
                    "step": "0.01",
                }
            ),
            "staff_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Add internal review notes."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["assigned_to"].queryset = (
            User.objects
            .filter(is_staff=True)
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )

        self.fields["assigned_to"].required = False

    def clean_amount_approved(self):
        amount_approved = self.cleaned_data.get(
            "amount_approved"
        )

        if amount_approved is None:
            return Decimal("0.00")

        if amount_approved < Decimal("0.00"):
            raise forms.ValidationError(
                "Approved amount cannot be negative."
            )

        refund_request = self.instance

        if not refund_request.order_id:
            return amount_approved

        if (
            amount_approved
            > refund_request.amount_requested
        ):
            raise forms.ValidationError(
                (
                    "Approved amount cannot exceed the "
                    "requested amount."
                )
            )

        already_refunded_for_request = (
            refund_request.completed_transactions_total()
        )

        remaining_for_order = remaining_refundable_amount(
            refund_request.order
        )

        maximum_available = (
            remaining_for_order
            + already_refunded_for_request
        )

        if amount_approved > maximum_available:
            raise forms.ValidationError(
                (
                    "Approved amount exceeds the remaining "
                    f"refundable order balance of "
                    f"${maximum_available:.2f}."
                )
            )

        return amount_approved

    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        amount_approved = cleaned_data.get(
            "amount_approved"
        )

        if status in {
            "approved",
            "processing",
            "completed",
        }:
            if (
                amount_approved is None
                or amount_approved
                <= Decimal("0.00")
            ):
                self.add_error(
                    "amount_approved",
                    (
                        "Enter an approved amount before "
                        "approving or processing the refund."
                    ),
                )

        return cleaned_data


class RefundApprovalForm(forms.Form):
    """
    Dedicated approval action form.
    """

    amount_approved = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0.01",
            }
        ),
    )

    staff_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional approval notes",
            }
        ),
    )

    def __init__(
        self,
        *args,
        refund_request=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.refund_request = refund_request

        if refund_request:
            self.fields[
                "amount_approved"
            ].initial = (
                refund_request.amount_approved
                or refund_request.amount_requested
            )

    def clean_amount_approved(self):
        amount = self.cleaned_data[
            "amount_approved"
        ]

        refund_request = self.refund_request

        if not refund_request:
            return amount

        if amount > refund_request.amount_requested:
            raise forms.ValidationError(
                (
                    "Approved amount cannot exceed the "
                    "requested amount."
                )
            )

        remaining = remaining_refundable_amount(
            refund_request.order
        )

        already_refunded_for_request = (
            refund_request.completed_transactions_total()
        )

        maximum_available = (
            remaining
            + already_refunded_for_request
        )

        if amount > maximum_available:
            raise forms.ValidationError(
                (
                    "Approved amount exceeds the "
                    f"remaining refundable balance of "
                    f"${maximum_available:.2f}."
                )
            )

        return amount


class RefundRejectionForm(forms.Form):
    """
    Dedicated rejection form.
    """

    rejection_reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": (
                    "Explain why the refund was rejected."
                ),
            }
        ),
    )

    def clean_rejection_reason(self):
        reason = self.cleaned_data[
            "rejection_reason"
        ].strip()

        if len(reason) < 5:
            raise forms.ValidationError(
                (
                    "Provide a more detailed rejection "
                    "reason."
                )
            )

        return reason


class RefundProcessingForm(forms.Form):
    """
    Staff form used immediately before calling Stripe.
    """

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0.01",
            }
        ),
    )

    confirmation = forms.BooleanField(
        required=True,
        label=(
            "I confirm that this refund should be "
            "submitted to Stripe."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    def __init__(
        self,
        *args,
        refund_request=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.refund_request = refund_request

        if refund_request:
            self.fields["amount"].initial = (
                refund_request.remaining_approved_amount()
            )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        refund_request = self.refund_request

        if not refund_request:
            return amount

        if refund_request.status not in {
            "approved",
            "failed",
        }:
            raise forms.ValidationError(
                (
                    "Only approved or failed refunds "
                    "can be processed."
                )
            )

        remaining_approved = (
            refund_request.remaining_approved_amount()
        )

        if amount > remaining_approved:
            raise forms.ValidationError(
                (
                    "Amount exceeds the remaining approved "
                    f"refund balance of "
                    f"${remaining_approved:.2f}."
                )
            )

        remaining_order = remaining_refundable_amount(
            refund_request.order
        )

        if amount > remaining_order:
            raise forms.ValidationError(
                (
                    "Amount exceeds the remaining refundable "
                    f"order balance of "
                    f"${remaining_order:.2f}."
                )
            )

        if refund_request.order.payment_status not in {
            "paid",
            "partially_refunded",
        }:
            raise forms.ValidationError(
                "The order is not currently refundable."
            )

        if not refund_request.stripe_payment_intent_id:
            raise forms.ValidationError(
                (
                    "This refund does not have a Stripe "
                    "payment intent ID."
                )
            )

        return amount


class RefundRetryForm(forms.Form):
    """
    Confirmation form for retrying a failed refund.
    """

    confirmation = forms.BooleanField(
        required=True,
        label=(
            "Retry this failed Stripe refund."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    def __init__(
        self,
        *args,
        refund_request=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.refund_request = refund_request

    def clean(self):
        cleaned_data = super().clean()

        refund_request = self.refund_request

        if (
            refund_request
            and refund_request.status != "failed"
        ):
            raise forms.ValidationError(
                (
                    "Only failed refund requests can "
                    "be retried."
                )
            )

        return cleaned_data


class RefundStaffNoteForm(forms.Form):
    """
    Add an internal refund activity note.
    """

    note = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Add an internal refund note",
            }
        ),
    )

    def clean_note(self):
        note = self.cleaned_data["note"].strip()

        if not note:
            raise forms.ValidationError(
                "Enter a note."
            )

        return note