from django import forms

from .models import OrderItem, Shipment, ShippingMethod


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = (
            "shipping_method",
            "carrier",
            "service_level",
            "tracking_number",
            "tracking_url",
            "shipping_cost",
            "estimated_ship_date",
            "estimated_delivery_date",
            "notes",
        )

        widgets = {
            "estimated_ship_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "estimated_delivery_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 4}
            ),
        }


class ShipmentItemSelectionForm(forms.Form):
    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not order:
            return

        for item in order.items.all():
            self.fields[f"item_{item.id}"] = forms.IntegerField(
                required=False,
                min_value=0,
                max_value=item.quantity,
                initial=item.quantity,
                label=f"{item.product_name} — ordered {item.quantity}",
            )