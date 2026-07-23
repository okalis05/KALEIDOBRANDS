document.addEventListener("DOMContentLoaded", function () {
    const quoteUser =
        document.body.dataset.quoteUser || "guest";

    const storageKey = `kbQuoteCart:${quoteUser}`;

    /*
     * Remove the old shared cart key.
     * This prevents different users from sharing the legacy cart.
     */
    if (localStorage.getItem("kbQuoteCart") !== null) {
        localStorage.removeItem("kbQuoteCart");
    }

    const cartItems =
        document.getElementById("quoteCartItems");

    const clearButton =
        document.getElementById("clearQuoteCart");

    const savedProductsField =
        document.getElementById("savedProductsField");

    const savedProductsPreview =
        document.getElementById("savedProductsPreview");

    const floatingCartPreview =
        document.getElementById("floatingCartPreview");

    const invalidValues = [
        "",
        "undefined",
        "null",
        "none",
        "nan",
    ];

    function normalizeValue(value) {
        return String(value ?? "").trim();
    }

    function normalizeId(value) {
        return normalizeValue(value).toLowerCase();
    }

    function isInvalidValue(value) {
        return invalidValues.includes(
            normalizeValue(value).toLowerCase()
        );
    }

    function isValidUrl(url) {
        const value = normalizeValue(url);

        if (isInvalidValue(value)) {
            return false;
        }

        return (
            value.startsWith("/") ||
            value.startsWith("http://") ||
            value.startsWith("https://")
        );
    }

    function escapeHtml(value) {
        const element = document.createElement("div");
        element.textContent = normalizeValue(value);
        return element.innerHTML;
    }

    function cleanCartItems(items) {
        if (!Array.isArray(items)) {
            return [];
        }

        const uniqueIds = new Set();

        return items.filter(function (item) {
            if (!item || typeof item !== "object") {
                return false;
            }

            const id = normalizeValue(item.id);
            const normalizedId = normalizeId(id);
            const name = normalizeValue(item.name);

            if (
                isInvalidValue(id) ||
                isInvalidValue(name)
            ) {
                return false;
            }

            if (uniqueIds.has(normalizedId)) {
                return false;
            }

            uniqueIds.add(normalizedId);

            item.id = id;
            item.name = name;
            item.url = normalizeValue(item.url);
            item.image = normalizeValue(item.image);
            item.category =
                normalizeValue(item.category) || "Product";
            item.price = normalizeValue(item.price);

            return true;
        });
    }

    function getCart() {
        try {
            const storedValue =
                localStorage.getItem(storageKey);

            if (!storedValue) {
                return [];
            }

            const parsedItems = JSON.parse(storedValue);

            if (!Array.isArray(parsedItems)) {
                localStorage.removeItem(storageKey);
                return [];
            }

            const validItems =
                cleanCartItems(parsedItems);

            if (
                validItems.length !== parsedItems.length ||
                JSON.stringify(validItems) !==
                    JSON.stringify(parsedItems)
            ) {
                localStorage.setItem(
                    storageKey,
                    JSON.stringify(validItems)
                );
            }

            return validItems;
        } catch (error) {
            console.error(
                "Unable to read quote cart:",
                error
            );

            localStorage.removeItem(storageKey);
            return [];
        }
    }

    function dispatchCartUpdated(items) {
        document.dispatchEvent(
            new CustomEvent("quoteCartUpdated", {
                detail: {
                    count: items.length,
                    storageKey: storageKey,
                },
            })
        );
    }

    function saveCart(items) {
        const cleanItems =
            cleanCartItems(items);

        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(cleanItems)
            );

            dispatchCartUpdated(cleanItems);
        } catch (error) {
            console.error(
                "Unable to save quote cart:",
                error
            );

            showToast(
                "Unable to save this product."
            );
        }
    }

    function showToast(message) {
        const toast =
            document.getElementById("kbToast");

        if (!toast) {
            return;
        }

        toast.textContent = message;
        toast.classList.add("show");

        window.clearTimeout(
            showToast.timeoutId
        );

        showToast.timeoutId =
            window.setTimeout(function () {
                toast.classList.remove("show");
            }, 2200);
    }

    function updateCartCount() {
        const count = getCart().length;

        document
            .querySelectorAll(
                "#quoteCartCount, " +
                "#floatingQuoteCartCount, " +
                ".quote-cart-count, " +
                "[data-quote-cart-count]"
            )
            .forEach(function (badge) {
                badge.textContent = count;
            });

        document
            .querySelectorAll(
                "#quoteCartPageCount, " +
                "[data-quote-cart-page-count]"
            )
            .forEach(function (element) {
                element.textContent =
                    count === 1
                        ? "1 item"
                        : `${count} items`;
            });

        document
            .querySelectorAll(
                ".floating-quote-cart"
            )
            .forEach(function (cart) {
                cart.classList.toggle(
                    "show",
                    count > 0
                );
            });
    }

    function updateFloatingPreview() {
        if (!floatingCartPreview) {
            return;
        }

        const items = getCart();

        if (!items.length) {
            floatingCartPreview.innerHTML = "";
            return;
        }

        const itemLinks = items
            .slice(0, 3)
            .map(function (item) {
                const name = escapeHtml(
                    item.name || "Unnamed product"
                );

                if (isValidUrl(item.url)) {
                    return `
                        <a href="${escapeHtml(item.url)}">
                            ${name}
                        </a>
                    `;
                }

                return `<span>${name}</span>`;
            })
            .join("");

        floatingCartPreview.innerHTML = `
            <strong>Saved Ideas</strong>

            ${itemLinks}

            <small>
                ${items.length} total
                item${items.length === 1 ? "" : "s"}
            </small>
        `;
    }

    function updateSavedProductsField() {
        const items = getCart();

        if (savedProductsField) {
            savedProductsField.value = items
                .map(function (item) {
                    const name =
                        normalizeValue(item.name) ||
                        "Unnamed product";

                    const category =
                        normalizeValue(item.category) ||
                        "Product";

                    const url =
                        isValidUrl(item.url)
                            ? normalizeValue(item.url)
                            : "";

                    return (
                        `${name} (${category})` +
                        `${url ? ` - ${url}` : ""}`
                    );
                })
                .join("\n");
        }

        if (!savedProductsPreview) {
            return;
        }

        if (!items.length) {
            savedProductsPreview.innerHTML = "";
            return;
        }

        savedProductsPreview.innerHTML = `
            <strong>
                Saved product ideas included:
            </strong>

            ${items
                .map(function (item) {
                    return `
                        <span>
                            ${escapeHtml(
                                item.name ||
                                "Unnamed product"
                            )}
                        </span>
                    `;
                })
                .join("")}
        `;
    }

    function renderCart() {
        if (!cartItems) {
            return;
        }

        const items = getCart();

        if (!items.length) {
            cartItems.innerHTML = `
                <div class="mini-card text-center">
                    <h4>
                        No saved products yet.
                    </h4>

                    <p>
                        Browse products and save ideas
                        for your quote request.
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

        cartItems.innerHTML = items
            .map(function (item) {
                const id =
                    escapeHtml(item.id);

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

                const price =
                    normalizeValue(item.price);

                const priceMarkup =
                    !isInvalidValue(price)
                        ? `
                            <span class="quote-cart-price">
                                ${escapeHtml(price)}
                            </span>
                        `
                        : "";

                const viewLink =
                    isValidUrl(item.url)
                        ? `
                            <a
                                href="${escapeHtml(item.url)}"
                                class="quote-cart-view-link"
                            >
                                View
                            </a>
                        `
                        : "";

                return `
                    <div
                        class="quote-cart-item"
                        data-cart-product-id="${id}"
                    >
                        <div class="quote-cart-item-info">
                            <strong>${name}</strong>

                            <span>${category}</span>

                            ${priceMarkup}
                        </div>

                        <div class="quote-cart-actions">
                            ${viewLink}

                            <button
                                type="button"
                                class="remove-cart-item"
                                data-product-id="${id}"
                                aria-label="Remove ${name}"
                            >
                                Remove
                            </button>
                        </div>
                    </div>
                `;
            })
            .join("");
    }

    function refreshSaveButtons() {
        const items = getCart();

        document
            .querySelectorAll(
                ".save-product-btn"
            )
            .forEach(function (button) {
                const productId =
                    normalizeId(
                        button.dataset.productId ||
                        button.dataset.id
                    );

                const exists = items.some(
                    function (item) {
                        return (
                            normalizeId(item.id) ===
                            productId
                        );
                    }
                );

                button.textContent = exists
                    ? "Saved ✓"
                    : "Save Product";

                button.classList.toggle(
                    "saved",
                    exists
                );

                button.setAttribute(
                    "aria-pressed",
                    exists ? "true" : "false"
                );
            });
    }

    function refreshQuoteCart() {
        renderCart();
        updateCartCount();
        updateFloatingPreview();
        updateSavedProductsField();
        refreshSaveButtons();
    }

    function buildCartItem(button) {
        return {
            id: normalizeValue(
                button.dataset.productId ||
                button.dataset.id
            ),

            name: normalizeValue(
                button.dataset.productName ||
                button.dataset.name
            ),

            url: normalizeValue(
                button.dataset.productUrl ||
                button.dataset.url
            ),

            image: normalizeValue(
                button.dataset.productImage ||
                button.dataset.image
            ),

            category:
                normalizeValue(
                    button.dataset.productCategory ||
                    button.dataset.category
                ) || "Product",

            price: normalizeValue(
                button.dataset.productPrice ||
                button.dataset.price
            ),
        };
    }

    document.addEventListener(
        "click",
        function (event) {
            const saveButton =
                event.target.closest(
                    ".save-product-btn"
                );

            if (saveButton) {
                event.preventDefault();
                event.stopPropagation();

                const item =
                    buildCartItem(saveButton);

                if (
                    isInvalidValue(item.id) ||
                    isInvalidValue(item.name)
                ) {
                    console.error(
                        "Save button is missing product data:",
                        {
                            button: saveButton,
                            dataset:
                                saveButton.dataset,
                            item: item,
                        }
                    );

                    showToast(
                        "This product is missing required information."
                    );

                    return;
                }

                const cart = getCart();

                const alreadySaved =
                    cart.some(
                        function (savedItem) {
                            return (
                                normalizeId(
                                    savedItem.id
                                ) ===
                                normalizeId(
                                    item.id
                                )
                            );
                        }
                    );

                if (alreadySaved) {
                    showToast(
                        "Product is already saved"
                    );

                    refreshQuoteCart();
                    return;
                }

                cart.push(item);
                saveCart(cart);

                showToast(
                    "Product saved to Quote Cart"
                );

                return;
            }

            const removeButton =
                event.target.closest(
                    ".remove-cart-item"
                );

            if (removeButton) {
                event.preventDefault();

                const productId =
                    normalizeId(
                        removeButton.dataset.productId
                    );

                const updatedCart =
                    getCart().filter(
                        function (item) {
                            return (
                                normalizeId(item.id) !==
                                productId
                            );
                        }
                    );

                saveCart(updatedCart);

                showToast(
                    "Product removed"
                );
            }
        }
    );

    if (clearButton) {
        clearButton.addEventListener(
            "click",
            function (event) {
                event.preventDefault();

                localStorage.removeItem(
                    storageKey
                );

                dispatchCartUpdated([]);

                showToast(
                    "Quote Cart cleared"
                );
            }
        );
    }

    document.addEventListener(
        "quoteCartUpdated",
        function () {
            refreshQuoteCart();
        }
    );

    window.addEventListener(
        "storage",
        function (event) {
            if (event.key === storageKey) {
                refreshQuoteCart();
            }
        }
    );

    window.addEventListener(
        "pageshow",
        function () {
            refreshQuoteCart();
        }
    );

    refreshQuoteCart();
});