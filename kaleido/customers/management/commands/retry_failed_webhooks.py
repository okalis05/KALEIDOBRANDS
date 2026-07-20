from django.core.management.base import BaseCommand

from customers.webhooks.refunds import (
    retry_failed_webhooks,
)


class Command(BaseCommand):
    help = "Retry failed Stripe refund webhooks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum failed webhooks to retry.",
        )

    def handle(self, *args, **options):
        processed = retry_failed_webhooks(
            limit=options["limit"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully retried {processed} webhook(s)."
            )
        )