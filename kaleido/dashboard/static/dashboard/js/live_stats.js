async function refreshDashboardStats() {
    const response = await fetch("/dashboard/api/stats/");
    if (!response.ok) return;

    const data = await response.json();

    document.querySelectorAll("[data-stat]").forEach((el) => {
        const key = el.dataset.stat;

        if (data[key] !== undefined) {
            if (key === "estimated_revenue") {
                el.textContent = "$" + Number(data[key]).toLocaleString();
            } else {
                el.textContent = data[key];
            }
        }
    });
}

document.addEventListener("DOMContentLoaded", refreshDashboardStats);