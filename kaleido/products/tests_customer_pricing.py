from decimal import Decimal

from django.test import TestCase

from products.models import Product, SupplierPriceBreak
from products.services.customer_pricing import (
    CUSTOMER_MARKUP_RATE,
    customer_price_breaks,
    customer_price_from_supplier_cost,
    customer_starting_price,
    resolve_customer_unit_price,
)


class CustomerPricingTests(TestCase):

    def test_markup_rate_is_ten_percent(self):
        self.assertEqual(
            CUSTOMER_MARKUP_RATE,
            Decimal("0.10"),
        )

    def test_customer_price_adds_ten_percent_markup(self):
        self.assertEqual(
            customer_price_from_supplier_cost(
                Decimal("10.00")
            ),
            Decimal("11.00"),
        )

    def test_customer_price_rounds_half_up(self):
        self.assertEqual(
            customer_price_from_supplier_cost(
                Decimal("0.9480")
            ),
            Decimal("1.04"),
        )

    def test_none_supplier_cost_returns_none(self):
        self.assertIsNone(
            customer_price_from_supplier_cost(None)
        )

    def test_negative_supplier_cost_is_rejected(self):
        with self.assertRaises(ValueError):
            customer_price_from_supplier_cost(
                Decimal("-1.00")
            )

    def test_customer_price_breaks_apply_markup(self):
        product = Product.objects.create(
            name="Pricing Test Product",
            slug="pricing-test-product",
            supplier="Test Supplier",
            supplier_sku="PRICE-TEST-1",
            supplier_price=Decimal("5.00"),
            min_quantity=50,
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=50,
            price=Decimal("5.0000"),
            price_uom="EA",
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=100,
            price=Decimal("4.6000"),
            price_uom="EA",
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=500,
            price=Decimal("3.9000"),
            price_uom="EA",
        )

        rows = customer_price_breaks(product)

        self.assertEqual(len(rows), 3)

        self.assertEqual(
            rows[0]["customer_price"],
            Decimal("5.50"),
        )

        self.assertEqual(
            rows[1]["customer_price"],
            Decimal("5.06"),
        )

        self.assertEqual(
            rows[2]["customer_price"],
            Decimal("4.29"),
        )

    def test_customer_starting_price_uses_lowest_quantity_price(self):
        product = Product.objects.create(
            name="Starting Price Test",
            slug="starting-price-test",
            supplier="Test Supplier",
            supplier_sku="PRICE-TEST-2",
            supplier_price=Decimal("5.00"),
            min_quantity=50,
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=50,
            price=Decimal("5.0000"),
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=500,
            price=Decimal("3.9000"),
        )

        self.assertEqual(
            customer_starting_price(product),
            Decimal("4.29"),
        )

    def test_starting_price_falls_back_to_supplier_price(self):
        product = Product.objects.create(
            name="No Break Test",
            slug="no-break-test",
            supplier="Test Supplier",
            supplier_sku="PRICE-TEST-3",
            supplier_price=Decimal("10.00"),
            min_quantity=1,
        )

        self.assertEqual(
            customer_starting_price(product),
            Decimal("11.00"),
        )

    def test_supplier_price_breaks_are_not_modified(self):
        product = Product.objects.create(
            name="Supplier Preservation Test",
            slug="supplier-preservation-test",
            supplier="Test Supplier",
            supplier_sku="PRICE-TEST-4",
            supplier_price=Decimal("5.00"),
            min_quantity=50,
        )

        supplier_break = SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=50,
            price=Decimal("5.0000"),
        )

        customer_price_breaks(product)

        supplier_break.refresh_from_db()

        self.assertEqual(
            supplier_break.price,
            Decimal("5.0000"),
        )

        product.refresh_from_db()

        self.assertEqual(
            product.supplier_price,
            Decimal("5.0000"),
        )

    def test_quantity_resolver_uses_matching_product_break(self):
        product = Product.objects.create(
            name="Quantity Resolver Test",
            slug="quantity-resolver-test",
            supplier="Test Supplier",
            supplier_sku="QTY-PRICE-1",
            min_quantity=50,
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=50,
            price=Decimal("5.0000"),
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=100,
            price=Decimal("4.6000"),
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=500,
            price=Decimal("3.9000"),
        )

        self.assertEqual(
            resolve_customer_unit_price(
                product,
                50,
            ),
            Decimal("5.50"),
        )

        self.assertEqual(
            resolve_customer_unit_price(
                product,
                100,
            ),
            Decimal("5.06"),
        )

        self.assertEqual(
            resolve_customer_unit_price(
                product,
                499,
            ),
            Decimal("5.06"),
        )

        self.assertEqual(
            resolve_customer_unit_price(
                product,
                500,
            ),
            Decimal("4.29"),
        )

    def test_quantity_resolver_rejects_quantity_below_first_break(self):
        product = Product.objects.create(
            name="Below MOQ Resolver Test",
            slug="below-moq-resolver-test",
            supplier="Test Supplier",
            supplier_sku="QTY-PRICE-2",
            min_quantity=50,
        )

        SupplierPriceBreak.objects.create(
            product=product,
            min_quantity=50,
            price=Decimal("5.0000"),
        )

        self.assertIsNone(
            resolve_customer_unit_price(
                product,
                49,
            )
        )

    def test_quantity_resolver_falls_back_to_supplier_price(self):
        product = Product.objects.create(
            name="Supplier Price Resolver Test",
            slug="supplier-price-resolver-test",
            supplier="Test Supplier",
            supplier_sku="QTY-PRICE-3",
            supplier_price=Decimal("10.00"),
            min_quantity=1,
        )

        self.assertEqual(
            resolve_customer_unit_price(
                product,
                1,
            ),
            Decimal("11.00"),
        )

