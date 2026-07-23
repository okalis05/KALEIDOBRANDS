from django import forms

from products.models import (
    Category,
    ImprintMethod,
    Industry,
    Product,
    ProductCollection,
    Supplier,
    SupplierPurchaseOrder,
)


class QuoteBuilderForm(forms.Form):
    customer_name = forms.CharField(
        max_length=120,
    )

    company = forms.CharField(
        required=False,
    )

    email = forms.EmailField()

    phone = forms.CharField(
        required=False,
    )

    project_name = forms.CharField(
        required=False,
    )

    deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            },
        ),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
            },
        ),
    )


class ProductSearchForm(forms.Form):
    SORT_CHOICES = (
        (
            "featured",
            "Featured first",
        ),
        (
            "newest",
            "Newest",
        ),
        (
            "price-low",
            "Price: low to high",
        ),
        (
            "price-high",
            "Price: high to low",
        ),
        (
            "name",
            "Name",
        ),
    )

    INVENTORY_CHOICES = (
        (
            "in_stock",
            "In Stock",
        ),
        (
            "low_stock",
            "Low Stock",
        ),
        (
            "out_of_stock",
            "Out of Stock",
        ),
        (
            "unknown",
            "Availability Unknown",
        ),
    )

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "type": "search",
                "class": "form-control catalog-search-input",
                "placeholder": (
                    "Scrubs, polos, tumblers, gifts..."
                ),
                "autocomplete": "off",
            },
        ),
    )

    categories = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Category.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    industries = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Industry.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    collections = forms.ModelMultipleChoiceField(
        required=False,
        queryset=ProductCollection.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    imprints = forms.ModelMultipleChoiceField(
        required=False,
        queryset=ImprintMethod.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    suppliers = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Supplier.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    colors = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
    )

    materials = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
    )

    inventory = forms.MultipleChoiceField(
        required=False,
        choices=INVENTORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )

    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "25.00",
            },
        ),
    )

    min_quantity = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "100",
            },
        ),
    )

    sort = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        initial="featured",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            },
        ),
    )

    def __init__(self, *args, active_collections=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["categories"].queryset = (
            Category.objects
            .filter(
                is_active=True,
            )
            .select_related(
                "parent",
            )
            .order_by(
                "order",
                "name",
            )
        )

        self.fields["industries"].queryset = (
            Industry.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "order",
                "name",
            )
        )

        if active_collections is None:
            active_collections = (
                ProductCollection.objects
                .filter(
                    is_active=True,
                )
                .order_by(
                    "order",
                    "name",
                )
            )

        self.fields["collections"].queryset = (
            active_collections
        )

        self.fields["imprints"].queryset = (
            ImprintMethod.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "name",
            )
        )

        self.fields["suppliers"].queryset = (
            Supplier.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "name",
            )
        )

        self.fields["colors"].choices = (
            self._product_text_choices(
                field_name="colors",
                split_commas=True,
            )
        )

        self.fields["materials"].choices = (
            self._product_text_choices(
                field_name="material",
                split_commas=False,
            )
        )

    @staticmethod
    def _product_text_choices(field_name, split_commas=False):
        values = (
            Product.objects
            .filter(
                is_active=True,
            )
            .exclude(
                **{
                    field_name: "",
                },
            )
            .values_list(
                field_name,
                flat=True,
            )
            .distinct()
        )

        normalized_values = set()

        for raw_value in values:
            if not raw_value:
                continue

            candidates = (
                raw_value.split(",")
                if split_commas
                else [raw_value]
            )

            for candidate in candidates:
                value = candidate.strip()

                if value:
                    normalized_values.add(value)

        return [
            (
                value,
                value,
            )
            for value in sorted(
                normalized_values,
                key=str.lower,
            )
        ]


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
                attrs={
                    "type": "date",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                },
            ),
        }