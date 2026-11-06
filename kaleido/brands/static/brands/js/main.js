document.addEventListener("DOMContentLoaded", function () {
    const revealElements = document.querySelectorAll(".reveal");
    const scrollTopButton = document.getElementById("scrollTop");
    const revealObserver = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("active");
                }
            });
        },
        {
            threshold: 0.16,
        }
    );

    revealElements.forEach(function (element) {
        revealObserver.observe(element);
    });

    window.addEventListener("scroll", function () {
        if (window.scrollY > 600) {
            scrollTopButton.classList.add("show");
        } else {
            scrollTopButton.classList.remove("show");
        }
    });

    scrollTopButton.addEventListener("click", function () {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    });

    
/* ==========================================
   KALEIDOBRANDS — MOBILE NAVBAR FIX
   Close navbar only when a navigation link
   is selected, not when opening a dropdown.
   ========================================== */

document.querySelectorAll(
    ".kb-navbar .navbar-brand, " +
    ".kb-navbar .navbar-collapse .nav-link:not(.dropdown-toggle), " +
    ".kb-navbar .navbar-collapse .dropdown-item"
).forEach(function (link) {

    link.addEventListener("click", function () {

        const navbarCollapse = document.getElementById("mainNav");

        if (!navbarCollapse ||
            !navbarCollapse.classList.contains("show")) {
            return;
        }

        if (window.bootstrap) {
            const bsCollapse =
                bootstrap.Collapse.getOrCreateInstance(
                    navbarCollapse,
                    { toggle: false }
                );

            bsCollapse.hide();
        }

    });

});


    const params = new URLSearchParams(window.location.search);

    if (params.get("quote") === "1") {
         const quoteTabButton = document.getElementById("quote-tab");

        if (quoteTabButton && window.bootstrap) {
            const tab = new bootstrap.Tab(quoteTabButton);
            tab.show();
        }
}
});