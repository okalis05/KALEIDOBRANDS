import os
import time

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zeep import Client
from zeep.helpers import serialize_object
from zeep.transports import Transport


HPG_BRANDS = {
    "denwell": {
        "name": "Denwell",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "DENWELL/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "DENWELL/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "denwell/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "hpg",
    },
    "hubpen": {
        "name": "Hub Pen",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "hubpen/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "hubpen/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "hubpen/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "sugarspot": {
        "name": "SugarSpot",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "sugarspot/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "sugarspot/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "sugarspot/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "beacon": {
        "name": "Beacon Promotions",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "beacon/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "beacon/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "beacon/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "best": {
        "name": "Best Promotions USA",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "best/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "best/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "best/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "handstands": {
        "name": "Handstands",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "handstands/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "handstands/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "handstands/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "mixie": {
        "name": "Mixie",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "mixie/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "mixie/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "mixie/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "origaudio": {
        "name": "Origaudio",
        "product_wsdl": (
            "https://svc2.hpgbrands.com/"
            "origaudio/PRODUCT/2.0.0?wsdl"
        ),
        "pricing_wsdl": (
            "https://svc2.hpgbrands.com/"
            "origaudio/PPC/1.0.0?wsdl"
        ),
        "media_wsdl": (
            "https://svc2.hpgbrands.com/"
            "origaudio/MEDIA/1.1.0?wsdl"
        ),
        "product_credentials": "hpg",
        "pricing_credentials": "hpg",
        "media_credentials": "hpg",
    },
    "mapleridge": {
        "name": "Maple Ridge Farms",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAPLERIDGEFARMSINC/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAPLERIDGEFARMSINC/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAPLERIDGEFARMSINC/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },
    "sanmar": {
        "name": "SanMar",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "SanMar/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "SanMar/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "SanMar/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },
     "pcna": {
        "name": "PCNA",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "PCNA/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "PCNA/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "PCNA/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },
    "koozie": {
        "name": "Koozie Group",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "kooziegroup/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "kooziegroup/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "kooziegroup/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },

    "magnet": {
        "name": "The Magnet Group",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAG/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAG/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "MAG/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },

    "vantage": {
        "name": "Vantage Apparel",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "vantage/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "vantage/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "vantage/MED/1.1.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
    },

    "jornik": {
        "name": "Jornik Manufacturing Corp",
        "product_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "JORNIKMANUFACTURINGCORP/Product/2.0.0/soap?wsdl"
        ),
        "pricing_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "JORNIKMANUFACTURINGCORP/PPC/1.0.0/soap?wsdl"
        ),
        "media_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "JORNIKMANUFACTURINGCORP/MED/1.1.0/soap?wsdl"
        ),
        "inventory_wsdl": (
            "https://api.dc-onesource.com/xml/"
            "JORNIKMANUFACTURINGCORP/INV/2.0.0/soap?wsdl"
        ),
        "product_credentials": "onesource",
        "pricing_credentials": "onesource",
        "media_credentials": "onesource",
        "inventory_credentials": "onesource",
    },

        
}



class HPGClient:
    """
    PromoStandards client for HPG supplier brands.

    Each brand defines its Product Data, Pricing & Configuration,
    and Media Content endpoints in HPG_BRANDS.

    Credentials are selected independently for each service using
    the brand configuration. This supports both HPG PromoStandards
    credentials and OneSource credentials where required.

    This client retrieves supplier data only and performs no
    database writes.
    """

    def __init__(
        self,
        brand="denwell",
        timeout=30,
        retries=3,
        retry_delay=2,
    ):
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay


        self.brand = str(brand).strip().lower()

        if self.brand not in HPG_BRANDS:
            supported = ", ".join(sorted(HPG_BRANDS))
            raise ValueError(
                f"Unsupported HPG brand '{brand}'. "
                f"Supported brands: {supported}"
            )

        self.brand_config = HPG_BRANDS[self.brand]

        # ----------------------------------------------------------
        # OneSource credentials
        # Product Data + Pricing
        # ----------------------------------------------------------

        self.onesource_api_key = os.getenv(
            "ONESOURCE_API_KEY"
        )

        self.onesource_api_password = os.getenv(
            "ONESOURCE_API_PASSWORD"
        )

        # ----------------------------------------------------------
        # HPG credentials
        # Media Content
        # ----------------------------------------------------------

        self.hpg_username = os.getenv(
            "HPG_PROMOSTANDARDS_USERNAME"
        )

        self.hpg_password = os.getenv(
            "HPG_PROMOSTANDARDS_PASSWORD"
        )

        self._validate_credentials()

        self.session = self._build_session()

        self.transport = Transport(
            session=self.session,
            timeout=self.timeout,
            operation_timeout=self.timeout,
        )

        self._product_client = None
        self._pricing_client = None
        self._media_client = None
        self._inventory_client = None

    # ==============================================================
    # Configuration
    # ==============================================================

    def _validate_credentials(self):
        missing = []

        credential_types = {
            self.brand_config["product_credentials"],
            self.brand_config["pricing_credentials"],
            self.brand_config["media_credentials"],
        }

        if "onesource" in credential_types:
            if not self.onesource_api_key:
                missing.append("ONESOURCE_API_KEY")

            if not self.onesource_api_password:
                missing.append("ONESOURCE_API_PASSWORD")

        if "hpg" in credential_types:
            if not self.hpg_username:
                missing.append("HPG_PROMOSTANDARDS_USERNAME")

            if not self.hpg_password:
                missing.append("HPG_PROMOSTANDARDS_PASSWORD")

        if missing:
            raise RuntimeError(
                f"Missing {self.brand_config['name']} integration "
                "environment variable(s): "
                + ", ".join(missing)
            )

    def _credentials_for(self, service):
        credential_type = self.brand_config[
            f"{service}_credentials"
        ]

        if credential_type == "onesource":
            return (
                self.onesource_api_key,
                self.onesource_api_password,
            )

        if credential_type == "hpg":
            return (
                self.hpg_username,
                self.hpg_password,
            )

        raise RuntimeError(
            f"Unsupported credential type "
            f"'{credential_type}' for {service}."
        )

    def _build_session(self):
        session = Session()

        retry_config = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            backoff_factor=1,
            status_forcelist=[
                429,
                500,
                502,
                503,
                504,
            ],
            allowed_methods=[
                "GET",
                "POST",
            ],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry_config
        )

        session.mount(
            "https://",
            adapter,
        )

        session.mount(
            "http://",
            adapter,
        )

        return session

    # ==============================================================
    # Zeep clients
    # ==============================================================

    def product_client(self):
        if self._product_client is None:
            self._product_client = Client(
                wsdl=self.brand_config["product_wsdl"],
                transport=self.transport,
            )

        return self._product_client


    def pricing_client(self):
        if self._pricing_client is None:
            self._pricing_client = Client(
                wsdl=self.brand_config["pricing_wsdl"],
                transport=self.transport,
            )

        return self._pricing_client


    def media_client(self):
        if self._media_client is None:
            self._media_client = Client(
                wsdl=self.brand_config["media_wsdl"],
                transport=self.transport,
            )

        return self._media_client


    def inventory_client(self):
        """
        Return the configured Inventory client.

        Currently used by Jornik. This is additive and does not
        alter Product/PPC/Media behavior for existing suppliers.
        """

        if "inventory_wsdl" not in self.brand_config:
            raise RuntimeError(
                f"{self.brand_config['name']} does not define "
                "an Inventory endpoint."
            )

        if self._inventory_client is None:
            self._inventory_client = Client(
                wsdl=self.brand_config["inventory_wsdl"],
                transport=self.transport,
            )

        return self._inventory_client

    # ==============================================================
    # Helper
    # ==============================================================

    def _call_with_retry(
        self,
        callback,
        operation_name,
    ):
        """
        Additional application-level retry around SOAP operations.

        This helps with the intermittent OneSource/HPG connection
        resets and read timeouts observed during testing.
        """

        last_error = None

        for attempt in range(
            1,
            self.retries + 1,
        ):
            try:
                return callback()

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                last_error = exc

                if attempt == self.retries:
                    break

                time.sleep(
                    self.retry_delay * attempt
                )

        raise RuntimeError(
            f"{operation_name} failed after "
            f"{self.retries} attempts: "
            f"{last_error}"
        )

    # ==============================================================
    # PRODUCT DATA 2.0
    # ==============================================================

    def get_product(
        self,
        product_id,
        part_id=None,
        color_name=None,
    ):
        """
        Retrieve one product from the configured Product Data 2.0 service.
        """

        product = self.product_client()
        username, password = self._credentials_for("product")

        def request():
            request_part_id = part_id
            request_color_name = color_name

            if self.brand == "mapleridge":
                if not request_part_id:
                    request_part_id = product_id

                request_color_name = None

            return product.service.getProduct(
                wsVersion="2.0.0",
                id=username,
                password=password,
                localizationCountry="US",
                localizationLanguage="en",
                productId=product_id,
                partId=request_part_id,
                colorName=request_color_name,
                ApparelSizeArray=None,
            )

        response = self._call_with_retry(
            request,
            f"getProduct({product_id})",
        )

        data = serialize_object(
            response
        )

        messages = data.get(
            "ServiceMessageArray"
        )

        if messages:
            raise RuntimeError(
                f"Product Data error for "
                f"{product_id}: {messages}"
            )

        product_data = data.get(
            "Product"
        )

        if not product_data:
            return None

        return product_data

    # ==============================================================
    # MEDIA CONTENT 1.1
    # ==============================================================

    def get_primary_image(
        self,
        product_id,
    ):
        """
        Retrieve the supplier primary image.

        PromoStandards classType 1006 = Primary.
        """

        media = self.media_client()
        username, password = self._credentials_for("media")

        def request():
            kwargs = {
                "wsVersion": "1.1.0",
                "id": username,
                "password": password,
                "cultureName": "en-US",
                "mediaType": "Image",
                "productId": product_id,
                "classType": 1006,
            }

            if self.brand != "mapleridge":
                kwargs["partId"] = ""

            return media.service.getMediaContent(
                **kwargs
            )

        response = self._call_with_retry(
            request,
            f"getMediaContent({product_id})",
        )

        data = serialize_object(
            response
        )

        error = data.get(
            "errorMessage"
        )

        if error:
            raise RuntimeError(
                f"Media error for "
                f"{product_id}: {error}"
            )

        media_array = data.get(
            "MediaContentArray"
        )

        if not media_array:
            return None

        media_items = media_array.get(
            "MediaContent"
        ) or []

        if not media_items:
            return None

        return media_items[0]
    # ==============================================================
    # PRICING & CONFIGURATION 1.0
    # ==============================================================

    def get_fob_points(
        self,
        product_id,
    ):
        pricing = self.pricing_client()
        username, password = self._credentials_for("pricing")

        def request():
            return pricing.service.getFobPoints(
                wsVersion="1.0.0",
                id=username,
                password=password,
                productId=product_id,
                localizationCountry="US",
                localizationLanguage="en",
            )

        response = self._call_with_retry(
            request,
            f"getFobPoints({product_id})",
        )

        data = serialize_object(
            response
        )

        error = data.get(
            "ErrorMessage"
        )

        if error:
            raise RuntimeError(
                f"Pricing FOB error for "
                f"{product_id}: {error}"
            )

        fob_array = (
            data.get("FobPointArray")
            or {}
        )

        return (
            fob_array.get("FobPoint")
            or []
        )

    def get_net_pricing(
        self,
        product_id,
        part_id=None,
        fob_id=None,
        currency="USD",
        configuration_type="Blank",
    ):
        """
        Retrieve Net supplier pricing.

        IMPORTANT:
        This represents supplier-side cost data.

        It should NOT automatically replace customer-facing
        KaleidoBrands selling prices.

        SanMar pricing is variant/part based. SanMar also returns
        parallel EA, DZ, and CA price records for the same quantity.
        KaleidoBrands normalizes SanMar supplier unit cost to EA.
        """

        pricing = self.pricing_client()
        username, password = self._credentials_for("pricing")

        if fob_id is None:
            fob_points = self.get_fob_points(
                product_id
            )

            if not fob_points:
                raise RuntimeError(
                    f"No FOB points returned for "
                    f"{product_id}."
                )

            fob_id = str(
                fob_points[0].get("fobId")
            )

        # SanMar and PCNA pricing are authoritative at the
        # parent + exact-part relationship level.
        request_part_id = (
            part_id
            if self.brand in {
                "sanmar",
                "pcna",
                "koozie",
                "jornik",
            }
            else None
        )

        if (
            self.brand in {
                "sanmar",
                "pcna",
                "koozie",
                "jornik",
            }
            and not request_part_id
        ):
            raise RuntimeError(
                f"{self.brand_config['name']} pricing "
                f"requires part_id for product "
                f"{product_id}."
            )
        if self.brand == "pcna":
            configuration_type = "Decorated"

        def request():
            return (
                pricing.service
                .getConfigurationAndPricing(
                    wsVersion="1.0.0",
                    id=username,
                    password=password,
                    productId=product_id,
                    partId=request_part_id,
                    currency=currency,
                    fobId=fob_id,
                    priceType="Net",
                    localizationCountry="US",
                    localizationLanguage="en",
                    configurationType=configuration_type,
                )
            )

        response = self._call_with_retry(
            request,
            (
                "getConfigurationAndPricing"
                f"({product_id})"
            ),
        )

        data = serialize_object(
            response
        )

        error = data.get(
            "ErrorMessage"
        )

        if error:
            raise RuntimeError(
                f"Pricing error for "
                f"{product_id}: {error}"
            )

        configuration = data.get(
            "Configuration"
        )

        if not configuration:
            return None

        # ----------------------------------------------------------
        # SanMar
        #
        # SanMar returns parallel EA / DZ / CA Net records at the
        # same minimum quantity. KaleidoBrands stores customer
        # pricing as unit pricing, so retain EA only.
        #
        # Do this here rather than in the shared mapper so no other
        # supplier catalog changes behavior.
        # ----------------------------------------------------------

        if self.brand == "sanmar":
            part_array = (
                configuration.get("PartArray")
                or {}
            )

            parts = (
                part_array.get("Part")
                or []
            )

            if not isinstance(parts, list):
                parts = [parts]

            for part in parts:
                if not isinstance(part, dict):
                    continue

                price_array = (
                    part.get("PartPriceArray")
                    or {}
                )

                prices = (
                    price_array.get("PartPrice")
                    or []
                )

                if not isinstance(prices, list):
                    prices = [prices]

                ea_prices = [
                    price
                    for price in prices
                    if isinstance(price, dict)
                    and str(
                        price.get("priceUom")
                        or ""
                    ).strip().upper() == "EA"
                ]

                price_array["PartPrice"] = (
                    ea_prices
                )

        return configuration

    
    def get_sanmar_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve a SanMar parent product and its discovered variants.

        SanMar optimization:
        - Product Data is retrieved once at parent level.
        - Primary media is retrieved once at parent level.
        - FOB points are retrieved once at parent level.
        - PPC pricing remains part-specific.

        Returns supplier data only. No database writes occur here.

        This method is intentionally SanMar-specific so existing HPG
        catalog behavior remains unchanged.
        """

        if self.brand != "sanmar":
            raise RuntimeError(
                "get_sanmar_parent_bundle() is only "
                "available for the SanMar integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

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
                "has no discovered part IDs."
            )

        # ----------------------------------------------------------
        # Product Data is parent-level for SanMar when partId is
        # omitted. The response contains the complete ProductPartArray.
        #
        # Retrieve it once rather than once per variant.
        # ----------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # ----------------------------------------------------------
        # Safety gate:
        #
        # The authoritative discovery family supplied by the caller
        # must be present in the parent Product Data response.
        #
        # Do not silently drop variants.
        # ----------------------------------------------------------

        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ----------------------------------------------------------
        # Media is product-level.
        # Retrieve once for the whole parent.
        # ----------------------------------------------------------

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        # ----------------------------------------------------------
        # FOB is product-level.
        #
        # Resolve it once and pass the same FOB ID into each
        # part-specific PPC request. This prevents
        # get_net_pricing() from performing another FOB lookup for
        # every variant.
        # ----------------------------------------------------------

        fob_points = self.get_fob_points(
            product_id
        )

        if not fob_points:
            raise RuntimeError(
                f"No FOB points returned for "
                f"SanMar product {product_id}."
            )

        fob_id = str(
            fob_points[0].get("fobId")
            or ""
        ).strip()

        if not fob_id:
            raise RuntimeError(
                f"SanMar product {product_id} "
                "returned an invalid FOB ID."
            )

        variants = []

        # ----------------------------------------------------------
        # PPC remains part-specific.
        #
        # Construct a lightweight Product response for each variant
        # using the already-retrieved parent Product Data plus that
        # variant's ProductPart.
        #
        # This preserves the structure expected by the existing
        # SanMar normalization/service layer without another Product
        # SOAP request.
        # ----------------------------------------------------------

        for part_id in normalized_part_ids:

            part = parts_by_id[
                part_id
            ]

            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    part
                ]
            }

            pricing = None
            pricing_error = None

            try:
                pricing = self.get_net_pricing(
                    product_id,
                    part_id=part_id,
                    fob_id=fob_id,
                )
            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append(
                {
                    "part_id": part_id,
                    "product": product,
                    "pricing": pricing,
                    "error": pricing_error,
                }
            )

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "variants": variants,
        }



    def get_pcna_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve one PCNA parent and its authoritative part family.

        READ ONLY.

        PCNA architecture:
            productId -> Product
            partId    -> ProductVariant

        Important:
        - A PCNA partId may legitimately belong to multiple parents.
        - Product Data is fetched once at parent level.
        - Media is fetched once at parent level.
        - FOB is fetched once at parent level.
        - PPC remains parent + part specific.
        - PPC uses Net + Decorated.
        - Decoration ChargeArray values are not merchandise cost.

        No database writes occur here.
        """

        if self.brand != "pcna":
            raise RuntimeError(
                "get_pcna_parent_bundle() is only "
                "available for the PCNA integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

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
                "has no discovered part IDs."
            )

        # ------------------------------------------------------
        # One parent Product Data request.
        # ------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"PCNA product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # ------------------------------------------------------
        # Safety gate.
        #
        # Discovery is authoritative. Never silently drop a
        # discovered PCNA parent/part relationship.
        # ------------------------------------------------------

        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"PCNA product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ------------------------------------------------------
        # Product-level media.
        #
        # Media failure does not invalidate Product/PPC data.
        # ------------------------------------------------------

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        # ------------------------------------------------------
        # PCNA currently exposes FOB 15068, but resolve it from
        # the service rather than hard-coding it into persistence.
        # ------------------------------------------------------

        fob_points = self.get_fob_points(
            product_id
        )

        if not fob_points:
            raise RuntimeError(
                f"No FOB points returned for "
                f"PCNA product {product_id}."
            )

        fob_id = str(
            fob_points[0].get("fobId")
            or ""
        ).strip()

        if not fob_id:
            raise RuntimeError(
                f"PCNA product {product_id} "
                "returned an invalid FOB ID."
            )

        variants = []

        for part_id in normalized_part_ids:

            exact_part = parts_by_id[
                part_id
            ]

            # Lightweight per-part Product structure using the
            # already-fetched parent response.
            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    exact_part
                ]
            }

            pricing = None
            pricing_error = None

            try:
                pricing = self.get_net_pricing(
                    product_id,
                    part_id=part_id,
                    fob_id=fob_id,
                    currency="USD",
                    configuration_type=(
                        "Decorated"
                    ),
                )

            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append({
                "part_id": part_id,
                "product": product,
                "pricing": pricing,
                "error": pricing_error,
            })

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "fob_id": fob_id,
            "variants": variants,
        }

    def get_koozie_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve one Koozie Group parent and its complete part family.

        READ ONLY.

        Koozie architecture:
            productId -> Product
            partId    -> ProductVariant

        Pricing contract:
            exact parent productId + exact partId
            priceType="Net"
            configurationType="Blank"

        A valid Koozie part may return no Blank pricing. That is an
        authoritative unpriced relationship and must not inherit pricing
        from another part in the family.

        No database writes occur here.
        """

        if self.brand != "koozie":
            raise RuntimeError(
                "get_koozie_parent_bundle() is only "
                "available for the Koozie integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

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
                "has no discovered part IDs."
            )

        # ----------------------------------------------------------
        # One parent Product Data request.
        # ----------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"Koozie product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # Discovery is authoritative. Never silently drop a part.
        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"Koozie product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ----------------------------------------------------------
        # Image
        #
        # Product Data primaryImageUrl is the reliable Koozie
        # parent image. Media 1.1 is an optional enhancement.
        # ----------------------------------------------------------

        product_image_url = str(
            parent_product.get(
                "primaryImageUrl"
            )
            or ""
        ).strip()

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        media_image_url = ""

        if isinstance(image, dict):
            media_image_url = str(
                image.get("url")
                or ""
            ).strip()

        #=======================================================
        # Prefer Product Data because discovery showed Media can
        # legitimately return No Results Found for Koozie products.
        #=========================================================

        primary_image_url = (
            product_image_url
            or media_image_url
        )

        # ----------------------------------------------------------
        # FOB
        #
        # Some valid Koozie products are present in Product Data but
        # the PPC service cannot return a usable FOB/configuration.
        # That must not prevent the structural product/variants from
        # being imported.
        #
        # When FOB lookup fails, pricing is authoritative unavailable
        # for this parent. Do not fabricate pricing or borrow pricing
        # from another part/configuration.
        # ----------------------------------------------------------

        fob_id = None
        fob_error = None

        try:
            fob_points = self.get_fob_points(
                product_id
            )

            if fob_points:
                candidate_fob_id = str(
                    fob_points[0].get("fobId")
                    or ""
                ).strip()

                if candidate_fob_id:
                    fob_id = candidate_fob_id
                else:
                    fob_error = (
                        f"Koozie product {product_id} "
                        "returned an invalid FOB ID."
                    )
            else:
                fob_error = (
                    f"No FOB points returned for "
                    f"Koozie product {product_id}."
                )

        except RuntimeError as exc:
            fob_error = str(exc)

        variants = []

        # ----------------------------------------------------------
        # Exact-part Net + Blank pricing.
        # ----------------------------------------------------------

        for part_id in normalized_part_ids:

            exact_part = parts_by_id[
                part_id
            ]

            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    exact_part
                ]
            }

            pricing = None
            pricing_error = fob_error

            try:
                if fob_id is not None:
                    pricing = self.get_net_pricing(
                        product_id,
                        part_id=part_id,
                        fob_id=fob_id,
                        currency="USD",
                        configuration_type="Blank",
                    )

            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append({
                "part_id": part_id,
                "product": product,
                "pricing": pricing,
                "error": pricing_error,
            })

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "primary_image_url": (
                primary_image_url
            ),
            "fob_id": fob_id,
            "variants": variants,
        }
    def get_magnet_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve one The Magnet Group parent and its complete
        authoritative part family.

        READ ONLY.

        Magnet architecture:
            productId -> Product
            partId    -> ProductVariant

        Pricing contract:
            exact parent productId + exact partId
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Product Data is fetched once at parent level.
        Media is retrieved at parent level as an enhancement.
        FOB is retrieved once at parent level.
        PPC pricing remains parent + exact-part specific.

        A valid Magnet part may return no Blank pricing. Such a
        relationship remains structurally valid and must not inherit
        pricing from another part.

        No database writes occur here.
        """

        if self.brand != "magnet":
            raise RuntimeError(
                "get_magnet_parent_bundle() is only "
                "available for The Magnet Group integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

        if not product_id:
            raise RuntimeError(
                "Magnet product_id is required."
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
                "has no discovered part IDs."
            )

        # ----------------------------------------------------------
        # Parent Product Data
        # ----------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"Magnet product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # Discovery is authoritative.
        # Never silently drop a discovered Magnet part.

        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"Magnet product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ----------------------------------------------------------
        # Parent image
        #
        # Magnet discovery proved both Product Data primaryImageUrl
        # and Media 1.1 can provide usable imagery.
        # Keep Product Data as the stable primary URL and retain the
        # Media response as an enhancement.
        # ----------------------------------------------------------

        product_image_url = str(
            parent_product.get(
                "primaryImageUrl"
            )
            or ""
        ).strip()

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        media_image_url = ""

        if isinstance(image, dict):
            media_image_url = str(
                image.get("url")
                or ""
            ).strip()

        primary_image_url = (
            product_image_url
            or media_image_url
        )

        # ----------------------------------------------------------
        # FOB
        #
        # Pricing is unavailable if PPC does not provide a usable
        # FOB. Structural product/variant data remains authoritative.
        # Never fabricate or borrow pricing.
        # ----------------------------------------------------------

        fob_id = None
        fob_error = None

        try:
            fob_points = self.get_fob_points(
                product_id
            )

            if fob_points:
                candidate_fob_id = str(
                    fob_points[0].get("fobId")
                    or ""
                ).strip()

                if candidate_fob_id:
                    fob_id = candidate_fob_id
                else:
                    fob_error = (
                        f"Magnet product {product_id} "
                        "returned an invalid FOB ID."
                    )
            else:
                fob_error = (
                    "No FOB points returned for "
                    f"Magnet product {product_id}."
                )

        except RuntimeError as exc:
            fob_error = str(exc)

        # ----------------------------------------------------------
        # Exact-part Net + Blank pricing
        # ----------------------------------------------------------

        variants = []

        for part_id in normalized_part_ids:

            exact_part = parts_by_id[
                part_id
            ]

            # Preserve parent metadata while restricting
            # ProductPartArray to the exact variant.
            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    exact_part
                ]
            }

            pricing = None
            pricing_error = fob_error

            try:
                if fob_id is not None:
                    pricing = self.get_net_pricing(
                        product_id,
                        part_id=part_id,
                        fob_id=fob_id,
                        currency="USD",
                        configuration_type="Blank",
                    )

            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append({
                "part_id": part_id,
                "product": product,
                "pricing": pricing,
                "error": pricing_error,
            })

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "primary_image_url": (
                primary_image_url
            ),
            "fob_id": fob_id,
            "variants": variants,
        }


    # ==============================================================
    # Convenience method
    # ==============================================================

    def get_product_bundle(
        self,
        product_id,
        part_id=None,
    ):
        """
        Retrieve the core supplier information needed by
        KaleidoBrands for a single product.

        SanMar requires an exact discovered part ID for Product Data
        and PPC. Media remains product-level.

        No database writes occur here.
        """

        if (
            self.brand == "sanmar"
            and not part_id
        ):
            raise RuntimeError(
                f"SanMar product {product_id} "
                f"requires part_id."
            )

        product = self.get_product(
            product_id,
            part_id=part_id,
        )

        image = None
        pricing = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            # Product can still be imported if media is temporarily
            # unavailable.
            image = None

        try:
            pricing = self.get_net_pricing(
                product_id,
                part_id=part_id,
            )
        except RuntimeError:
            # Product can still be inspected if pricing is temporarily
            # unavailable.
            pricing = None

        return {
            "product": product,
            "primary_image": image,
            "pricing": pricing,
        }

        
    def get_products_modified_since(
        self,
        change_timestamp,
    ):
        """
        Retrieve product IDs changed since the supplied timestamp.

        Uses PromoStandards Product Data 2.0
        getProductDateModified.
        """

        product = self.product_client()
        username, password = self._credentials_for("product")

        def request():
            return product.service.getProductDateModified(
                wsVersion="2.0.0",
                id=username,
                password=password,
                changeTimeStamp=change_timestamp,
            )

        response = self._call_with_retry(
            request,
            "getProductDateModified",
        )

        data = serialize_object(response)

        messages = data.get(
            "ServiceMessageArray"
        )

        modified_array = (
            data.get("ProductDateModifiedArray")
            or {}
        )

        items = (
            modified_array.get(
                "ProductDateModified"
            )
            or []
        )

        return {
            "items": items,
            "messages": messages,
        }

    def get_vantage_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve one Vantage Apparel parent and its complete
        authoritative part family.

        READ ONLY.

        Vantage architecture:
            productId -> Product
            partId    -> ProductVariant

        Pricing contract:
            exact parent productId + exact partId
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Product Data is fetched once at parent level.
        Media is retrieved at parent level as an enhancement.
        FOB is retrieved once at parent level.
        PPC pricing remains parent + exact-part specific.

        A valid Vantage part may return no Blank pricing. Such a
        relationship remains structurally valid and must not inherit
        pricing from another part.

        No database writes occur here.
        """

        if self.brand != "vantage":
            raise RuntimeError(
                "get_vantage_parent_bundle() is only "
                "available for Vantage Apparel integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

        if not product_id:
            raise RuntimeError(
                "Vantage product_id is required."
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
                "has no discovered part IDs."
            )

        # ----------------------------------------------------------
        # Parent Product Data
        # ----------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"Vantage product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # Discovery is authoritative.
        # Never silently drop a discovered Vantage part.

        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"Vantage product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ----------------------------------------------------------
        # Parent image
        #
        # Vantage discovery proved both Product Data primaryImageUrl
        # and Media 1.1 can provide usable imagery.
        # Keep Product Data as the stable primary URL and retain the
        # Media response as an enhancement.
        # ----------------------------------------------------------

        product_image_url = str(
            parent_product.get(
                "primaryImageUrl"
            )
            or ""
        ).strip()

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        media_image_url = ""

        if isinstance(image, dict):
            media_image_url = str(
                image.get("url")
                or ""
            ).strip()

        primary_image_url = (
            product_image_url
            or media_image_url
        )

        # ----------------------------------------------------------
        # FOB
        #
        # Pricing is unavailable if PPC does not provide a usable
        # FOB. Structural product/variant data remains authoritative.
        # Never fabricate or borrow pricing.
        # ----------------------------------------------------------

        fob_id = "AVENEL"
        fob_error = None

        try:
            fob_points = self.get_fob_points(
                product_id
            )

            if fob_points:
                candidate_fob_id = str(
                    fob_points[0].get("fobId")
                    or ""
                ).strip()

                if candidate_fob_id:
                    fob_id = candidate_fob_id
                else:
                    fob_error = (
                        f"Vantage product {product_id} "
                        "returned an invalid FOB ID."
                    )
            else:
                fob_error = (
                    "No FOB points returned for "
                    f"Vantage product {product_id}."
                )

        except RuntimeError as exc:
            fob_error = str(exc)

        # ----------------------------------------------------------
        # Exact-part Net + Blank pricing
        # ----------------------------------------------------------

        variants = []

        for part_id in normalized_part_ids:

            exact_part = parts_by_id[
                part_id
            ]

            # Preserve parent metadata while restricting
            # ProductPartArray to the exact variant.
            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    exact_part
                ]
            }

            pricing = None
            pricing_error = fob_error

            try:
                if fob_id is not None:
                    pricing = self.get_net_pricing(
                        product_id,
                        part_id=part_id,
                        fob_id=fob_id,
                        currency="USD",
                        configuration_type="Blank",
                    )

            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append({
                "part_id": part_id,
                "product": product,
                "pricing": pricing,
                "error": pricing_error,
            })

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "primary_image_url": (
                primary_image_url
            ),
            "fob_id": fob_id,
            "variants": variants,
        }



    def get_jornik_inventory_levels(
        self,
        product_id,
        filter_value=None,
    ):
        """
        Retrieve raw Jornik Inventory 2.0 levels.

        READ ONLY.

        Inventory is deliberately returned as supplier data only.
        KaleidoBrands does not yet convert quantityAvailable into
        storefront inventory_status until the representative response
        has been validated.

        Confirmed contract:
            getInventoryLevels(
                wsVersion,
                id,
                password,
                productId,
                Filter,
            )
        """

        if self.brand != "jornik":
            raise RuntimeError(
                "get_jornik_inventory_levels() requires "
                "brand='jornik'."
            )

        inventory = self.inventory_client()

        credential_type = self.brand_config.get(
            "inventory_credentials",
            "onesource",
        )

        if credential_type == "onesource":
            username = self.onesource_api_key
            password = self.onesource_api_password
        elif credential_type == "hpg":
            username = self.hpg_username
            password = self.hpg_password
        else:
            raise RuntimeError(
                "Unsupported Jornik inventory credential type: "
                f"{credential_type}"
            )

        def request():
            return inventory.service.getInventoryLevels(
                wsVersion="2.0.0",
                id=username,
                password=password,
                productId=str(product_id).strip(),
                Filter=filter_value,
            )

        response = self._call_with_retry(
            request,
            f"getInventoryLevels({product_id})",
        )

        return serialize_object(response)

    def get_jornik_parent_bundle(
        self,
        product_id,
        part_ids,
    ):
        """
        Retrieve one Jornik Manufacturing Corp parent and its complete
        authoritative part family.

        READ ONLY.

        Jornik architecture:
            productId -> Product
            partId    -> ProductVariant

        Pricing contract:
            exact parent productId + exact partId
            priceType="Net"
            configurationType="Blank"
            currency="USD"

        Product Data is fetched once at parent level.
        Media is retrieved at parent level as an enhancement.
        FOB is retrieved once at parent level.
        PPC pricing remains parent + exact-part specific.

        A valid Jornik part may return no Blank pricing. Such a
        relationship remains structurally valid and must not inherit
        pricing from another part.

        No database writes occur here.
        """

        if self.brand != "jornik":
            raise RuntimeError(
                "get_jornik_parent_bundle() is only "
                "available for Jornik Manufacturing Corp integration."
            )

        product_id = str(
            product_id or ""
        ).strip()

        if not product_id:
            raise RuntimeError(
                "Jornik product_id is required."
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
                "has no discovered part IDs."
            )

        # ----------------------------------------------------------
        # Parent Product Data
        # ----------------------------------------------------------

        parent_product = self.get_product(
            product_id,
            part_id=None,
        )

        if not parent_product:
            raise RuntimeError(
                f"Jornik product {product_id} "
                "returned no parent Product Data."
            )

        product_part_array = (
            parent_product.get(
                "ProductPartArray"
            )
            or {}
        )

        product_parts = (
            product_part_array.get(
                "ProductPart"
            )
            or []
        )

        if not isinstance(
            product_parts,
            list,
        ):
            product_parts = [
                product_parts
            ]

        parts_by_id = {}

        for part in product_parts:

            if not isinstance(
                part,
                dict,
            ):
                continue

            part_id = str(
                part.get("partId")
                or ""
            ).strip()

            if part_id:
                parts_by_id[
                    part_id
                ] = part

        # Discovery is authoritative.
        # Never silently drop a discovered Jornik part.

        missing_part_ids = [
            part_id
            for part_id in normalized_part_ids
            if part_id not in parts_by_id
        ]

        if missing_part_ids:
            raise RuntimeError(
                f"Jornik product {product_id} "
                "parent Product Data is missing "
                f"{len(missing_part_ids)} discovered "
                "part(s): "
                f"{missing_part_ids[:20]}"
            )

        # ----------------------------------------------------------
        # Parent image
        #
        # Jornik discovery proved both Product Data primaryImageUrl
        # and Media 1.1 can provide usable imagery.
        # Keep Product Data as the stable primary URL and retain the
        # Media response as an enhancement.
        # ----------------------------------------------------------

        product_image_url = str(
            parent_product.get(
                "primaryImageUrl"
            )
            or ""
        ).strip()

        image = None

        try:
            image = self.get_primary_image(
                product_id
            )
        except RuntimeError:
            image = None

        media_image_url = ""

        if isinstance(image, dict):
            media_image_url = str(
                image.get("url")
                or ""
            ).strip()

        primary_image_url = (
            product_image_url
            or media_image_url
        )

        # ----------------------------------------------------------
        # FOB
        #
        # Pricing is unavailable if PPC does not provide a usable
        # FOB. Structural product/variant data remains authoritative.
        # Never fabricate or borrow pricing.
        # ----------------------------------------------------------

        fob_id = None
        fob_error = None

        try:
            fob_points = self.get_fob_points(
                product_id
            )

            if fob_points:
                candidate_fob_id = str(
                    fob_points[0].get("fobId")
                    or ""
                ).strip()

                if candidate_fob_id:
                    fob_id = candidate_fob_id
                else:
                    fob_error = (
                        f"Jornik product {product_id} "
                        "returned an invalid FOB ID."
                    )
            else:
                fob_error = (
                    "No FOB points returned for "
                    f"Jornik product {product_id}."
                )

        except RuntimeError as exc:
            fob_error = str(exc)

        # ----------------------------------------------------------
        # Exact-part Net + Blank pricing
        # ----------------------------------------------------------

        variants = []

        for part_id in normalized_part_ids:

            exact_part = parts_by_id[
                part_id
            ]

            # Preserve parent metadata while restricting
            # ProductPartArray to the exact variant.
            product = dict(
                parent_product
            )

            product[
                "ProductPartArray"
            ] = {
                "ProductPart": [
                    exact_part
                ]
            }

            pricing = None
            pricing_error = fob_error

            try:
                if fob_id is not None:
                    pricing = self.get_net_pricing(
                        product_id,
                        part_id=part_id,
                        fob_id=fob_id,
                        currency="USD",
                        configuration_type="Blank",
                    )

            except RuntimeError as exc:
                pricing_error = str(
                    exc
                )

            variants.append({
                "part_id": part_id,
                "product": product,
                "pricing": pricing,
                "error": pricing_error,
            })

        return {
            "product_id": product_id,
            "product": parent_product,
            "primary_image": image,
            "primary_image_url": (
                primary_image_url
            ),
            "fob_id": fob_id,
            "variants": variants,
        }


    # ==============================================================
    # Convenience method
    # ==============================================================
