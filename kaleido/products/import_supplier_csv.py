from django.core.management.base import BaseCommand, CommandError

from products.services.csv_importer import ProductCSVImporter


class Command(BaseCommand):
    help = "Import Kaeser & Blair supplier products from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to the supplier CSV file.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the CSV file without importing products.",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        dry_run = options["dry_run"]

        try:
            importer = ProductCSVImporter()

            if dry_run:
                path = importer.validate_file_exists(file_path)

                with path.open(newline="", encoding="utf-8-sig") as csvfile:
                    import csv
                    reader = csv.DictReader(csvfile)
                    importer.validate_columns(reader.fieldnames)

                self.stdout.write(
                    self.style.SUCCESS(
                        "CSV validation passed. No products imported."
                    )
                )
                return

            sync_log = importer.import_csv(file_path)

        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {file_path}")

        except Exception as error:
            raise CommandError(f"Import failed: {error}")

        self.stdout.write(
            self.style.SUCCESS(
                "CSV import complete. "
                f"Created: {sync_log.products_created}, "
                f"Updated: {sync_log.products_updated}, "
                f"Failed: {sync_log.products_failed}"
            )
        )