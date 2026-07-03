document.addEventListener("DOMContentLoaded", function () {
    const storageKey = "kbQuoteCart";
    const buttons = document.querySelectorAll(".save-product-btn");
    const cartItems = document.getElementById("quoteCartItems");
    const clearButton = document.getElementById("clearQuoteCart");
    const countBadge = document.getElementById("quoteCartCount");
    const pageCount = document.getElementById("quoteCartPageCount");
    const savedProductsField = document.getElementById("savedProductsField");
    const savedProductsPreview = document.getElementById("savedProductsPreview");
    const floatingCountBadge = document.getElementById("floatingQuoteCartCount");
    const floatingCartPreview = document.getElementById("floatingCartPreview");

    function getCart() {
        return JSON.parse(localStorage.getItem(storageKey) || "[]");
    }

    function saveCart(items) {
        localStorage.setItem(storageKey, JSON.stringify(items));
    }

    function showToast(message) {
        const toast = document.getElementById("kbToast");
        if (!toast) return;

        toast.textContent = message;
        toast.classList.add("show");

        setTimeout(function () {
            toast.classList.remove("show");
        }, 2200);
    }

    function updateFloatingPreview() {
        if (!floatingCartPreview) return;

        const items = getCart();

        if (!items.length) {
            floatingCartPreview.innerHTML = "";
            return;
        }

        floatingCartPreview.innerHTML = `
            <strong>Saved Ideas</strong>
            ${items.slice(0, 3).map(function (item) {
                return `<a href="${item.url}">${item.name}</a>`;
            }).join("")}
            <small>${items.length} total item${items.length === 1 ? "" : "s"}</small>
        `;
    }

    function updateCartCount() {
        const count = getCart().length;

        if (countBadge) countBadge.textContent = count;
        if (pageCount) pageCount.textContent = count === 1 ? "1 item" : `${count} items`;
        if (floatingCountBadge) floatingCountBadge.textContent = count;

        const floatingCart = document.querySelector(".floating-quote-cart");
        if (floatingCart) floatingCart.classList.toggle("show", count > 0);
    }

    function updateSavedProductsField() {
        if (!savedProductsField) return;

        const items = getCart();
        savedProductsField.value = items.map(function (item) {
            return `${item.name} (${item.category}) - ${item.url}`;
        }).join("\n");
    }
    if (savedProductsPreview) {
        if (!items.length) {
            savedProductsPreview.innerHTML = "";
            return;
        }

        savedProductsPreview.innerHTML = `
            <strong>Saved product ideas included:</strong>
            ${items.map(function (item) {
                return `<span>${item.name}</span>`;
            }).join("")}`;
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
                const updatedCart = getCart().filter(function (item) {
                    return item.url !== button.dataset.url;
                });

                saveCart(updatedCart);
                renderCart();
                updateCartCount();
                updateFloatingPreview();
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
            updateFloatingPreview();
            updateSavedProductsField();
        });
    });

    if (clearButton) {
        clearButton.addEventListener("click", function () {
            saveCart([]);
            renderCart();
            updateCartCount();
            updateFloatingPreview();
            updateSavedProductsField();
        });
    }
buttons.forEach(function (button) {
    const cart = getCart();

    const exists = cart.some(function (saved) {
        return saved.url === button.dataset.url;
    });

    if (exists) {
        button.textContent = "Saved ✓";
        button.classList.add("saved");
        showToast("Product saved to Quote Cart");
    }
});
    renderCart();
    updateCartCount();
    updateFloatingPreview();
    updateSavedProductsField();
});