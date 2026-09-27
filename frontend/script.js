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
let jobs = [];

const jobForm = document.getElementById("jobForm");
const jobTableBody = document.getElementById("jobTableBody");

jobForm.addEventListener("submit", function(e) {
  e.preventDefault();

  const newJob = {
    jobId: document.getElementById("jobId").value,
    product: document.getElementById("product").value,
    quantity: document.getElementById("quantity").value,
    priority: document.getElementById("priority").value,
    deadline: document.getElementById("deadline").value,
    operation: document.getElementById("operation").value
  };

  jobs.push(newJob);
  renderJobs();
  jobForm.reset();
});

function renderJobs() {
  jobTableBody.innerHTML = "";
  jobs.forEach((job, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${job.jobId}</td>
      <td>${job.product}</td>
      <td>${job.quantity}</td>
      <td>${job.priority}</td>
      <td>${job.deadline}</td>
      <td>${job.operation}</td>
      <td><button onclick="deleteJob(${index})">Delete</button></td>
    `;
    jobTableBody.appendChild(row);
  });
}

function deleteJob(index) {
  jobs.splice(index, 1);
  renderJobs();
}
const scheduleData = [ { machine: "M1", job: "J1", start: 8, end: 10, color: "#4da3ff" }, { machine: "M1", job: "J3", start: 10, end: 12, color: "#ff9f4d" }, { machine: "M1", job: "J5", start: 12, end: 14, color: "#4dff88" }, { machine: "M2", job: "J2", start: 8, end: 11, color: "#ff4d4d" }, { machine: "M2", job: "J4", start: 11, end: 13, color: "#c74dff" }, { machine: "M3", job: "J6", start: 8, end: 14, color: "#ffe14d" } ]; const timelineStart = 8; const timelineEnd = 14; function renderGantt() { const header = document.getElementById("ganttHeader"); for (let h = timelineStart; h <= timelineEnd; h++) { const span = document.createElement("span"); span.textContent = h + ":00"; header.appendChild(span); } const machines = [...new Set(scheduleData.map(d => d.machine))]; const rowsContainer = document.getElementById("ganttRows"); machines.forEach(machine => { const row = document.createElement("div"); row.className = "gantt-row"; const label = document.createElement("div"); label.className = "gantt-label"; label.textContent = machine; row.appendChild(label); const track = document.createElement("div"); track.className = "gantt-track"; scheduleData .filter(d => d.machine === machine) .forEach(d => { const bar = document.createElement("div"); bar.className = "gantt-bar"; const totalSpan = timelineEnd - timelineStart; const leftPct = ((d.start - timelineStart) / totalSpan) * 100; const widthPct = ((d.end - d.start) / totalSpan) * 100; bar.style.left = leftPct + "%"; bar.style.width = widthPct + "%"; bar.style.background = d.color; bar.textContent = d.job; track.appendChild(bar); }); row.appendChild(track); rowsContainer.appendChild(row); }); } renderGantt();
