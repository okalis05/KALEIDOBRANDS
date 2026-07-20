from django.core.management.base import BaseCommand

from products.models import (
    Product,
    Supplier,
    SupplierPurchaseOrder,
    SupplierPurchaseOrderActivity,
    SupplierSyncLog,
)


class Command(BaseCommand):
    help = "Run a Phase 6 supplier operations health check."

    def handle(self, *args, **options):
        suppliers = Supplier.objects.count()
        products = Product.objects.filter(
            supplier_record__isnull=False
        ).count()
        sync_logs = SupplierSyncLog.objects.count()
        purchase_orders = SupplierPurchaseOrder.objects.count()
        activities = SupplierPurchaseOrderActivity.objects.count()

        self.stdout.write("KaleidoBrands Supplier Operations Check")
        self.stdout.write("-" * 45)
        self.stdout.write(f"Suppliers: {suppliers}")
        self.stdout.write(f"Supplier products: {products}")
        self.stdout.write(f"Sync logs: {sync_logs}")
        self.stdout.write(f"Purchase orders: {purchase_orders}")
        self.stdout.write(f"PO activities: {activities}")

        missing_supplier = Product.objects.filter(
            supplier_record__isnull=True,
            is_active=True,
        ).count()

        missing_inventory = Product.objects.filter(
            supplier_record__isnull=False,
            supplier_inventory__isnull=True,
        ).count()

        missing_price = Product.objects.filter(
            supplier_record__isnull=False,
            supplier_price__isnull=True,
        ).count()

        unassigned_pos = SupplierPurchaseOrder.objects.filter(
            supplier__isnull=True
        ).count()

        self.stdout.write("")
        self.stdout.write("Warnings")
        self.stdout.write("-" * 45)
        self.stdout.write(
            f"Active products without supplier: {missing_supplier}"
        )
        self.stdout.write(
            f"Supplier products without inventory: {missing_inventory}"
        )
        self.stdout.write(
            f"Supplier products without supplier price: {missing_price}"
        )
        self.stdout.write(
            f"Unassigned purchase orders: {unassigned_pos}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Supplier operations health check completed."
            )
        )