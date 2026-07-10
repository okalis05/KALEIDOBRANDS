from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import Order


class Command(BaseCommand):
    help = "Send shipping notification emails for shipped orders."

    def handle(self, *args, **options):
        orders = Order.objects.filter(
            status="shipped",
            shipping_email_sent=False,
            tracking_number__isnull=False,
        ).exclude(
            tracking_number="",
        )

        sent = 0

        for order in orders:
            tracking = order.tracking_url() or order.tracking_number

            body = f"""
Your KaleidoBrands order has shipped.

Order Number: {order.order_number}
Carrier: {order.carrier or "Carrier not specified"}
Tracking: {tracking}
Estimated Delivery: {order.estimated_delivery or "TBD"}

Thank you for choosing KaleidoBrands.
"""

            email = EmailMessage(
                subject=f"Your KaleidoBrands Order Has Shipped - {order.order_number}",
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[order.customer.email],
            )

            email.send(fail_silently=False)

            order.shipping_email_sent = True
            order.shipping_email_sent_at = timezone.now()
            order.save(update_fields=["shipping_email_sent", "shipping_email_sent_at"])

            sent += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Shipping notifications sent: {sent}"
            )
        )