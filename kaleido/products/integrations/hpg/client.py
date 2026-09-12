import os
import time

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zeep import Client
from zeep.helpers import serialize_object
from zeep.transports import Transport


PRODUCT_DATA_WSDL = (
    "https://api.dc-onesource.com/xml/"
    "DENWELL/Product/2.0.0/soap?wsdl"
)

PRICING_WSDL = (
    "https://api.dc-onesource.com/xml/"
    "DENWELL/PPC/1.0.0/soap?wsdl"
)

MEDIA_WSDL = (
    "https://svc2.hpgbrands.com/"
    "denwell/MEDIA/1.1.0?wsdl"
)


class HPGClient:
    """
    PromoStandards client for Denwell / HPG.

    Credential split:

    Product Data + Pricing:
        OneSource credentials

    Media:
        HPG PromoStandards credentials
    """

    def __init__(
        self,
        timeout=30,
        retries=3,
        retry_delay=2,
    ):
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

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

    # ==============================================================
    # Configuration
    # ==============================================================

    def _validate_credentials(self):
        missing = []

        if not self.onesource_api_key:
            missing.append(
                "ONESOURCE_API_KEY"
            )

        if not self.onesource_api_password:
            missing.append(
                "ONESOURCE_API_PASSWORD"
            )

        if not self.hpg_username:
            missing.append(
                "HPG_PROMOSTANDARDS_USERNAME"
            )

        if not self.hpg_password:
            missing.append(
                "HPG_PROMOSTANDARDS_PASSWORD"
            )

        if missing:
            raise RuntimeError(
                "Missing HPG integration environment variable(s): "
                + ", ".join(missing)
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
                wsdl=PRODUCT_DATA_WSDL,
                transport=self.transport,
            )

        return self._product_client

    def pricing_client(self):
        if self._pricing_client is None:
            self._pricing_client = Client(
                wsdl=PRICING_WSDL,
                transport=self.transport,
            )

        return self._pricing_client

    def media_client(self):
        if self._media_client is None:
            self._media_client = Client(
                wsdl=MEDIA_WSDL,
                transport=self.transport,
            )

        return self._media_client

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
        Retrieve one product from OneSource Product Data 2.0.
        """

        product = self.product_client()

        def request():
            return product.service.getProduct(
                wsVersion="2.0.0",
                id=self.onesource_api_key,
                password=self.onesource_api_password,
                localizationCountry="US",
                localizationLanguage="en",
                productId=product_id,
                partId=part_id,
                colorName=color_name,
                ApparelSizeArray=None,
            )

        response = self._call_with_retry(
            request,
            f"getProduct({product_id})",
        )

        data = serialize_object(
            response
        )

        messages = (
            data.get("ServiceMessageArray")
            or {}
        )

        product_data = data.get(
            "Product"
        )

        if not product_data:
            raise RuntimeError(
                f"No product data returned for "
                f"{product_id}. "
                f"Messages: {messages}"
            )

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

        def request():
            return media.service.getMediaContent(
                wsVersion="1.1.0",
                id=self.hpg_username,
                password=self.hpg_password,
                cultureName="en-US",
                mediaType="Image",
                productId=product_id,
                partId="",
                classType=1006,
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
                f"HPG Media error for "
                f"{product_id}: {error}"
            )

        media_array = (
            data.get("MediaContentArray")
            or {}
        )

        media_items = (
            media_array.get(
                "MediaContent"
            )
            or []
        )

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

        def request():
            return pricing.service.getFobPoints(
                wsVersion="1.0.0",
                id=self.onesource_api_key,
                password=self.onesource_api_password,
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
        """

        pricing = self.pricing_client()

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

        def request():
            return (
                pricing.service
                .getConfigurationAndPricing(
                    wsVersion="1.0.0",
                    id=self.onesource_api_key,
                    password=self.onesource_api_password,
                    productId=product_id,
                    partId=None,
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

        return configuration

    # ==============================================================
    # Convenience method
    # ==============================================================

    def get_product_bundle(
        self,
        product_id,
    ):
        """
        Retrieve the core supplier information needed by
        KaleidoBrands for a single product.

        No database writes occur here.
        """

        product = self.get_product(
            product_id
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
                product_id
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

        def request():
            return product.service.getProductDateModified(
                wsVersion="2.0.0",
                id=self.onesource_api_key,
                password=self.onesource_api_password,
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


    