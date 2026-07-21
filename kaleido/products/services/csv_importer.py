import csv
from pathlib import Path

from products.integrations.kaeser_blair import (
    KaeserBlairImporter,
)


REQUIRED_COLUMNS = [
    "name",
]


OPTIONAL_COLUMNS = [
    "sku",
    "supplier_sku",
    "category",
    "short_description",
    "description",
    "starting_price",
    "supplier_price",
    "wholesale_price",
    "supplier_inventory",
    "inventory",
    "stock",
    "quantity_available",
    "discontinued",
    "min_quantity",
    "colors",
    "decoration_methods",
    "industries",
    "material",
    "dimensions",
    "lead_time",
    "setup_fee",
    "supplier_product_id",
    "supplier_url",
    "image_url",
    "gallery_urls",
    "catalog_name",
    "catalog_url",
]


ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class ProductCSVImporter:
    """
    Validate and import supplier product CSV files.

    The importer normalizes supported supplier columns and delegates
    product creation and updates to KaeserBlairImporter.
    """

    def __init__(self):
        self.importer = KaeserBlairImporter()

    def validate_file_exists(self, file_path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {file_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Supplier CSV path is not a file: {file_path}"
            )

        if path.suffix.lower() != ".csv":
            raise ValueError(
                "Supplier import file must be a .csv file."
            )

        return path

    def validate_columns(self, fieldnames):
        if not fieldnames:
            raise ValueError(
                "CSV file has no header row."
            )

        normalized_fieldnames = {
            str(fieldname or "").strip()
            for fieldname in fieldnames
        }

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in normalized_fieldnames
        ]

        if missing:
            raise ValueError(
                "CSV file is missing required columns: "
                + ", ".join(missing)
            )

    def normalize_row(self, row):
        """
        Return only supported columns while preserving blank values.
        """

        return {
            column: row.get(column, "")
            for column in ALL_COLUMNS
        }

    def import_csv(self, file_path):
        """
        Import a complete supplier CSV using the legacy direct-import
        workflow.

        The orchestration service uses the same normalization and product
        importer but manages checkpoints and per-row isolation itself.
        """

        path = self.validate_file_exists(
            file_path
        )

        sync_log = self.importer.start_log()

        try:
            with path.open(
                newline="",
                encoding="utf-8-sig",
            ) as csvfile:
                reader = csv.DictReader(
                    csvfile
                )

                self.validate_columns(
                    reader.fieldnames
                )

                for row in reader:
                    normalized = self.normalize_row(
                        row
                    )

                    self.importer.import_product_dict(
                        normalized,
                        sync_log=sync_log,
                    )

            self.importer.finish_log(
                sync_log,
                status="success",
                message=(
                    "CSV import completed successfully."
                ),
            )

            return sync_log

        except Exception as error:
            self.importer.finish_log(
                sync_log,
                status="failed",
                message=str(error),
            )

            raise