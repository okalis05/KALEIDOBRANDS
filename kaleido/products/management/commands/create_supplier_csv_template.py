import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from products.services.csv_importer import ALL_COLUMNS


class Command(BaseCommand):
    help = "Create a blank supplier CSV import template."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="data/supplier_import_template.csv",
            help="Output path for the CSV template.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=ALL_COLUMNS)
            writer.writeheader()

        self.stdout.write(
            self.style.SUCCESS(
                f"Supplier CSV template created: {output_path}"
            )
        )