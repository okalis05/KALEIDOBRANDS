from django.core.management.base import BaseCommand

from customers.models import Order
from products.services.order_fulfillment import (
    synchronize_customer_order_from_purchase_orders,
)


class Command(BaseCommand):
    help = "Synchronize customer order statuses from supplier purchase orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--order-id",
            type=int,
            help="Synchronize one customer order only.",
        )

    def handle(self, *args, **options):
        order_id = options.get("order_id")

        orders = Order.objects.filter(
            supplier_purchase_orders__isnull=False
        ).distinct()

        if order_id:
            orders = orders.filter(id=order_id)

        updated = 0

        for order in orders:
            previous_status = order.status

            synchronize_customer_order_from_purchase_orders(
                order
            )

            order.refresh_from_db()

            if order.status != previous_status:
                updated += 1

                self.stdout.write(
                    (
                        f"{order.order_number}: "
                        f"{previous_status} → {order.status}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Fulfillment synchronization complete. "
                f"Orders changed: {updated}."
            )
        )