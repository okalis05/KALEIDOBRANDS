from django.db import models


class Quote(models.Model):
    customer_name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)

    email = models.EmailField()

    phone = models.CharField(
        max_length=40,
        blank=True,
    )

    project_name = models.CharField(
        max_length=200,
        blank=True,
    )

    deadline = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    pdf_file = models.FileField(
    upload_to="quotes/pdfs/",
    blank=True,
    null=True,
)

    def __str__(self):
        return f"{self.customer_name} - {self.created_at:%Y-%m-%d}"


class QuoteItem(models.Model):
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product_name = models.CharField(max_length=200)

    category = models.CharField(
        max_length=120,
        blank=True,
    )

    product_url = models.URLField(blank=True)

    quantity = models.PositiveIntegerField(default=100)

    notes = models.CharField(
        max_length=300,
        blank=True,
    )

    def __str__(self):
        return self.product_name