from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from products.services.csv_importer import ProductCSVImporter


class Command(BaseCommand):
    help = "Scheduled supplier sync command for KaleidoBrands."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/sample_kaeser_blair_products.csv",
            help="Supplier CSV file path.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate without importing.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        dry_run = options["dry_run"]

        if not file_path.exists():
            raise CommandError(f"Supplier file not found: {file_path}")

        importer = ProductCSVImporter()

        if dry_run:
            importer.validate_file_exists(file_path)

            import csv
            with file_path.open(newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)
                importer.validate_columns(reader.fieldnames)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Supplier sync dry-run passed: {file_path}"
                )
            )
            return

        sync_log = importer.import_csv(file_path)

        self.stdout.write(
            self.style.SUCCESS(
                "Supplier sync complete. "
                f"Created: {sync_log.products_created}, "
                f"Updated: {sync_log.products_updated}, "
                f"Failed: {sync_log.products_failed}"
            )
        )