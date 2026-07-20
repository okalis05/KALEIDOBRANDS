from django.db import models
from django.conf import settings


# Create your models here.
class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )

    company = models.CharField(
        max_length=200,
        blank=True,
    )

    phone = models.CharField(
        max_length=40,
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
    )

    country = models.CharField(
        max_length=100,
        default="United States",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.user.get_full_name() or self.user.username
    
from .models_assets import *
from .models_orders import *
from .models_artwork import *
from .models_crm import *
from .models_cart import *
from .models_addresses import *
from .models_shipping import *
from .models_support import *
from .models_returns import *
from .models_refunds import *
