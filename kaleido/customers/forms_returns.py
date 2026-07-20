from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory

from customers.models import (
    Order,
    OrderItem,
    ReturnRequest,
    ReturnRequestAttachment,
    ReturnRequestItem,
    ReturnRequestMessage,
)

User = get_user_model()


class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = (
            "order",
            "request_type",
            "reason",
            "customer_notes",
        )

        widgets = {
            "order": forms.Select(
                attrs={"class": "form-select"}
            ),
            "request_type": forms.Select(
                attrs={"class": "form-select"}
            ),
            "reason": forms.Select(
                attrs={"class": "form-select"}
            ),
            "customer_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Explain what happened and what resolution "
                        "you are requesting."
                    ),
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            self.fields["order"].queryset = (
                Order.objects
                .filter(customer=user)
                .exclude(status="cancelled")
                .order_by("-created_at")
            )
        else:
            self.fields["order"].queryset = (
                Order.objects.none()
            )


class ReturnItemSelectionForm(forms.Form):
    order_item = forms.ModelChoiceField(
        queryset=OrderItem.objects.none(),
        widget=forms.Select(
            attrs={"class": "form-select"}
        ),
    )

    quantity_requested = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
            }
        ),
    )

    condition = forms.ChoiceField(
        choices=ReturnRequestItem.CONDITION_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-select"}
        ),
    )

    customer_item_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
            }
        ),
    )

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)

        if order:
            self.fields["order_item"].queryset = (
                order.items.all()
            )
        else:
            self.fields["order_item"].queryset = (
                OrderItem.objects.none()
            )

    def clean(self):
        cleaned_data = super().clean()

        order_item = cleaned_data.get("order_item")
        quantity = cleaned_data.get("quantity_requested")

        if (
            order_item
            and quantity
            and quantity > order_item.quantity
        ):
            self.add_error(
                "quantity_requested",
                (
                    f"Maximum available quantity is "
                    f"{order_item.quantity}."
                ),
            )

        return cleaned_data


ReturnItemFormSet = formset_factory(
    ReturnItemSelectionForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class ReturnMessageForm(forms.ModelForm):
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control"}
        ),
    )

    attachment_description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Optional attachment description",
            }
        ),
    )

    class Meta:
        model = ReturnRequestMessage
        fields = ("message",)

        widgets = {
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Write your message",
                }
            ),
        }


class StaffReturnUpdateForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = (
            "status",
            "resolution",
            "assigned_to",
            "staff_notes",
            "return_tracking_number",
            "return_tracking_url",
        )

        widgets = {
            "status": forms.Select(
                attrs={"class": "form-select"}
            ),
            "resolution": forms.Select(
                attrs={"class": "form-select"}
            ),
            "assigned_to": forms.Select(
                attrs={"class": "form-select"}
            ),
            "staff_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                }
            ),
            "return_tracking_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "return_tracking_url": forms.URLInput(
                attrs={"class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["assigned_to"].queryset = (
            User.objects
            .filter(is_staff=True)
            .order_by("first_name", "last_name", "username")
        )

        self.fields["assigned_to"].required = False


class StaffReturnItemForm(forms.ModelForm):
    class Meta:
        model = ReturnRequestItem
        fields = (
            "quantity_approved",
            "quantity_received",
            "condition",
            "resolution",
            "staff_item_notes",
        )

        widgets = {
            "quantity_approved": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),
            "quantity_received": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),
            "condition": forms.Select(
                attrs={"class": "form-select"}
            ),
            "resolution": forms.Select(
                attrs={"class": "form-select"}
            ),
            "staff_item_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }


class StaffReturnMessageForm(forms.ModelForm):
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control"}
        ),
    )

    attachment_description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-control"}
        ),
    )

    class Meta:
        model = ReturnRequestMessage
        fields = (
            "message",
            "is_internal",
        )

        widgets = {
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                }
            ),
            "is_internal": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }