document.addEventListener("DOMContentLoaded", function () {
    const trendCanvas = document.getElementById("trendChart");
    const leadSourceCanvas = document.getElementById("leadSourceChart");

    if (!trendCanvas || !leadSourceCanvas) return;

    const quoteLabels = JSON.parse(document.getElementById("quote-labels").textContent);
    const quoteValues = JSON.parse(document.getElementById("quote-values").textContent);
    const contactLabels = JSON.parse(document.getElementById("contact-labels").textContent);
    const contactValues = JSON.parse(document.getElementById("contact-values").textContent);
    const leadSourceLabels = JSON.parse(document.getElementById("lead-source-labels").textContent);
    const leadSourceValues = JSON.parse(document.getElementById("lead-source-values").textContent);

    new Chart(trendCanvas, {
        type: "line",
        data: {
            labels: quoteLabels,
            datasets: [
                {
                    label: "Quotes",
                    data: quoteValues,
                    borderWidth: 3,
                    tension: 0.38,
                    fill: true
                },
                {
                    label: "Contacts",
                    data: contactValues,
                    borderWidth: 3,
                    tension: 0.38,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1300,
                easing: "easeOutQuart"
            },
            plugins: {
                legend: {
                    position: "bottom"
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });

    new Chart(leadSourceCanvas, {
        type: "doughnut",
        data: {
            labels: leadSourceLabels,
            datasets: [
                {
                    data: leadSourceValues
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                animateScale: true,
                duration: 1200
            },
            plugins: {
                legend: {
                    position: "bottom"
                }
            }
        }
    });
});