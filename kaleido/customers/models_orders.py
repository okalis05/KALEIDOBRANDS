from django.conf import settings
from django.db import models
from products.models import Quote


class Order(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("artwork", "Artwork Approval"),
        ("production", "In Production"),
        ("quality", "Quality Control"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    quote = models.ForeignKey(
        Quote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    order_number = models.CharField(
        max_length=30,
        unique=True,
    )

    company = models.CharField(
        max_length=200,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    shipping = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    invoice_pdf = models.FileField(
        upload_to="orders/invoices/",
        blank=True,
        null=True,
    )

    tracking_number = models.CharField(
        max_length=100,
        blank=True,
    )

    carrier = models.CharField(
        max_length=80,
        blank=True,
    )

    estimated_delivery = models.DateField(
        null=True,
        blank=True,
    )

    shipping_email_sent = models.BooleanField(
        default=False
    
    )
    shipping_email_sent_at = models.DateTimeField(
        null=True, blank=True
    )


    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
    )

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def tracking_url(self):
        if not self.tracking_number:
            return ""

        carrier = (self.carrier or "").lower()

        if "ups" in carrier:
            return f"https://www.ups.com/track?tracknum={self.tracking_number}"

        if "fedex" in carrier:
            return f"https://www.fedex.com/fedextrack/?trknbr={self.tracking_number}"

        if "usps" in carrier:
            return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={self.tracking_number}"

        return ""

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number
    
    
    
class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product_name = models.CharField(max_length=200)

    sku = models.CharField(
        max_length=80,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    decoration = models.CharField(
        max_length=150,
        blank=True,
    )

    color = models.CharField(
        max_length=100,
        blank=True,
    )

    def __str__(self):
        return self.product_name