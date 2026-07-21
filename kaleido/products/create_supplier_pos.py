from django.core.management.base import BaseCommand, CommandError

from customers.models import Order
from products.services.purchase_orders import create_purchase_orders_from_order


class Command(BaseCommand):
    help = "Create supplier purchase orders from a paid customer order."

    def add_arguments(self, parser):
        parser.add_argument(
            "order_id",
            type=int,
            help="Customer order ID.",
        )

    def handle(self, *args, **options):
        order_id = options["order_id"]

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist as error:
            raise CommandError(f"Order {order_id} was not found.") from error

        existing = order.supplier_purchase_orders.exists()

        if existing:
            raise CommandError(
                f"Supplier purchase orders already exist for {order.order_number}."
            )

        try:
            purchase_orders = create_purchase_orders_from_order(order)
        except ValueError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(purchase_orders)} purchase order(s) "
                f"for {order.order_number}."
            )
        )