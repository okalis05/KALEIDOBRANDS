document.addEventListener("DOMContentLoaded", function () {
    const shareButtons = document.querySelectorAll(".share-product-btn");

    function showToast(message) {
        const toast = document.getElementById("kbToast");
        if (!toast) return;

        toast.textContent = message;
        toast.classList.add("show");

        setTimeout(function () {
            toast.classList.remove("show");
        }, 2200);
    }

    shareButtons.forEach(function (button) {
        button.addEventListener("click", async function () {
            const url = button.dataset.url || window.location.href;
            const title = button.dataset.title || document.title;

            if (navigator.share) {
                try {
                    await navigator.share({
                        title: title,
                        url: url,
                    });
                    return;
                } catch (error) {
                    // User cancelled share. Fall back silently.
                }
            }

            try {
                await navigator.clipboard.writeText(url);
                showToast("Product link copied");
            } catch (error) {
                showToast("Copy failed");
            }
        });
    });
});