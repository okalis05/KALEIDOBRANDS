from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from products.integrations.orchestration import (
    SupplierSyncOrchestrator,
)
from products.integrations.registry import (
    get_supplier_adapter,
)
from products.models import (
    Supplier,
    SupplierSyncBatch,
)


class Command(BaseCommand):
    help = (
        "Create or resume a supplier synchronization batch."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--supplier",
            action="append",
            dest="suppliers",
            default=[],
            help=(
                "Supplier slug to synchronize. "
                "May be supplied multiple times."
            ),
        )

        parser.add_argument(
            "--operation",
            action="append",
            dest="operations",
            default=[],
            help=(
                "Adapter method or registered sync "
                "operation. May be supplied multiple "
                "times."
            ),
        )

        parser.add_argument(
            "--batch",
            dest="batch_id",
            help=(
                "Existing batch UUID to resume."
            ),
        )

        parser.add_argument(
            "--all-suppliers",
            action="store_true",
            dest="all_suppliers",
            help=(
                "Run the selected operations for all "
                "eligible suppliers."
            ),
        )

        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            dest="stop_on_error",
            help=(
                "Stop execution after the first "
                "failed job."
            ),
        )

        parser.add_argument(
            "--max-attempts",
            type=int,
            default=3,
            dest="max_attempts",
            help=(
                "Maximum execution attempts per job."
            ),
        )

        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help=(
                "Optional CSV path for CSV-backed "
                "supplier synchronization."
            ),
        )

    def handle(self, *args, **options):
        batch_id = options.get(
            "batch_id"
        )

        if batch_id:
            batch = self._get_batch(
                batch_id
            )

            batch = (
                SupplierSyncOrchestrator
                .execute_batch(
                    batch,
                    stop_on_error=options[
                        "stop_on_error"
                    ],
                    resume=True,
                )
            )

            self._print_summary(
                batch
            )
            return

        operations = (
            options.get("operations")
            or []
        )

        if not operations:
            raise CommandError(
                "Provide at least one "
                "--operation value."
            )

        suppliers = self._resolve_suppliers(
            options
        )

        if not suppliers:
            raise CommandError(
                "No eligible suppliers were found."
            )

        self._validate_operations(
            suppliers,
            operations,
        )

        batch_metadata = {
            "source": "management_command",
        }

        if options.get("file"):
            batch_metadata["file_path"] = str(
                options["file"]
            )

        batch = (
            SupplierSyncOrchestrator
            .create_batch(
                suppliers=suppliers,
                operations=operations,
                metadata=batch_metadata,
                max_attempts=options[
                    "max_attempts"
                ],
            )
        )

        self.stdout.write(
            (
                "Created supplier sync batch "
                f"{batch.pk} with "
                f"{batch.total_jobs} job(s)."
            )
        )

        batch = (
            SupplierSyncOrchestrator
            .execute_batch(
                batch,
                stop_on_error=options[
                    "stop_on_error"
                ],
            )
        )

        self._print_summary(
            batch
        )

    def _get_batch(
        self,
        batch_id,
    ):
        try:
            return (
                SupplierSyncBatch.objects.get(
                    pk=batch_id
                )
            )

        except (
            ValueError,
            SupplierSyncBatch.DoesNotExist,
        ) as error:
            raise CommandError(
                "The requested supplier sync "
                "batch does not exist."
            ) from error

    def _resolve_suppliers(
        self,
        options,
    ):
        suppliers = Supplier.objects.filter(
            is_active=True
        )

        if options.get(
            "all_suppliers"
        ):
            return list(
                suppliers
            )

        supplier_slugs = (
            options.get("suppliers")
            or []
        )

        if not supplier_slugs:
            raise CommandError(
                "Provide at least one "
                "--supplier value or use "
                "--all-suppliers."
            )

        suppliers = suppliers.filter(
            slug__in=supplier_slugs
        )

        found_slugs = set(
            suppliers.values_list(
                "slug",
                flat=True,
            )
        )

        missing_slugs = sorted(
            set(supplier_slugs)
            - found_slugs
        )

        if missing_slugs:
            raise CommandError(
                "Unknown or inactive supplier "
                "slug(s): "
                + ", ".join(
                    missing_slugs
                )
            )

        return list(
            suppliers
        )

    def _validate_operations(
        self,
        suppliers,
        operations,
    ):
        unsupported = []

        for supplier in suppliers:
            try:
                adapter = (
                    get_supplier_adapter(
                        supplier
                    )
                )

            except Exception as error:
                raise CommandError(
                    "Unable to load the adapter "
                    f"for supplier "
                    f"'{supplier.slug}': {error}"
                ) from error

            capability_method = getattr(
                adapter,
                "supported_sync_operations",
                None,
            )

            if not callable(
                capability_method
            ):
                continue

            supported_operations = set(
                capability_method()
            )

            for operation in operations:
                if (
                    operation
                    not in supported_operations
                ):
                    unsupported.append(
                        (
                            supplier.slug,
                            operation,
                        )
                    )

        if not unsupported:
            return

        details = ", ".join(
            (
                f"{supplier_slug}:"
                f"{operation}"
            )
            for (
                supplier_slug,
                operation,
            ) in unsupported
        )

        raise CommandError(
            "One or more supplier adapters "
            "do not support the requested "
            f"operations: {details}"
        )

    def _print_summary(
        self,
        batch,
    ):
        style = (
            self.style.SUCCESS
            if batch.status
            == SupplierSyncBatch.STATUS_COMPLETED
            else self.style.WARNING
        )

        self.stdout.write(
            style(
                (
                    f"Batch {batch.pk}: "
                    f"status={batch.status}, "
                    f"completed="
                    f"{batch.completed_jobs}/"
                    f"{batch.total_jobs}, "
                    f"successful="
                    f"{batch.successful_jobs}, "
                    f"failed="
                    f"{batch.failed_jobs}, "
                    f"skipped="
                    f"{batch.skipped_jobs}"
                )
            )
        )