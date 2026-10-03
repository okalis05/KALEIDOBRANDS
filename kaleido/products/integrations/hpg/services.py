from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import re
import json

from products.models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    Supplier,
    SupplierCatalog,
    SupplierPriceBreak,
)

from .client import HPGClient
from .mapper import (
    extract_net_price_breaks,
    map_product_bundle,
)
from django.utils.text import slugify
from products.services.customer_pricing import (
    customer_price_from_supplier_cost,
    customer_starting_price,
)

HPG_SUPPLIER_NAME = "HPG"
HPG_SUPPLIER_SLUG = "hpg"

HPG_CATALOGS = {
    "denwell": {
        "external_id": "denwell-promostandards",
        "name": "Denwell PromoStandards Catalog",
        "product_supplier_name": "HPG",
        "description": (
            "Denwell product data synchronized "
            "through PromoStandards."
        ),
    },
    "hubpen": {
        "external_id": "hubpen-promostandards",
        "name": "Hub Pen PromoStandards Catalog",
        "product_supplier_name": "Hub Pen",
        "description": (
            "Hub Pen product data synchronized "
            "through PromoStandards."
        ),
    },
    "sugarspot": {
        "external_id": "sugarspot-promostandards",
        "name": "SugarSpot PromoStandards Catalog",
        "product_supplier_name": "SugarSpot",
        "description": (
            "SugarSpot product data synchronized "
            "through PromoStandards."
        ),
    },
    "beacon": {
        "external_id": "beacon-promostandards",
        "name": "Beacon Promotions PromoStandards Catalog",
        "product_supplier_name": "Beacon Promotions",
        "description": (
            "Beacon Promotions product data synchronized "
            "through PromoStandards."
        ),
    },
    "best": {
        "external_id": "best-promostandards",
        "name": "Best Promotions USA PromoStandards Catalog",
        "product_supplier_name": "Best Promotions USA",
        "description": (
            "Best Promotions USA product data synchronized "
            "through PromoStandards."
        ),
    },
    "handstands": {
        "external_id": "handstands-promostandards",
        "name": "Handstands PromoStandards Catalog",
        "product_supplier_name": "Handstands",
        "description": (
            "Handstands product data synchronized "
            "through PromoStandards."
        ),
    },
    "mixie": {
        "external_id": "mixie-promostandards",
        "name": "Mixie PromoStandards Catalog",
        "product_supplier_name": "Mixie",
        "description": (
            "Mixie product data synchronized "
            "through PromoStandards."
        ),
    },
    "origaudio": {
        "external_id": "origaudio-promostandards",
        "name": "Origaudio PromoStandards Catalog",
        "product_supplier_name": "Origaudio",
        "description": (
            "Origaudio product data synchronized "
            "through PromoStandards."
        ),
    },
    "mapleridge": {
        "external_id": "mapleridge-promostandards",
        "name": "Maple Ridge Farms PromoStandards Catalog",
        "product_supplier_name": "Maple Ridge Farms",
        "description": (
            "Maple Ridge Farms product data synchronized "
            "through PromoStandards."
        ),
    },
    "sanmar": {
        "external_id": "sanmar-promostandards",
        "name": "SanMar PromoStandards Catalog",
        "product_supplier_name": "SanMar",
        "description": (
            "SanMar product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },
    "pcna": {
        "external_id": "pcna-promostandards",
        "name": "PCNA PromoStandards Catalog",
        "product_supplier_name": "PCNA",
        "description": (
            "PCNA product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },
    "koozie": {
        "external_id": "koozie-promostandards",
        "name": "Koozie Group PromoStandards Catalog",
        "product_supplier_name": "Koozie Group",
        "description": (
            "Koozie Group product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },

    "magnet": {
        "external_id": "magnet-promostandards",
        "name": "The Magnet Group PromoStandards Catalog",
        "product_supplier_name": "The Magnet Group",
        "description": (
            "The Magnet Group product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },

    "vantage": {
        "external_id": "vantage-promostandards",
        "name": "Vantage Apparel PromoStandards Catalog",
        "product_supplier_name": "Vantage Apparel",
        "description": (
            "Vantage Apparel product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },


    "jornik": {
        "external_id": "jornik-promostandards",
        "name": "Jornik Manufacturing Corp PromoStandards Catalog",
        "product_supplier_name": "Jornik Manufacturing Corp",
        "description": (
            "Jornik Manufacturing Corp product data synchronized "
            "through PromoStandards via DC OneSource."
        ),
    },


}


class HPGSyncService:
    """
    Coordinates HPG / Denwell supplier synchronization.

    The client retrieves supplier data.
    The mapper normalizes supplier data.
    This service handles Django model persistence.
    """

    def __init__(
        self,
        *,
        brand="denwell",
        dry_run=False,
        client=None,
    ):
        self.brand = str(brand).strip().lower()

        if self.brand not in HPG_CATALOGS:
            supported = ", ".join(sorted(HPG_CATALOGS))
            raise ValueError(
                f"Unsupported HPG sync brand '{brand}'. "
                f"Supported brands: {supported}"
            )

        self.brand_config = HPG_CATALOGS[self.brand]
        self.dry_run = dry_run

        if client is not None:
            client_brand = getattr(client, "brand", None)

            if (
                client_brand is not None
                and client_brand != self.brand
            ):
                raise ValueError(
                    f"Client brand '{client_brand}' does not match "
                    f"sync brand '{self.brand}'."
                )

            self.client = client
        else:
            self.client = HPGClient(
                brand=self.brand
            )

    # ==============================================================
    # Supplier / catalog
    # ==============================================================

    def get_supplier(self):
        supplier, _ = (
            Supplier.objects.get_or_create(
                slug=HPG_SUPPLIER_SLUG,
                defaults={
                    "name": HPG_SUPPLIER_NAME,
                    "website": (
                        "https://hpgbrands.com/"
                    ),
                    "api_enabled": True,
                    "is_active": True,
                },
            )
        )

        return supplier

    def get_catalog(
        self,
        supplier,
    ):
        catalog, _ = (
            SupplierCatalog.objects.get_or_create(
                supplier=supplier,
                external_id=self.brand_config["external_id"],
                defaults={
                    "name": self.brand_config["name"],
                    "source_type": "api",
                    "description": (
                        self.brand_config["description"]
                    ),
                    "is_active": True,
                },
            )
        )

        return catalog

    # ==============================================================
    # Category mapping
    # ==============================================================

    def resolve_category(
        self,
        mapped,
    ):
        """
        Resolve supplier categories into KaleidoBrands storefront
        categories.

        Resolution order:
        1. Exact match against an existing KaleidoBrands category.
        2. Product-name/content based normalization for broad supplier
        categories such as "Auto & Home" or "Other".
        3. Return None when no confident mapping exists.

        We intentionally do not create arbitrary supplier categories.
        """
        # Supplier-specific category correction for products whose
        # PromoStandards Product Data omits category metadata.
        category_overrides = {
            # SugarSpot
            ("sugarspot", "BBMOVIE"): "Food & Candy",

            # Beacon — PromoStandards category metadata omitted,
            # but product identity gives a confident storefront category.

            # Bags
            ("beacon", "BL256"): "Bags",
            ("beacon", "X112"): "Bags",
            ("beacon", "YDAY5L"): "Bags",
            ("best", "MCCT"): "Bags",

            # Technology
            ("beacon", "CBTEYEMASK1"): "Technology",
            ("beacon", "JBLGO5"): "Technology",
            ("beacon", "JBLLIVE780NC"): "Technology",
            ("beacon", "JBLSENSELITE"): "Technology",
            ("beacon", "JBLSENSEPRO"): "Technology",

            # Drinkware
            ("beacon", "CORCAN20"): "Drinkware",
            ("beacon", "CORMUG16"): "Drinkware",
            ("beacon", "CORSPORTJ64"): "Drinkware",
            ("beacon", "DWER40"): "Drinkware",
            ("beacon", "DWLP12"): "Drinkware",
            ("beacon", "DWMV15"): "Drinkware",
            ("beacon", "DWMV25"): "Drinkware",
            ("beacon", "DWMV35"): "Drinkware",
            ("beacon", "DWRS35"): "Drinkware",
            ("beacon", "RTIC20EDT"): "Drinkware",
            ("beacon", "RTIC28EDT"): "Drinkware",
            ("beacon", "RTIC32OB"): "Drinkware",
            ("beacon", "RTIC40OB"): "Drinkware",
            ("beacon", "YRAMT16"): "Drinkware",
            ("best", "1000BEZ4CP"): "Drinkware",

            # Handstands supplier-specific category overrides
            ("handstands", "10214"): "Office",
            ("handstands", "10800"): "Corporate Gifts",
            ("handstands", "10801"): "Corporate Gifts",
            ("handstands", "16101HS"): "Corporate Gifts",
            ("handstands", "21028"): "Technology",
            ("handstands", "34081"): "Corporate Gifts",
            ("handstands", "34110"): "Healthcare",
            ("handstands", "35220"): "Office",
            ("handstands", "37710"): "Technology",
            ("handstands", "52100"): "Corporate Gifts",
            ("handstands", "701271"): "Corporate Gifts",
            ("handstands", "74604"): "Corporate Gifts",
            ("handstands", "75100"): "Technology",
            ("handstands", "75700"): "Corporate Gifts",
            ("handstands", "9505"): "Corporate Gifts",
            ("handstands", "9571"): "Corporate Gifts",
            ("handstands", "9572"): "Corporate Gifts",
            ("handstands", "9605"): "Corporate Gifts",
            ("handstands", "99033"): "Technology",
            ("handstands", "99055"): "Technology",
            ("handstands", "99091"): "Office",

            # Correct incorrect automatic content match.
            ("handstands", "99036"): "Technology",

            # ------------------------------------------------------------------
            # Mixie
            # Supplier-specific category overrides.
            # ------------------------------------------------------------------
            # Toys, novelty, stress-relief, fidget and general promotional items.
            # ------------------------------------------------------------------
            ("mixie", "25014"): "Corporate Gifts",
            ("mixie", "25104"): "Corporate Gifts",
            ("mixie", "25204"): "Corporate Gifts",
            ("mixie", "25230"): "Corporate Gifts",
            ("mixie", "3213"): "Corporate Gifts",
            ("mixie", "7023"): "Corporate Gifts",
            ("mixie", "80803"): "Corporate Gifts",
            ("mixie", "80880CIRCLE"): "Healthcare",
            ("mixie", "80880SEMICIRCLE"): "Healthcare",
            ("mixie", "80880SQUARE"): "Healthcare",
            ("mixie", "8133"): "Corporate Gifts",
            ("mixie", "SP01BP"): "Corporate Gifts",
            ("mixie", "SP02FP"): "Corporate Gifts",
            ("mixie", "SP03CP"): "Corporate Gifts",
            ("mixie", "SR01MB"): "Corporate Gifts",
            ("mixie", "SR02CB"): "Corporate Gifts",
            ("mixie", "SR03SCB"): "Corporate Gifts",
            ("mixie", "SR07NR"): "Healthcare",
            ("mixie", "SR10SP"): "Corporate Gifts",
            ("mixie", "SR11TP"): "Corporate Gifts",
            ("mixie", "SR12FB"): "Corporate Gifts",
            ("mixie", "SR13GB"): "Corporate Gifts",
            ("mixie", "SR14FT"): "Corporate Gifts",
            ("mixie", "SR15PC"): "Corporate Gifts",
            ("mixie", "SR16BB"): "Corporate Gifts",
            ("mixie", "SR17RB"): "Corporate Gifts",
            ("mixie", "SR18FB"): "Corporate Gifts",
            ("mixie", "SR22PC"): "Corporate Gifts",
            ("mixie", "SR26FS"): "Technology",
            ("mixie", "SR27FP"): "Corporate Gifts",
            ("mixie", "SR28FC"): "Corporate Gifts",
            ("mixie", "SR29BB"): "Corporate Gifts",
            ("mixie", "SR31IC"): "Corporate Gifts",
            ("mixie", "SR32GD"): "Corporate Gifts",
            ("mixie", "WE03AC"): "Corporate Gifts",
            ("mixie", "WE09DGS"): "Corporate Gifts",

            # Auto & Home.
            ("mixie", "CBB3"): "Corporate Gifts",
            ("mixie", "CGB5"): "Corporate Gifts",
            ("mixie", "DC04TH"): "Healthcare",
            ("mixie", "FTBMC"): "Food & Candy",
            ("mixie", "LK15RE"): "Healthcare",
            ("mixie", "LK16CC"): "Healthcare",
            ("mixie", "NP11"): "Corporate Gifts",
            ("mixie", "PBMC"): "Food & Candy",
            ("mixie", "PC24PB"): "Healthcare",
            ("mixie", "PC25PB"): "Healthcare",
            ("mixie", "PM01MT"): "Food & Candy",
            ("mixie", "PM350"): "Food & Candy",
            ("mixie", "WE13NP"): "Corporate Gifts",

            # Outdoor & Leisure.
            ("mixie", "CCT10"): "Corporate Gifts",
            ("mixie", "CTYM9095"): "Corporate Gifts",
            ("mixie", "FSSG"): "Apparel",
            ("mixie", "G5000M"): "Corporate Gifts",
            ("mixie", "G7325M"): "Corporate Gifts",
            ("mixie", "GPGB"): "Corporate Gifts",
            ("mixie", "SG01SC"): "Apparel",
            ("mixie", "SG02TR"): "Apparel",
            ("mixie", "SG03TT"): "Apparel",
            ("mixie", "SG05ML"): "Apparel",
            ("mixie", "WE04WB"): "Corporate Gifts",
            ("mixie", "WE12GT"): "Corporate Gifts",
            ("mixie", "YM8915M"): "Healthcare",

            # No supplier category.
            ("mixie", "BUS"): "Corporate Gifts",
            ("mixie", "CLIP"): "Healthcare",
            ("mixie", "GPRLB"): "Healthcare",

            # Supplier category: Other.
            ("mixie", "70010"): "Healthcare",
            ("mixie", "70036"): "Healthcare",
            ("mixie", "80880STRIP"): "Healthcare",
            ("mixie", "BABMC"): "Food & Candy",
            ("mixie", "BBMC"): "Food & Candy",
            ("mixie", "BOBBUD"): "Corporate Gifts",
            ("mixie", "CT50"): "Food & Candy",
            ("mixie", "DC02TC"): "Healthcare",
            ("mixie", "DENKITWHEAT"): "Healthcare",
            ("mixie", "FUNONRUN"): "Bags",
            ("mixie", "GB44"): "Food & Candy",
            ("mixie", "GLA25"): "Food & Candy",
            ("mixie", "HG04SB"): "Corporate Gifts",
            ("mixie", "IMTB"): "Food & Candy",
            ("mixie", "LK05GK"): "Corporate Gifts",
            ("mixie", "LK06OS"): "Corporate Gifts",
            ("mixie", "LK07GS"): "Corporate Gifts",
            ("mixie", "LK08GM"): "Corporate Gifts",
            ("mixie", "LK14LL"): "Healthcare",
            ("mixie", "LK40CK"): "Healthcare",
            ("mixie", "MBMC"): "Food & Candy",
            ("mixie", "MINIFAN"): "Technology",
            ("mixie", "MLED"): "Office",
            ("mixie", "MM11"): "Healthcare",
            ("mixie", "PC14EM"): "Healthcare",
            ("mixie", "PC17NB"): "Healthcare",
            ("mixie", "PC18GC"): "Healthcare",
            ("mixie", "PC20EM"): "Healthcare",
            ("mixie", "PC23HC"): "Healthcare",
            ("mixie", "PC28BF"): "Technology",
            ("mixie", "PC29RF"): "Technology",
            ("mixie", "PC34SF"): "Technology",
            ("mixie", "PEMC"): "Food & Candy",
            ("mixie", "PM03MT"): "Food & Candy",
            ("mixie", "RBMC"): "Food & Candy",
            ("mixie", "SELFCARE"): "Healthcare",
            ("mixie", "SLEEPIN"): "Healthcare",
            ("mixie", "SSS1"): "Healthcare",
            ("mixie", "SSS2"): "Healthcare",
            ("mixie", "T140"): "Food & Candy",
            ("mixie", "TBMC"): "Food & Candy",
            ("mixie", "TIN9"): "Food & Candy",
            ("mixie", "WE05MR"): "Office",
            ("mixie", "WE08GB"): "Corporate Gifts",
            ("mixie", "WODKM1"): "Corporate Gifts",
            ("mixie", "WSBMC"): "Food & Candy",
            ("mixie", "WSBSB"): "Corporate Gifts",
            ("mixie", "WSCS"): "Corporate Gifts",
            ("mixie", "WSLBS"): "Corporate Gifts",
            ("mixie", "WSMKC"): "Food & Candy",
            ("mixie", "WSUS"): "Corporate Gifts",

            # Origaudio
            ("origaudio", "10002"): "Drinkware",
            ("origaudio", "10007"): "Corporate Gifts",
            ("origaudio", "10010"): "Corporate Gifts",
            ("origaudio", "10017"): "Corporate Gifts",
            ("origaudio", "10038"): "Corporate Gifts",
            ("origaudio", "10039"): "Corporate Gifts",
            ("origaudio", "10040"): "Corporate Gifts",
            ("origaudio", "10041"): "Corporate Gifts",
            ("origaudio", "10042"): "Technology",
            ("origaudio", "10043"): "Technology",
            ("origaudio", "10044"): "Technology",
            ("origaudio", "10045"): "Technology",
            ("origaudio", "10046"): "Technology",
            ("origaudio", "10047"): "Corporate Gifts",
            ("origaudio", "10048"): "Corporate Gifts",

            ("origaudio", "15234"): "Bags",
            ("origaudio", "39010"): "Corporate Gifts",
            ("origaudio", "75200"): "Corporate Gifts",
            ("origaudio", "75300"): "Corporate Gifts",
            ("origaudio", "95019"): "Corporate Gifts",
            ("origaudio", "96017"): "Corporate Gifts",
            ("origaudio", "96019"): "Corporate Gifts",
            ("origaudio", "96055"): "Corporate Gifts",

            ("origaudio", "97021"): "Bags",
            ("origaudio", "97022"): "Technology",
            ("origaudio", "9812"): "Technology",
            ("origaudio", "98230"): "Office",
            ("origaudio", "99010"): "Corporate Gifts",
            ("origaudio", "99090"): "Office",

            ("origaudio", "99150"): "Corporate Gifts",
            ("origaudio", "99160"): "Corporate Gifts",
            ("origaudio", "99190"): "Corporate Gifts",
            ("origaudio", "99200"): "Corporate Gifts",
            ("origaudio", "99210"): "Corporate Gifts",
            ("origaudio", "99220"): "Corporate Gifts",
                                    
}

        supplier_sku = (
            mapped.get("supplier_sku")
            or ""
        ).strip()

        override_category_name = category_overrides.get(
            (
                self.brand,
                supplier_sku,
            )
        )

        if override_category_name:
            override_category = Category.objects.filter(
                name__iexact=override_category_name,
                is_active=True,
            ).first()

            if override_category:
                return override_category

        # ----------------------------------------------------------
        # Maple Ridge Farms
        # ----------------------------------------------------------
        if self.brand == "mapleridge":
            maple_ridge_category = (
                Category.objects
                .filter(
                    name__iexact="Food & Candy",
                    is_active=True,
                )
                .first()
            )

            if maple_ridge_category:
                return maple_ridge_category

            return None

        supplier_categories = (
            mapped.get("supplier_categories")
            or []
        )

        # ----------------------------------------------------------
        # 1. Exact supplier-category match
        # ----------------------------------------------------------

        for name in supplier_categories:

            category = (
                Category.objects
                .filter(
                    name__iexact=name,
                    is_active=True,
                )
                .first()
            )

            if category:
                return category


        supplier_category_aliases = {
            "Trade Show & Signage": "Trade Shows",
            "Stationery": "Office",
            "Office & Awards": "Office",
            "Wellness & Safety": "Healthcare",
        }

        for supplier_category_name in supplier_categories:
            target_category_name = supplier_category_aliases.get(
                supplier_category_name
            )

            if not target_category_name:
                continue

            category = (
                Category.objects
                .filter(
                    name__iexact=target_category_name,
                    is_active=True,
                )
                .first()
            )

            if category:
                return category

        # ----------------------------------------------------------
        # 2. KaleidoBrands category normalization
        # ----------------------------------------------------------

        searchable_text = " ".join(
            [
                str(mapped.get("name") or ""),
                str(mapped.get("short_description") or ""),
                str(mapped.get("description") or ""),
                " ".join(
                    str(value)
                    for value in supplier_categories
                ),
            ]
        ).lower()

        # ----------------------------------------------------------
        # Avoid over-classifying kits/sets from accessory keywords
        # ----------------------------------------------------------

        product_name = (
            str(mapped.get("name") or "")
            .strip()
            .lower()
        )

        ambiguous_product_terms = (
            "kit",
            "set",
            "bundle",
        )

        product_name_words = set(
            re.findall(
                r"[a-z0-9]+",
                product_name,
            )
        )

        if any(
            term in product_name_words
            for term in ambiguous_product_terms
        ):
            return None

        category_keywords = {
            "Drinkware": (
                "mug",
                "tumbler",
                "drinkware",
                "water bottle",
                "sports bottle",
                "vacuum bottle",
                "wine tumbler",
                "beer mug",
                "ceramic mug",
                "glass mug",
                "travel mug",
                "coffee mug",
                "old fashion glass",
                "old fashioned glass",
                "canteen",
                "sport jug",
                "travel bottle",
                "hydration bottle",
            ),
            "Apparel": (
                "t-shirt",
                "tee shirt",
                "polo",
                "hoodie",
                "sweatshirt",
                "jacket",
                "shirt",
                "vest",
                "apparel",
            ),
            "Bags": (
                "backpack",
                "tote bag",
                "duffel",
                "drawstring bag",
                "lunch bag",
                "cooler bag",
                "travel bag",
                "packing cube",
                "weekender",
                "lunch box",
            ),
            "Technology": (
                "power bank",
                "wireless charger",
                "bluetooth",
                "speaker",
                "earbuds",
                "usb",
                "tech accessory",
                "headphones",
                "wireless headphones",
                "sleep mask",
            ),
           "Office": (
                "ballpoint pen",
                "rollerball pen",
                "stylus pen",
                "pencil",
                "writing instrument",
                "notebook",
                "journal",
            ),
            "Healthcare": (
                "wellness",
                "sanitizer",
                "first aid",
                "fitness",
                "yoga",
            ),
        }

        for category_name, keywords in category_keywords.items():

            if not any(
                keyword in searchable_text
                for keyword in keywords
            ):
                continue

            category = (
                Category.objects
                .filter(
                    name__iexact=category_name,
                    is_active=True,
                )
                .first()
            )

            if category:
                return category

        # ----------------------------------------------------------
        # 3. No confident mapping
        # ----------------------------------------------------------

        return None

    # ==============================================================
    # Product defaults
    # ==============================================================

    def build_product_defaults(
        self,
        mapped,
        supplier,
        catalog,
    ):
        category = self.resolve_category(
            mapped
        )

        now = timezone.now()

        defaults = {
            "supplier": self.brand_config["product_supplier_name"],
            "supplier_record": supplier,
            "catalog": catalog,
            "category": category,

            "name": mapped["name"],

            "short_description": (
                mapped.get(
                    "short_description"
                )
                or ""
            ),

            "description": (
                mapped.get(
                    "description"
                )
                or ""
            ),

            "colors": (
                mapped.get(
                    "colors"
                )
                or ""
            ),

            "dimensions": (
                mapped.get(
                    "dimensions"
                )
                or ""
            ),

            "lead_time": (
                mapped.get(
                    "lead_time"
                )
                or "Varies by product"
            ),

            "decoration_methods": (
                mapped.get(
                    "decoration_methods"
                )
                or ""
            ),

            "supplier_price": (
                mapped.get(
                    "supplier_price"
                )
            ),

            "min_quantity": (
                mapped.get(
                    "min_quantity"
                )
                or 1
            ),

            "external_image_url": (
                mapped.get(
                    "external_image_url"
                )
                or ""
            ),

            "source": "PromoStandards",

            "supplier_last_synced_at": now,
            "last_synced_at": now,

            "is_active": (
                not mapped.get(
                    "is_closeout",
                    False,
                )
            ),
            "sku": (
                mapped.get("supplier_sku")
                or ""
            ),

            "supplier_product_id": (
                mapped.get("supplier_product_id")
                or mapped.get("supplier_sku")
                or ""),
    }

        return defaults
    
    def build_sanmar_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build a normalized SanMar parent + variant structure.

        READ ONLY.

        SanMar supplier pricing is variant-specific. Each exact
        part is therefore normalized independently.

        The parent customer starting price is the minimum
        calculable customer-facing variant price across the
        complete part_ids supplied to this method.

        No Product, ProductVariant, SupplierPriceBreak, or image
        records are created or updated here.
        """

        if self.brand != "sanmar":
            raise RuntimeError(
                "build_sanmar_parent_dry_run() is only "
                "available for the SanMar integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "has no part IDs."
            )

        bundle = (
            self.client
            .get_sanmar_parent_bundle(
                product_id,
                normalized_part_ids,
            )
        )

        parent_product = (
            bundle.get("product")
            or {}
        )

        if not parent_product:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned no parent Product Data."
            )

        variants = []

        for order, row in enumerate(
            bundle.get("variants")
            or [],
            start=1,
        ):
            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            exact_part = (
                self._extract_sanmar_exact_part(
                    product_data,
                    part_id,
                )
            )

            price_breaks = (
                extract_net_price_breaks(
                    row.get("pricing")
                )
            )

            ea_prices = [
                price_row["price"]
                for price_row in price_breaks
                if (
                    str(
                        price_row.get(
                            "price_uom"
                        )
                        or ""
                    ).upper()
                    == "EA"
                    and price_row.get(
                        "price"
                    )
                    is not None
                )
            ]

            supplier_net = (
                min(ea_prices)
                if ea_prices
                else None
            )

            customer_price = None

            if supplier_net is not None:
                customer_price = (
                    customer_price_from_supplier_cost(
                        supplier_net
                    )
                )

            color = (
                self._extract_sanmar_color(
                    exact_part
                )
            )

            size = (
                self._extract_sanmar_size(
                    exact_part
                )
            )

            name_parts = [
                value
                for value in (
                    color,
                    size,
                )
                if value
            ]

            variant_name = (
                " / ".join(
                    name_parts
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "supplier_sku": part_id,
                "name": variant_name,
                "color": color,
                "size": size,
                "supplier_net": (
                    supplier_net
                ),
                "customer_price": (
                    customer_price
                ),
                "price_adjustment": None,
                "order": order,
                "error": row.get(
                    "error"
                ),
                "source_payload": {
                    "supplier": "SanMar",
                    "product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "supplier_net": (
                        str(supplier_net)
                        if supplier_net
                        is not None
                        else None
                    ),
                    "price_uom": (
                        "EA"
                        if supplier_net
                        is not None
                        else ""
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "color": color,
                    "size": size,
                    "gtin": (
                        exact_part.get(
                            "gtin"
                        )
                        or exact_part.get(
                            "GTIN"
                        )
                        or ""
                    ),
                },
            })

        customer_prices = [
            row["customer_price"]
            for row in variants
            if (
                row["customer_price"]
                is not None
            )
        ]

        parent_starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        for row in variants:
            customer_price = (
                row["customer_price"]
            )

            if (
                customer_price
                is not None
                and parent_starting_price
                is not None
            ):
                row["price_adjustment"] = (
                    customer_price
                    - parent_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        mapped_parent = (
            map_product_bundle({
                "product": parent_product,
                "primary_image": (
                    bundle.get(
                        "primary_image"
                    )
                ),
                "pricing": None,
            })
        )

        #
        # SanMar parent supplier cost is deliberately not
        # represented as a universal variant cost.
        #
        mapped_parent[
            "supplier_price"
        ] = None

        mapped_parent[
            "price_breaks"
        ] = []

        return {
            "product_id": str(
                product_id
            ).strip(),
            "part_ids": (
                normalized_part_ids
            ),
            "mapped_parent": (
                mapped_parent
            ),
            "parent_starting_price": (
                parent_starting_price
            ),
            "primary_image": (
                bundle.get(
                    "primary_image"
                )
            ),
            "variants": variants,
            "variant_count": (
                len(variants)
            ),
            "priced_variant_count": (
                len(customer_prices)
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(customer_prices)
            ),
        }

    def sync_sanmar_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one SanMar parent product and its ProductVariant rows.

        SanMar pricing is variant-specific:

            variant customer price
                = supplier Net + KaleidoBrands markup

            parent starting_price
                = minimum customer price across the complete family

            variant price_adjustment
                = variant customer price - parent starting_price

        Supplier Net remains variant-level source data and is stored in
        ProductVariant.source_payload.

        No SupplierPriceBreak rows are created for SanMar variant pricing.

        Stale variants are deactivated only when complete_family=True.

        Supplier retrieval and normalization happen before the database
        transaction so an incomplete supplier response cannot partially
        modify the database.
        """

        if self.brand != "sanmar":
            raise RuntimeError(
                "sync_sanmar_parent() is only available "
                "for the SanMar integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization happen BEFORE any DB writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_sanmar_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        mapped_parent = dict(
            normalized.get(
                "mapped_parent"
            )
            or {}
        )

        variants = list(
            normalized.get(
                "variants"
            )
            or []
        )

        parent_starting_price = (
            normalized.get(
                "parent_starting_price"
            )
        )

        # ----------------------------------------------------------
        # Safety validation before persistence
        # ----------------------------------------------------------

        if not mapped_parent:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned no mapped parent."
            )

        if (
            str(
                mapped_parent.get(
                    "supplier_sku"
                )
                or ""
            ).strip()
            != str(product_id).strip()
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned an unexpected parent SKU."
            )

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        returned_part_ids = [
            str(
                row.get("part_id")
                or ""
            ).strip()
            for row in variants
        ]

        if (
            len(
                set(returned_part_ids)
            )
            != len(
                returned_part_ids
            )
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned duplicate part IDs."
            )

        if set(
            returned_part_ids
        ) != set(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        retrieval_errors = [
            row
            for row in variants
            if row.get("error")
        ]

        if retrieval_errors:
            raise RuntimeError(
                f"SanMar product {product_id} "
                f"has {len(retrieval_errors)} "
                "variant retrieval error(s)."
            )

        priced_variants = [
            row
            for row in variants
            if row.get(
                "customer_price"
            )
            is not None
        ]

        if not priced_variants:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "has no calculable customer pricing."
            )

        true_starting_price = min(
            row["customer_price"]
            for row in priced_variants
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                "parent starting price does not equal "
                "the minimum variant customer price."
            )

        # Recompute adjustment against the complete supplied family.
        # This is important when callers previously processed batches.

        for row in variants:
            customer_price = row.get(
                "customer_price"
            )

            if customer_price is None:
                row[
                    "final_price_adjustment"
                ] = None
            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ]
                < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends here.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ),
                "mapped_parent": mapped_parent,
                "parent_starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            defaults = (
                self.build_product_defaults(
                    mapped_parent,
                    supplier,
                    catalog,
                )
            )

            # SanMar has no universal parent supplier Net.
            defaults[
                "supplier_price"
            ] = None

            # Customer-facing minimum across this complete family.
            defaults[
                "starting_price"
            ] = true_starting_price

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects.filter(
                    **parent_lookup
                ).first()
            )

            if existing_product is None:

                base_slug = slugify(
                    mapped_parent.get(
                        "name"
                    )
                    or f"sanmar-{product_id}"
                )

                slug = base_slug

                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults[
                    "slug"
                ] = slug

            product, created = (
                Product.objects.update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # SanMar variant pricing must never be represented as
            # Product-level quantity price breaks.
            product.supplier_price_breaks.all().delete()

            # Parent-level primary image remains valid for SanMar.
            self.sync_primary_image(
                product,
                mapped_parent,
            )

            # Avoid violating the one-default-variant constraint while
            # updating an already-synchronized family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            default_part_id = (
                returned_part_ids[0]
                if returned_part_ids
                else None
            )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                # Unpriced variants remain represented but cannot
                # manufacture a customer price.
                if adjustment is None:
                    adjustment = Decimal(
                        "0.00"
                    )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload[
                    "customer_price"
                ] = (
                    str(
                        row[
                            "customer_price"
                        ]
                    )
                    if row.get(
                        "customer_price"
                    )
                    is not None
                    else None
                )

                source_payload[
                    "parent_starting_price"
                ] = str(
                    true_starting_price
                )

                source_payload[
                    "price_adjustment"
                ] = (
                    str(
                        row[
                            "final_price_adjustment"
                        ]
                    )
                    if row.get(
                        "final_price_adjustment"
                    )
                    is not None
                    else None
                )

                variant_defaults = {
                    "name": (
                        row.get("name")
                        or part_id
                    ),

                    # Exact supplier part ID is our deterministic
                    # per-parent variant SKU.
                    "supplier_sku": part_id,

                    "color": (
                        row.get("color")
                        or ""
                    ),

                    "size": (
                        row.get("size")
                        or ""
                    ),

                    "material": (
                        row.get("material")
                        or ""
                    ),

                    "price_adjustment": (
                        adjustment
                    ),

                    "inventory_status": (
                        "unknown"
                    ),

                    "is_default": (
                        part_id
                        == default_part_id
                    ),

                    "is_active": True,

                    "order": order,

                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            # Ensure exactly one active default variant.
            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }

    @staticmethod
    def _extract_sanmar_exact_part(
        product_data,
        expected_part_id,
    ):
        product_data = (
            product_data
            or {}
        )

        part_array = (
            product_data.get(
                "ProductPartArray"
            )
            or {}
        )

        parts = (
            part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            parts,
            list,
        ):
            parts = [parts]

        expected = str(
            expected_part_id
            or ""
        ).strip()

        for part in parts:
            if not isinstance(
                part,
                dict,
            ):
                continue

            actual = str(
                part.get("partId")
                or ""
            ).strip()

            if actual == expected:
                return part

        if (
            len(parts) == 1
            and isinstance(
                parts[0],
                dict,
            )
        ):
            return parts[0]

        return {}

    @staticmethod
    def _extract_sanmar_color(
        part,
    ):
        part = part or {}

        primary_color = (
            part.get(
                "primaryColor"
            )
            or {}
        )

        color = (
            primary_color.get(
                "Color"
            )
            or {}
        )

        if isinstance(
            color,
            list,
        ):
            color = (
                color[0]
                if color
                else {}
            )

        if not isinstance(
            color,
            dict,
        ):
            return ""

        return str(
            color.get(
                "colorName"
            )
            or color.get(
                "standardColorName"
            )
            or ""
        ).strip()

    @staticmethod
    def _extract_sanmar_size(
        part,
    ):
        part = part or {}

        apparel_size = (
            part.get(
                "ApparelSize"
            )
            or {}
        )

        if isinstance(
            apparel_size,
            list,
        ):
            apparel_size = (
                apparel_size[0]
                if apparel_size
                else {}
            )

        if not isinstance(
            apparel_size,
            dict,
        ):
            return ""

        return str(
            apparel_size.get(
                "labelSize"
            )
            or apparel_size.get(
                "customSize"
            )
            or apparel_size.get(
                "size"
            )
            or ""
        ).strip()

    # ==========================================================
    # PCNA PARENT / VARIANT SUPPORT
    # ==========================================================

    @staticmethod
    def _pcna_text(value):
        """
        Normalize PromoStandards scalar/list text values.
        """
        if value is None:
            return ""

        if isinstance(value, (list, tuple)):
            values = [
                HPGSyncService._pcna_text(item)
                for item in value
            ]
            return " ".join(
                item
                for item in values
                if item
            ).strip()

        if isinstance(value, dict):
            for key in (
                "value",
                "_value_1",
                "name",
                "colorName",
                "size",
                "material",
            ):
                if value.get(key) not in (
                    None,
                    "",
                ):
                    return str(
                        value[key]
                    ).strip()

            return ""

        return str(value).strip()


    @staticmethod
    def _pcna_part_color(part):
        """
        Prefer PCNA primaryColor; fall back to ColorArray.
        """
        primary = (
            part.get("primaryColor")
            or {}
        )

        color = HPGSyncService._pcna_text(
            primary
        )

        if color:
            return color

        color_array = (
            part.get("ColorArray")
            or {}
        )

        colors = (
            color_array.get("Color")
            or []
        )

        if not isinstance(colors, list):
            colors = [colors]

        for item in colors:
            color = HPGSyncService._pcna_text(
                item
            )
            if color:
                return color

        return ""


    @staticmethod
    def _pcna_part_size(part):
        return HPGSyncService._pcna_text(
            part.get("ApparelSize")
        )


    @staticmethod
    def _pcna_part_material(part):
        return HPGSyncService._pcna_text(
            part.get("primaryMaterial")
        )


    @staticmethod
    def _pcna_customer_breaks(
        supplier_breaks,
    ):
        """
        Convert authoritative PCNA Net merchandise breaks
        into customer-facing breaks using the locked 10%
        KaleidoBrands markup.

        Decoration charges are never passed here.
        """
        rows = []

        for supplier_break in (
            supplier_breaks or []
        ):
            supplier_price = (
                supplier_break.get("price")
            )

            if supplier_price is None:
                continue

            customer_price = (
                customer_price_from_supplier_cost(
                    supplier_price
                )
            )

            rows.append({
                "min_quantity": (
                    supplier_break.get(
                        "min_quantity"
                    )
                ),
                "supplier_price": (
                    supplier_price
                ),
                "customer_price": (
                    customer_price
                ),
                "price_uom": (
                    supplier_break.get(
                        "price_uom"
                    )
                ),
                "discount_code": (
                    supplier_break.get(
                        "discount_code"
                    )
                ),
            })

        return rows


    def build_pcna_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build one complete PCNA parent/variant result.

        READ ONLY.

        No Product, ProductVariant, ProductImage, or pricing
        records are created or modified.
        """

        if self.brand != "pcna":
            raise RuntimeError(
                "build_pcna_parent_dry_run() "
                "requires brand='pcna'."
            )

        product_id = str(
            product_id or ""
        ).strip()

        bundle = (
            self.client.get_pcna_parent_bundle(
                product_id,
                part_ids,
            )
        )

        parent_data = (
            bundle.get("product")
            or {}
        )

        name = (
            self._pcna_text(
                parent_data.get(
                    "productName"
                )
            )
            or product_id
        )

        description = self._pcna_text(
            parent_data.get(
                "description"
            )
            or parent_data.get(
                "productDescription"
            )
        )

        primary_image = (
            bundle.get("primary_image")
            or {}
        )

        image_url = ""

        if isinstance(
            primary_image,
            dict,
        ):
            image_url = str(
                primary_image.get("url")
                or ""
            ).strip()

        # ------------------------------------------------------
        # Category
        #
        # Reuse the existing supplier/category mapper. Do not
        # create arbitrary PCNA categories.
        # ------------------------------------------------------

        category = None

        if self.brand != "pcna":
            try:
                category = self.resolve_category(
                    parent_data
                )
            except Exception:
                category = None

        variants = []
        customer_prices = []

        for row in (
            bundle.get("variants")
            or []
        ):
            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            part_array = (
                product_data.get(
                    "ProductPartArray"
                )
                or {}
            )

            parts = (
                part_array.get(
                    "ProductPart"
                )
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            exact_part = None

            for part in parts:
                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                if (
                    str(
                        part.get("partId")
                        or ""
                    ).strip()
                    == part_id
                ):
                    exact_part = part
                    break

            if exact_part is None:
                raise RuntimeError(
                    f"PCNA parent {product_id} "
                    f"is missing exact part "
                    f"{part_id}."
                )

            supplier_breaks = []

            pricing = row.get(
                "pricing"
            )

            if pricing:
                supplier_breaks = (
                    extract_net_price_breaks(
                        pricing
                    )
                )

            customer_breaks = (
                self._pcna_customer_breaks(
                    supplier_breaks
                )
            )

            calculable = [
                item["customer_price"]
                for item in customer_breaks
                if item.get(
                    "customer_price"
                ) is not None
            ]

            # Starting/base variant display price follows the
            # existing KaleidoBrands "Starting at" rule:
            # lowest customer-facing tier.
            variant_customer_price = (
                min(calculable)
                if calculable
                else None
            )

            if (
                variant_customer_price
                is not None
            ):
                customer_prices.append(
                    variant_customer_price
                )

            part_description = (
                self._pcna_text(
                    exact_part.get(
                        "description"
                    )
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "sku": part_id,
                "supplier_sku": part_id,
                "name": part_description,
                "color": (
                    self._pcna_part_color(
                        exact_part
                    )
                ),
                "size": (
                    self._pcna_part_size(
                        exact_part
                    )
                ),
                "material": (
                    self._pcna_part_material(
                        exact_part
                    )
                ),
                "supplier_breaks": (
                    supplier_breaks
                ),
                "customer_breaks": (
                    customer_breaks
                ),
                "customer_price": (
                    variant_customer_price
                ),
                "pricing_error": (
                    row.get("error")
                ),
                "source_payload": {
                    "supplier": "PCNA",
                    "parent_product_id": (
                        product_id
                    ),
                    "part_id": part_id,
                    "product_part": (
                        exact_part
                    ),
                    "supplier_price_breaks": (
                        supplier_breaks
                    ),
                    "customer_price_breaks": (
                        customer_breaks
                    ),
                    "pricing_error": (
                        row.get("error")
                    ),
                    "fob_id": (
                        bundle.get(
                            "fob_id"
                        )
                    ),
                },
            })

        starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        return {
            "product_id": product_id,
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "external_image_url": (
                image_url
            ),
            "category": category,
            "supplier_price": None,
            "starting_price": (
                starting_price
            ),
            "fob_id": (
                bundle.get("fob_id")
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": sum(
                1
                for row in variants
                if row.get(
                    "customer_price"
                ) is not None
            ),
            "variants": variants,
        }

    def sync_pcna_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one PCNA parent product and its ProductVariant rows.

        PCNA pricing is relationship-specific:

            parent productId + partId -> pricing context

        A shared part can legitimately have pricing under its standalone
        parent while having no pricing under a gift-set/composite parent.

        Therefore:

        - Never borrow pricing from another parent/part relationship.
        - Product.supplier_price remains None.
        - No Product-level SupplierPriceBreak rows are created.
        - Product.starting_price is the minimum calculable customer
          price across this parent family.
        - Valid unpriced variants remain persisted.
        - Full supplier/customer quantity tiers remain in
          ProductVariant.source_payload.
        """

        if self.brand != "pcna":
            raise RuntimeError(
                "sync_pcna_parent() is only available "
                "for the PCNA integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"PCNA product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization BEFORE database writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_pcna_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        variants = list(
            normalized.get("variants")
            or []
        )

        parent_starting_price = (
            normalized.get("starting_price")
        )

        # ----------------------------------------------------------
        # Safety validation
        # ----------------------------------------------------------

        returned_part_ids = [
            str(
                row.get("part_id")
                or row.get("sku")
                or ""
            ).strip()
            for row in variants
        ]

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"PCNA product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        if (
            len(set(returned_part_ids))
            != len(returned_part_ids)
        ):
            raise RuntimeError(
                f"PCNA product {product_id} "
                "returned duplicate part IDs."
            )

        if (
            set(returned_part_ids)
            != set(normalized_part_ids)
        ):
            raise RuntimeError(
                f"PCNA product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        priced_variants = [
            row
            for row in variants
            if row.get("customer_price")
            is not None
        ]

        true_starting_price = (
            min(
                row["customer_price"]
                for row in priced_variants
            )
            if priced_variants
            else None
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"PCNA product {product_id} "
                "parent starting price does not equal "
                "the minimum calculable variant "
                "customer price."
            )

        # Recompute adjustments against the complete family.
        for row in variants:

            customer_price = row.get(
                "customer_price"
            )

            if (
                customer_price is None
                or true_starting_price is None
            ):
                row[
                    "final_price_adjustment"
                ] = None

            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ] < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"PCNA product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends before DB mutation.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ).strip(),
                "name": normalized.get("name"),
                "starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "priced_variant_count": len(
                    priced_variants
                ),
                "unpriced_variant_count": (
                    len(variants)
                    - len(priced_variants)
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            now = timezone.now()

            product_name = (
                normalized.get("name")
                or str(product_id).strip()
            )

            product_description = (
                normalized.get("description")
                or ""
            )

            category = normalized.get(
                "category"
            )

            external_image_url = (
                normalized.get(
                    "external_image_url"
                )
                or ""
            )

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects
                .filter(
                    **parent_lookup
                )
                .first()
            )

            defaults = {
                "supplier": (
                    self.brand_config[
                        "product_supplier_name"
                    ]
                ),
                "supplier_record": supplier,
                "catalog": catalog,
                "category": category,
                "name": product_name,
                "short_description": "",
                "description": (
                    product_description
                ),
                "supplier_price": None,
                "starting_price": (
                    true_starting_price
                ),
                "external_image_url": (
                    external_image_url
                ),
                "source": "PromoStandards",
                "supplier_last_synced_at": now,
                "last_synced_at": now,
                "is_active": True,
                "sku": str(
                    product_id
                ).strip(),
                "supplier_product_id": str(
                    product_id
                ).strip(),
            }

            if existing_product is None:

                base_slug = slugify(
                    product_name
                    or f"pcna-{product_id}"
                )

                if not base_slug:
                    base_slug = (
                        f"pcna-{product_id}"
                    )

                slug = base_slug
                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults["slug"] = slug

            product, created = (
                Product.objects
                .update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # PCNA relationship pricing must NEVER become
            # Product-level SupplierPriceBreak rows.
            product.supplier_price_breaks.all().delete()

            # Parent-level media is authoritative for PCNA.
            if external_image_url:

                mapped_image = {
                    "external_image_url": (
                        external_image_url
                    )
                }

                self.sync_primary_image(
                    product,
                    mapped_image,
                )

            # Clear existing default before rebuilding the family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            # Prefer the first priced relationship as the default.
            # If the entire family is unpriced, preserve the first
            # relationship as the structural default.
            default_part_id = None

            if priced_variants:
                default_part_id = str(
                    priced_variants[0].get(
                        "part_id"
                    )
                    or priced_variants[0].get(
                        "sku"
                    )
                    or ""
                ).strip()

            elif returned_part_ids:
                default_part_id = (
                    returned_part_ids[0]
                )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or row.get("sku")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                customer_price = row.get(
                    "customer_price"
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                pricing_available = (
                    customer_price is not None
                )

                # ProductVariant.price_adjustment is non-null.
                # Zero is storage-only for an unpriced relationship;
                # pricing_available in source_payload is authoritative
                # and prevents callers from treating it as purchasable.
                stored_adjustment = (
                    adjustment
                    if adjustment is not None
                    else Decimal("0.00")
                )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload.update({
                    "supplier": "PCNA",
                    "parent_product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "pricing_available": (
                        pricing_available
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "parent_starting_price": (
                        str(true_starting_price)
                        if true_starting_price
                        is not None
                        else None
                    ),
                    "price_adjustment": (
                        str(adjustment)
                        if adjustment
                        is not None
                        else None
                    ),
                })
                # PCNA SOAP payloads can contain Decimal, datetime,
                # OrderedDict and other values that Django JSONField
                # cannot validate directly.
                source_payload = (
                    self._pcna_json_safe(
                        source_payload
                    )
                )

                variant_name = (
                    row.get("name")
                    or part_id
                )

                variant_defaults = {
                    "name": variant_name,
                    "supplier_sku": part_id,
                    "color": (
                        row.get("color")
                        or ""
                    ),
                    "size": (
                        row.get("size")
                        or ""
                    ),
                    "material": (
                        row.get("material")
                        or ""
                    ),
                    "price_adjustment": (
                        stored_adjustment
                    ),
                    "inventory_status": (
                        "unknown"
                    ),
                    "is_default": (
                        part_id
                        == default_part_id
                    ),
                    "is_active": True,
                    "order": order,
                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ).strip(),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": len(
                priced_variants
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(priced_variants)
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }


    def build_magnet_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build one complete The Magnet Group parent/variant result.

        READ ONLY.

        Uses the dedicated Magnet client bundle and the existing
        hardened normalization/pricing helpers.

        Supplier-cost contract:
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Decoration charges remain separate from merchandise pricing.

        No database writes occur here.
        """

        if self.brand != "magnet":
            raise RuntimeError(
                "build_magnet_parent_dry_run() "
                "requires brand='magnet'."
            )

        product_id = str(
            product_id or ""
        ).strip()

        bundle = (
            self.client.get_magnet_parent_bundle(
                product_id,
                part_ids,
            )
        )

        parent_data = (
            bundle.get("product")
            or {}
        )

        name = (
            self._pcna_text(
                parent_data.get(
                    "productName"
                )
            )
            or product_id
        )

        description = self._pcna_text(
            parent_data.get(
                "description"
            )
            or parent_data.get(
                "productDescription"
            )
        )

        image_url = str(
            bundle.get(
                "primary_image_url"
            )
            or ""
        ).strip()

        # Do not create arbitrary categories.
        mapped_for_category = {
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "short_description": "",
            "supplier_categories": [],
        }

        category = self.resolve_category(
            mapped_for_category
        )

        variants = []
        customer_prices = []

        for row in (
            bundle.get("variants")
            or []
        ):

            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            part_array = (
                product_data.get(
                    "ProductPartArray"
                )
                or {}
            )

            parts = (
                part_array.get(
                    "ProductPart"
                )
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            exact_part = None

            for part in parts:

                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                if (
                    str(
                        part.get("partId")
                        or ""
                    ).strip()
                    == part_id
                ):
                    exact_part = part
                    break

            if exact_part is None:
                raise RuntimeError(
                    f"Magnet parent {product_id} "
                    f"is missing exact part "
                    f"{part_id}."
                )

            # --------------------------------------------------
            # Supplier pricing
            #
            # The client already requested exact-part:
            # Net + Blank + USD.
            #
            # Do not use decoration ChargeArray as merchandise
            # cost and do not borrow another part's price.
            # --------------------------------------------------

            supplier_breaks = []

            pricing = row.get(
                "pricing"
            )

            if pricing:
                extracted_breaks = (
                    extract_net_price_breaks(
                        pricing
                    )
                )

                # Magnet PPC can return price rows for the entire
                # parent family even when an exact partId was sent.
                #
                # Keep only the authoritative breaks belonging to
                # this exact variant. Never allow one Magnet part
                # to inherit another part's merchandise pricing.
                supplier_breaks = [
                    item
                    for item in extracted_breaks
                    if str(
                        item.get("part_id")
                        or ""
                    ).strip() == part_id
                ]

            customer_breaks = (
                self._pcna_customer_breaks(
                    supplier_breaks
                )
            )

            calculable = [
                item["customer_price"]
                for item in customer_breaks
                if item.get(
                    "customer_price"
                ) is not None
            ]

            variant_customer_price = (
                min(calculable)
                if calculable
                else None
            )

            if (
                variant_customer_price
                is not None
            ):
                customer_prices.append(
                    variant_customer_price
                )

            part_description = (
                self._pcna_text(
                    exact_part.get(
                        "description"
                    )
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "sku": part_id,
                "supplier_sku": part_id,
                "name": part_description,
                "color": (
                    self._pcna_part_color(
                        exact_part
                    )
                ),
                "size": (
                    self._pcna_part_size(
                        exact_part
                    )
                ),
                "material": (
                    self._pcna_part_material(
                        exact_part
                    )
                ),
                "supplier_breaks": (
                    supplier_breaks
                ),
                "customer_breaks": (
                    customer_breaks
                ),
                "customer_price": (
                    variant_customer_price
                ),
                "pricing_error": (
                    row.get("error")
                ),
                "source_payload": {
                    "supplier": (
                        "The Magnet Group"
                    ),
                    "parent_product_id": (
                        product_id
                    ),
                    "part_id": part_id,
                    "product_part": (
                        exact_part
                    ),
                    "supplier_price_breaks": (
                        supplier_breaks
                    ),
                    "customer_price_breaks": (
                        customer_breaks
                    ),
                    "pricing_error": (
                        row.get("error")
                    ),
                    "fob_id": (
                        bundle.get(
                            "fob_id"
                        )
                    ),
                    "pricing_contract": {
                        "price_type": "Net",
                        "configuration_type": (
                            "Blank"
                        ),
                        "currency": "USD",
                    },
                },
            })

        starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        return {
            "product_id": product_id,
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "external_image_url": (
                image_url
            ),
            "category": category,
            "supplier_price": None,
            "starting_price": (
                starting_price
            ),
            "fob_id": (
                bundle.get("fob_id")
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": sum(
                1
                for row in variants
                if row.get(
                    "customer_price"
                ) is not None
            ),
            "variants": variants,
        }


    def build_koozie_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build one complete Koozie parent/variant result.

        READ ONLY.
        """

        if self.brand != "koozie":
            raise RuntimeError(
                "build_koozie_parent_dry_run() "
                "requires brand='koozie'."
            )

        product_id = str(
            product_id or ""
        ).strip()

        bundle = (
            self.client.get_koozie_parent_bundle(
                product_id,
                part_ids,
            )
        )

        parent_data = (
            bundle.get("product")
            or {}
        )

        name = (
            self._pcna_text(
                parent_data.get(
                    "productName"
                )
            )
            or product_id
        )

        description = self._pcna_text(
            parent_data.get(
                "description"
            )
            or parent_data.get(
                "productDescription"
            )
        )

        image_url = str(
            bundle.get(
                "primary_image_url"
            )
            or ""
        ).strip()

        # Do not create arbitrary categories.
        mapped_for_category = {
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "short_description": "",
            "supplier_categories": [],
        }

        category = self.resolve_category(
            mapped_for_category
        )

        variants = []
        customer_prices = []

        for row in (
            bundle.get("variants")
            or []
        ):

            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            part_array = (
                product_data.get(
                    "ProductPartArray"
                )
                or {}
            )

            parts = (
                part_array.get(
                    "ProductPart"
                )
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            exact_part = None

            for part in parts:

                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                if (
                    str(
                        part.get("partId")
                        or ""
                    ).strip()
                    == part_id
                ):
                    exact_part = part
                    break

            if exact_part is None:
                raise RuntimeError(
                    f"Koozie parent {product_id} "
                    f"is missing exact part "
                    f"{part_id}."
                )

            supplier_breaks = []

            pricing = row.get(
                "pricing"
            )

            if pricing:
                supplier_breaks = (
                    extract_net_price_breaks(
                        pricing
                    )
                )

            customer_breaks = (
                self._pcna_customer_breaks(
                    supplier_breaks
                )
            )

            calculable = [
                item["customer_price"]
                for item in customer_breaks
                if item.get(
                    "customer_price"
                ) is not None
            ]

            variant_customer_price = (
                min(calculable)
                if calculable
                else None
            )

            if (
                variant_customer_price
                is not None
            ):
                customer_prices.append(
                    variant_customer_price
                )

            part_description = (
                self._pcna_text(
                    exact_part.get(
                        "description"
                    )
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "sku": part_id,
                "supplier_sku": part_id,
                "name": part_description,
                "color": (
                    self._pcna_part_color(
                        exact_part
                    )
                ),
                "size": (
                    self._pcna_part_size(
                        exact_part
                    )
                ),
                "material": (
                    self._pcna_part_material(
                        exact_part
                    )
                ),
                "supplier_breaks": (
                    supplier_breaks
                ),
                "customer_breaks": (
                    customer_breaks
                ),
                "customer_price": (
                    variant_customer_price
                ),
                "pricing_error": (
                    row.get("error")
                ),
                "source_payload": {
                    "supplier": "Koozie Group",
                    "parent_product_id": (
                        product_id
                    ),
                    "part_id": part_id,
                    "product_part": (
                        exact_part
                    ),
                    "supplier_price_breaks": (
                        supplier_breaks
                    ),
                    "customer_price_breaks": (
                        customer_breaks
                    ),
                    "pricing_error": (
                        row.get("error")
                    ),
                    "fob_id": (
                        bundle.get(
                            "fob_id"
                        )
                    ),
                    "pricing_contract": {
                        "price_type": "Net",
                        "configuration_type": (
                            "Blank"
                        ),
                        "currency": "USD",
                    },
                },
            })

        starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        return {
            "product_id": product_id,
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "external_image_url": (
                image_url
            ),
            "category": category,
            "supplier_price": None,
            "starting_price": (
                starting_price
            ),
            "fob_id": (
                bundle.get("fob_id")
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": sum(
                1
                for row in variants
                if row.get(
                    "customer_price"
                ) is not None
            ),
            "variants": variants,
        }


    def sync_koozie_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one Koozie parent product and its ProductVariant rows.

        Koozie pricing is exact-part-specific:

            parent productId + partId -> pricing context

        A shared part can legitimately have pricing under its standalone
        parent while having no pricing under a gift-set/composite parent.

        Therefore:

        - Never borrow pricing from another parent/part relationship.
        - Product.supplier_price remains None.
        - No Product-level SupplierPriceBreak rows are created.
        - Product.starting_price is the minimum calculable customer
          price across this parent family.
        - Valid unpriced variants remain persisted.
        - Full supplier/customer quantity tiers remain in
          ProductVariant.source_payload.
        """

        if self.brand != "koozie":
            raise RuntimeError(
                "sync_koozie_parent() is only available "
                "for the Koozie integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"Koozie product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization BEFORE database writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_koozie_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        variants = list(
            normalized.get("variants")
            or []
        )

        parent_starting_price = (
            normalized.get("starting_price")
        )

        # ----------------------------------------------------------
        # Safety validation
        # ----------------------------------------------------------

        returned_part_ids = [
            str(
                row.get("part_id")
                or row.get("sku")
                or ""
            ).strip()
            for row in variants
        ]

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"Koozie product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        if (
            len(set(returned_part_ids))
            != len(returned_part_ids)
        ):
            raise RuntimeError(
                f"Koozie product {product_id} "
                "returned duplicate part IDs."
            )

        if (
            set(returned_part_ids)
            != set(normalized_part_ids)
        ):
            raise RuntimeError(
                f"Koozie product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        priced_variants = [
            row
            for row in variants
            if row.get("customer_price")
            is not None
        ]

        true_starting_price = (
            min(
                row["customer_price"]
                for row in priced_variants
            )
            if priced_variants
            else None
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"Koozie product {product_id} "
                "parent starting price does not equal "
                "the minimum calculable variant "
                "customer price."
            )

        # Recompute adjustments against the complete family.
        for row in variants:

            customer_price = row.get(
                "customer_price"
            )

            if (
                customer_price is None
                or true_starting_price is None
            ):
                row[
                    "final_price_adjustment"
                ] = None

            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ] < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"Koozie product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends before DB mutation.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ).strip(),
                "name": normalized.get("name"),
                "starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "priced_variant_count": len(
                    priced_variants
                ),
                "unpriced_variant_count": (
                    len(variants)
                    - len(priced_variants)
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            now = timezone.now()

            product_name = (
                normalized.get("name")
                or str(product_id).strip()
            )

            product_description = (
                normalized.get("description")
                or ""
            )

            category = normalized.get(
                "category"
            )

            external_image_url = (
                normalized.get(
                    "external_image_url"
                )
                or ""
            )

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects
                .filter(
                    **parent_lookup
                )
                .first()
            )

            defaults = {
                "supplier": (
                    self.brand_config[
                        "product_supplier_name"
                    ]
                ),
                "supplier_record": supplier,
                "catalog": catalog,
                "category": category,
                "name": product_name,
                "short_description": "",
                "description": (
                    product_description
                ),
                "supplier_price": None,
                "starting_price": (
                    true_starting_price
                ),
                "external_image_url": (
                    external_image_url
                ),
                "source": "PromoStandards",
                "supplier_last_synced_at": now,
                "last_synced_at": now,
                "is_active": True,
                "sku": str(
                    product_id
                ).strip(),
                "supplier_product_id": str(
                    product_id
                ).strip(),
            }

            if existing_product is None:

                base_slug = slugify(
                    product_name
                    or f"koozie-{product_id}"
                )

                if not base_slug:
                    base_slug = (
                        f"koozie-{product_id}"
                    )

                slug = base_slug
                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults["slug"] = slug

            product, created = (
                Product.objects
                .update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # Koozie variant pricing must NEVER become
            # Product-level SupplierPriceBreak rows.
            product.supplier_price_breaks.all().delete()

            # Parent-level media is authoritative for Koozie.
            if external_image_url:

                mapped_image = {
                    "external_image_url": (
                        external_image_url
                    )
                }

                self.sync_primary_image(
                    product,
                    mapped_image,
                )

            # Clear existing default before rebuilding the family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            # Prefer the first priced relationship as the default.
            # If the entire family is unpriced, preserve the first
            # relationship as the structural default.
            default_part_id = None

            if priced_variants:
                default_part_id = str(
                    priced_variants[0].get(
                        "part_id"
                    )
                    or priced_variants[0].get(
                        "sku"
                    )
                    or ""
                ).strip()

            elif returned_part_ids:
                default_part_id = (
                    returned_part_ids[0]
                )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or row.get("sku")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                customer_price = row.get(
                    "customer_price"
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                pricing_available = (
                    customer_price is not None
                )

                # ProductVariant.price_adjustment is non-null.
                # Zero is storage-only for an unpriced relationship;
                # pricing_available in source_payload is authoritative
                # and prevents callers from treating it as purchasable.
                stored_adjustment = (
                    adjustment
                    if adjustment is not None
                    else Decimal("0.00")
                )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload.update({
                    "supplier": "Koozie Group",
                    "parent_product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "pricing_available": (
                        pricing_available
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "parent_starting_price": (
                        str(true_starting_price)
                        if true_starting_price
                        is not None
                        else None
                    ),
                    "price_adjustment": (
                        str(adjustment)
                        if adjustment
                        is not None
                        else None
                    ),
                })
                # Koozie SOAP payloads can contain Decimal, datetime,
                # OrderedDict and other values that Django JSONField
                # cannot validate directly.
                source_payload = (
                    self._pcna_json_safe(
                        source_payload
                    )
                )

                variant_name = (
                    row.get("name")
                    or part_id
                )

                variant_defaults = {
                    "name": variant_name,
                    "supplier_sku": part_id,
                    "color": (
                        row.get("color")
                        or ""
                    ),
                    "size": (
                        row.get("size")
                        or ""
                    ),
                    "material": (
                        row.get("material")
                        or ""
                    ),
                    "price_adjustment": (
                        stored_adjustment
                    ),
                    "inventory_status": (
                        "unknown"
                    ),
                    "is_default": (
                        part_id
                        == default_part_id
                    ),
                    "is_active": True,
                    "order": order,
                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ).strip(),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": len(
                priced_variants
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(priced_variants)
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }


    def sync_magnet_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one Koozie parent product and its ProductVariant rows.

        Koozie pricing is exact-part-specific:

            parent productId + partId -> pricing context

        A shared part can legitimately have pricing under its standalone
        parent while having no pricing under a gift-set/composite parent.

        Therefore:

        - Never borrow pricing from another parent/part relationship.
        - Product.supplier_price remains None.
        - No Product-level SupplierPriceBreak rows are created.
        - Product.starting_price is the minimum calculable customer
          price across this parent family.
        - Valid unpriced variants remain persisted.
        - Full supplier/customer quantity tiers remain in
          ProductVariant.source_payload.
        """

        if self.brand != "magnet":
            raise RuntimeError(
                "sync_magnet_parent() is only available "
                "for the Koozie integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"Magnet product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization BEFORE database writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_magnet_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        variants = list(
            normalized.get("variants")
            or []
        )

        parent_starting_price = (
            normalized.get("starting_price")
        )

        # ----------------------------------------------------------
        # Safety validation
        # ----------------------------------------------------------

        returned_part_ids = [
            str(
                row.get("part_id")
                or row.get("sku")
                or ""
            ).strip()
            for row in variants
        ]

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"Magnet product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        if (
            len(set(returned_part_ids))
            != len(returned_part_ids)
        ):
            raise RuntimeError(
                f"Magnet product {product_id} "
                "returned duplicate part IDs."
            )

        if (
            set(returned_part_ids)
            != set(normalized_part_ids)
        ):
            raise RuntimeError(
                f"Magnet product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        priced_variants = [
            row
            for row in variants
            if row.get("customer_price")
            is not None
        ]

        true_starting_price = (
            min(
                row["customer_price"]
                for row in priced_variants
            )
            if priced_variants
            else None
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"Magnet product {product_id} "
                "parent starting price does not equal "
                "the minimum calculable variant "
                "customer price."
            )

        # Recompute adjustments against the complete family.
        for row in variants:

            customer_price = row.get(
                "customer_price"
            )

            if (
                customer_price is None
                or true_starting_price is None
            ):
                row[
                    "final_price_adjustment"
                ] = None

            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ] < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"Magnet product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends before DB mutation.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ).strip(),
                "name": normalized.get("name"),
                "starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "priced_variant_count": len(
                    priced_variants
                ),
                "unpriced_variant_count": (
                    len(variants)
                    - len(priced_variants)
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            now = timezone.now()

            product_name = (
                normalized.get("name")
                or str(product_id).strip()
            )

            product_description = (
                normalized.get("description")
                or ""
            )

            category = normalized.get(
                "category"
            )

            external_image_url = (
                normalized.get(
                    "external_image_url"
                )
                or ""
            )

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects
                .filter(
                    **parent_lookup
                )
                .first()
            )

            defaults = {
                "supplier": (
                    self.brand_config[
                        "product_supplier_name"
                    ]
                ),
                "supplier_record": supplier,
                "catalog": catalog,
                "category": category,
                "name": product_name,
                "short_description": "",
                "description": (
                    product_description
                ),
                "supplier_price": None,
                "starting_price": (
                    true_starting_price
                ),
                "external_image_url": (
                    external_image_url
                ),
                "source": "PromoStandards",
                "supplier_last_synced_at": now,
                "last_synced_at": now,
                "is_active": True,
                "sku": str(
                    product_id
                ).strip(),
                "supplier_product_id": str(
                    product_id
                ).strip(),
            }

            if existing_product is None:

                base_slug = slugify(
                    product_name
                    or f"magnet-{product_id}"
                )

                if not base_slug:
                    base_slug = (
                        f"magnet-{product_id}"
                    )

                slug = base_slug
                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults["slug"] = slug

            product, created = (
                Product.objects
                .update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # Magnet variant pricing must NEVER become
            # Product-level SupplierPriceBreak rows.
            product.supplier_price_breaks.all().delete()

            # Parent-level media is authoritative for Magnet.
            if external_image_url:

                mapped_image = {
                    "external_image_url": (
                        external_image_url
                    )
                }

                self.sync_primary_image(
                    product,
                    mapped_image,
                )

            # Clear existing default before rebuilding the family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            # Prefer the first priced relationship as the default.
            # If the entire family is unpriced, preserve the first
            # relationship as the structural default.
            default_part_id = None

            if priced_variants:
                default_part_id = str(
                    priced_variants[0].get(
                        "part_id"
                    )
                    or priced_variants[0].get(
                        "sku"
                    )
                    or ""
                ).strip()

            elif returned_part_ids:
                default_part_id = (
                    returned_part_ids[0]
                )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or row.get("sku")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                customer_price = row.get(
                    "customer_price"
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                pricing_available = (
                    customer_price is not None
                )

                # ProductVariant.price_adjustment is non-null.
                # Zero is storage-only for an unpriced relationship;
                # pricing_available in source_payload is authoritative
                # and prevents callers from treating it as purchasable.
                stored_adjustment = (
                    adjustment
                    if adjustment is not None
                    else Decimal("0.00")
                )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload.update({
                    "supplier": "The Magnet Group",
                    "parent_product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "pricing_available": (
                        pricing_available
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "parent_starting_price": (
                        str(true_starting_price)
                        if true_starting_price
                        is not None
                        else None
                    ),
                    "price_adjustment": (
                        str(adjustment)
                        if adjustment
                        is not None
                        else None
                    ),
                })
                # Magnet SOAP payloads can contain Decimal, datetime,
                # OrderedDict and other values that Django JSONField
                # cannot validate directly.
                source_payload = (
                    self._pcna_json_safe(
                        source_payload
                    )
                )

                variant_name = (
                    row.get("name")
                    or part_id
                )

                variant_defaults = {
                    "name": variant_name,
                    "supplier_sku": part_id,
                    "color": (
                        row.get("color")
                        or ""
                    ),
                    "size": (
                        row.get("size")
                        or ""
                    ),
                    "material": (
                        row.get("material")
                        or ""
                    ),
                    "price_adjustment": (
                        stored_adjustment
                    ),
                    "inventory_status": (
                        "unknown"
                    ),
                    "is_default": (
                        part_id
                        == default_part_id
                    ),
                    "is_active": True,
                    "order": order,
                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ).strip(),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": len(
                priced_variants
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(priced_variants)
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }

    @staticmethod
    def _pcna_json_safe(value):
        """
        Convert PCNA SOAP/Zeep payload data into values safe for
        Django JSONField persistence without changing the supplier
        data's logical structure.
        """

        return json.loads(
            json.dumps(
                value,
                default=str,
            )
        )
    # ==============================================================
    # Product sync
    # ==============================================================

    def sync_product(
        self,
        product_id,
        part_id=None,
    ):
        bundle = (
            self.client
            .get_product_bundle(
                product_id,
                part_id=part_id,
            )
        )

        mapped = map_product_bundle(
            bundle
        )

        if self.dry_run:
            return {
                "action": "dry-run",
                "product_id": product_id,
                "mapped": mapped,
            }

        with transaction.atomic():

            supplier = (
                self.get_supplier()
            )

            catalog = (
                self.get_catalog(
                    supplier
                )
            )

            defaults = (
                self.build_product_defaults(
                    mapped,
                    supplier,
                    catalog,
                )
            )

            lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": mapped[
                    "supplier_sku"
                ],
            }

            existing_product = (
                Product.objects.filter(
                    **lookup
                ).first()
            )

            if existing_product is None:
                defaults["slug"] = (
                    self.generate_unique_slug(
                        mapped.get("name")
                        or mapped[
                            "supplier_sku"
                        ],
                        mapped[
                            "supplier_sku"
                        ],
                    )
                )
                defaults["sku"] = (
                    mapped.get("supplier_sku")
                    or ""
                )


            product, created = (
                Product.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
            )


            self.sync_primary_image(
                product,
                mapped,
            )

            price_break_result = (
            self.sync_price_breaks(
                product,
                mapped,
            )
        )

        # ----------------------------------------------------------
        # KaleidoBrands customer pricing
        # ----------------------------------------------------------

        #
        customer_price = customer_starting_price(
            product
        )

        if customer_price is not None:
            product.starting_price = customer_price
            product.save(
                update_fields=[
                    "starting_price",
                ]
            )

        supplier.last_synced_at = (
            timezone.now()
        )

        supplier.save(
            update_fields=[
            "last_synced_at"
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_id": product_id,
            "product_pk": product.pk,
            "mapped": mapped,
            "price_breaks": (
                price_break_result
            ),
    }
    def sync_price_breaks(
        self,
        product,
        mapped,
    ):
        """
        Synchronize supplier Net quantity-price breaks.

        Existing price breaks are updated when their values change.

        If the supplier pricing API is temporarily unavailable and
        no price breaks are returned, existing database records are
        preserved.
        """

        price_breaks = (
            mapped.get("price_breaks")
            or []
        )

        if not price_breaks:
            return {
                "created": 0,
                "updated": 0,
                "deleted": 0,
            }

        created_count = 0
        updated_count = 0

        active_keys = set()

        for row in price_breaks:
            min_quantity = row.get(
                "min_quantity"
            )

            price = row.get(
                "price"
            )

            if min_quantity is None:
                continue

            if price is None:
                continue

            part_id = (
                row.get("part_id")
                or ""
            )

            active_keys.add(
                (
                    part_id,
                    min_quantity,
                )
            )

            price_break, created = (
                SupplierPriceBreak.objects.update_or_create(
                    product=product,
                    part_id=part_id,
                    min_quantity=min_quantity,
                    defaults={
                        "price": price,
                        "price_uom": (
                            row.get("price_uom")
                            or ""
                        ),
                        "discount_code": (
                            row.get("discount_code")
                            or ""
                        ),
                        "part_description": (
                            row.get(
                                "part_description"
                            )
                            or ""
                        ),
                        "effective_date": (
                            row.get(
                                "effective_date"
                            )
                        ),
                        "expiry_date": (
                            row.get(
                                "expiry_date"
                            )
                        ),
                    },
                )
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        # Remove old price breaks that the supplier no longer returns.
        deleted_count = 0

        existing_breaks = (
            SupplierPriceBreak.objects
            .filter(product=product)
        )

        for price_break in existing_breaks:
            key = (
                price_break.part_id,
                price_break.min_quantity,
            )

            if key not in active_keys:
                price_break.delete()
                deleted_count += 1

        return {
            "created": created_count,
            "updated": updated_count,
            "deleted": deleted_count,
        }
    # ==============================================================
    # Product image
    # ==============================================================

    def sync_primary_image(
        self,
        product,
        mapped,
    ):
        image_url = (
            mapped.get(
                "external_image_url"
            )
            or ""
        )

        if not image_url:
            return None

        existing = (
            product.gallery_images
            .filter(
                order=0
            )
            .first()
        )

        if existing:
            changed = False

            if (
                existing.external_image_url
                != image_url
            ):
                existing.external_image_url = (
                    image_url
                )
                changed = True

            if not existing.alt_text:
                existing.alt_text = (
                    product.name
                )
                changed = True

            if changed:
                existing.save()

            return existing

        return ProductImage.objects.create(
            product=product,
            external_image_url=image_url,
            alt_text=product.name,
            order=0,
        )

    def generate_unique_slug(
        self,
        name,
        supplier_sku,
    ):
        max_length = (
            Product._meta
            .get_field("slug")
            .max_length
            or 255
        )

        base = slugify(
            f"{name}-{supplier_sku}"
        )

        if not base:
            base = slugify(
                supplier_sku
            ) or "product"

        base = base[:max_length]

        candidate = base
        counter = 2

        while Product.objects.filter(
            slug=candidate
        ).exists():
            suffix = f"-{counter}"

            candidate = (
                base[
                    : max_length
                    - len(suffix)
                ]
                + suffix
            )

            counter += 1

        return candidate

    def build_vantage_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build one complete Vantage Apparel parent/variant result.

        READ ONLY.

        Uses the dedicated Vantage client bundle and the existing
        hardened normalization/pricing helpers.

        Supplier-cost contract:
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Decoration charges remain separate from merchandise pricing.

        No database writes occur here.
        """

        if self.brand != "vantage":
            raise RuntimeError(
                "build_vantage_parent_dry_run() "
                "requires brand='vantage'."
            )

        product_id = str(
            product_id or ""
        ).strip()

        bundle = (
            self.client.get_vantage_parent_bundle(
                product_id,
                part_ids,
            )
        )

        parent_data = (
            bundle.get("product")
            or {}
        )

        name = (
            self._pcna_text(
                parent_data.get(
                    "productName"
                )
            )
            or product_id
        )

        description = self._pcna_text(
            parent_data.get(
                "description"
            )
            or parent_data.get(
                "productDescription"
            )
        )

        image_url = str(
            bundle.get(
                "primary_image_url"
            )
            or ""
        ).strip()

        # Do not create arbitrary categories.
        mapped_for_category = {
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "short_description": "",
            "supplier_categories": [],
        }

        category = self.resolve_category(
            mapped_for_category
        )

        variants = []
        customer_prices = []

        for row in (
            bundle.get("variants")
            or []
        ):

            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            part_array = (
                product_data.get(
                    "ProductPartArray"
                )
                or {}
            )

            parts = (
                part_array.get(
                    "ProductPart"
                )
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            exact_part = None

            for part in parts:

                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                if (
                    str(
                        part.get("partId")
                        or ""
                    ).strip()
                    == part_id
                ):
                    exact_part = part
                    break

            if exact_part is None:
                raise RuntimeError(
                    f"Vantage parent {product_id} "
                    f"is missing exact part "
                    f"{part_id}."
                )

            # --------------------------------------------------
            # Supplier pricing
            #
            # The client already requested exact-part:
            # Net + Blank + USD.
            #
            # Do not use decoration ChargeArray as merchandise
            # cost and do not borrow another part's price.
            # --------------------------------------------------

            supplier_breaks = []

            pricing = row.get(
                "pricing"
            )

            if pricing:
                extracted_breaks = (
                    extract_net_price_breaks(
                        pricing
                    )
                )

                # Vantage PPC can return price rows for the entire
                # parent family even when an exact partId was sent.
                #
                # Keep only the authoritative breaks belonging to
                # this exact variant. Never allow one Vantage part
                # to inherit another part's merchandise pricing.
                supplier_breaks = [
                    item
                    for item in extracted_breaks
                    if str(
                        item.get("part_id")
                        or ""
                    ).strip() == part_id
                ]

            customer_breaks = (
                self._pcna_customer_breaks(
                    supplier_breaks
                )
            )

            calculable = [
                item["customer_price"]
                for item in customer_breaks
                if item.get(
                    "customer_price"
                ) is not None
            ]

            variant_customer_price = (
                min(calculable)
                if calculable
                else None
            )

            if (
                variant_customer_price
                is not None
            ):
                customer_prices.append(
                    variant_customer_price
                )

            part_description = (
                self._pcna_text(
                    exact_part.get(
                        "description"
                    )
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "sku": part_id,
                "supplier_sku": part_id,
                "name": part_description,
                "color": (
                    self._pcna_part_color(
                        exact_part
                    )
                ),
                "size": (
                    self._pcna_part_size(
                        exact_part
                    )
                ),
                "material": (
                    self._pcna_part_material(
                        exact_part
                    )
                ),
                "supplier_breaks": (
                    supplier_breaks
                ),
                "customer_breaks": (
                    customer_breaks
                ),
                "customer_price": (
                    variant_customer_price
                ),
                "pricing_error": (
                    row.get("error")
                ),
                "source_payload": {
                    "supplier": (
                        "Vantage Apparel"
                    ),
                    "parent_product_id": (
                        product_id
                    ),
                    "part_id": part_id,
                    "product_part": (
                        exact_part
                    ),
                    "supplier_price_breaks": (
                        supplier_breaks
                    ),
                    "customer_price_breaks": (
                        customer_breaks
                    ),
                    "pricing_error": (
                        row.get("error")
                    ),
                    "fob_id": (
                        bundle.get(
                            "fob_id"
                        )
                    ),
                    "pricing_contract": {
                        "price_type": "Net",
                        "configuration_type": (
                            "Blank"
                        ),
                        "currency": "USD",
                    },
                },
            })

        starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        return {
            "product_id": product_id,
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "external_image_url": (
                image_url
            ),
            "category": category,
            "supplier_price": None,
            "starting_price": (
                starting_price
            ),
            "fob_id": (
                bundle.get("fob_id")
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": sum(
                1
                for row in variants
                if row.get(
                    "customer_price"
                ) is not None
            ),
            "variants": variants,
        }

    def sync_vantage_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one Koozie parent product and its ProductVariant rows.

        Koozie pricing is exact-part-specific:

            parent productId + partId -> pricing context

        A shared part can legitimately have pricing under its standalone
        parent while having no pricing under a gift-set/composite parent.

        Therefore:

        - Never borrow pricing from another parent/part relationship.
        - Product.supplier_price remains None.
        - No Product-level SupplierPriceBreak rows are created.
        - Product.starting_price is the minimum calculable customer
          price across this parent family.
        - Valid unpriced variants remain persisted.
        - Full supplier/customer quantity tiers remain in
          ProductVariant.source_payload.
        """

        if self.brand != "vantage":
            raise RuntimeError(
                "sync_vantage_parent() is only available "
                "for the Koozie integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"Vantage product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization BEFORE database writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_vantage_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        variants = list(
            normalized.get("variants")
            or []
        )

        parent_starting_price = (
            normalized.get("starting_price")
        )

        # ----------------------------------------------------------
        # Safety validation
        # ----------------------------------------------------------

        returned_part_ids = [
            str(
                row.get("part_id")
                or row.get("sku")
                or ""
            ).strip()
            for row in variants
        ]

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"Vantage product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        if (
            len(set(returned_part_ids))
            != len(returned_part_ids)
        ):
            raise RuntimeError(
                f"Vantage product {product_id} "
                "returned duplicate part IDs."
            )

        if (
            set(returned_part_ids)
            != set(normalized_part_ids)
        ):
            raise RuntimeError(
                f"Vantage product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        priced_variants = [
            row
            for row in variants
            if row.get("customer_price")
            is not None
        ]

        true_starting_price = (
            min(
                row["customer_price"]
                for row in priced_variants
            )
            if priced_variants
            else None
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"Vantage product {product_id} "
                "parent starting price does not equal "
                "the minimum calculable variant "
                "customer price."
            )

        # Recompute adjustments against the complete family.
        for row in variants:

            customer_price = row.get(
                "customer_price"
            )

            if (
                customer_price is None
                or true_starting_price is None
            ):
                row[
                    "final_price_adjustment"
                ] = None

            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ] < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"Vantage product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends before DB mutation.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ).strip(),
                "name": normalized.get("name"),
                "starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "priced_variant_count": len(
                    priced_variants
                ),
                "unpriced_variant_count": (
                    len(variants)
                    - len(priced_variants)
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            now = timezone.now()

            product_name = (
                normalized.get("name")
                or str(product_id).strip()
            )

            product_description = (
                normalized.get("description")
                or ""
            )

            category = normalized.get(
                "category"
            )

            external_image_url = (
                normalized.get(
                    "external_image_url"
                )
                or ""
            )

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects
                .filter(
                    **parent_lookup
                )
                .first()
            )

            defaults = {
                "supplier": (
                    self.brand_config[
                        "product_supplier_name"
                    ]
                ),
                "supplier_record": supplier,
                "catalog": catalog,
                "category": category,
                "name": product_name,
                "short_description": "",
                "description": (
                    product_description
                ),
                "supplier_price": None,
                "starting_price": (
                    true_starting_price
                ),
                "external_image_url": (
                    external_image_url
                ),
                "source": "PromoStandards",
                "supplier_last_synced_at": now,
                "last_synced_at": now,
                "is_active": True,
                "sku": str(
                    product_id
                ).strip(),
                "supplier_product_id": str(
                    product_id
                ).strip(),
            }

            if existing_product is None:

                base_slug = slugify(
                    product_name
                    or f"vantage-{product_id}"
                )

                if not base_slug:
                    base_slug = (
                        f"vantage-{product_id}"
                    )

                slug = base_slug
                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults["slug"] = slug

            product, created = (
                Product.objects
                .update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # Vantage variant pricing must NEVER become
            # Product-level SupplierPriceBreak rows.
            product.supplier_price_breaks.all().delete()

            # Parent-level media is authoritative for Vantage.
            if external_image_url:

                mapped_image = {
                    "external_image_url": (
                        external_image_url
                    )
                }

                self.sync_primary_image(
                    product,
                    mapped_image,
                )

            # Clear existing default before rebuilding the family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            # Prefer the first priced relationship as the default.
            # If the entire family is unpriced, preserve the first
            # relationship as the structural default.
            default_part_id = None

            if priced_variants:
                default_part_id = str(
                    priced_variants[0].get(
                        "part_id"
                    )
                    or priced_variants[0].get(
                        "sku"
                    )
                    or ""
                ).strip()

            elif returned_part_ids:
                default_part_id = (
                    returned_part_ids[0]
                )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or row.get("sku")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                customer_price = row.get(
                    "customer_price"
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                pricing_available = (
                    customer_price is not None
                )

                # ProductVariant.price_adjustment is non-null.
                # Zero is storage-only for an unpriced relationship;
                # pricing_available in source_payload is authoritative
                # and prevents callers from treating it as purchasable.
                stored_adjustment = (
                    adjustment
                    if adjustment is not None
                    else Decimal("0.00")
                )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload.update({
                    "supplier": "Vantage Apparel",
                    "parent_product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "pricing_available": (
                        pricing_available
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "parent_starting_price": (
                        str(true_starting_price)
                        if true_starting_price
                        is not None
                        else None
                    ),
                    "price_adjustment": (
                        str(adjustment)
                        if adjustment
                        is not None
                        else None
                    ),
                })
                # Vantage SOAP payloads can contain Decimal, datetime,
                # OrderedDict and other values that Django JSONField
                # cannot validate directly.
                source_payload = (
                    self._pcna_json_safe(
                        source_payload
                    )
                )

                variant_name = (
                    row.get("name")
                    or part_id
                )

                variant_defaults = {
                    "name": variant_name,
                    "supplier_sku": part_id,
                    "color": (
                        row.get("color")
                        or ""
                    ),
                    "size": (
                        row.get("size")
                        or ""
                    ),
                    "material": (
                        row.get("material")
                        or ""
                    ),
                    "price_adjustment": (
                        stored_adjustment
                    ),
                    "inventory_status": (
                        "unknown"
                    ),
                    "is_default": (
                        part_id
                        == default_part_id
                    ),
                    "is_active": True,
                    "order": order,
                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ).strip(),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": len(
                priced_variants
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(priced_variants)
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }

    def build_jornik_parent_dry_run(
        self,
        product_id,
        part_ids,
    ):
        """
        Build one complete Jornik Manufacturing Corp parent/variant result.

        READ ONLY.

        Uses the dedicated Jornik client bundle and the existing
        hardened normalization/pricing helpers.

        Supplier-cost contract:
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Decoration charges remain separate from merchandise pricing.

        No database writes occur here.
        """

        if self.brand != "jornik":
            raise RuntimeError(
                "build_jornik_parent_dry_run() "
                "requires brand='vantage'."
            )

        product_id = str(
            product_id or ""
        ).strip()

        bundle = (
            self.client.get_jornik_parent_bundle(
                product_id,
                part_ids,
            )
        )

        parent_data = (
            bundle.get("product")
            or {}
        )

        name = (
            self._pcna_text(
                parent_data.get(
                    "productName"
                )
            )
            or product_id
        )

        description = self._pcna_text(
            parent_data.get(
                "description"
            )
            or parent_data.get(
                "productDescription"
            )
        )

        image_url = str(
            bundle.get(
                "primary_image_url"
            )
            or ""
        ).strip()

        # Do not create arbitrary categories.
        mapped_for_category = {
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "short_description": "",
            "supplier_categories": [],
        }

        category = self.resolve_category(
            mapped_for_category
        )

        variants = []
        customer_prices = []

        for row in (
            bundle.get("variants")
            or []
        ):

            part_id = str(
                row.get("part_id")
                or ""
            ).strip()

            product_data = (
                row.get("product")
                or {}
            )

            part_array = (
                product_data.get(
                    "ProductPartArray"
                )
                or {}
            )

            parts = (
                part_array.get(
                    "ProductPart"
                )
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            exact_part = None

            for part in parts:

                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                if (
                    str(
                        part.get("partId")
                        or ""
                    ).strip()
                    == part_id
                ):
                    exact_part = part
                    break

            if exact_part is None:
                raise RuntimeError(
                    f"Jornik parent {product_id} "
                    f"is missing exact part "
                    f"{part_id}."
                )

            # --------------------------------------------------
            # Supplier pricing
            #
            # The client already requested exact-part:
            # Net + Blank + USD.
            #
            # Do not use decoration ChargeArray as merchandise
            # cost and do not borrow another part's price.
            # --------------------------------------------------

            supplier_breaks = []

            pricing = row.get(
                "pricing"
            )

            if pricing:
                extracted_breaks = (
                    extract_net_price_breaks(
                        pricing
                    )
                )

                # Jornik PPC can return price rows for the entire
                # parent family even when an exact partId was sent.
                #
                # Keep only the authoritative breaks belonging to
                # this exact variant. Never allow one Jornik part
                # to inherit another part's merchandise pricing.
                supplier_breaks = [
                    item
                    for item in extracted_breaks
                    if str(
                        item.get("part_id")
                        or ""
                    ).strip() == part_id
                ]

            customer_breaks = (
                self._pcna_customer_breaks(
                    supplier_breaks
                )
            )

            calculable = [
                item["customer_price"]
                for item in customer_breaks
                if item.get(
                    "customer_price"
                ) is not None
            ]

            variant_customer_price = (
                min(calculable)
                if calculable
                else None
            )

            if (
                variant_customer_price
                is not None
            ):
                customer_prices.append(
                    variant_customer_price
                )

            part_description = (
                self._pcna_text(
                    exact_part.get(
                        "description"
                    )
                )
                or part_id
            )

            variants.append({
                "part_id": part_id,
                "sku": part_id,
                "supplier_sku": part_id,
                "name": part_description,
                "color": (
                    self._pcna_part_color(
                        exact_part
                    )
                ),
                "size": (
                    self._pcna_part_size(
                        exact_part
                    )
                ),
                "material": (
                    self._pcna_part_material(
                        exact_part
                    )
                ),
                "supplier_breaks": (
                    supplier_breaks
                ),
                "customer_breaks": (
                    customer_breaks
                ),
                "customer_price": (
                    variant_customer_price
                ),
                "pricing_error": (
                    row.get("error")
                ),
                "source_payload": {
                    "supplier": (
                        "Jornik Manufacturing Corp"
                    ),
                    "parent_product_id": (
                        product_id
                    ),
                    "part_id": part_id,
                    "product_part": (
                        exact_part
                    ),
                    "supplier_price_breaks": (
                        supplier_breaks
                    ),
                    "customer_price_breaks": (
                        customer_breaks
                    ),
                    "pricing_error": (
                        row.get("error")
                    ),
                    "fob_id": (
                        bundle.get(
                            "fob_id"
                        )
                    ),
                    "pricing_contract": {
                        "price_type": "Net",
                        "configuration_type": (
                            "Blank"
                        ),
                        "currency": "USD",
                    },
                },
            })

        starting_price = (
            min(customer_prices)
            if customer_prices
            else None
        )

        return {
            "product_id": product_id,
            "supplier_sku": product_id,
            "name": name,
            "description": description,
            "external_image_url": (
                image_url
            ),
            "category": category,
            "supplier_price": None,
            "starting_price": (
                starting_price
            ),
            "fob_id": (
                bundle.get("fob_id")
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": sum(
                1
                for row in variants
                if row.get(
                    "customer_price"
                ) is not None
            ),
            "variants": variants,
        }

    def sync_jornik_parent(
        self,
        product_id,
        part_ids,
        *,
        complete_family=False,
    ):
        """
        Persist one Koozie parent product and its ProductVariant rows.

        Koozie pricing is exact-part-specific:

            parent productId + partId -> pricing context

        A shared part can legitimately have pricing under its standalone
        parent while having no pricing under a gift-set/composite parent.

        Therefore:

        - Never borrow pricing from another parent/part relationship.
        - Product.supplier_price remains None.
        - No Product-level SupplierPriceBreak rows are created.
        - Product.starting_price is the minimum calculable customer
          price across this parent family.
        - Valid unpriced variants remain persisted.
        - Full supplier/customer quantity tiers remain in
          ProductVariant.source_payload.
        """

        if self.brand != "jornik":
            raise RuntimeError(
                "sync_jornik_parent() is only available "
                "for the Koozie integration."
            )

        normalized_part_ids = []

        for part_id in part_ids or []:
            value = str(
                part_id or ""
            ).strip()

            if (
                value
                and value not in normalized_part_ids
            ):
                normalized_part_ids.append(
                    value
                )

        if not normalized_part_ids:
            raise RuntimeError(
                f"Jornik product {product_id} "
                "has no part IDs."
            )

        # ----------------------------------------------------------
        # Supplier reads + normalization BEFORE database writes.
        # ----------------------------------------------------------

        normalized = (
            self.build_jornik_parent_dry_run(
                product_id,
                normalized_part_ids,
            )
        )

        variants = list(
            normalized.get("variants")
            or []
        )

        parent_starting_price = (
            normalized.get("starting_price")
        )

        # ----------------------------------------------------------
        # Safety validation
        # ----------------------------------------------------------

        returned_part_ids = [
            str(
                row.get("part_id")
                or row.get("sku")
                or ""
            ).strip()
            for row in variants
        ]

        if len(variants) != len(
            normalized_part_ids
        ):
            raise RuntimeError(
                f"Jornik product {product_id} "
                "did not return the complete requested "
                "variant set."
            )

        if (
            len(set(returned_part_ids))
            != len(returned_part_ids)
        ):
            raise RuntimeError(
                f"Jornik product {product_id} "
                "returned duplicate part IDs."
            )

        if (
            set(returned_part_ids)
            != set(normalized_part_ids)
        ):
            raise RuntimeError(
                f"Jornik product {product_id} "
                "returned a different variant set "
                "than requested."
            )

        priced_variants = [
            row
            for row in variants
            if row.get("customer_price")
            is not None
        ]

        true_starting_price = (
            min(
                row["customer_price"]
                for row in priced_variants
            )
            if priced_variants
            else None
        )

        if (
            parent_starting_price
            != true_starting_price
        ):
            raise RuntimeError(
                f"Jornik product {product_id} "
                "parent starting price does not equal "
                "the minimum calculable variant "
                "customer price."
            )

        # Recompute adjustments against the complete family.
        for row in variants:

            customer_price = row.get(
                "customer_price"
            )

            if (
                customer_price is None
                or true_starting_price is None
            ):
                row[
                    "final_price_adjustment"
                ] = None

            else:
                row[
                    "final_price_adjustment"
                ] = (
                    customer_price
                    - true_starting_price
                ).quantize(
                    Decimal("0.01")
                )

        negative_adjustments = [
            row
            for row in variants
            if (
                row.get(
                    "final_price_adjustment"
                )
                is not None
                and row[
                    "final_price_adjustment"
                ] < Decimal("0.00")
            )
        ]

        if negative_adjustments:
            raise RuntimeError(
                f"Jornik product {product_id} "
                "produced negative variant adjustments."
            )

        # ----------------------------------------------------------
        # Dry run ends before DB mutation.
        # ----------------------------------------------------------

        if self.dry_run:
            return {
                "action": "dry_run",
                "product_id": str(
                    product_id
                ).strip(),
                "name": normalized.get("name"),
                "starting_price": (
                    true_starting_price
                ),
                "variants": variants,
                "variant_count": len(
                    variants
                ),
                "priced_variant_count": len(
                    priced_variants
                ),
                "unpriced_variant_count": (
                    len(variants)
                    - len(priced_variants)
                ),
                "complete_family": (
                    complete_family
                ),
            }

        # ----------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------

        with transaction.atomic():

            supplier = self.get_supplier()

            catalog = self.get_catalog(
                supplier
            )

            now = timezone.now()

            product_name = (
                normalized.get("name")
                or str(product_id).strip()
            )

            product_description = (
                normalized.get("description")
                or ""
            )

            category = normalized.get(
                "category"
            )

            external_image_url = (
                normalized.get(
                    "external_image_url"
                )
                or ""
            )

            parent_lookup = {
                "supplier_record": supplier,
                "catalog": catalog,
                "supplier_sku": str(
                    product_id
                ).strip(),
            }

            existing_product = (
                Product.objects
                .filter(
                    **parent_lookup
                )
                .first()
            )

            defaults = {
                "supplier": (
                    self.brand_config[
                        "product_supplier_name"
                    ]
                ),
                "supplier_record": supplier,
                "catalog": catalog,
                "category": category,
                "name": product_name,
                "short_description": "",
                "description": (
                    product_description
                ),
                "supplier_price": None,
                "starting_price": (
                    true_starting_price
                ),
                "external_image_url": (
                    external_image_url
                ),
                "source": "PromoStandards",
                "supplier_last_synced_at": now,
                "last_synced_at": now,
                "is_active": True,
                "sku": str(
                    product_id
                ).strip(),
                "supplier_product_id": str(
                    product_id
                ).strip(),
            }

            if existing_product is None:

                base_slug = slugify(
                    product_name
                    or f"jornik-{product_id}"
                )

                if not base_slug:
                    base_slug = (
                        f"jornik-{product_id}"
                    )

                slug = base_slug
                counter = 2

                while Product.objects.filter(
                    slug=slug
                ).exists():
                    slug = (
                        f"{base_slug}-{counter}"
                    )
                    counter += 1

                defaults["slug"] = slug

            product, created = (
                Product.objects
                .update_or_create(
                    **parent_lookup,
                    defaults=defaults,
                )
            )

            # Jornik variant pricing must NEVER become
            # Product-level SupplierPriceBreak rows.
            product.supplier_price_breaks.all().delete()

            # Parent-level media is authoritative for Jornik.
            if external_image_url:

                mapped_image = {
                    "external_image_url": (
                        external_image_url
                    )
                }

                self.sync_primary_image(
                    product,
                    mapped_image,
                )

            # Clear existing default before rebuilding the family.
            product.variants.filter(
                is_default=True
            ).update(
                is_default=False
            )

            active_part_ids = []

            variant_created = 0
            variant_updated = 0

            # Prefer the first priced relationship as the default.
            # If the entire family is unpriced, preserve the first
            # relationship as the structural default.
            default_part_id = None

            if priced_variants:
                default_part_id = str(
                    priced_variants[0].get(
                        "part_id"
                    )
                    or priced_variants[0].get(
                        "sku"
                    )
                    or ""
                ).strip()

            elif returned_part_ids:
                default_part_id = (
                    returned_part_ids[0]
                )

            for order, row in enumerate(
                variants,
                start=1,
            ):

                part_id = str(
                    row.get("part_id")
                    or row.get("sku")
                    or ""
                ).strip()

                active_part_ids.append(
                    part_id
                )

                customer_price = row.get(
                    "customer_price"
                )

                adjustment = row.get(
                    "final_price_adjustment"
                )

                pricing_available = (
                    customer_price is not None
                )

                # ProductVariant.price_adjustment is non-null.
                # Zero is storage-only for an unpriced relationship;
                # pricing_available in source_payload is authoritative
                # and prevents callers from treating it as purchasable.
                stored_adjustment = (
                    adjustment
                    if adjustment is not None
                    else Decimal("0.00")
                )

                source_payload = dict(
                    row.get(
                        "source_payload"
                    )
                    or {}
                )

                source_payload.update({
                    "supplier": "Jornik Manufacturing Corp",
                    "parent_product_id": str(
                        product_id
                    ).strip(),
                    "part_id": part_id,
                    "pricing_available": (
                        pricing_available
                    ),
                    "customer_price": (
                        str(customer_price)
                        if customer_price
                        is not None
                        else None
                    ),
                    "parent_starting_price": (
                        str(true_starting_price)
                        if true_starting_price
                        is not None
                        else None
                    ),
                    "price_adjustment": (
                        str(adjustment)
                        if adjustment
                        is not None
                        else None
                    ),
                })
                # Jornik SOAP payloads can contain Decimal, datetime,
                # OrderedDict and other values that Django JSONField
                # cannot validate directly.
                source_payload = (
                    self._pcna_json_safe(
                        source_payload
                    )
                )

                variant_name = (
                    row.get("name")
                    or part_id
                )

                variant_defaults = {
                    "name": variant_name,
                    "supplier_sku": part_id,
                    "color": (
                        row.get("color")
                        or ""
                    ),
                    "size": (
                        row.get("size")
                        or ""
                    ),
                    "material": (
                        row.get("material")
                        or ""
                    ),
                    "price_adjustment": (
                        stored_adjustment
                    ),
                    "inventory_status": (
                        "unknown"
                    ),
                    "is_default": (
                        part_id
                        == default_part_id
                    ),
                    "is_active": True,
                    "order": order,
                    "source_payload": (
                        source_payload
                    ),
                }

                variant, was_created = (
                    ProductVariant.objects
                    .update_or_create(
                        product=product,
                        sku=part_id,
                        defaults=(
                            variant_defaults
                        ),
                    )
                )

                if was_created:
                    variant_created += 1
                else:
                    variant_updated += 1

            stale_deactivated = 0

            if complete_family:

                stale_queryset = (
                    product.variants
                    .exclude(
                        sku__in=active_part_ids
                    )
                    .filter(
                        is_active=True
                    )
                )

                stale_deactivated = (
                    stale_queryset.update(
                        is_active=False,
                        is_default=False,
                    )
                )

            if default_part_id:

                product.variants.filter(
                    sku=default_part_id
                ).update(
                    is_default=True,
                    is_active=True,
                )

            product.supplier_last_synced_at = (
                timezone.now()
            )

            product.last_synced_at = (
                timezone.now()
            )

            product.save(
                update_fields=[
                    "supplier_last_synced_at",
                    "last_synced_at",
                ]
            )

        return {
            "action": (
                "created"
                if created
                else "updated"
            ),
            "product_pk": product.pk,
            "product_id": str(
                product_id
            ).strip(),
            "supplier_sku": (
                product.supplier_sku
            ),
            "starting_price": (
                product.starting_price
            ),
            "variant_count": len(
                variants
            ),
            "priced_variant_count": len(
                priced_variants
            ),
            "unpriced_variant_count": (
                len(variants)
                - len(priced_variants)
            ),
            "variants_created": (
                variant_created
            ),
            "variants_updated": (
                variant_updated
            ),
            "stale_variants_deactivated": (
                stale_deactivated
            ),
            "complete_family": (
                complete_family
            ),
        }
