from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from products.models import (
    Product,
    Supplier,
    SupplierPurchaseOrder,
)


class Command(BaseCommand):
    help = "Send supplier operations alerts for aging POs, stale syncs, and inventory risks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default=getattr(
                settings,
                "SUPPLIER_ALERT_EMAIL",
                "sales@kaleidobrands.com",
            ),
        )

    def handle(self, *args, **options):
        recipient = options["to"]
        now = timezone.now()

        aging_cutoff = now - timedelta(days=7)
        stale_sync_cutoff = now - timedelta(hours=48)

        aging_pos = SupplierPurchaseOrder.objects.filter(
            status__in=[
                "draft",
                "ready",
                "sent",
                "confirmed",
                "in_production",
                "shipped",
            ],
            created_at__lt=aging_cutoff,
        ).select_related(
            "supplier",
            "customer_order",
        )

        stale_suppliers = Supplier.objects.filter(
            is_active=True,
            last_synced_at__lt=stale_sync_cutoff,
        )

        never_synced_suppliers = Supplier.objects.filter(
            is_active=True,
            last_synced_at__isnull=True,
        )

        low_stock = Product.objects.filter(
            is_active=True,
            inventory_status="low_stock",
        )

        out_of_stock = Product.objects.filter(
            is_active=True,
            inventory_status="out_of_stock",
        )

        discontinued = Product.objects.filter(
            inventory_status="discontinued",
        )

        if not any(
            [
                aging_pos.exists(),
                stale_suppliers.exists(),
                never_synced_suppliers.exists(),
                low_stock.exists(),
                out_of_stock.exists(),
                discontinued.exists(),
            ]
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "No supplier operations alerts found."
                )
            )
            return

        lines = [
            "KaleidoBrands Supplier Operations Alert",
            "",
        ]

        if aging_pos.exists():
            lines.extend(
                [
                    "AGING PURCHASE ORDERS",
                    "-" * 40,
                ]
            )

            for po in aging_pos:
                lines.append(
                    (
                        f"{po.po_number} | "
                        f"{po.supplier.name if po.supplier else 'Unassigned'} | "
                        f"{po.get_status_display()} | "
                        f"Created {po.created_at:%Y-%m-%d}"
                    )
                )

            lines.append("")

        if never_synced_suppliers.exists():
            lines.extend(
                [
                    "SUPPLIERS NEVER SYNCED",
                    "-" * 40,
                ]
            )

            for supplier in never_synced_suppliers:
                lines.append(supplier.name)

            lines.append("")

        if stale_suppliers.exists():
            lines.extend(
                [
                    "STALE SUPPLIER SYNCS",
                    "-" * 40,
                ]
            )

            for supplier in stale_suppliers:
                lines.append(
                    (
                        f"{supplier.name} | "
                        f"Last sync: {supplier.last_synced_at}"
                    )
                )

            lines.append("")

        if low_stock.exists():
            lines.extend(
                [
                    "LOW STOCK",
                    "-" * 40,
                ]
            )

            for product in low_stock:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU {product.sku or 'N/A'} | "
                        f"Inventory {product.supplier_inventory}"
                    )
                )

            lines.append("")

        if out_of_stock.exists():
            lines.extend(
                [
                    "OUT OF STOCK",
                    "-" * 40,
                ]
            )

            for product in out_of_stock:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU {product.sku or 'N/A'}"
                    )
                )

            lines.append("")

        if discontinued.exists():
            lines.extend(
                [
                    "DISCONTINUED PRODUCTS",
                    "-" * 40,
                ]
            )

            for product in discontinued:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU {product.sku or 'N/A'}"
                    )
                )

        try:
            EmailMessage(
                subject="KaleidoBrands Supplier Operations Alert",
                body="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            ).send(fail_silently=False)

        except Exception as error:
            self.stderr.write(
                self.style.WARNING(
                    f"Supplier operations alert could not be sent: {error}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Supplier operations alert sent to {recipient}."
            )
        )