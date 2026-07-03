document.addEventListener("DOMContentLoaded", function () {
    const mainImage = document.getElementById("mainProductImage");
    const thumbnails = document.querySelectorAll(".product-thumb");

    thumbnails.forEach(function (thumb) {
        thumb.addEventListener("click", function () {
            const imageUrl = thumb.dataset.image;

            if (!mainImage || !imageUrl) return;

            mainImage.src = imageUrl;

            thumbnails.forEach(function (item) {
                item.classList.remove("active");
            });

            thumb.classList.add("active");
        });
    });
});
