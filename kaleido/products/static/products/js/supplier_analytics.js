document.addEventListener("DOMContentLoaded", function () {
    const categoryCanvas = document.getElementById("supplierCategoryChart");
    const pricingCanvas = document.getElementById("supplierPricingChart");

    function fetchJSON(url) {
        return fetch(url).then(function (response) {
            return response.json();
        });
    }

    if (categoryCanvas) {
        fetchJSON("/products/api/supplier-categories/")
            .then(function (data) {
                new Chart(categoryCanvas, {
                    type: "bar",
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: "Products",
                                data: data.values,
                                borderWidth: 1,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false,
                            },
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    precision: 0,
                                },
                            },
                        },
                    },
                });
            });
    }

    if (pricingCanvas) {
        fetchJSON("/products/api/supplier-pricing/")
            .then(function (data) {
                new Chart(pricingCanvas, {
                    type: "bar",
                    data: {
                        labels: ["Minimum", "Average", "Maximum"],
                        datasets: [
                            {
                                label: "Price",
                                data: [
                                    data.minimum_price,
                                    data.average_price,
                                    data.maximum_price,
                                ],
                                borderWidth: 1,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false,
                            },
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                            },
                        },
                    },
                });
            });
    }
});