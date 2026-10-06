(function () {
    "use strict";

    /*
     * Use the SAME user-scoped Quote Cart key as
     * quote_cart.js.
     *
     * This prevents carts from leaking between users
     * and ensures Build a Quote reads the exact cart
     * shown by the customer-facing Quote Cart UI.
     */
    const quoteUser =
        document.body.dataset.quoteUser ||
        "guest";

    const QUOTE_CART_KEY =
        `kbQuoteCart:${quoteUser}`;

    const COMPARE_CART_KEY =
        window.KB_COMPARE_CART_KEY ||
        "kb_compare_cart";

    window.KB_QUOTE_CART_KEY =
        QUOTE_CART_KEY;

    window.KB_COMPARE_CART_KEY =
        COMPARE_CART_KEY;


    function readArray(key) {
        try {
            const raw =
                localStorage.getItem(key);

            if (!raw) {
                return [];
            }

            const parsed =
                JSON.parse(raw);

            return Array.isArray(parsed)
                ? parsed
                : [];

        } catch (error) {
            console.error(
                "Unable to read localStorage:",
                key,
                error
            );

            return [];
        }
    }


    function productId(item) {
        if (!item) {
            return "";
        }

        return String(
            item.id ??
            item.product_id ??
            item.productId ??
            ""
        ).trim();
    }


    function normalizeProduct(item) {
        if (
            !item ||
            typeof item !== "object"
        ) {
            return null;
        }

        const id =
            productId(item);

        if (!id) {
            return null;
        }

        let minimum =
            parseInt(
                item.min_quantity ??
                item.minimum_quantity ??
                item.moq ??
                1,
                10
            );

        if (
            Number.isNaN(minimum) ||
            minimum < 1
        ) {
            minimum = 1;
        }

        let quantity =
            parseInt(
                item.quantity ??
                minimum,
                10
            );

        if (
            Number.isNaN(quantity) ||
            quantity < minimum
        ) {
            quantity = minimum;
        }

        return {
            ...item,

            id: id,

            name:
                item.name ||
                item.product_name ||
                item.title ||
                "Promotional Product",

            category:
                item.category ||
                item.category_name ||
                "Promotional Product",

            url:
                item.url ||
                item.product_url ||
                "",

            image:
                item.image ||
                item.image_url ||
                item.external_image_url ||
                "",

            min_quantity:
                minimum,

            minimum_quantity:
                minimum,

            quantity:
                quantity,

            notes:
                item.notes ||
                "",
        };
    }


    function mergeProducts() {
        const compareCart =
            readArray(
                COMPARE_CART_KEY
            );

        const quoteCart =
            readArray(
                QUOTE_CART_KEY
            );

        const merged =
            new Map();

        /*
         * Compare products may enter the quote workflow,
         * but Quote Cart entries override them because
         * Quote Cart represents explicit quote intent.
         */
        compareCart.forEach(
            function (rawItem) {
                const item =
                    normalizeProduct(
                        rawItem
                    );

                if (item) {
                    merged.set(
                        item.id,
                        item
                    );
                }
            }
        );

        quoteCart.forEach(
            function (rawItem) {
                const item =
                    normalizeProduct(
                        rawItem
                    );

                if (!item) {
                    return;
                }

                const previous =
                    merged.get(
                        item.id
                    ) || {};

                merged.set(
                    item.id,
                    {
                        ...previous,
                        ...item,
                    }
                );
            }
        );

        return Array.from(
            merged.values()
        );
    }


    function removeProduct(productIdValue) {
        const target =
            String(
                productIdValue
            );

        [
            QUOTE_CART_KEY,
            COMPARE_CART_KEY,
        ].forEach(
            function (key) {
                const updated =
                    readArray(key)
                        .filter(
                            function (item) {
                                return (
                                    productId(item)
                                    !== target
                                );
                            }
                        );

                localStorage.setItem(
                    key,
                    JSON.stringify(
                        updated
                    )
                );
            }
        );

        /*
         * Notify the existing global Quote Cart UI.
         *
         * quote_cart.js already listens for this event
         * and refreshes the navbar/floating cart count.
         */
        document.dispatchEvent(
            new CustomEvent(
                "quoteCartUpdated",
                {
                    detail: {
                        items: readArray(
                            QUOTE_CART_KEY
                        ),
                    },
                }
            )
        );

        /*
         * Notify the Quote Builder so its product rows
         * and hidden submission state refresh immediately.
         */
        window.dispatchEvent(
            new CustomEvent(
                "kbQuoteProductsChanged"
            )
        );
    }


    /*
     * Public API only.
     *
     * This module owns quote-product STORAGE.
     * It intentionally does NOT render the
     * Quote Builder DOM.
     */
    window.getKBQuoteRequestProducts =
        mergeProducts;

    window.removeKBQuoteRequestProduct =
        removeProduct;

    window.refreshKBQuoteRequestProducts =
        function () {
            const products =
                mergeProducts();

            window.dispatchEvent(
                new CustomEvent(
                    "kbQuoteProductsChanged"
                )
            );

            return products;
        };
})();
