from django.conf import settings
from django.db import models

from products.models import Product


class Cart(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("converted", "Converted to Order"),
        ("abandoned", "Abandoned"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shopping_carts",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def subtotal(self):
        return sum(item.line_total() for item in self.items.all())

    def __str__(self):
        return f"{self.user.email or self.user.username} cart"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    product_name = models.CharField(max_length=200)

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    notes = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return self.product_name