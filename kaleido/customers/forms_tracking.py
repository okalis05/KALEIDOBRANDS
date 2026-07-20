from django import forms

from customers.models import Shipment


class ShipmentTrackingForm(forms.Form):
    CARRIER_CHOICES = [
        ("", "Choose a carrier"),
        ("UPS", "UPS"),
        ("FedEx", "FedEx"),
        ("USPS", "USPS"),
        ("DHL", "DHL"),
        ("Other", "Other"),
    ]

    carrier = forms.ChoiceField(
        choices=CARRIER_CHOICES,
        required=False,
    )

    tracking_number = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter tracking number",
            }
        ),
    )

    status = forms.ChoiceField(
        choices=Shipment.STATUS_CHOICES,
        required=True,
    )

    estimated_delivery_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    message = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Optional shipment update message"
                ),
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        carrier = cleaned_data.get("carrier")
        tracking_number = cleaned_data.get(
            "tracking_number"
        )

        if tracking_number and not carrier:
            self.add_error(
                "carrier",
                "Select a carrier when entering tracking.",
            )

        return cleaned_data