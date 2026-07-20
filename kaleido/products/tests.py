from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from products.models import (
    Category,
    Product,
    Supplier,
    SupplierCatalog,
    SupplierListing,
)


class SupplierListingModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Drinkware",
            slug="drinkware",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Insulated Tumbler",
            slug="insulated-tumbler",
            sku="KB-TUMBLER-001",
        )

        self.supplier = Supplier.objects.create(
            name="Kaeser & Blair",
            slug="kaeser-blair",
        )

        self.other_supplier = Supplier.objects.create(
            name="Secondary Supplier",
            slug="secondary-supplier",
        )

        self.catalog = SupplierCatalog.objects.create(
            supplier=self.supplier,
            name="Drinkware Catalog",
        )

    def test_supplier_listing_can_be_created(self):
        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            catalog=self.catalog,
            supplier_sku="KB-SUP-100",
            supplier_product_name="20 oz Insulated Tumbler",
            unit_cost=Decimal("4.25"),
            minimum_order_quantity=48,
            inventory_quantity=500,
            inventory_status="in_stock",
            is_preferred=True,
        )

        self.assertEqual(
            listing.product,
            self.product,
        )
        self.assertEqual(
            listing.supplier,
            self.supplier,
        )
        self.assertEqual(
            listing.unit_cost,
            Decimal("4.25"),
        )
        self.assertTrue(
            listing.is_preferred,
        )

    def test_catalog_must_belong_to_listing_supplier(self):
        other_catalog = SupplierCatalog.objects.create(
            supplier=self.other_supplier,
            name="Other Supplier Catalog",
        )

        listing = SupplierListing(
            product=self.product,
            supplier=self.supplier,
            catalog=other_catalog,
            supplier_sku="INVALID-CATALOG",
        )

        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_inventory_quantity_cannot_be_negative(self):
        listing = SupplierListing(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="NEGATIVE-INVENTORY",
            inventory_quantity=-1,
        )

        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_discontinued_listing_must_be_inactive(self):
        listing = SupplierListing(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="DISCONTINUED-ACTIVE",
            inventory_status="discontinued",
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_out_of_stock_listing_cannot_have_positive_inventory(self):
        listing = SupplierListing(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="OUT-WITH-STOCK",
            inventory_status="out_of_stock",
            inventory_quantity=10,
        )

        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_supplier_sku_is_unique_per_supplier(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="SHARED-SKU",
        )

        other_product = Product.objects.create(
            category=self.category,
            name="Second Tumbler",
            slug="second-tumbler",
        )

        with self.assertRaises(ValidationError):
            SupplierListing.objects.create(
                product=other_product,
                supplier=self.supplier,
                supplier_sku="SHARED-SKU",
            )

    def test_same_supplier_sku_can_exist_for_different_suppliers(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="COMMON-SKU",
        )

        listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.other_supplier,
            supplier_sku="COMMON-SKU",
        )

        self.assertIsNotNone(
            listing.pk,
        )

    def test_only_one_preferred_listing_is_allowed_per_product(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="PREFERRED-ONE",
            is_preferred=True,
        )

        with self.assertRaises(ValidationError):
            SupplierListing.objects.create(
                product=self.product,
                supplier=self.other_supplier,
                supplier_sku="PREFERRED-TWO",
                is_preferred=True,
            )

    def test_blank_supplier_skus_do_not_conflict(self):
        first_listing = SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="",
        )

        other_product = Product.objects.create(
            category=self.category,
            name="Blank SKU Product",
            slug="blank-sku-product",
        )

        second_listing = SupplierListing.objects.create(
            product=other_product,
            supplier=self.supplier,
            supplier_sku="",
        )

        self.assertIsNotNone(
            first_listing.pk,
        )
        self.assertIsNotNone(
            second_listing.pk,
        )

    def test_supplier_cannot_be_deleted_while_listing_exists(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="PROTECTED-SUPPLIER",
        )

        from django.db.models.deletion import ProtectedError

        with self.assertRaises(ProtectedError):
            self.supplier.delete()

    def test_deleting_product_deletes_its_listings(self):
        SupplierListing.objects.create(
            product=self.product,
            supplier=self.supplier,
            supplier_sku="CASCADE-LISTING",
        )

        self.product.delete()

        self.assertFalse(
            SupplierListing.objects.filter(
                supplier_sku="CASCADE-LISTING",
            ).exists()
        )
# Create your tests here.
