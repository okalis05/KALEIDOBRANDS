from django.core.management.base import BaseCommand

from customers.models import ReturnRequest


class Command(BaseCommand):
    help = "Run a return and replacement operations health check."

    def handle(self, *args, **options):
        total = ReturnRequest.objects.count()

        submitted = ReturnRequest.objects.filter(
            status="submitted"
        ).count()

        under_review = ReturnRequest.objects.filter(
            status="under_review"
        ).count()

        approved = ReturnRequest.objects.filter(
            status="approved"
        ).count()

        awaiting_return = ReturnRequest.objects.filter(
            status="awaiting_return"
        ).count()

        item_received = ReturnRequest.objects.filter(
            status="item_received"
        ).count()

        replacement_processing = ReturnRequest.objects.filter(
            status="replacement_processing"
        ).count()

        completed = ReturnRequest.objects.filter(
            status="completed"
        ).count()

        unassigned = ReturnRequest.objects.filter(
            assigned_to__isnull=True
        ).exclude(
            status__in=[
                "completed",
                "cancelled",
                "rejected",
            ]
        ).count()

        approved_without_rma = ReturnRequest.objects.filter(
            status__in=[
                "approved",
                "awaiting_return",
            ],
            rma_number__isnull=True,
        ).count()

        without_items = ReturnRequest.objects.filter(
            items__isnull=True
        ).distinct().count()

        self.stdout.write(
            "KaleidoBrands Return Operations Check"
        )
        self.stdout.write("-" * 45)

        self.stdout.write(f"Total requests: {total}")
        self.stdout.write(f"Submitted: {submitted}")
        self.stdout.write(f"Under review: {under_review}")
        self.stdout.write(f"Approved: {approved}")
        self.stdout.write(
            f"Awaiting return: {awaiting_return}"
        )
        self.stdout.write(
            f"Items received: {item_received}"
        )
        self.stdout.write(
            f"Replacement processing: {replacement_processing}"
        )
        self.stdout.write(f"Completed: {completed}")

        self.stdout.write("")
        self.stdout.write("Warnings")
        self.stdout.write("-" * 45)

        self.stdout.write(
            f"Unassigned active requests: {unassigned}"
        )
        self.stdout.write(
            f"Approved requests without RMA: {approved_without_rma}"
        )
        self.stdout.write(
            f"Requests without items: {without_items}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Return operations health check completed."
            )
        )