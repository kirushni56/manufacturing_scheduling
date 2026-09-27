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

const insightsList = document.getElementById("insightsList");

fetch("../scheduler_predictions.json")
  .then(res => res.json())
  .then(data => {
    const allOps = [];
    for (const jobId in data) {
      data[jobId].forEach(op => {
        allOps.push({
          job: jobId,
          operation: op.operation_id,
          machine: op.machine_id,
          risk: op.machine_risk
        });
      });
    }

    const highRisk = allOps
      .filter(op => op.risk > 0.7)
      .sort((a, b) => b.risk - a.risk)
      .slice(0, 6);

    insightsList.innerHTML = "";

    if (highRisk.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No high-risk operations detected.";
      insightsList.appendChild(li);
      return;
    }

    highRisk.forEach(op => {
      const li = document.createElement("li");
      li.textContent = `⚠️ Job ${op.job} (${op.operation}) has elevated failure risk (${(op.risk * 100).toFixed(0)}%) on ${op.machine}.`;
      insightsList.appendChild(li);
    });
  })
  .catch(err => console.error("Failed to load scheduler_predictions.json:", err));
  
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
let scheduleData = [];
let timelineStart = 8;
let timelineEnd = 14;

function renderGantt() {
    const header = document.getElementById("ganttHeader");
  header.innerHTML = "";
  header.style.minWidth = ((timelineEnd - timelineStart) * 30) + "px";
  const step = Math.max(1, Math.round((timelineEnd - timelineStart) / 20));
  for (let h = Math.floor(timelineStart); h <= Math.ceil(timelineEnd); h += step) {
    const span = document.createElement("span");
    span.textContent = h + "h";
    span.style.flex = "none";
    span.style.width = (step * 30) + "px";
    header.appendChild(span);
  }

  const machines = [...new Set(scheduleData.map(d => d.machine))];
  const rowsContainer = document.getElementById("ganttRows");
  rowsContainer.innerHTML = "";

  machines.forEach(machine => {
    const row = document.createElement("div");
    row.className = "gantt-row";

    const label = document.createElement("div");
    label.className = "gantt-label";
    label.textContent = machine;
    row.appendChild(label);

    const track = document.createElement("div");
    track.className = "gantt-track";
    track.style.minWidth = ((timelineEnd - timelineStart) * 30) + "px";

    scheduleData
      .filter(d => d.machine === machine)
      .forEach(d => {
        const bar = document.createElement("div");
        bar.className = "gantt-bar";
        const totalSpan = timelineEnd - timelineStart;
        const leftPct = ((d.start - timelineStart) / totalSpan) * 100;
        const widthPct = ((d.end - d.start) / totalSpan) * 100;
        bar.style.left = leftPct + "%";
        bar.style.width = widthPct + "%";
        bar.style.background = d.color;
        bar.textContent = d.job;
        track.appendChild(bar);
      });

    row.appendChild(track);
    rowsContainer.appendChild(row);
  });
}

const palette = ["#4da3ff", "#ff9f4d", "#4dff88", "#ff4d4d", "#c74dff", "#ffe14d", "#4de9ff", "#ff7eb6"];
const jobColors = {};
let colorIndex = 0;

fetch("../ga_schedule.json")
  .then(res => res.json())
  .then(data => {
    scheduleData = data.map(op => {
      if (!jobColors[op.job_id]) {
        jobColors[op.job_id] = palette[colorIndex % palette.length];
        colorIndex++;
      }
      return {
        machine: op.machine_id,
        job: op.job_id,
        start: op.start_h,
        end: op.end_h,
        color: jobColors[op.job_id]
      };
    });

    timelineStart = Math.floor(Math.min(...scheduleData.map(d => d.start)));
    timelineEnd = Math.ceil(Math.max(...scheduleData.map(d => d.end)));

    renderGantt();
  })
  .catch(err => console.error("Failed to load ga_schedule.json:", err));

function renderGanttInto(data, headerId, rowsId) {
  const header = document.getElementById(headerId);
  const rowsContainer = document.getElementById(rowsId);
  header.innerHTML = "";
  rowsContainer.innerHTML = "";

  for (let h = timelineStart; h <= timelineEnd; h++) {
    const span = document.createElement("span");
    span.textContent = h + ":00";
    header.appendChild(span);
  }

  const machines = [...new Set(data.map(d => d.machine))];

  machines.forEach(machine => {
    const row = document.createElement("div");
    row.className = "gantt-row";

    const label = document.createElement("div");
    label.className = "gantt-label";
    label.textContent = machine;
    row.appendChild(label);

    const track = document.createElement("div");
    track.className = "gantt-track";

    data
      .filter(d => d.machine === machine)
      .forEach(d => {
        const bar = document.createElement("div");
        bar.className = "gantt-bar";
        const totalSpan = timelineEnd - timelineStart;
        const leftPct = ((d.start - timelineStart) / totalSpan) * 100;
        const widthPct = ((d.end - d.start) / totalSpan) * 100;
        bar.style.left = leftPct + "%";
        bar.style.width = widthPct + "%";
        bar.style.background = d.color;
        bar.textContent = d.job;
        track.appendChild(bar);
      });

    row.appendChild(track);
    rowsContainer.appendChild(row);
  });
}

const simulateBtn = document.getElementById("simulateBreakdownBtn");
const reasonText = document.getElementById("rescheduleReason");

simulateBtn.addEventListener("click", function() {
  // "Before" is the original schedule
  renderGanttInto(scheduleData, "beforeGanttHeader", "beforeGanttRows");

  // "After" simulates M2 breaking down — its jobs move to M1 and M3
  const afterSchedule = scheduleData
    .filter(d => d.machine !== "M2")
    .concat([
      { machine: "M1", job: "J2", start: 14, end: 17, color: "#ff4d4d" },
      { machine: "M3", job: "J4", start: 14, end: 16, color: "#c74dff" }
    ]);

  renderGanttInto(afterSchedule, "afterGanttHeader", "afterGanttRows");

  reasonText.textContent = "⚠️ M2 breakdown detected — J2 and J4 rerouted to M1 and M3.";
});