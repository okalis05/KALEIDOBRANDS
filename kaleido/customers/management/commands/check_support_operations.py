from django.core.management.base import BaseCommand

from customers.models import SupportTicket


class Command(BaseCommand):
    help = "Run a support operations health check."

    def handle(self, *args, **options):
        total = SupportTicket.objects.count()

        open_count = SupportTicket.objects.filter(
            status="open"
        ).count()

        waiting_staff = SupportTicket.objects.filter(
            status="waiting_staff"
        ).count()

        waiting_customer = SupportTicket.objects.filter(
            status="waiting_customer"
        ).count()

        in_progress = SupportTicket.objects.filter(
            status="in_progress"
        ).count()

        resolved = SupportTicket.objects.filter(
            status="resolved"
        ).count()

        closed = SupportTicket.objects.filter(
            status="closed"
        ).count()

        urgent = SupportTicket.objects.filter(
            priority="urgent",
        ).exclude(
            status__in=[
                "resolved",
                "closed",
            ]
        ).count()

        unassigned = SupportTicket.objects.filter(
            assigned_to__isnull=True,
        ).exclude(
            status__in=[
                "resolved",
                "closed",
            ]
        ).count()

        without_messages = SupportTicket.objects.filter(
            messages__isnull=True
        ).distinct().count()

        self.stdout.write(
            "KaleidoBrands Support Operations Check"
        )
        self.stdout.write("-" * 45)

        self.stdout.write(
            f"Total tickets: {total}"
        )
        self.stdout.write(
            f"Open: {open_count}"
        )
        self.stdout.write(
            f"Waiting for staff: {waiting_staff}"
        )
        self.stdout.write(
            f"Waiting for customer: {waiting_customer}"
        )
        self.stdout.write(
            f"In progress: {in_progress}"
        )
        self.stdout.write(
            f"Resolved: {resolved}"
        )
        self.stdout.write(
            f"Closed: {closed}"
        )

        self.stdout.write("")
        self.stdout.write("Warnings")
        self.stdout.write("-" * 45)

        self.stdout.write(
            f"Urgent active tickets: {urgent}"
        )
        self.stdout.write(
            f"Unassigned active tickets: {unassigned}"
        )
        self.stdout.write(
            f"Tickets without messages: {without_messages}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Support operations health check completed."
            )
        )