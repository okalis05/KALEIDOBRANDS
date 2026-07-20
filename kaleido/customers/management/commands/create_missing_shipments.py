from django.core.management.base import BaseCommand

from customers.models import Order
from customers.services.shipping import (
    create_default_shipment_for_paid_order,
)


class Command(BaseCommand):
    help = "Create missing shipments for paid customer orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--order-id",
            type=int,
            help="Create a shipment for one paid order only.",
        )

    def handle(self, *args, **options):
        order_id = options.get("order_id")

        orders = Order.objects.filter(
            payment_status="paid",
            shipments__isnull=True,
        ).distinct()

        if order_id:
            orders = orders.filter(id=order_id)

        created = 0
        failed = 0
        skipped = 0

        for order in orders:
            if not order.items.exists():
                skipped += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"{order.order_number}: skipped because the order has no items."
                    )
                )
                continue

            try:
                shipment, was_created = (
                    create_default_shipment_for_paid_order(order)
                )

            except Exception as error:
                failed += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"{order.order_number}: {error}"
                    )
                )
                continue

            if was_created:
                created += 1

                self.stdout.write(
                    f"{order.order_number}: {shipment.shipment_number}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Shipment backfill complete. "
                f"Created: {created}, "
                f"Skipped: {skipped}, "
                f"Failed: {failed}."
            )
        )