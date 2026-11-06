
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from products.models import Product, Industry, ImprintMethod
from products.views import HOME_INDUSTRIES


class Command(BaseCommand):
    help = "Populate existing industry and imprint method search filters."

    @transaction.atomic
    def handle(self, *args, **options):
        self.populate_industries()
        self.populate_imprint_methods()

        self.stdout.write(
            self.style.SUCCESS(
                "Industry and imprint method filters populated successfully."
            )
        )

    def populate_industries(self):
        self.stdout.write("Populating industries...")

        for index, config in enumerate(HOME_INDUSTRIES, start=1):
            name = config["name"]
            slug = slugify(name)
            category_slugs = config["category_slugs"]

            industry, created = Industry.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": config.get("description", ""),
                    "is_active": True,
                    "order": index,
                },
            )

            products = (
                Product.objects
                .filter(
                    is_active=True,
                    category__slug__in=category_slugs,
                )
                .distinct()
            )

            product_ids = list(
                products.values_list("pk", flat=True)
            )

            # Synchronize only the relationship for this industry.
            # This keeps repeated runs idempotent.
            through = Product.industry_groups.through

            through.objects.filter(
                industry_id=industry.pk
            ).exclude(
                product_id__in=product_ids
            ).delete()

            through.objects.bulk_create(
                [
                    through(
                        product_id=product_id,
                        industry_id=industry.pk,
                    )
                    for product_id in product_ids
                ],
                ignore_conflicts=True,
                batch_size=1000,
            )

            self.stdout.write(
                f"  {name}: {len(product_ids)} products"
            )

    def populate_imprint_methods(self):
        self.stdout.write("Populating imprint methods...")

        through = Product.imprint_methods.through

        products = (
            Product.objects
            .filter(is_active=True)
            .exclude(decoration_methods__isnull=True)
            .exclude(decoration_methods="")
            .only("id", "decoration_methods")
        )

        methods_by_slug = {}

        for product in products.iterator(chunk_size=500):
            names = [
                value.strip()
                for value in product.decoration_methods.split(",")
                if value.strip()
            ]

            for name in names:
                slug = slugify(name)

                if not slug:
                    continue

                method = methods_by_slug.get(slug)

                if method is None:
                    method, _ = ImprintMethod.objects.get_or_create(
                        slug=slug,
                        defaults={
                            "name": name,
                            "is_active": True,
                        },
                    )

                    if not method.is_active:
                        method.is_active = True
                        method.save(update_fields=["is_active"])

                    methods_by_slug[slug] = method

                through.objects.get_or_create(
                    product_id=product.pk,
                    imprintmethod_id=method.pk,
                )

        self.stdout.write(
            f"  {len(methods_by_slug)} imprint methods processed."
        )
