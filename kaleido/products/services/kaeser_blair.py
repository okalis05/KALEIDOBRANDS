from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.utils.text import slugify

from products.models import (
    Category,
    Product,
    ProductImage,
    Supplier,
    SupplierCatalog,
    SupplierSyncLog,
)
from products.services.supplier_inventory import update_supplier_product


class KaeserBlairImporter:
    """
    Phase 3 supplier importer.

    This supports CSV/dictionary-based product importing now.
    Later, if Kaeser & Blair provides API credentials, this service can be extended
    without changing the frontend product catalog.
    """

    supplier_name = "Kaeser & Blair"
    supplier_slug = "kaeser-blair"

    def __init__(self):
        self.supplier = self.get_or_create_supplier()

    def get_or_create_supplier(self):
        supplier, _ = Supplier.objects.update_or_create(
            slug=self.supplier_slug,
            defaults={
                "name": self.supplier_name,
                "website": "https://www.kaeser-blair.com/",
                "is_active": True,
            },
        )
        return supplier

    def get_or_create_category(self, name):
        if not name:
            name = "Promotional Products"

        slug = slugify(name)

        category, _ = Category.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": f"{name} promotional products and branded merchandise.",
                "is_active": True,
            },
        )

        return category

    def get_or_create_catalog(self, name="", catalog_url=""):
        if not name:
            name = "Kaeser & Blair Catalog"

        catalog, _ = SupplierCatalog.objects.update_or_create(
            supplier=self.supplier,
            name=name,
            defaults={
                "catalog_url": catalog_url,
                "is_active": True,
            },
        )

        return catalog

    def clean_price(self, value):
        if value in [None, ""]:
            return None

        try:
            cleaned = str(value).replace("$", "").replace(",", "").strip()
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def clean_int(self, value, default=1):
        if value in [None, ""]:
            return default

        try:
            return int(float(str(value).strip()))
        except ValueError:
            return default

    def build_slug(self, name, sku=""):
        base = slugify(name)

        if sku:
            sku_slug = slugify(str(sku))
            return f"{base}-{sku_slug}"

        return base

    def import_product_dict(self, data, sync_log=None):
        name = str(data.get("name", "")).strip()

        if not name:
            if sync_log:
                sync_log.products_failed += 1
                sync_log.save(update_fields=["products_failed"])
            return None, False

        sku = str(data.get("sku", "")).strip()
        category_name = str(data.get("category", "Promotional Products")).strip()

        category = self.get_or_create_category(category_name)
        catalog = self.get_or_create_catalog(
            name=data.get("catalog_name", ""),
            catalog_url=data.get("catalog_url", ""),
        )

        slug = data.get("slug") or self.build_slug(name, sku)

        product, created = Product.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category": category,
                "supplier": self.supplier.name,
                "supplier_record": self.supplier,
                "catalog": catalog,
                "sku": sku,
                "supplier_product_id": str(data.get("supplier_product_id", "")).strip(),
                "supplier_url": str(data.get("supplier_url", "")).strip(),
                "external_image_url": str(data.get("image_url", "")).strip(),
                "short_description": str(data.get("short_description", "")).strip(),
                "description": str(data.get("description", "")).strip(),
                "min_quantity": self.clean_int(data.get("min_quantity"), default=1),
                "starting_price": self.clean_price(data.get("starting_price")),
                "colors": str(data.get("colors", "")).strip(),
                "decoration_methods": str(data.get("decoration_methods", "")).strip(),
                "industries": str(data.get("industries", "")).strip(),
                "lead_time": str(data.get("lead_time", "Varies by product")).strip(),
                "setup_fee": str(data.get("setup_fee", "Varies")).strip(),
                "material": str(data.get("material", "")).strip(),
                "dimensions": str(data.get("dimensions", "")).strip(),
                "source": "kaeser_blair",
                "last_synced_at": timezone.now(),
                "is_active": True,
                
            },
        )

        supplier_price = (
            data.get("supplier_price")
            or data.get("wholesale_price")
            or data.get("starting_price")
        )

        supplier_inventory = (
            data.get("supplier_inventory")
            or data.get("inventory")
            or data.get("stock")
            or data.get("quantity_available")
        )

        discontinued_value = str(
            data.get("discontinued", "")
        ).strip().lower()

        discontinued = discontinued_value in {
            "true",
            "1",
            "yes",
            "y",
        }

        update_supplier_product(
            product,
            supplier_price=supplier_price,
            supplier_inventory=supplier_inventory,
            discontinued=discontinued,
        )

        gallery_urls = data.get("gallery_urls", [])
        if isinstance(gallery_urls, str):
            gallery_urls = [
                url.strip()
                for url in gallery_urls.split("|")
                if url.strip()
            ]

        if product.external_image_url and product.external_image_url not in gallery_urls:
            gallery_urls.insert(0, product.external_image_url)

        if isinstance(gallery_urls, str):
            gallery_urls = [
                item.strip()
                for item in gallery_urls.split("|")
                if item.strip()
            ]
        product.gallery_images.all().delete()
        for index, image_url in enumerate(gallery_urls):
            ProductImage.objects.update_or_create(
                product=product,
                external_image_url=image_url,
                defaults={
                    "alt_text": product.name,
                    "order": index,
                },
            )

        if sync_log:
            if created:
                sync_log.products_created += 1
            else:
                sync_log.products_updated += 1

            sync_log.save(
                update_fields=[
                    "products_created",
                    "products_updated",
                ]
            )

        return product, created

    def start_log(self):
        return SupplierSyncLog.objects.create(
            supplier=self.supplier,
            status="started",
        )

    def finish_log(self, sync_log, status="success", message="Sync completed."):
        sync_log.status = status
        sync_log.message = message
        sync_log.completed_at = timezone.now()
        sync_log.save()
        return sync_log