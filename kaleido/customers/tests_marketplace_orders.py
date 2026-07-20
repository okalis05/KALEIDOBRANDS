from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Order, OrderItem
from customers.services.marketplace import (
    select_supplier_listing,
)
from products.models import (
    Category,
    Product,
    Supplier,
    SupplierCatalog,
    SupplierListing,
)


User = get_user_model()


class MarketplaceOrderTraceabilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="marketplace-customer",
            email="marketplace@example.com",
            password="test-password-123",
        )

        self.category = Category.objects.create(
            name="Drinkware",
            slug="marketplace-drinkware",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Marketplace Tumbler",
            slug="marketplace-tumbler",
            sku="KB-TUMBLER",
            starting_price=Decimal("12.50"),
        )

        self.supplier = Supplier.objects.create(
            name="Primary Supplier",
            slug="primary-supplier",
        )

        self.second_supplier = Supplier.objects.create(
            name="Secondary Supplier",
            slug="secondary-supplier-orders",
        )

        self.catalog = SupplierCatalog.objects.create(
            supplier=self.supplier,
            name="Primary Catalog",
        )

        self.order = Order.objects.create(
            customer=self.user,
            order_number="KB-MARKETPLACE-001",
            subtotal=Decimal("25.00"),
            total=Decimal("25.00"),
        )

    def test_preferred_listing_is_selected(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.second_supplier,
            supplier_sku="CHEAPER",
            unit_cost=Decimal("2.00"),
            inventory_status="in_stock",
        )

        preferred = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="PREFERRED",
            unit_cost=Decimal("4.00"),
            inventory_status="in_stock",
            is_preferred=True,
        )

        selected = select_supplier_listing(
            self.product
        )

        self.assertEqual(
            selected,
            preferred,
        )

    def test_lowest_cost_in_stock_listing_is_selected_without_preferred(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="EXPENSIVE",
            unit_cost=Decimal("5.00"),
            inventory_status="in_stock",
        )

        cheapest = SupplierListing.objects.create(
            product=self.product,
            supplier=self.second_supplier,
            supplier_sku="CHEAPEST",
            unit_cost=Decimal("3.00"),
            inventory_status="in_stock",
        )

        selected = select_supplier_listing(
            self.product
        )

        self.assertEqual(
            selected,
            cheapest,
        )

    def test_inactive_listing_is_not_selected(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="INACTIVE",
            unit_cost=Decimal("1.00"),
            inventory_status="in_stock",
            is_active=False,
        )

        selected = select_supplier_listing(
            self.product
        )

        self.assertIsNone(
            selected,
        )

    def test_order_item_captures_supplier_snapshot(self):
        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            catalog=self.catalog,
            supplier_product_id="SUPPLIER-PRODUCT-100",
            supplier_sku="SUPPLIER-SKU-100",
            supplier_product_name="Supplier Tumbler",
            unit_cost=Decimal("4.25"),
            setup_cost=Decimal("35.00"),
            minimum_order_quantity=48,
            inventory_status="in_stock",
            source="api",
        )

        order_item = OrderItem(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=10,
            unit_price=Decimal("12.50"),
            line_total=Decimal("125.00"),
        )

        order_item.apply_supplier_listing_snapshot(
            listing
        )
        order_item.save()

        self.assertEqual(
            order_item.supplier_listing,
            listing,
        )
        self.assertEqual(
            order_item.supplier_name_snapshot,
            self.supplier.name,
        )
        self.assertEqual(
            order_item.supplier_sku_snapshot,
            "SUPPLIER-SKU-100",
        )
        self.assertEqual(
            order_item.supplier_product_id_snapshot,
            "SUPPLIER-PRODUCT-100",
        )
        self.assertEqual(
            order_item.supplier_catalog_snapshot,
            "Primary Catalog",
        )
        self.assertEqual(
            order_item.supplier_unit_cost_snapshot,
            Decimal("4.25"),
        )
        self.assertEqual(
            order_item.supplier_setup_cost_snapshot,
            Decimal("35.00"),
        )
        self.assertEqual(
            order_item.supplier_minimum_quantity_snapshot,
            48,
        )
        self.assertEqual(
            order_item.supplier_source_snapshot,
            "api",
        )

    def test_supplier_snapshot_does_not_change_with_listing(self):
        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="HISTORICAL-SKU",
            unit_cost=Decimal("4.25"),
            inventory_status="in_stock",
        )

        order_item = OrderItem(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=10,
            unit_price=Decimal("12.50"),
            line_total=Decimal("125.00"),
        )

        order_item.apply_supplier_listing_snapshot(
            listing
        )
        order_item.save()

        listing.unit_cost = Decimal("8.75")
        listing.save()

        order_item.refresh_from_db()

        self.assertEqual(
            order_item.supplier_unit_cost_snapshot,
            Decimal("4.25"),
        )

    def test_order_item_remains_when_listing_is_deleted(self):
        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="DELETABLE-LISTING",
            unit_cost=Decimal("4.25"),
            inventory_status="in_stock",
        )

        order_item = OrderItem(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=2,
            unit_price=Decimal("12.50"),
            line_total=Decimal("25.00"),
        )

        order_item.apply_supplier_listing_snapshot(
            listing
        )
        order_item.save()

        listing.delete()

        order_item.refresh_from_db()

        self.assertIsNone(
            order_item.supplier_listing,
        )
        self.assertEqual(
            order_item.supplier_name_snapshot,
            self.supplier.name,
        )
        self.assertEqual(
            order_item.supplier_sku_snapshot,
            "DELETABLE-LISTING",
        )

    def test_order_item_can_exist_without_supplier_listing(self):
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=1,
            unit_price=Decimal("12.50"),
            line_total=Decimal("12.50"),
        )

        self.assertIsNone(
            order_item.supplier_listing,
        )
        self.assertEqual(
            order_item.supplier_name_snapshot,
            "",
        )

    def test_supplier_line_cost_uses_snapshot(self):
        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="COST-SNAPSHOT",
            unit_cost=Decimal("4.25"),
            inventory_status="in_stock",
        )

        order_item = OrderItem(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=10,
            unit_price=Decimal("12.50"),
            line_total=Decimal("125.00"),
        )

        order_item.apply_supplier_listing_snapshot(
            listing
        )
        order_item.save()

        self.assertEqual(
            order_item.supplier_line_cost,
            Decimal("42.50"),
        )