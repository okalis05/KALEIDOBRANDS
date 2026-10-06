from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.models import Brand


BRANDS = [
    {
        "name": "Denwell",
        "display_order": 10,
    },
    {
        "name": "HUB Pen",
        "display_order": 20,
    },
    {
        "name": "SugarSpot",
        "display_order": 30,
    },
    {
        "name": "Beacon",
        "display_order": 40,
    },
    {
        "name": "Best",
        "display_order": 50,
    },
    {
        "name": "Handstands",
        "display_order": 60,
    },
    {
        "name": "Mixie",
        "display_order": 70,
    },
    {
        "name": "Origaudio",
        "display_order": 80,
    },
    {
        "name": "Maple Ridge",
        "display_order": 90,
    },
    {
        "name": "Koozie",
        "display_order": 100,
    },
    {
    "name": "SanMar",
    "display_order": 110,
    },
    {
        "name": "PCNA",
        "display_order": 120,
    },
    {
        "name": "The Magnet Group",
        "display_order": 130,
    },
    {
        "name": "JORNIK",
        "display_order": 140,
    },
    {
        "name": "VANTAGE",
        "display_order": 150,
    },
]


class Command(BaseCommand):
    help = "Seed KaleidoBrands customer-facing marketplace brands."

    def handle(self, *args, **options):

        created_count = 0
        updated_count = 0

        for data in BRANDS:

            name = data["name"]

            brand, created = Brand.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "display_order": data["display_order"],
                    "is_active": True,
                    "show_in_brand_showcase": True,
                },
            )

            if created:
                created_count += 1
                action = "CREATED"
            else:
                updated_count += 1
                action = "UPDATED"

            self.stdout.write(
                f"{action:8} "
                f"{brand.display_order:3} "
                f"{brand.name}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Brand seed complete — "
                f"created={created_count}, "
                f"updated={updated_count}, "
                f"total={Brand.objects.count()}"
            )
        )