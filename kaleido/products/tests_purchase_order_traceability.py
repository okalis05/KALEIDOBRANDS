from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Order, OrderItem
from products.models import (
    Product,
    Supplier,
    SupplierListing,
    SupplierPurchaseOrder,
    SupplierPurchaseOrderItem,
)
from products.services.purchase_orders import (
    create_purchase_orders_from_order,
)


User = get_user_model()


class PurchaseOrderTraceabilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="marketplace-test",
            email="marketplace@example.com",
            password="test-password",
        )

        self.supplier = Supplier.objects.create(
            name="Primary Supplier",
        )

        self.product = Product.objects.create(
            name="Custom Polo",
            sku="POLO-001",
        )

        self.listing = SupplierListing.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="SUP-POLO-001",
            supplier_product_id="SUPPLIER-123",
            supplier_product_name="Supplier Custom Polo",
            unit_cost=Decimal("18.50"),
            setup_cost=Decimal("25.00"),
            minimum_order_quantity=12,
            is_active=True,
)

        self.order = Order.objects.create(
            customer=self.user,
            order_number="KB-ORDER-001",
            payment_status="paid",
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            supplier_listing=self.listing,
            product_name="Custom Polo",
            sku="POLO-001",
            quantity=4,
            unit_price=Decimal("25.00"),
            line_total=Decimal("100.00"),
            supplier_name_snapshot=self.supplier.name,
            supplier_sku_snapshot="SUP-POLO-001",
            supplier_product_id_snapshot="SUPPLIER-123",
            supplier_product_name_snapshot="Supplier Custom Polo",
            supplier_unit_cost_snapshot=Decimal("18.50"),
            supplier_setup_cost_snapshot=Decimal("25.00"),
            supplier_minimum_quantity_snapshot=12,
        )

    def test_purchase_order_is_created_for_supplier(self):
        purchase_orders = create_purchase_orders_from_order(
            self.order
        )

        self.assertEqual(len(purchase_orders), 1)

        purchase_order = purchase_orders[0]

        self.assertEqual(
            purchase_order.supplier,
            self.supplier,
        )

        self.assertEqual(
            purchase_order.customer_order,
            self.order,
        )

    def test_purchase_order_item_keeps_order_item_reference(self):
        create_purchase_orders_from_order(self.order)

        purchase_order_item = (
            SupplierPurchaseOrderItem.objects.get()
        )

        self.assertEqual(
            purchase_order_item.order_item,
            self.order_item,
        )

    def test_purchase_order_item_keeps_listing_reference(self):
        create_purchase_orders_from_order(self.order)

        purchase_order_item = (
            SupplierPurchaseOrderItem.objects.get()
        )

        self.assertEqual(
            purchase_order_item.supplier_listing,
            self.listing,
        )

    def test_supplier_snapshots_are_copied(self):
        create_purchase_orders_from_order(self.order)

        purchase_order_item = (
            SupplierPurchaseOrderItem.objects.get()
        )

        self.assertEqual(
            purchase_order_item.supplier_sku,
            "SUP-POLO-001",
        )

        self.assertEqual(
            purchase_order_item.supplier_product_id_snapshot,
            "SUPPLIER-123",
        )

        self.assertEqual(
            purchase_order_item.supplier_product_name_snapshot,
            "Supplier Custom Polo",
        )

        self.assertEqual(
            purchase_order_item.unit_cost,
            Decimal("18.50"),
        )

        self.assertEqual(
            purchase_order_item.setup_cost_snapshot,
            Decimal("25.00"),
        )

        self.assertEqual(
            purchase_order_item.minimum_quantity_snapshot,
            12,
        )

    def test_line_total_is_calculated(self):
        create_purchase_orders_from_order(self.order)

        purchase_order_item = (
            SupplierPurchaseOrderItem.objects.get()
        )

        self.assertEqual(
            purchase_order_item.line_total,
            Decimal("74.00"),
        )

    def test_existing_purchase_orders_are_returned(self):
        first_result = create_purchase_orders_from_order(
            self.order
        )

        second_result = create_purchase_orders_from_order(
            self.order
        )

        self.assertEqual(
            SupplierPurchaseOrder.objects.count(),
            1,
        )

        self.assertEqual(
            first_result[0],
            second_result[0],
        )

    def test_unpaid_order_is_rejected(self):
        self.order.payment_status = "pending"
        self.order.save(update_fields=["payment_status"])

        with self.assertRaises(ValueError):
            create_purchase_orders_from_order(
                self.order
            )

    def test_snapshot_survives_listing_deletion(self):
        create_purchase_orders_from_order(self.order)

        purchase_order_item = (
            SupplierPurchaseOrderItem.objects.get()
        )

        self.listing.delete()

        purchase_order_item.refresh_from_db()

        self.assertIsNone(
            purchase_order_item.supplier_listing
        )

        self.assertEqual(
            purchase_order_item.supplier_sku,
            "SUP-POLO-001",
        )

        self.assertEqual(
            purchase_order_item.supplier_product_id_snapshot,
            "SUPPLIER-123",
        )