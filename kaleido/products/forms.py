from django import forms
from products.models import SupplierPurchaseOrder

class QuoteBuilderForm(forms.Form):
    customer_name = forms.CharField(max_length=120)
    company = forms.CharField(required=False)
    email = forms.EmailField()
    phone = forms.CharField(required=False)

    project_name = forms.CharField(required=False)

    deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
    )



class SupplierPurchaseOrderStatusForm(forms.ModelForm):
    class Meta:
        model = SupplierPurchaseOrder
        fields = (
            "status",
            "supplier_reference",
            "estimated_ship_date",
            "tracking_number",
            "tracking_url",
            "notes",
        )

        widgets = {
            "estimated_ship_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 4}
            ),
        }