import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from products.models import (
    Category,
    Product,
    Supplier,
    SupplierCatalog,
)


class Command(BaseCommand):
    help = "Import or update HPG / Kaeser & Blair products from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the HPG catalog CSV file.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the import without saving changes.",
        )

        parser.add_argument(
            "--catalog-name",
            type=str,
            default="HPG Holiday Gift Guide 2026",
            help="Catalog name stored in KaleidoBrands.",
        )

        parser.add_argument(
            "--catalog-url",
            type=str,
            default="https://viewer.zoomcatalog.com/hpg-holiday-gift-guide-2026/",
            help="Original digital catalog URL.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(
                f"CSV file does not exist: {csv_path}"
            )

        supplier, _ = Supplier.objects.get_or_create(
            slug="hpg",
            defaults={
                "name": "HPG",
                "website": "https://www.hpgbrands.com/",
                "is_active": True,
            },
        )

        catalog, _ = SupplierCatalog.objects.get_or_create(
            supplier=supplier,
            external_id="hpg-holiday-gift-guide-2026",
            defaults={
                "name": options["catalog_name"],
                "catalog_url": options["catalog_url"],
                "year": 2026,
                "source_type": "csv",
                "is_active": True,
            },
        )

        created_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "HPG Catalog Import"
            )
        )

        self.stdout.write(
            f"File: {csv_path}"
        )

        self.stdout.write(
            f"Catalog: {catalog.name}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN ENABLED — no database changes will be saved."
                )
            )

        try:
            with open(
                csv_path,
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as csvfile:

                reader = csv.DictReader(csvfile)

                required_columns = {
                    "sku",
                    "name",
                }

                if not reader.fieldnames:
                    raise CommandError(
                        "The CSV file does not contain a header row."
                    )

                missing = required_columns - set(reader.fieldnames)

                if missing:
                    raise CommandError(
                        "Missing required CSV columns: "
                        + ", ".join(sorted(missing))
                    )

                with transaction.atomic():

                    for row_number, row in enumerate(
                        reader,
                        start=2,
                    ):

                        try:
                            sku = clean(row.get("sku"))
                            name = clean(row.get("name"))

                            if not sku or not name:
                                skipped_count += 1

                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Row {row_number}: "
                                        "missing SKU or product name. Skipped."
                                    )
                                )

                                continue

                            category = get_category(
                                clean(row.get("category"))
                            )

                            starting_price = parse_decimal(
                                row.get("starting_price")
                            )

                            supplier_price = parse_decimal(
                                row.get("supplier_price")
                            )

                            min_quantity = parse_integer(
                                row.get("min_quantity"),
                                default=1,
                            )

                            supplier_inventory = parse_optional_integer(
                                row.get("supplier_inventory")
                            )

                            slug = create_unique_slug(
                                name=name,
                                sku=sku,
                            )

                            defaults = {
                                "name": name,
                                "slug": slug,

                                "category": category,

                                "supplier": "HPG",
                                "supplier_record": supplier,
                                "catalog": catalog,

                                "supplier_sku": sku,
                                "sku": sku,
                                "supplier_product_id": (
                                    clean(
                                        row.get(
                                            "supplier_product_id"
                                        )
                                    )
                                    or sku
                                ),

                                "short_description": clean(
                                    row.get("short_description")
                                ),

                                "description": clean(
                                    row.get("description")
                                ),

                                "supplier_url": clean(
                                    row.get("supplier_url")
                                ),

                                "external_image_url": clean(
                                    row.get("image_url")
                                ),

                                "starting_price": starting_price,

                                "supplier_price": (
                                    supplier_price
                                    if supplier_price is not None
                                    else starting_price
                                ),

                                "min_quantity": min_quantity,

                                "supplier_inventory": (
                                    supplier_inventory
                                ),

                                "inventory_status": clean(
                                    row.get("inventory_status")
                                )
                                or "unknown",

                                "colors": clean(
                                    row.get("colors")
                                ),

                                "decoration_methods": clean(
                                    row.get("decoration_methods")
                                ),

                                "industries": clean(
                                    row.get("industries")
                                ),

                                "lead_time": (
                                    clean(row.get("lead_time"))
                                    or "Varies by product"
                                ),

                                "setup_fee": (
                                    clean(row.get("setup_fee"))
                                    or "Varies"
                                ),

                                "material": clean(
                                    row.get("material")
                                ),

                                "dimensions": clean(
                                    row.get("dimensions")
                                ),

                                "source": "hpg_catalog",

                                "is_active": parse_boolean(
                                    row.get("is_active"),
                                    default=True,
                                ),

                                "supplier_last_synced_at": (
                                    timezone.now()
                                ),

                                "last_synced_at": (
                                    timezone.now()
                                ),
                            }

                            product = Product.objects.filter(
                                supplier_record=supplier,
                                supplier_sku=sku,
                            ).first()

                            if product:
                                for field, value in defaults.items():
                                    setattr(
                                        product,
                                        field,
                                        value,
                                    )

                                if not dry_run:
                                    product.save()

                                updated_count += 1

                                self.stdout.write(
                                    f"UPDATED: {sku} — {name}"
                                )

                            else:
                                if not dry_run:
                                    Product.objects.create(
                                        **defaults
                                    )

                                created_count += 1

                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"CREATED: {sku} — {name}"
                                    )
                                )

                        except Exception as exc:
                            failed_count += 1

                            self.stdout.write(
                                self.style.ERROR(
                                    f"Row {row_number}: {exc}"
                                )
                            )

                    if dry_run:
                        transaction.set_rollback(True)

        except UnicodeDecodeError:
            raise CommandError(
                "The CSV could not be read as UTF-8."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Import Summary"
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )

        self.stdout.write(
            f"Skipped: {skipped_count}"
        )

        self.stdout.write(
            f"Failed: {failed_count}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No changes were saved."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "HPG catalog import complete."
                )
            )


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def parse_decimal(value):
    value = clean(value)

    if not value:
        return None

    value = (
        value
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        return Decimal(value)

    except InvalidOperation:
        return None


def parse_integer(value, default=0):
    value = clean(value)

    if not value:
        return default

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return default


def parse_optional_integer(value):
    value = clean(value)

    if not value:
        return None

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return None


def parse_boolean(value, default=True):
    value = clean(value).lower()

    if not value:
        return default

    return value in {
        "1",
        "true",
        "yes",
        "y",
        "active",
    }


def get_category(category_name):
    if not category_name:
        return None

    slug = slugify(category_name)

    category, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={
            "name": category_name,
            "is_active": True,
        },
    )

    return category


def create_unique_slug(name, sku):
    base_slug = slugify(name)

    if not base_slug:
        base_slug = slugify(sku)

    existing = Product.objects.filter(
        slug=base_slug
    ).first()

    if not existing:
        return base_slug

    if (
        existing.supplier_sku == sku
        or existing.sku == sku
    ):
        return existing.slug

    sku_slug = slugify(sku)

    candidate = f"{base_slug}-{sku_slug}"

    counter = 2

    while Product.objects.filter(
        slug=candidate
    ).exists():

        candidate = (
            f"{base_slug}-{sku_slug}-{counter}"
        )

        counter += 1

    return candidate