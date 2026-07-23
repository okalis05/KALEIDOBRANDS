document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.querySelector(
        ".catalog-search-input"
    );

    if (!searchInput) {
        return;
    }

    const searchForm = searchInput.closest("form");

    const resultsContainer = document.createElement("div");
    resultsContainer.className = "live-search-results";
    resultsContainer.hidden = true;

    searchInput.parentElement.style.position = "relative";
    searchInput.parentElement.appendChild(resultsContainer);

    let debounceTimer = null;
    let activeRequest = null;
    let highlightedIndex = -1;


    function escapeHtml(value) {
        const element = document.createElement("div");
        element.textContent = value ?? "";
        return element.innerHTML;
    }


    function inventoryClass(status) {
        const allowedStatuses = [
            "in_stock",
            "low_stock",
            "out_of_stock",
            "discontinued",
        ];

        if (!allowedStatuses.includes(status)) {
            return "";
        }

        return `status-${status.replaceAll("_", "-")}`;
    }


    function createPlaceholder(productName) {
        const initials = productName
            .trim()
            .slice(0, 2)
            .toUpperCase();

        return `
            <div class="live-search-placeholder">
                ${escapeHtml(initials || "KB")}
            </div>
        `;
    }


    function createImage(result) {
        if (!result.image) {
            return createPlaceholder(result.name);
        }

        return `
            <img
                src="${escapeHtml(result.image)}"
                alt=""
                loading="lazy"
                class="live-search-image"
            >
        `;
    }


    function createResultMarkup(result) {
        const statusClass = inventoryClass(
            result.inventory_status
        );

        const supplierMarkup = result.supplier
            ? `
                <span class="live-search-supplier">
                    ${escapeHtml(result.supplier)}
                </span>
            `
            : "";

        const inventoryMarkup = result.inventory_label
            ? `
                <span
                    class="live-search-status ${statusClass}"
                >
                    ${escapeHtml(result.inventory_label)}
                </span>
            `
            : "";

        const minimumMarkup = result.minimum_quantity
            ? `
                <span>
                    MOQ ${escapeHtml(
                        String(result.minimum_quantity)
                    )}
                </span>
            `
            : "";

        return `
            <a
                href="${escapeHtml(result.url)}"
                class="live-search-result"
                role="option"
                tabindex="-1"
            >
                <div class="live-search-media">
                    ${createImage(result)}
                </div>

                <div class="live-search-content">
                    <div class="live-search-heading">
                        <strong>
                            ${escapeHtml(result.name)}
                        </strong>

                        <span class="live-search-price">
                            ${escapeHtml(result.price)}
                        </span>
                    </div>

                    <div class="live-search-meta">
                        <span>
                            ${escapeHtml(result.category)}
                        </span>

                        ${supplierMarkup}
                    </div>

                    <div class="live-search-details">
                        ${inventoryMarkup}
                        ${minimumMarkup}
                    </div>
                </div>
            </a>
        `;
    }


    function showMessage(message, className = "") {
        resultsContainer.innerHTML = `
            <div class="live-search-message ${className}">
                ${escapeHtml(message)}
            </div>
        `;

        resultsContainer.hidden = false;
        highlightedIndex = -1;
    }


    function hideResults() {
        resultsContainer.hidden = true;
        highlightedIndex = -1;
    }


    function renderResults(results) {
        if (!Array.isArray(results) || results.length === 0) {
            showMessage(
                "No matching products found.",
                "live-search-empty"
            );
            return;
        }

        resultsContainer.innerHTML = results
            .map(createResultMarkup)
            .join("");

        resultsContainer.hidden = false;
        highlightedIndex = -1;
    }


    async function fetchResults(query) {
        if (activeRequest) {
            activeRequest.abort();
        }

        activeRequest = new AbortController();

        showMessage(
            "Searching products...",
            "live-search-loading"
        );

        try {
            const endpoint = new URL(
                "/products/api/search/",
                window.location.origin
            );

            endpoint.searchParams.set("q", query);

            const response = await fetch(endpoint, {
                method: "GET",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                signal: activeRequest.signal,
            });

            if (!response.ok) {
                throw new Error(
                    `Search request failed: ${response.status}`
                );
            }

            const data = await response.json();

            renderResults(data.results);
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }

            console.error("Live search failed:", error);

            showMessage(
                "Search is temporarily unavailable.",
                "live-search-error"
            );
        }
    }


    function scheduleSearch() {
        window.clearTimeout(debounceTimer);

        const query = searchInput.value.trim();

        if (query.length < 2) {
            hideResults();
            resultsContainer.innerHTML = "";
            return;
        }

        debounceTimer = window.setTimeout(() => {
            fetchResults(query);
        }, 250);
    }


    function getResultLinks() {
        return Array.from(
            resultsContainer.querySelectorAll(
                ".live-search-result"
            )
        );
    }


    function updateHighlight() {
        const links = getResultLinks();

        links.forEach((link, index) => {
            const isActive = index === highlightedIndex;

            link.classList.toggle(
                "is-highlighted",
                isActive
            );

            link.setAttribute(
                "aria-selected",
                String(isActive)
            );
        });

        if (
            highlightedIndex >= 0
            && links[highlightedIndex]
        ) {
            links[highlightedIndex].scrollIntoView({
                block: "nearest",
            });
        }
    }


    function handleKeyboardNavigation(event) {
        if (resultsContainer.hidden) {
            return;
        }

        const links = getResultLinks();

        if (event.key === "Escape") {
            hideResults();
            searchInput.focus();
            return;
        }

        if (links.length === 0) {
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();

            highlightedIndex = (
                highlightedIndex + 1
            ) % links.length;

            updateHighlight();
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();

            highlightedIndex = highlightedIndex <= 0
                ? links.length - 1
                : highlightedIndex - 1;

            updateHighlight();
            return;
        }

        if (
            event.key === "Enter"
            && highlightedIndex >= 0
        ) {
            event.preventDefault();
            links[highlightedIndex].click();
        }
    }


    searchInput.setAttribute(
        "autocomplete",
        "off"
    );

    searchInput.setAttribute(
        "aria-autocomplete",
        "list"
    );

    searchInput.setAttribute(
        "aria-expanded",
        "false"
    );


    searchInput.addEventListener("input", () => {
        scheduleSearch();

        searchInput.setAttribute(
            "aria-expanded",
            String(
                searchInput.value.trim().length >= 2
            )
        );
    });


    searchInput.addEventListener(
        "keydown",
        handleKeyboardNavigation
    );


    searchInput.addEventListener("focus", () => {
        if (
            searchInput.value.trim().length >= 2
            && resultsContainer.innerHTML.trim()
        ) {
            resultsContainer.hidden = false;

            searchInput.setAttribute(
                "aria-expanded",
                "true"
            );
        }
    });


    document.addEventListener("click", (event) => {
        const clickedInsideSearch = (
            searchInput.contains(event.target)
            || resultsContainer.contains(event.target)
        );

        if (!clickedInsideSearch) {
            hideResults();

            searchInput.setAttribute(
                "aria-expanded",
                "false"
            );
        }
    });


    if (searchForm) {
        searchForm.addEventListener("submit", () => {
            hideResults();
        });
    }
});