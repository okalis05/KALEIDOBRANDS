from django import forms


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