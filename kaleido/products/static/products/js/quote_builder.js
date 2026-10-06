document.addEventListener(
    "DOMContentLoaded",
    function () {
        "use strict";

        const container =
            document.getElementById(
                "quoteBuilderItems"
            );

        const hiddenField =
            document.getElementById(
                "quoteItemsJSON"
            );

        const emptyState =
            document.getElementById(
                "quoteBuilderEmpty"
            );

        const countElement =
            document.getElementById(
                "savedProductsCount"
            );

        const form =
            document.getElementById(
                "quoteBuilderForm"
            );

        const submitButton =
            document.getElementById(
                "submitQuoteButton"
            );

        /*
         * The old provider rendered a second product
         * preview. The Builder now owns all visible
         * product state.
         */
        const legacyPreview =
            document.getElementById(
                "savedProductsPreview"
            );

        const legacyEmpty =
            document.getElementById(
                "savedProductsEmpty"
            );

        if (legacyPreview) {
            legacyPreview.hidden = false;
        }

        if (legacyEmpty) {
            legacyEmpty.hidden = true;
        }

        if (
            !container ||
            !hiddenField
        ) {
            return;
        }


        function loadItems() {
            if (
                typeof window
                    .getKBQuoteRequestProducts
                !== "function"
            ) {
                return [];
            }

            const result =
                window
                    .getKBQuoteRequestProducts();

            return Array.isArray(result)
                ? result
                : [];
        }


        let items =
            loadItems();


        function minimumFor(item) {
            let value =
                parseInt(
                    item.minimum ??
                    item.min_quantity ??
                    item.minimum_quantity ??
                    1,
                    10
                );

            if (
                Number.isNaN(value) ||
                value < 1
            ) {
                value = 1;
            }

            return value;
        }


        function quantityFor(item) {
            const minimum =
                minimumFor(item);

            let value =
                parseInt(
                    item.quantity ??
                    minimum,
                    10
                );

            if (
                Number.isNaN(value) ||
                value < minimum
            ) {
                value = minimum;
            }

            return value;
        }


        function updateState(
            quoteItems
        ) {
            const count =
                quoteItems.length;

            if (countElement) {
                countElement.textContent =
                    `${count} selected product${
                        count === 1
                            ? ""
                            : "s"
                    }`;
            }

            if (emptyState) {
                emptyState.hidden =
                    count !== 0;
            }

            if (submitButton) {
                submitButton.disabled =
                    count === 0;
            }
        }


        function syncHiddenField() {
            const quoteItems = [];

            container
                .querySelectorAll(
                    ".quote-builder-item"
                )
                .forEach(
                    function (card) {
                        const qty =
                            card.querySelector(
                                ".qty"
                            );

                        const note =
                            card.querySelector(
                                ".note"
                            );

                        const minimum =
                            parseInt(
                                card.dataset
                                    .minQuantity ||
                                "1",
                                10
                            );

                        let quantity =
                            parseInt(
                                qty.value ||
                                minimum,
                                10
                            );

                        if (
                            Number.isNaN(
                                quantity
                            ) ||
                            quantity < minimum
                        ) {
                            quantity =
                                minimum;

                            qty.value =
                                minimum;
                        }

                        quoteItems.push({
                            id:
                                card.dataset.id,

                            name:
                                card.dataset.name,

                            category:
                                card.dataset
                                    .category,

                            url:
                                card.dataset.url,

                            quantity:
                                quantity,

                            notes:
                                note.value.trim(),
                        });
                    }
                );

            hiddenField.value =
                JSON.stringify(
                    quoteItems
                );

            updateState(
                quoteItems
            );

            return quoteItems;
        }


        function removeItem(index) {
            const item =
                items[index];

            if (!item) {
                return;
            }

            if (
                typeof window
                    .removeKBQuoteRequestProduct
                === "function"
            ) {
                window
                    .removeKBQuoteRequestProduct(
                        item.id
                    );
            }

            items =
                loadItems();

            renderItems();
        }


        function renderItems() {
            container.innerHTML = "";

            /*
             * Restore the original compact Quote Builder preview.
             *
             * This is presentation only. Both this preview and the
             * detailed cards below use the same normalized item state.
             */
            if (legacyPreview) {
                legacyPreview.innerHTML = "";

                if (!items.length) {
                    legacyPreview.hidden = true;
                } else {
                    legacyPreview.hidden = false;

                    items.forEach(
                        function (item) {
                            const minimum =
                                minimumFor(item);

                            const row =
                                document.createElement(
                                    "div"
                                );

                            row.className =
                                "mb-2";

                            const name =
                                document.createElement(
                                    item.url
                                        ? "a"
                                        : "div"
                                );

                            name.className =
                                "fw-semibold";

                            name.textContent =
                                item.name ||
                                "Promotional Product";

                            if (item.url) {
                                name.href =
                                    item.url;
                            }

                            const minimumText =
                                document.createElement(
                                    "div"
                                );

                            minimumText.className =
                                "small text-muted";

                            minimumText.textContent =
                                `Minimum quantity: ${minimum}`;

                            row.appendChild(
                                name
                            );

                            row.appendChild(
                                minimumText
                            );

                            legacyPreview.appendChild(
                                row
                            );
                        }
                    );
                }
            }

            if (!items.length) {
                hiddenField.value =
                    "[]";

                updateState([]);

                return;
            }

            items.forEach(
                function (
                    item,
                    index
                ) {
                    const minimum =
                        minimumFor(item);

                    const quantity =
                        quantityFor(item);

                    const card =
                        document.createElement(
                            "div"
                        );

                    card.className =
                        "quote-builder-item";

                    card.dataset.id =
                        String(
                            item.id
                        );

                    card.dataset.name =
                        String(
                            item.name ||
                            ""
                        );

                    card.dataset.category =
                        String(
                            item.category ||
                            "Promotional Product"
                        );

                    card.dataset.url =
                        String(
                            item.url ||
                            ""
                        );

                    card.dataset.minQuantity =
                        String(
                            minimum
                        );

                    const top =
                        document.createElement(
                            "div"
                        );

                    top.className =
                        "d-flex " +
                        "justify-content-between " +
                        "align-items-start gap-3";

                    const info =
                        document.createElement(
                            "div"
                        );

                    /*
                     * Product identity:
                     * thumbnail + existing product information.
                     *
                     * This is presentation only. The image URL already
                     * comes from the normalized Quote Cart item.
                     */
                    info.style.display =
                        "flex";

                    info.style.alignItems =
                        "center";

                    info.style.gap =
                        "14px";

                    info.style.minWidth =
                        "0";

                    const imageBox =
                        document.createElement(
                            "div"
                        );

                    imageBox.style.width =
                        "72px";

                    imageBox.style.height =
                        "72px";

                    imageBox.style.flex =
                        "0 0 72px";

                    imageBox.style.borderRadius =
                        "14px";

                    imageBox.style.overflow =
                        "hidden";

                    imageBox.style.display =
                        "flex";

                    imageBox.style.alignItems =
                        "center";

                    imageBox.style.justifyContent =
                        "center";

                    imageBox.style.background =
                        "rgba(255,255,255,0.72)";

                    imageBox.style.border =
                        "1px solid rgba(15,23,42,0.08)";

                    if (item.image) {
                        const productImage =
                            document.createElement(
                                "img"
                            );

                        productImage.src =
                            item.image;

                        productImage.alt =
                            item.name ||
                            "Product";

                        productImage.loading =
                            "lazy";

                        productImage.style.width =
                            "100%";

                        productImage.style.height =
                            "100%";

                        productImage.style.objectFit =
                            "contain";

                        productImage.addEventListener(
                            "error",
                            function () {
                                imageBox.innerHTML =
                                    "";

                                const fallback =
                                    document.createElement(
                                        "span"
                                    );

                                fallback.textContent =
                                    (
                                        item.name ||
                                        "KB"
                                    )
                                        .slice(0, 2)
                                        .toUpperCase();

                                fallback.style.fontWeight =
                                    "700";

                                fallback.style.opacity =
                                    "0.5";

                                imageBox.appendChild(
                                    fallback
                                );
                            },
                            {
                                once: true
                            }
                        );

                        imageBox.appendChild(
                            productImage
                        );
                    } else {
                        const fallback =
                            document.createElement(
                                "span"
                            );

                        fallback.textContent =
                            (
                                item.name ||
                                "KB"
                            )
                                .slice(0, 2)
                                .toUpperCase();

                        fallback.style.fontWeight =
                            "700";

                        fallback.style.opacity =
                            "0.5";

                        imageBox.appendChild(
                            fallback
                        );
                    }

                    const productText =
                        document.createElement(
                            "div"
                        );

                    productText.style.minWidth =
                        "0";

                    const category =
                        document.createElement(
                            "div"
                        );

                    category.className =
                        "small text-muted";

                    category.textContent =
                        item.category ||
                        "Promotional Product";

                    const name =
                        document.createElement(
                            item.url
                                ? "a"
                                : "div"
                        );

                    name.className =
                        "fw-semibold";

                    name.textContent =
                        item.name ||
                        "Promotional Product";

                    if (item.url) {
                        name.href =
                            item.url;
                    }

                    const minimumText =
                        document.createElement(
                            "div"
                        );

                    minimumText.className =
                        "small text-muted mt-1";

                    minimumText.textContent =
                        `Minimum quantity: ${minimum}`;

                    productText.appendChild(
                        category
                    );

                    productText.appendChild(
                        name
                    );

                    productText.appendChild(
                        minimumText
                    );

                    info.appendChild(
                        imageBox
                    );

                    info.appendChild(
                        productText
                    );

                    const removeButton =
                        document.createElement(
                            "button"
                        );

                    removeButton.type =
                        "button";

                    removeButton.className =
                        "btn btn-sm " +
                        "btn-outline-danger";

                    removeButton.textContent =
                        "Remove";

                    removeButton.addEventListener(
                        "click",
                        function () {
                            removeItem(
                                index
                            );
                        }
                    );

                    top.appendChild(
                        info
                    );

                    top.appendChild(
                        removeButton
                    );

                    const controls =
                        document.createElement(
                            "div"
                        );

                    controls.className =
                        "row g-3 mt-2";

                    const qtyColumn =
                        document.createElement(
                            "div"
                        );

                    qtyColumn.className =
                        "col-md-4";

                    const qtyLabel =
                        document.createElement(
                            "label"
                        );

                    qtyLabel.className =
                        "form-label";

                    qtyLabel.textContent =
                        "Quantity";

                    const qtyInput =
                        document.createElement(
                            "input"
                        );

                    qtyInput.type =
                        "number";

                    qtyInput.className =
                        "form-control qty";

                    qtyInput.min =
                        String(minimum);

                    qtyInput.step =
                        "1";

                    qtyInput.value =
                        String(quantity);

                    qtyInput.addEventListener(
                        "input",
                        syncHiddenField
                    );

                    qtyInput.addEventListener(
                        "change",
                        syncHiddenField
                    );

                    qtyColumn.appendChild(
                        qtyLabel
                    );

                    qtyColumn.appendChild(
                        qtyInput
                    );

                    const noteColumn =
                        document.createElement(
                            "div"
                        );

                    noteColumn.className =
                        "col-md-8";

                    const noteLabel =
                        document.createElement(
                            "label"
                        );

                    noteLabel.className =
                        "form-label";

                    noteLabel.textContent =
                        "Product notes";

                    const noteInput =
                        document.createElement(
                            "input"
                        );

                    noteInput.type =
                        "text";

                    noteInput.className =
                        "form-control note";

                    noteInput.placeholder =
                        "Color, decoration, logo placement...";

                    noteInput.value =
                        item.notes ||
                        "";

                    noteInput.addEventListener(
                        "input",
                        syncHiddenField
                    );

                    noteInput.addEventListener(
                        "change",
                        syncHiddenField
                    );

                    noteColumn.appendChild(
                        noteLabel
                    );

                    noteColumn.appendChild(
                        noteInput
                    );

                    controls.appendChild(
                        qtyColumn
                    );

                    controls.appendChild(
                        noteColumn
                    );

                    card.appendChild(
                        top
                    );

                    card.appendChild(
                        controls
                    );

                    container.appendChild(
                        card
                    );
                }
            );

            syncHiddenField();
        }


        window.addEventListener(
            "kbQuoteProductsChanged",
            function () {
                items =
                    loadItems();

                renderItems();
            }
        );


        window.addEventListener(
            "storage",
            function (event) {
                if (
                    event.key ===
                        window
                            .KB_QUOTE_CART_KEY ||
                    event.key ===
                        window
                            .KB_COMPARE_CART_KEY
                ) {
                    items =
                        loadItems();

                    renderItems();
                }
            }
        );


        if (form) {
            form.addEventListener(
                "submit",
                function (event) {
                    const quoteItems =
                        syncHiddenField();

                    if (
                        !quoteItems.length
                    ) {
                        event.preventDefault();

                        alert(
                            "Please select at least " +
                            "one product before " +
                            "submitting your quote."
                        );
                    }
                }
            );
        }


        renderItems();
    }
);
