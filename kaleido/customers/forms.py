from django import forms
from django.contrib.auth.models import User

from .models import CustomerProfile, BrandAsset, ArtworkProof, CustomerAddress


class CustomerRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User

        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
        )

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise forms.ValidationError("Passwords do not match.")

        return cleaned


class CustomerProfileForm(forms.ModelForm):

    class Meta:
        model = CustomerProfile

        exclude = (
            "user",
            "created_at",
            "updated_at",
        )


class BrandAssetForm(forms.ModelForm):
    class Meta:
        model = BrandAsset
        fields = ("title", "asset_type", "file", "notes")


class ArtworkProofForm(forms.ModelForm):
    class Meta:
        model = ArtworkProof
        fields = ("title", "file", "customer_notes")


class CheckoutForm(forms.Form):
    company = forms.CharField(max_length=200, required=False)
    shipping_name = forms.CharField(max_length=200)
    shipping_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    shipping_city = forms.CharField(max_length=100)
    shipping_state = forms.CharField(max_length=100)
    shipping_postal_code = forms.CharField(max_length=20)
    shipping_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

class CustomerAddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        exclude = ("user", "created_at")


class CheckoutForm(forms.Form):
    saved_address = forms.ModelChoiceField(
        queryset=CustomerAddress.objects.none(),
        required=False,
        empty_label="Use a new shipping address",
    )

    company = forms.CharField(max_length=200, required=False)
    shipping_name = forms.CharField(max_length=200, required=False)
    shipping_address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    shipping_city = forms.CharField(max_length=100, required=False)
    shipping_state = forms.CharField(max_length=100, required=False)
    shipping_postal_code = forms.CharField(max_length=20, required=False)
    shipping_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    save_address = forms.BooleanField(required=False, label="Save this address for future orders")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields["saved_address"].queryset = CustomerAddress.objects.filter(user=user)

    def clean(self):
        cleaned = super().clean()
        saved_address = cleaned.get("saved_address")

        if saved_address:
            return cleaned

        required_fields = [
            "shipping_name",
            "shipping_address",
            "shipping_city",
            "shipping_state",
            "shipping_postal_code",
        ]

        for field in required_fields:
            if not cleaned.get(field):
                self.add_error(field, "This field is required unless using a saved address.")

        return cleaned