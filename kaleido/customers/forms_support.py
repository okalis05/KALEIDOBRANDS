from django import forms

from customers.models import (
    Order,
    Shipment,
    SupportTicket,
    SupportTicketMessage,
)


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = (
            "category",
            "priority",
            "order",
            "shipment",
            "subject",
            "description",
        )

        widgets = {
            "category": forms.Select(
                attrs={"class": "form-select"}
            ),
            "priority": forms.Select(
                attrs={"class": "form-select"}
            ),
            "order": forms.Select(
                attrs={"class": "form-select"}
            ),
            "shipment": forms.Select(
                attrs={"class": "form-select"}
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Briefly describe the issue",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Provide details that will help us resolve "
                        "your request."
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
                .order_by("-created_at")
            )

            self.fields["shipment"].queryset = (
                Shipment.objects
                .filter(order__customer=user)
                .order_by("-created_at")
            )
        else:
            self.fields["order"].queryset = Order.objects.none()
            self.fields["shipment"].queryset = Shipment.objects.none()

        self.fields["order"].required = False
        self.fields["shipment"].required = False
        self.fields["order"].empty_label = "No related order"
        self.fields["shipment"].empty_label = "No related shipment"

    def clean(self):
        cleaned_data = super().clean()

        order = cleaned_data.get("order")
        shipment = cleaned_data.get("shipment")

        if shipment and order and shipment.order_id != order.id:
            self.add_error(
                "shipment",
                "The selected shipment does not belong to the selected order.",
            )

        return cleaned_data


class SupportTicketReplyForm(forms.ModelForm):
    class Meta:
        model = SupportTicketMessage
        fields = (
            "message",
            "attachment",
        )

        widgets = {
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Write your reply",
                }
            ),
            "attachment": forms.ClearableFileInput(
                attrs={"class": "form-control"}
            ),
        }

class StaffTicketReplyForm(forms.ModelForm):

    class Meta:
        model = SupportTicketMessage

        fields = (
            "message",
            "attachment",
            "is_internal",
        )

        widgets = {
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                }
            ),
            "attachment": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "is_internal": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

from django.contrib.auth import get_user_model

User = get_user_model()


class SupportTicketUpdateForm(forms.ModelForm):

    class Meta:

        model = SupportTicket

        fields = (
            "status",
            "priority",
            "assigned_to",
        )

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "priority": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "assigned_to": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["assigned_to"].queryset = (
            User.objects
            .filter(is_staff=True)
            .order_by("first_name", "last_name")
        )

        self.fields["assigned_to"].required = False