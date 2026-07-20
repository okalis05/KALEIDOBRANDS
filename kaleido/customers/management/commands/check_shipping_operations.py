from django.core.management.base import BaseCommand

from customers.models import Order, Shipment


class Command(BaseCommand):
    help = "Run a shipping and fulfillment health check."

    def handle(self, *args, **options):
        total_shipments = Shipment.objects.count()

        pending = Shipment.objects.filter(
            status="pending"
        ).count()

        in_transit = Shipment.objects.filter(
            status__in=[
                "in_transit",
                "out_for_delivery",
            ]
        ).count()

        delivered = Shipment.objects.filter(
            status="delivered"
        ).count()

        exceptions = Shipment.objects.filter(
            status="exception"
        ).count()

        with_tracking = Shipment.objects.exclude(
            tracking_number=""
        ).count()

        with_packing_slips = Shipment.objects.exclude(
            packing_slip=""
        ).count()

        paid_orders_without_shipments = (
            Order.objects
            .filter(
                payment_status="paid",
                shipments__isnull=True,
            )
            .distinct()
            .count()
        )

        shipments_without_items = Shipment.objects.filter(
            items__isnull=True
        ).distinct().count()

        self.stdout.write(
            "KaleidoBrands Shipping Operations Check"
        )
        self.stdout.write("-" * 45)

        self.stdout.write(
            f"Total shipments: {total_shipments}"
        )
        self.stdout.write(
            f"Pending: {pending}"
        )
        self.stdout.write(
            f"In transit: {in_transit}"
        )
        self.stdout.write(
            f"Delivered: {delivered}"
        )
        self.stdout.write(
            f"Exceptions: {exceptions}"
        )
        self.stdout.write(
            f"With tracking: {with_tracking}"
        )
        self.stdout.write(
            f"With packing slips: {with_packing_slips}"
        )

        self.stdout.write("")
        self.stdout.write("Warnings")
        self.stdout.write("-" * 45)

        self.stdout.write(
            (
                "Paid orders without shipments: "
                f"{paid_orders_without_shipments}"
            )
        )

        self.stdout.write(
            (
                "Shipments without items: "
                f"{shipments_without_items}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Shipping operations health check completed."
            )
        )