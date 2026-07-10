document.addEventListener("DOMContentLoaded", function () {
    const storageKey = "kbQuoteCart";
    const reorderItems = document.querySelectorAll(".reorder-item");
    const continueButton = document.getElementById("continueReorder");

    function saveReorderItems() {
        const items = [];

        reorderItems.forEach(function (item) {
            items.push({
                name: item.dataset.name,
                category: item.dataset.category || "Reorder",
                url: item.dataset.url || "/products/",
            });
        });

        localStorage.setItem(storageKey, JSON.stringify(items));
    }

    if (continueButton) {
        continueButton.addEventListener("click", function () {
            saveReorderItems();
        });
    }
});