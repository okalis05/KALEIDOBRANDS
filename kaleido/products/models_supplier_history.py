from django.db import models


class SupplierPriceHistory(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="supplier_price_history",
    )

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="price_history",
    )

    previous_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    new_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.product.name}: {self.previous_price} → {self.new_price}"


class SupplierInventoryHistory(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="supplier_inventory_history",
    )

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_history",
    )

    previous_quantity = models.IntegerField(
        null=True,
        blank=True,
    )

    new_quantity = models.IntegerField(
        null=True,
        blank=True,
    )

    previous_status = models.CharField(
        max_length=30,
        blank=True,
    )

    new_status = models.CharField(
        max_length=30,
        blank=True,
    )

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.product.name}: inventory {self.new_quantity}"