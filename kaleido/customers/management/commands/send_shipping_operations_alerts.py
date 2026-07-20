from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import Order, Shipment


class Command(BaseCommand):
    help = (
        "Send shipping operations alerts for unshipped orders, "
        "missing tracking, delivery exceptions, and late shipments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default=getattr(
                settings,
                "SUPPLIER_ALERT_EMAIL",
                "sales@kaleidobrands.com",
            ),
        )

    def handle(self, *args, **options):
        recipient = options["to"]
        today = timezone.localdate()

        paid_orders_without_shipments = (
            Order.objects
            .filter(
                payment_status="paid",
                shipments__isnull=True,
            )
            .distinct()
        )

        shipments_missing_tracking = (
            Shipment.objects
            .filter(
                status__in=[
                    "label_created",
                    "ready",
                    "in_transit",
                    "out_for_delivery",
                ],
                tracking_number="",
            )
            .select_related("order")
        )

        delivery_exceptions = (
            Shipment.objects
            .filter(status="exception")
            .select_related("order")
        )

        late_shipments = (
            Shipment.objects
            .filter(
                status__in=[
                    "pending",
                    "label_created",
                    "ready",
                    "in_transit",
                    "out_for_delivery",
                ],
                estimated_delivery_date__lt=today,
            )
            .select_related("order")
        )

        stale_pending_cutoff = timezone.now() - timedelta(days=3)

        stale_pending_shipments = (
            Shipment.objects
            .filter(
                status="pending",
                created_at__lt=stale_pending_cutoff,
            )
            .select_related("order")
        )

        if not any(
            [
                paid_orders_without_shipments.exists(),
                shipments_missing_tracking.exists(),
                delivery_exceptions.exists(),
                late_shipments.exists(),
                stale_pending_shipments.exists(),
            ]
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "No shipping operations alerts found."
                )
            )
            return

        lines = [
            "KaleidoBrands Shipping Operations Alert",
            "",
        ]

        if paid_orders_without_shipments.exists():
            lines.extend(
                [
                    "PAID ORDERS WITHOUT SHIPMENTS",
                    "-" * 45,
                ]
            )

            for order in paid_orders_without_shipments:
                lines.append(
                    (
                        f"{order.order_number} | "
                        f"Customer: {order.customer.email or order.customer.username} | "
                        f"Paid: {order.paid_at or 'Unknown'}"
                    )
                )

            lines.append("")

        if shipments_missing_tracking.exists():
            lines.extend(
                [
                    "SHIPMENTS MISSING TRACKING",
                    "-" * 45,
                ]
            )

            for shipment in shipments_missing_tracking:
                lines.append(
                    (
                        f"{shipment.shipment_number} | "
                        f"Order: {shipment.order.order_number} | "
                        f"Status: {shipment.get_status_display()}"
                    )
                )

            lines.append("")

        if delivery_exceptions.exists():
            lines.extend(
                [
                    "DELIVERY EXCEPTIONS",
                    "-" * 45,
                ]
            )

            for shipment in delivery_exceptions:
                lines.append(
                    (
                        f"{shipment.shipment_number} | "
                        f"Order: {shipment.order.order_number} | "
                        f"Carrier: {shipment.carrier or 'Unknown'}"
                    )
                )

            lines.append("")

        if late_shipments.exists():
            lines.extend(
                [
                    "LATE SHIPMENTS",
                    "-" * 45,
                ]
            )

            for shipment in late_shipments:
                lines.append(
                    (
                        f"{shipment.shipment_number} | "
                        f"Order: {shipment.order.order_number} | "
                        f"Expected: {shipment.estimated_delivery_date} | "
                        f"Status: {shipment.get_status_display()}"
                    )
                )

            lines.append("")

        if stale_pending_shipments.exists():
            lines.extend(
                [
                    "STALE PENDING SHIPMENTS",
                    "-" * 45,
                ]
            )

            for shipment in stale_pending_shipments:
                lines.append(
                    (
                        f"{shipment.shipment_number} | "
                        f"Order: {shipment.order.order_number} | "
                        f"Created: {shipment.created_at:%Y-%m-%d}"
                    )
                )

        try:
            EmailMessage(
                subject="KaleidoBrands Shipping Operations Alert",
                body="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)

        except Exception as error:
            self.stderr.write(
                self.style.WARNING(
                    f"Shipping operations alert could not be sent: {error}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Shipping operations alert sent to {recipient}."
            )
        )