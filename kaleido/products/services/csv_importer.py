import csv
from pathlib import Path

from products.services.kaeser_blair import KaeserBlairImporter


REQUIRED_COLUMNS = [
    "name",
]

OPTIONAL_COLUMNS = [
    "sku",
    "category",
    "short_description",
    "description",
    "starting_price",
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
    Imports supplier products from a CSV file.

    Required:
        name

    Optional:
        sku
        category
        short_description
        description
        starting_price
        min_quantity
        colors
        decoration_methods
        industries
        material
        dimensions
        lead_time
        setup_fee
        supplier_product_id
        supplier_url
        image_url
        gallery_urls
        catalog_name
        catalog_url
    """

    def __init__(self):
        self.importer = KaeserBlairImporter()

    def validate_file_exists(self, file_path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        if path.suffix.lower() != ".csv":
            raise ValueError("Supplier import file must be a .csv file.")

        return path

    def validate_columns(self, fieldnames):
        if not fieldnames:
            raise ValueError("CSV file has no header row.")

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in fieldnames
        ]

        if missing:
            raise ValueError(
                "CSV file is missing required columns: "
                + ", ".join(missing)
            )

    def normalize_row(self, row):
        normalized = {}

        for column in ALL_COLUMNS:
            normalized[column] = row.get(column, "")

        return normalized

    def import_csv(self, file_path):
        path = self.validate_file_exists(file_path)
        sync_log = self.importer.start_log()

        try:
            with path.open(newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)

                self.validate_columns(reader.fieldnames)

                for row in reader:
                    normalized = self.normalize_row(row)
                    self.importer.import_product_dict(
                        normalized,
                        sync_log=sync_log,
                    )

            self.importer.finish_log(
                sync_log,
                status="success",
                message="CSV import completed successfully.",
            )

            return sync_log

        except Exception as error:
            self.importer.finish_log(
                sync_log,
                status="failed",
                message=str(error),
            )
            raise