from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand

from products.models import Product


class Command(BaseCommand):
    help = "Send supplier inventory alerts for low-stock, out-of-stock, and discontinued products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            default="sales@kaleidobrands.com",
            help="Recipient for supplier inventory alerts.",
        )

    def handle(self, *args, **options):
        recipient = options["to"]

        low_stock = Product.objects.filter(
            is_active=True,
            inventory_status="low_stock",
        ).select_related("supplier_record")

        out_of_stock = Product.objects.filter(
            is_active=True,
            inventory_status="out_of_stock",
        ).select_related("supplier_record")

        discontinued = Product.objects.filter(
            inventory_status="discontinued",
        ).select_related("supplier_record")

        if not low_stock.exists() and not out_of_stock.exists() and not discontinued.exists():
            self.stdout.write(
                self.style.SUCCESS("No supplier inventory alerts found.")
            )
            return

        lines = [
            "KaleidoBrands Supplier Inventory Alert",
            "",
        ]

        if low_stock.exists():
            lines.append("LOW STOCK")
            lines.append("-" * 40)

            for product in low_stock:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU: {product.sku or 'N/A'} | "
                        f"Supplier: "
                        f"{product.supplier_record.name if product.supplier_record else 'Unknown'} | "
                        f"Inventory: {product.supplier_inventory}"
                    )
                )

            lines.append("")

        if out_of_stock.exists():
            lines.append("OUT OF STOCK")
            lines.append("-" * 40)

            for product in out_of_stock:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU: {product.sku or 'N/A'} | "
                        f"Supplier: "
                        f"{product.supplier_record.name if product.supplier_record else 'Unknown'}"
                    )
                )

            lines.append("")

        if discontinued.exists():
            lines.append("DISCONTINUED")
            lines.append("-" * 40)

            for product in discontinued:
                lines.append(
                    (
                        f"{product.name} | "
                        f"SKU: {product.sku or 'N/A'} | "
                        f"Supplier: "
                        f"{product.supplier_record.name if product.supplier_record else 'Unknown'}"
                    )
                )

        EmailMessage(
            subject="KaleidoBrands Supplier Inventory Alert",
            body="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        ).send(fail_silently=False)

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Inventory alert sent to {recipient}. "
                    f"Low stock: {low_stock.count()}, "
                    f"Out of stock: {out_of_stock.count()}, "
                    f"Discontinued: {discontinued.count()}."
                )
            )
        )