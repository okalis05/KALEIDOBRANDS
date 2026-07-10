from django.conf import settings
from django.db import models


class RecommendationEvent(models.Model):
    CONTEXT_CHOICES = [
        ("product_detail", "Product Detail"),
        ("customer_dashboard", "Customer Dashboard"),
        ("quote_builder", "Quote Builder"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    product_name = models.CharField(max_length=200)
    product_slug = models.SlugField(blank=True)
    context = models.CharField(max_length=60, choices=CONTEXT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product_name} - {self.context}"
    

from .models_recommendations import *