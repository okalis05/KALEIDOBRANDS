from django.core.management.base import BaseCommand

from products.integrations.kaeser_blair import KaeserBlairImporter


class Command(BaseCommand):
    help = "Create the Kaeser & Blair supplier record."

    def handle(self, *args, **options):
        importer = KaeserBlairImporter()

        self.stdout.write(
            self.style.SUCCESS(
                f"Supplier ready: {importer.supplier.name}"
            )
        )