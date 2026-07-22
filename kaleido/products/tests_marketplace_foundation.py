from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from products.models import (
    Category,
    HomepageProductRail,
    ImprintMethod,
    Industry,
    Product,
    ProductCollection,
    ProductSpecification,
    ProductVariant,
    Supplier,
    SupplierCatalog,
)


class MarketplaceFoundationModelTests(TestCase):
    def setUp(self):
        self.parent_category = Category.objects.create(
            name="Apparel",
            slug="apparel",
        )

        self.category = Category.objects.create(
            name="Polos",
            slug="polos",
            parent=self.parent_category,
        )

        self.product = Product.objects.create(
            name="Performance Polo",
            slug="performance-polo",
            category=self.category,
            starting_price=Decimal("24.00"),
        )

    def test_category_parent_hierarchy(self):
        self.assertEqual(
            self.category.parent,
            self.parent_category,
        )

        self.assertIn(
            self.category,
            self.parent_category.children.all(),
        )

        self.assertFalse(
            self.category.is_root,
        )

        self.assertTrue(
            self.parent_category.is_root,
        )

    def test_product_updated_at_is_populated(self):
        self.assertIsNotNone(
            self.product.updated_at,
        )

    def test_structured_product_relationships(self):
        industry = Industry.objects.create(
            name="Healthcare",
            slug="healthcare",
        )

        collection = ProductCollection.objects.create(
            name="Staff Favorites",
            slug="staff-favorites",
        )

        imprint_method = ImprintMethod.objects.create(
            name="Embroidery",
            slug="embroidery",
        )

        self.product.industry_groups.add(
            industry,
        )

        self.product.collections.add(
            collection,
        )

        self.product.imprint_methods.add(
            imprint_method,
        )

        self.assertIn(
            industry,
            self.product.industry_groups.all(),
        )

        self.assertIn(
            collection,
            self.product.collections.all(),
        )

        self.assertIn(
            imprint_method,
            self.product.imprint_methods.all(),
        )

    def test_product_variant_effective_price(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            name="Large / Navy",
            sku="POLO-NAVY-L",
            price_adjustment=Decimal("3.50"),
        )

        self.assertEqual(
            variant.effective_price,
            Decimal("27.50"),
        )

    def test_negative_variant_inventory_is_rejected(self):
        variant = ProductVariant(
            product=self.product,
            name="Invalid Variant",
            inventory_quantity=-1,
        )

        with self.assertRaises(
            ValidationError,
        ):
            variant.full_clean()

    def test_product_specification(self):
        specification = ProductSpecification.objects.create(
            product=self.product,
            name="Material",
            value="100% polyester",
        )

        self.assertEqual(
            self.product.specifications.get(),
            specification,
        )

    def test_collection_date_validation(self):
        starts_at = timezone.now()

        collection = ProductCollection(
            name="Invalid Collection",
            slug="invalid-collection",
            starts_at=starts_at,
            ends_at=(
                starts_at
                - timedelta(days=1)
            ),
        )

        with self.assertRaises(
            ValidationError,
        ):
            collection.full_clean()

    def test_homepage_category_rail_requires_category(self):
        rail = HomepageProductRail(
            title="Category Rail",
            slug="category-rail",
            rail_type="category",
        )

        with self.assertRaises(
            ValidationError,
        ):
            rail.full_clean()

    def test_homepage_manual_rail_accepts_products(self):
        rail = HomepageProductRail.objects.create(
            title="Featured Products",
            slug="featured-products",
            rail_type="manual",
        )

        rail.products.add(
            self.product,
        )

        self.assertIn(
            self.product,
            rail.products.all(),
        )

        self.assertTrue(
            rail.is_current,
        )


class SupplierCatalogEnhancementTests(TestCase):
    def test_supplier_catalog_enhancements(self):
        supplier = Supplier.objects.create(
            name="Test Supplier",
            slug="test-supplier",
        )

        catalog = SupplierCatalog.objects.create(
            supplier=supplier,
            name="2026 Main Catalog",
            external_id="CAT-2026",
            year=2026,
            source_type="csv",
            metadata={
                "currency": "USD",
            },
        )

        self.assertEqual(
            catalog.external_id,
            "CAT-2026",
        )

        self.assertEqual(
            catalog.year,
            2026,
        )

        self.assertEqual(
            catalog.metadata["currency"],
            "USD",
        )

        self.assertIsNotNone(
            catalog.updated_at,
        )