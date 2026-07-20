document.addEventListener("DOMContentLoaded", function () {
    const revealElements = document.querySelectorAll(".reveal");
    const scrollTopButton = document.getElementById("scrollTop");
    const navLinks = document.querySelectorAll(".nav-link, .navbar-brand, .hero-actions a, .catalog-pill");

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

    navLinks.forEach(function (link) {
        link.addEventListener("click", function () {
            const navbarCollapse = document.querySelector(".navbar-collapse");

            if (navbarCollapse && navbarCollapse.classList.contains("show")) {
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);

                if (bsCollapse) {
                    bsCollapse.hide();
                }
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