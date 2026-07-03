document.addEventListener("DOMContentLoaded", function () {
    const productData = document.getElementById("recentProductData");
    const recentContainer = document.getElementById("recentlyViewedProducts");
    const storageKey = "kbRecentlyViewed";

    function getRecent() {
        return JSON.parse(localStorage.getItem(storageKey) || "[]");
    }

    function saveRecent(items) {
        localStorage.setItem(storageKey, JSON.stringify(items.slice(0, 6)));
    }

    if (productData) {
        const product = {
            name: productData.dataset.name,
            url: productData.dataset.url,
            category: productData.dataset.category,
        };

        let items = getRecent().filter(function (item) {
            return item.url !== product.url;
        });

        items.unshift(product);
        saveRecent(items);
    }

    if (recentContainer) {
        const items = getRecent();

        if (!items.length) {
            recentContainer.innerHTML = "";
            return;
        }

        recentContainer.innerHTML = items.map(function (item) {
            return `
                <a href="${item.url}" class="recent-product-pill">
                    <strong>${item.name}</strong>
                    <span>${item.category}</span>
                </a>
            `;
        }).join("");
    }
});