from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import ReturnRequest


class Command(BaseCommand):
    help = (
        "Send alerts for unassigned, overdue, and incomplete "
        "return requests."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default=getattr(
                settings,
                "RETURN_NOTIFICATION_EMAIL",
                "sales@kaleidobrands.com",
            ),
        )

    def handle(self, *args, **options):
        recipient = options["to"]
        now = timezone.now()

        active_statuses = [
            "submitted",
            "under_review",
            "information_requested",
            "approved",
            "awaiting_return",
            "item_received",
            "replacement_processing",
            "refund_processing",
        ]

        unassigned = ReturnRequest.objects.filter(
            status__in=active_statuses,
            assigned_to__isnull=True,
        )

        awaiting_review = ReturnRequest.objects.filter(
            status="submitted",
            requested_at__lt=(
                now - timedelta(hours=24)
            ),
        )

        approved_without_rma = ReturnRequest.objects.filter(
            status="approved",
            rma_number__isnull=True,
        )

        overdue_returns = ReturnRequest.objects.filter(
            status="awaiting_return",
            approved_at__lt=(
                now - timedelta(days=14)
            ),
        )

        received_waiting_resolution = ReturnRequest.objects.filter(
            status="item_received",
            received_at__lt=(
                now - timedelta(days=2)
            ),
        )

        replacement_waiting = ReturnRequest.objects.filter(
            status="replacement_processing",
            replacement_shipment__isnull=True,
        )

        if not any(
            [
                unassigned.exists(),
                awaiting_review.exists(),
                approved_without_rma.exists(),
                overdue_returns.exists(),
                received_waiting_resolution.exists(),
                replacement_waiting.exists(),
            ]
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "No return operations alerts found."
                )
            )
            return

        lines = [
            "KaleidoBrands Return Operations Alert",
            "",
        ]

        groups = [
            ("UNASSIGNED REQUESTS", unassigned),
            ("AWAITING REVIEW OVER 24 HOURS", awaiting_review),
            ("APPROVED WITHOUT RMA", approved_without_rma),
            ("OVERDUE RETURNS", overdue_returns),
            (
                "RECEIVED ITEMS AWAITING RESOLUTION",
                received_waiting_resolution,
            ),
            (
                "REPLACEMENTS WITHOUT SHIPMENTS",
                replacement_waiting,
            ),
        ]

        for title, queryset in groups:
            if not queryset.exists():
                continue

            lines.extend(
                [
                    title,
                    "-" * 45,
                ]
            )

            for return_request in queryset:
                lines.append(
                    (
                        f"{return_request.request_number} | "
                        f"Order {return_request.order.order_number} | "
                        f"{return_request.get_status_display()}"
                    )
                )

            lines.append("")

        try:
            EmailMessage(
                subject=(
                    "KaleidoBrands Return Operations Alert"
                ),
                body="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)

        except Exception as error:
            self.stderr.write(
                self.style.WARNING(
                    f"Return alert could not be sent: {error}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Return alert sent to {recipient}."
            )
        )