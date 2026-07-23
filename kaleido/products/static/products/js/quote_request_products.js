document.addEventListener("DOMContentLoaded", function () {
    const quoteUser =
        document.body.dataset.quoteUser || "guest";

    const quoteCartKey =
        `kbQuoteCart:${quoteUser}`;

    /*
     * Change this only if your compare-cart JavaScript
     * uses a different key name.
     */
    const compareCartKey =
        `kbCompareCart:${quoteUser}`;

    const savedProductsField =
        document.getElementById("savedProductsField");

    const savedProductsPreview =
        document.getElementById("savedProductsPreview");

    const savedProductsCount =
        document.getElementById("savedProductsCount");

    function normalizeValue(value) {
        return String(value ?? "").trim();
    }

    function normalizeId(value) {
        return normalizeValue(value).toLowerCase();
    }

    function escapeHtml(value) {
        const element =
            document.createElement("div");

        element.textContent =
            normalizeValue(value);

        return element.innerHTML;
    }

    function readStorageCart(storageKey) {
        try {
            const storedValue =
                localStorage.getItem(storageKey);

            if (!storedValue) {
                return [];
            }

            const parsedItems =
                JSON.parse(storedValue);

            if (!Array.isArray(parsedItems)) {
                return [];
            }

            return parsedItems.filter(
                function (item) {
                    return (
                        item &&
                        typeof item === "object" &&
                        normalizeValue(item.id) &&
                        normalizeValue(item.name)
                    );
                }
            );
        } catch (error) {
            console.error(
                `Unable to read ${storageKey}:`,
                error
            );

            return [];
        }
    }

    function mergeProducts() {
        const quoteProducts =
            readStorageCart(quoteCartKey);

        const compareProducts =
            readStorageCart(compareCartKey);

        const productsById = new Map();

        quoteProducts.forEach(function (item) {
            const id = normalizeId(item.id);

            if (!id) {
                return;
            }

            productsById.set(id, {
                ...item,
                source: "Quote Cart",
            });
        });

        compareProducts.forEach(function (item) {
            const id = normalizeId(item.id);

            if (!id) {
                return;
            }

            if (!productsById.has(id)) {
                productsById.set(id, {
                    ...item,
                    source: "Compare Cart",
                });
            }
        });

        return Array.from(
            productsById.values()
        );
    }

    function updateRequestQuoteProducts() {
        const products = mergeProducts();

        if (savedProductsCount) {
            savedProductsCount.textContent =
                products.length === 1
                    ? "1 selected product"
                    : `${products.length} selected products`;
        }

        if (savedProductsField) {
            savedProductsField.value =
                products
                    .map(function (item) {
                        const name =
                            normalizeValue(item.name) ||
                            "Unnamed product";

                        const category =
                            normalizeValue(
                                item.category
                            ) || "Product";

                        const url =
                            normalizeValue(item.url);

                        const source =
                            normalizeValue(
                                item.source
                            );

                        return [
                            `Product: ${name}`,
                            `Category: ${category}`,
                            `Source: ${source}`,
                            url
                                ? `URL: ${url}`
                                : "",
                        ]
                            .filter(Boolean)
                            .join(" | ");
                    })
                    .join("\n");
        }

        if (!savedProductsPreview) {
            return;
        }

        if (!products.length) {
            savedProductsPreview.innerHTML = `
                <div class="mini-card text-center">
                    <h4>
                        No products selected
                    </h4>

                    <p>
                        Save products to your Quote Cart
                        or Compare Cart before submitting
                        your request.
                    </p>

                    <a
                        href="/products/"
                        class="btn btn-kb-primary"
                    >
                        Browse Products
                    </a>
                </div>
            `;

            return;
        }

        savedProductsPreview.innerHTML = `
            <div class="saved-products-heading">
                <strong>
                    Products included in this request
                </strong>

                <span>
                    ${products.length}
                </span>
            </div>

            <div class="saved-products-list">
                ${products
                    .map(function (item) {
                        const name =
                            escapeHtml(
                                item.name ||
                                "Unnamed product"
                            );

                        const category =
                            escapeHtml(
                                item.category ||
                                "Product"
                            );

                        const source =
                            escapeHtml(
                                item.source ||
                                "Saved Products"
                            );

                        const url =
                            normalizeValue(item.url);

                        const viewLink =
                            url.startsWith("/") ||
                            url.startsWith("http://") ||
                            url.startsWith("https://")
                                ? `
                                    <a
                                        href="${escapeHtml(url)}"
                                        class="saved-product-view"
                                    >
                                        View
                                    </a>
                                `
                                : "";

                        return `
                            <div
                                class="saved-product-preview-item"
                            >
                                <div>
                                    <strong>
                                        ${name}
                                    </strong>

                                    <span>
                                        ${category}
                                    </span>

                                    <small>
                                        From ${source}
                                    </small>
                                </div>

                                ${viewLink}
                            </div>
                        `;
                    })
                    .join("")}
            </div>
        `;
    }

    document.addEventListener(
        "quoteCartUpdated",
        updateRequestQuoteProducts
    );

    document.addEventListener(
        "compareCartUpdated",
        updateRequestQuoteProducts
    );

    window.addEventListener(
        "storage",
        function (event) {
            if (
                event.key === quoteCartKey ||
                event.key === compareCartKey
            ) {
                updateRequestQuoteProducts();
            }
        }
    );

    window.addEventListener(
        "pageshow",
        updateRequestQuoteProducts
    );

    updateRequestQuoteProducts();
});