document.addEventListener("DOMContentLoaded", () => {

    document.querySelectorAll(".pipeline-column").forEach(column => {

        new Sortable(column, {

            group: "quotes",

            animation: 200,

            ghostClass: "pipeline-ghost",

            onEnd: async function (evt) {

                const card = evt.item;

                const quoteId = card.dataset.id;

                const newStatus = evt.to.dataset.status;

                try {

                    const response = await fetch(
                        `/dashboard/api/quotes/${quoteId}/update_status/`,
                        {
                            method: "PATCH",
                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken")
                            },
                            body: JSON.stringify({
                                status: newStatus
                            })
                        }
                    );

                    if (!response.ok) {
                        alert("Unable to update quote.");
                        location.reload();
                        return;
                    }

                    card.dataset.status = newStatus;
                        showToast("Quote moved successfully.");
                        updatePipelineCount(evt.from);
                        updatePipelineCount(evt.to);
                        if (typeof refreshDashboardStats === "function") {
                            refreshDashboardStats();
                    }
                if (typeof refreshDashboardCharts === "function") {
                    refreshDashboardCharts();
                    }

                } catch (err) {

                    console.error(err);

                    alert("Server connection failed.");

                    location.reload();

                }

            }

        });

    });

});


function getCookie(name) {

    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {

        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {

            cookie = cookie.trim();

            if (cookie.startsWith(name + "=")) {

                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );

                break;

            }

        }

    }

    return cookieValue;

}

function updatePipelineCount(column) {
    const countBadge = column.querySelector(".pipeline-title span");
    const cards = column.querySelectorAll(".pipeline-card");

    if (countBadge) {
        countBadge.textContent = cards.length;
    }
}

function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "dashboard-toast";
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("show");
    }, 50);

    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}