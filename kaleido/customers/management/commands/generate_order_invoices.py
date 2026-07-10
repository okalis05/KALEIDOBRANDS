from django.core.management.base import BaseCommand

from customers.models import Order
from customers.services.order_invoice import generate_order_invoice_pdf


class Command(BaseCommand):
    help = "Generate invoice PDFs for orders that do not have one."

    def handle(self, *args, **options):
        orders = Order.objects.filter(invoice_pdf="")

        generated = 0

        for order in orders:
            generate_order_invoice_pdf(order)
            generated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Order invoices generated: {generated}"
            )
        )