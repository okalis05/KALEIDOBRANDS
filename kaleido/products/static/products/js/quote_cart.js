document.addEventListener("DOMContentLoaded", function () {
    const storageKey = "kbQuoteCart";
    const buttons = document.querySelectorAll(".save-product-btn");
    const cartItems = document.getElementById("quoteCartItems");
    const clearButton = document.getElementById("clearQuoteCart");
    const countBadge = document.getElementById("quoteCartCount");
    const savedProductsField = document.getElementById("savedProductsField");

    function getCart() {
        return JSON.parse(localStorage.getItem(storageKey) || "[]");
    }

    function saveCart(items) {
        localStorage.setItem(storageKey, JSON.stringify(items));
    }

    function updateCartCount() {
        if (!countBadge) return;
        countBadge.textContent = getCart().length;
    }

    function updateSavedProductsField() {
        if (!savedProductsField) return;

        const items = getCart();

        savedProductsField.value = items.map(function (item) {
            return `${item.name} (${item.category}) - ${item.url}`;
        }).join("\n");
    }

    function renderCart() {
        if (!cartItems) return;

        const items = getCart();

        if (!items.length) {
            cartItems.innerHTML = `
                <div class="mini-card text-center">
                    <h4>No saved products yet.</h4>
                    <p>Browse products and save ideas for your quote request.</p>
                    <a href="/products/" class="btn btn-kb-primary">Browse Products</a>
                </div>
            `;
            return;
        }

        cartItems.innerHTML = items.map(function (item) {
            return `
                <div class="quote-cart-item">
                    <div>
                        <strong>${item.name}</strong>
                        <span>${item.category}</span>
                    </div>
                    <div class="quote-cart-actions">
                        <a href="${item.url}">View</a>
                        <button type="button" class="remove-cart-item" data-url="${item.url}">
                            Remove
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        document.querySelectorAll(".remove-cart-item").forEach(function (button) {
            button.addEventListener("click", function () {
                const url = button.dataset.url;

                const updatedCart = getCart().filter(function (item) {
                    return item.url !== url;
                });

                saveCart(updatedCart);
                renderCart();
                updateCartCount();
                updateSavedProductsField();
            });
        });
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();

            const item = {
                name: button.dataset.name,
                url: button.dataset.url,
                category: button.dataset.category,
            };

            const cart = getCart();

            const exists = cart.some(function (saved) {
                return saved.url === item.url;
            });

            if (!exists) {
                cart.push(item);
                saveCart(cart);
            }

            button.textContent = "Saved ✓";
            button.classList.add("saved");

            updateCartCount();
            updateSavedProductsField();
        });
    });

    if (clearButton) {
        clearButton.addEventListener("click", function () {
            saveCart([]);
            renderCart();
            updateCartCount();
            updateSavedProductsField();
        });
    }

    renderCart();
    updateCartCount();
    updateSavedProductsField();
});