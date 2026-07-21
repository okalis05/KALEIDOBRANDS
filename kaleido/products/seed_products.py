from django.core.management.base import BaseCommand
from products.models import Category, Product


class Command(BaseCommand):
    help = "Seed starter product categories and sample promotional products."

    def handle(self, *args, **options):
        categories = [
            ("Apparel", "apparel", "👕", "Polos, t-shirts, hats, scrubs, jackets, and uniforms."),
            ("Drinkware", "drinkware", "🥤", "Tumblers, mugs, bottles, and branded cups."),
            ("Corporate Gifts", "corporate-gifts", "🎁", "Client gifts, employee appreciation, and premium kits."),
            ("Healthcare", "healthcare", "🩺", "Scrubs, wellness products, badge holders, and healthcare gifts."),
            ("Trade Shows", "trade-shows", "🎪", "Giveaways, booth items, bags, pens, and event products."),
            ("Technology", "technology", "🔌", "Chargers, speakers, cables, and modern branded accessories."),
            ("Office", "office", "🖊️", "Pens, notebooks, calendars, folders, and desk essentials."),
            ("Bags", "bags", "🛍️", "Totes, backpacks, drawstring bags, and event bags."),
        ]

        category_map = {}

        for index, item in enumerate(categories, start=1):
            name, slug, icon, description = item
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "description": description,
                    "order": index,
                    "is_active": True,
                },
            )
            category_map[slug] = category

        products = [
            
            (   
                 "Healthcare Scrubs",
                "healthcare-scrubs",
                "healthcare",
                "Comfortable branded scrubs for clinics and healthcare teams.",
                24.99,
                24,
                "Navy, Black, Royal Blue, Gray",
                "Healthcare, Clinics, Wellness",
                "Embroidery, Heat Transfer",
                "Poly-cotton blend",
                "Adult sizing varies",
                "7–14 business days",
            ),
            (
                "Custom Polo Shirts",
                "custom-polo-shirts",
                "apparel",
                "Professional polos for teams, offices, and events.",
                19.99,
                24,
                "Black, White, Navy, Red, Gray",
                "Corporate, Events, Teams",
                "Embroidery, Screen Printing",
                "Performance knit",
                "Adult sizing varies",
                "7–12 business days",
            ),
            (
                "Branded Hats",
                "branded-hats",
                "apparel",
                "Custom hats for events, crews, sports teams, and giveaways.",
                12.99,
                48,
                "Black, Navy, White, Red, Khaki",
                "Events, Construction, Teams",
                "Embroidery, Patch",
                "Cotton twill",
                "Adjustable",
                "7–14 business days",
            ),
            (
                "Custom T-Shirts",
                "custom-t-shirts",
                "apparel",
                "Soft promotional t-shirts for campaigns, events, and teams.",
                9.99,
                50,
                "Black, White, Navy, Red, Heather Gray",
                "Events, Schools, Nonprofits",
                "Screen Printing, DTF",
                "Cotton blend",
                "Adult sizing varies",
                "5–10 business days",
            ),
            (
                "Insulated Tumblers",
                "insulated-tumblers",
                "drinkware",
                "Premium tumblers for employees, clients, and events.",
                14.99,
                36,
                "Black, White, Silver, Blue, Red",
                "Corporate, Healthcare, Events",
                "Laser Engraving, Pad Print",
                "Stainless steel",
                "20 oz",
                "7–14 business days",
            ),
            (
                "Corporate Gift Sets",
                "corporate-gift-sets",
                "corporate-gifts",
                "Premium appreciation kits for clients and employees.",
                39.99,
                12,
                "Black, Kraft, White",
                "Corporate, Finance, Healthcare",
                "Custom Packaging, Laser Engraving",
                "Mixed materials",
                "Varies by set",
                "10–20 business days",
            ),
            (
                "Trade Show Tote Bags",
                "trade-show-tote-bags",
                "trade-shows",
                "Useful event bags for conferences, booths, and giveaways.",
                3.99,
                100,
                "Black, White, Navy, Natural",
                "Events, Trade Shows",
                "Screen Printing",
                "Non-woven polypropylene",
                "Standard tote sizing",
                "5–12 business days",
            ),
            (
                "Branded Pens",
                "branded-pens",
                "office",
                "Affordable high-volume promotional pens.",
                0.79,
                250,
                "Black, Blue, Red, White",
                "Office, Events, Schools",
                "Pad Print",
                "Plastic or metal",
                "Standard pen size",
                "5–10 business days",
            ),
            (
                "Wireless Chargers",
                "wireless-chargers",
                "technology",
                "Modern tech gifts for desks, travel, and client appreciation.",
                18.99,
                25,
                "Black, White",
                "Corporate, Technology",
                "Pad Print, Full Color",
                "Plastic / electronic components",
                "Varies",
                "10–15 business days",
            ),
            (
                "Backpacks",
                "custom-backpacks",
                "bags",
                "Durable branded backpacks for teams, schools, and corporate gifts.",
                29.99,
                24,
                "Black, Navy, Gray",
                "Schools, Corporate, Events",
                "Embroidery, Patch",
                "Polyester",
                "Standard backpack sizing",
                "10–15 business days",
            ),

        ]

        for item in products:
            (  
                name,
                slug,
                category_slug,
                desc,
                price,
                min_qty,
                colors,
                industries,
                decoration,
                material,
                dimensions,
                lead_time,
            ) = item

            Product.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "category": category_map[category_slug],
                    "short_description": desc,
                    "description": desc,
                    "starting_price": price,
                    "min_quantity": min_qty,
                    "colors": colors,
                    "industries": industries,
                    "decoration_methods": decoration,
                    "material": material,
                    "dimensions": dimensions,
                    "lead_time": lead_time,
                    "is_featured": True,
                    "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Starter product categories and products created."))