from django.conf import settings
from django.db import models


class BrandAsset(models.Model):
    ASSET_TYPES = [
        ("logo", "Logo"),
        ("artwork", "Artwork"),
        ("brand_guide", "Brand Guide"),
        ("font", "Font"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_assets",
    )

    title = models.CharField(max_length=160)
    asset_type = models.CharField(max_length=40, choices=ASSET_TYPES, default="logo")
    file = models.FileField(upload_to="brand_assets/")
    notes = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title