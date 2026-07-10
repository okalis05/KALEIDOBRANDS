document.addEventListener("DOMContentLoaded", function () {
    function fetchJSON(url) {
        return fetch(url).then(function (response) {
            return response.json();
        });
    }

    const orderCanvas = document.getElementById("executiveOrderStatusChart");
    const crmCanvas = document.getElementById("executiveCrmPipelineChart");
    const syncCanvas = document.getElementById("executiveSupplierSyncChart");

    if (orderCanvas) {
        fetchJSON("/customers/api/executive/order-status/")
            .then(function (data) {
                new Chart(orderCanvas, {
                    type: "bar",
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: "Orders",
                                data: data.counts,
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

    if (crmCanvas) {
        fetchJSON("/customers/api/executive/crm-pipeline/")
            .then(function (data) {
                new Chart(crmCanvas, {
                    type: "bar",
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: "Pipeline Value",
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
                            },
                        },
                    },
                });
            });
    }

    if (syncCanvas) {
        fetchJSON("/customers/api/executive/supplier-sync/")
            .then(function (data) {
                new Chart(syncCanvas, {
                    type: "line",
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: "Created",
                                data: data.created,
                                borderWidth: 2,
                                tension: 0.35,
                            },
                            {
                                label: "Updated",
                                data: data.updated,
                                borderWidth: 2,
                                tension: 0.35,
                            },
                            {
                                label: "Failed",
                                data: data.failed,
                                borderWidth: 2,
                                tension: 0.35,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
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
});