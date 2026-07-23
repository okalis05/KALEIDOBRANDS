(function () {
    "use strict";

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];

        for (const cookie of cookies) {
            const trimmedCookie = cookie.trim();

            if (trimmedCookie.startsWith(`${name}=`)) {
                return decodeURIComponent(
                    trimmedCookie.substring(name.length + 1)
                );
            }
        }

        return "";
    }

    function getCsrfToken() {
        const input = document.querySelector(
            "#comparisonCsrfForm input[name='csrfmiddlewaretoken']"
        );

        if (input && input.value) {
            return input.value;
        }

        return getCookie("csrftoken");
        }


    async function postComparisonRequest(url) {
        const csrfToken = getCsrfToken();

        if (!csrfToken) {
            throw new Error(
                "The security token is unavailable. Refresh the page and try again."
            );
        }

        const response = await fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
            credentials: "same-origin",
        });

        let data;

        try {
            data = await response.json();
        } catch (error) {
            throw new Error("The comparison request returned an invalid response.");
        }

        if (!response.ok) {
            throw new Error(
                data.message || "The comparison request could not be completed."
            );
        }

        return data;
    }


    function updateComparisonCount(count) {
        document
            .querySelectorAll("[data-compare-count]")
            .forEach((element) => {
                element.textContent = count;
            });

        document
            .querySelectorAll("[data-compare-link]")
            .forEach((element) => {
                element.hidden = count === 0;
            });
    }


    function updateCompareButton(button, isAdded) {
        if (!button) {
            return;
        }

        button.classList.toggle("is-added", isAdded);
        button.setAttribute("aria-pressed", String(isAdded));

        const label = button.querySelector("[data-compare-label]");

        if (label) {
            label.textContent = isAdded ? "Added to Compare" : "Compare";
        }
    }


    function showComparisonMessage(message, type = "success") {
        if (!message) {
            return;
        }

        let notification = document.getElementById(
            "comparisonNotification"
        );

        if (!notification) {
            notification = document.createElement("div");
            notification.id = "comparisonNotification";
            notification.className = "comparison-notification";
            notification.setAttribute("role", "status");
            notification.setAttribute("aria-live", "polite");

            document.body.appendChild(notification);
        }

        notification.textContent = message;
        notification.classList.remove(
            "is-success",
            "is-error",
            "is-visible"
        );

        notification.classList.add(
            type === "error" ? "is-error" : "is-success"
        );

        window.requestAnimationFrame(() => {
            notification.classList.add("is-visible");
        });

        window.clearTimeout(notification.hideTimeout);

        notification.hideTimeout = window.setTimeout(() => {
            notification.classList.remove("is-visible");
        }, 3500);
    }


    async function handleCompareAdd(button) {
        const addUrl = button.dataset.addUrl;

        if (!addUrl || button.disabled) {
            return;
        }

        button.disabled = true;

        try {
            const data = await postComparisonRequest(addUrl);

            updateComparisonCount(data.compare_count);
            updateCompareButton(button, true);
            showComparisonMessage(data.message);
        } catch (error) {
            showComparisonMessage(error.message, "error");
        } finally {
            button.disabled = false;
        }
    }


    async function handleCompareRemove(button) {
        const removeUrl = button.dataset.removeUrl;
        const productId = button.dataset.productId;

        if (!removeUrl || button.disabled) {
            return;
        }

        button.disabled = true;

        try {
            const data = await postComparisonRequest(removeUrl);

            document
                .querySelectorAll(
                    `[data-compare-column="${productId}"]`
                )
                .forEach((column) => {
                    column.remove();
                });

            updateComparisonCount(data.compare_count);
            showComparisonMessage(data.message);

            if (data.compare_count === 0) {
                window.location.reload();
            }
        } catch (error) {
            showComparisonMessage(error.message, "error");
            button.disabled = false;
        }
    }


    async function handleCompareClear(button) {
        const clearUrl = button.dataset.url;

        if (!clearUrl || button.disabled) {
            return;
        }

        button.disabled = true;

        try {
            const data = await postComparisonRequest(clearUrl);

            updateComparisonCount(data.compare_count);
            showComparisonMessage(data.message);

            window.location.reload();
        } catch (error) {
            showComparisonMessage(error.message, "error");
            button.disabled = false;
        }
    }


    document.addEventListener("click", (event) => {
        const addButton = event.target.closest(
            "[data-compare-add]"
        );

        if (addButton) {
            event.preventDefault();
            handleCompareAdd(addButton);
            return;
        }

        const removeButton = event.target.closest(
            ".compare-remove-btn"
        );

        if (removeButton) {
            event.preventDefault();
            handleCompareRemove(removeButton);
            return;
        }

        const clearButton = event.target.closest(
            "#clearComparisonButton"
        );

        if (clearButton) {
            event.preventDefault();
            handleCompareClear(clearButton);
        }
    });
})();