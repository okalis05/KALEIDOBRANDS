from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from products.services.supplier_sync import (
    KaeserBlairCSVSyncService,
)


class Command(BaseCommand):
    help = (
        "Synchronize Kaeser & Blair supplier "
        "products from a CSV file."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help=(
                "Supplier CSV path. Defaults to "
                "KAESER_BLAIR_CSV_PATH or "
                "data/sample_kaeser_blair_products.csv."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate the CSV file without "
                "importing or updating products."
            ),
        )

        parser.add_argument(
            "--inventory-only",
            action="store_true",
            help=(
                "Update inventory and supplier "
                "pricing without importing new products."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        service = KaeserBlairCSVSyncService(
            file_path=options["file"],
        )

        try:
            if options["dry_run"]:
                path = service.validate()

                self.stdout.write(
                    self.style.SUCCESS(
                        "Supplier sync dry-run passed: "
                        f"{path}"
                    )
                )

                return

            if options["inventory_only"]:
                result = (
                    service.sync_inventory()
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        "Supplier inventory sync complete. "
                        f"Processed: {result.processed}, "
                        f"Updated: {result.updated}, "
                        f"Skipped: {result.skipped}, "
                        f"Failed: {result.failed}"
                    )
                )

                return

            result = service.sync_catalog()

        except (
            FileNotFoundError,
            ValueError,
        ) as error:
            raise CommandError(
                str(error)
            ) from error

        except Exception as error:
            raise CommandError(
                "Supplier sync failed: "
                f"{error}"
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                "Supplier sync complete. "
                f"Processed: {result.processed}, "
                f"Created: {result.created}, "
                f"Updated: {result.updated}, "
                f"Failed: {result.failed}"
            )
        )