function swapProductImage(url) {

    const image = document.getElementById("mainProductImage");

    if (!image) return;

    image.src = url;
}