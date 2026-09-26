// Placeholder data — replace with real API calls once backend is ready
const overview = {
  totalJobs: 50,
  completedJobs: 32,
  inProgressJobs: 10,
  delayedJobs: 5
};

const machines = [
  { id: "M1", status: "Available" },
  { id: "M2", status: "Breakdown" },
  { id: "M3", status: "Maintenance" },
  { id: "M4", status: "Running" }
];

const insights = [
  "Job J12 has a high probability of missing its deadline.",
  "Machine M3 has elevated failure risk.",
  "Schedule automatically re-optimized after M2 breakdown."
];

// Fill in overview cards
document.getElementById("totalJobs").textContent = overview.totalJobs;
document.getElementById("completedJobs").textContent = overview.completedJobs;
document.getElementById("inProgressJobs").textContent = overview.inProgressJobs;
document.getElementById("delayedJobs").textContent = overview.delayedJobs;

// Fill in machine status cards
const machineList = document.getElementById("machineList");
machines.forEach(m => {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `<span>${m.id}</span><p>${m.status}</p>`;
  machineList.appendChild(card);
});

// Fill in AI insights
const insightsList = document.getElementById("insightsList");
insights.forEach(text => {
  const li = document.createElement("li");
  li.textContent = text;
  insightsList.appendChild(li);
});