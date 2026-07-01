document.addEventListener("DOMContentLoaded", function () {
    let draggedCard = null;

    document.querySelectorAll(".pipeline-card").forEach(function (card) {
        card.addEventListener("dragstart", function () {
            draggedCard = card;
            card.classList.add("dragging");
        });

        card.addEventListener("dragend", function () {
            card.classList.remove("dragging");
            draggedCard = null;
        });
    });

    document.querySelectorAll(".pipeline-column").forEach(function (column) {
        column.addEventListener("dragover", function (event) {
            event.preventDefault();
            column.classList.add("drop-ready");
        });

        column.addEventListener("dragleave", function () {
            column.classList.remove("drop-ready");
        });

        column.addEventListener("drop", async function () {
            column.classList.remove("drop-ready");

            if (!draggedCard) return;

            const quoteId = draggedCard.dataset.id;
            const newStatus = column.dataset.status;

            column.appendChild(draggedCard);
            draggedCard.dataset.status = newStatus;

            try {
                const response = await fetch(`/dashboard/api/quotes/${quoteId}/`, {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken")
                    },
                    body: JSON.stringify({
                        status: newStatus
                    })
                });

                if (!response.ok) {
                    throw new Error("Status update failed");
                }
            } catch (error) {
                alert("Could not update quote status. Please refresh and try again.");
                console.error(error);
            }
        });
    });

    function getCookie(name) {
        let cookieValue = null;

        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");

            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();

                if (cookie.substring(0, name.length + 1) === name + "=") {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }

        return cookieValue;
    }
});