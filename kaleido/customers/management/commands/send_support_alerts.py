from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import SupportTicket


class Command(BaseCommand):
    help = (
        "Send support alerts for urgent, unassigned, "
        "and overdue tickets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default=getattr(
                settings,
                "SUPPORT_NOTIFICATION_EMAIL",
                "sales@kaleidobrands.com",
            ),
        )

    def handle(self, *args, **options):
        recipient = options["to"]
        now = timezone.now()

        open_statuses = [
            "open",
            "waiting_staff",
            "in_progress",
        ]

        urgent_tickets = (
            SupportTicket.objects
            .filter(
                status__in=open_statuses,
                priority="urgent",
            )
            .select_related(
                "customer",
                "assigned_to",
            )
        )

        unassigned_tickets = (
            SupportTicket.objects
            .filter(
                status__in=open_statuses,
                assigned_to__isnull=True,
            )
            .select_related("customer")
        )

        overdue_waiting_staff = (
            SupportTicket.objects
            .filter(
                status="waiting_staff",
                updated_at__lt=(
                    now - timedelta(hours=24)
                ),
            )
            .select_related(
                "customer",
                "assigned_to",
            )
        )

        stale_open_tickets = (
            SupportTicket.objects
            .filter(
                status__in=[
                    "open",
                    "in_progress",
                ],
                updated_at__lt=(
                    now - timedelta(days=3)
                ),
            )
            .select_related(
                "customer",
                "assigned_to",
            )
        )

        if not any(
            [
                urgent_tickets.exists(),
                unassigned_tickets.exists(),
                overdue_waiting_staff.exists(),
                stale_open_tickets.exists(),
            ]
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "No support alerts found."
                )
            )
            return

        lines = [
            "KaleidoBrands Support Operations Alert",
            "",
        ]

        if urgent_tickets.exists():
            lines.extend(
                [
                    "URGENT TICKETS",
                    "-" * 45,
                ]
            )

            for ticket in urgent_tickets:
                lines.append(
                    (
                        f"{ticket.ticket_number} | "
                        f"{ticket.subject} | "
                        f"Customer: "
                        f"{ticket.customer.email or ticket.customer.username}"
                    )
                )

            lines.append("")

        if unassigned_tickets.exists():
            lines.extend(
                [
                    "UNASSIGNED TICKETS",
                    "-" * 45,
                ]
            )

            for ticket in unassigned_tickets:
                lines.append(
                    (
                        f"{ticket.ticket_number} | "
                        f"{ticket.get_priority_display()} | "
                        f"{ticket.subject}"
                    )
                )

            lines.append("")

        if overdue_waiting_staff.exists():
            lines.extend(
                [
                    "WAITING FOR STAFF OVER 24 HOURS",
                    "-" * 45,
                ]
            )

            for ticket in overdue_waiting_staff:
                lines.append(
                    (
                        f"{ticket.ticket_number} | "
                        f"Updated: {ticket.updated_at} | "
                        f"{ticket.subject}"
                    )
                )

            lines.append("")

        if stale_open_tickets.exists():
            lines.extend(
                [
                    "STALE OPEN TICKETS",
                    "-" * 45,
                ]
            )

            for ticket in stale_open_tickets:
                lines.append(
                    (
                        f"{ticket.ticket_number} | "
                        f"Status: {ticket.get_status_display()} | "
                        f"Updated: {ticket.updated_at}"
                    )
                )

        try:
            EmailMessage(
                subject=(
                    "KaleidoBrands Support Operations Alert"
                ),
                body="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)

        except Exception as error:
            self.stderr.write(
                self.style.WARNING(
                    f"Support alert could not be sent: {error}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Support alert sent to {recipient}."
            )
        )