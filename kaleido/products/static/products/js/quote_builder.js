document.addEventListener("DOMContentLoaded", function () {
    const storageKey = "kbQuoteCart";
    const container = document.getElementById("quoteBuilderItems");
    const hiddenField = document.getElementById("quoteItemsJSON");

    if (!container) return;

    const items = JSON.parse(localStorage.getItem(storageKey) || "[]");

    if (!items.length) {
        container.innerHTML = `
            <div class="mini-card text-center">
                <h3>No saved products.</h3>
                <p>Browse products and save items before building a quote.</p>
                <a href="/products/" class="btn btn-kb-primary">Browse Products</a>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(function (item) {
        return `
            <div class="quote-builder-item glass-card"
                 data-name="${item.name}"
                 data-category="${item.category}"
                 data-url="${item.url}">
                <h4>${item.name}</h4>
                <p>${item.category}</p>

                <div class="row g-3">
                    <div class="col-md-4">
                        <label>Quantity</label>
                        <input class="form-control qty" type="number" min="1" value="100">
                    </div>

                    <div class="col-md-8">
                        <label>Product Notes</label>
                        <input class="form-control note" placeholder="Colors, decoration, logo placement...">
                    </div>
                </div>
            </div>
        `;
    }).join("");

    const form = document.querySelector("form");

    if (form && hiddenField) {
        form.addEventListener("submit", function () {
            const quoteItems = [];

            document.querySelectorAll(".quote-builder-item").forEach(function (card) {
                quoteItems.push({
                    name: card.dataset.name,
                    category: card.dataset.category,
                    url: card.dataset.url,
                    quantity: card.querySelector(".qty").value,
                    notes: card.querySelector(".note").value,
                });
            });

            hiddenField.value = JSON.stringify(quoteItems);
        });
    }
});