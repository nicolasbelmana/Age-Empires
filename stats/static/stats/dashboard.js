document.addEventListener("DOMContentLoaded", () => {
  const syncForm = document.getElementById("sync-form");
  syncForm.addEventListener("submit", () => {
    const button = syncForm.querySelector("button");
    button.disabled = true;
    button.textContent = "Actualizando...";
  });

  const leaderboardTable = document.getElementById("leaderboard-table");
  if (leaderboardTable) {
    const body = leaderboardTable.tBodies[0];
    const headers = Array.from(leaderboardTable.tHead.rows[0].cells);
    const textCollator = new Intl.Collator("es", {
      numeric: true,
      sensitivity: "base",
    });

    headers.forEach((header, columnIndex) => {
      const button = header.querySelector(".sort-button");
      button.addEventListener("click", () => {
        const ascending = header.getAttribute("aria-sort") !== "ascending";
        headers.forEach((item) => item.setAttribute("aria-sort", "none"));
        header.setAttribute("aria-sort", ascending ? "ascending" : "descending");

        const rows = Array.from(body.rows);
        rows.sort((left, right) => {
          const leftValue = left.cells[columnIndex].dataset.sortValue || "";
          const rightValue = right.cells[columnIndex].dataset.sortValue || "";
          if (!leftValue && rightValue) return 1;
          if (leftValue && !rightValue) return -1;

          let comparison;
          if (button.dataset.sortType === "number") {
            comparison = Number(leftValue) - Number(rightValue);
          } else {
            comparison = textCollator.compare(leftValue, rightValue);
          }
          return ascending ? comparison : -comparison;
        });
        body.append(...rows);
      });
    });
  }

  const stats = JSON.parse(document.getElementById("stats-data").textContent);
  const colors = [
    "#e2a34a", "#62a7dc", "#d96c55", "#70b88a", "#ad86d6",
    "#e2cc68", "#54b8b0", "#db83a8", "#96a8ba", "#c7a48c",
  ];
  const pickCanvas = document.getElementById("pick-chart");
  const pickEmpty = document.getElementById("pick-empty");

  if (stats.civilizations.length) {
    new Chart(pickCanvas, {
      type: "doughnut",
      data: {
        labels: stats.civilizations.map((item) => item.name),
        datasets: [{
          data: stats.civilizations.map((item) => item.pick_rate),
          backgroundColor: stats.civilizations.map((_, index) => colors[index % colors.length]),
          borderColor: "#18222e",
          borderWidth: 3,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { color: "#c3cfdb", padding: 14 } } },
      },
    });
  } else {
    pickCanvas.hidden = true;
    pickEmpty.hidden = false;
  }

  const winrateCanvas = document.getElementById("winrate-chart");
  const winrateEmpty = document.getElementById("winrate-empty");
  if (stats.winrates.length) {
    new Chart(winrateCanvas, {
      type: "bar",
      data: {
        labels: stats.winrates.map((item) => item.name),
        datasets: [{
          label: "Winrate (%)",
          data: stats.winrates.map((item) => item.win_rate),
          backgroundColor: "#62a7dc",
          borderRadius: 6,
          maxBarThickness: 42,
        }],
      },
      options: {
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#c3cfdb" }, grid: { display: false } },
          y: { beginAtZero: true, max: 100, ticks: { color: "#9aa8b8", callback: (value) => `${value}%` }, grid: { color: "#293747" } },
        },
        plugins: { legend: { display: false } },
      },
    });
  } else {
    winrateCanvas.hidden = true;
    winrateEmpty.hidden = false;
  }
});
