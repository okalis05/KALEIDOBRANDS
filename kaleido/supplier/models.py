from django.db import models

# Create your models here.
class Supplier(models.Model):
    name = models.CharField(max_length=200)
    supplier_code = models.CharField(max_length=50, unique=True)

    api_enabled = models.BooleanField(default=False)

    api_url = models.URLField(blank=True)

    api_key = models.CharField(max_length=300, blank=True)

    ftp_host = models.CharField(max_length=200, blank=True)

    ftp_username = models.CharField(max_length=200, blank=True)

    ftp_password = models.CharField(max_length=200, blank=True)

    active = models.BooleanField(default=True)

    last_sync = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name