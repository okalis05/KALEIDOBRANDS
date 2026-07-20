from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Run supplier synchronization and supplier/shipping "
        "operations maintenance."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=settings.SUPPLIER_SYNC_FILE,
            help="Supplier CSV file to synchronize.",
        )

        parser.add_argument(
            "--alert-to",
            type=str,
            default=settings.SUPPLIER_ALERT_EMAIL,
            help="Alert recipient.",
        )

        parser.add_argument(
            "--skip-alerts",
            action="store_true",
            help="Run synchronization without sending alerts.",
        )

    def handle(self, *args, **options):
        supplier_file = options["file"]
        recipient = options["alert_to"]
        skip_alerts = options["skip_alerts"]

        self.stdout.write("Starting supplier synchronization...")

        call_command(
            "sync_suppliers",
            file=supplier_file,
        )

        if not skip_alerts:
            self.stdout.write(
                "Checking supplier inventory alerts..."
            )

            call_command(
                "send_inventory_alerts",
                to=recipient,
            )

            self.stdout.write(
                "Checking supplier operations alerts..."
            )

            call_command(
                "send_supplier_operations_alerts",
                to=recipient,
            )

            self.stdout.write(
                "Checking shipping operations alerts..."
            )

            call_command(
                "send_shipping_operations_alerts",
                to=recipient,
            )

            self.stdout.write(
                "Checking support operations alerts..."
            )

            call_command(
                "send_support_alerts",
                to=recipient,
            )

            self.stdout.write(
                "Checking return operations alerts..."
            )

            call_command(
                "send_return_alerts",
                to=recipient,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Supplier maintenance completed."
            )
        )