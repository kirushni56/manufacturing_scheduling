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

function renderGanttInto(data, headerId, rowsId, rangeStart, rangeEnd) {
  const header = document.getElementById(headerId);
  const rowsContainer = document.getElementById(rowsId);
  header.innerHTML = "";
  rowsContainer.innerHTML = "";

  const start = rangeStart !== undefined ? rangeStart : timelineStart;
  const end = rangeEnd !== undefined ? rangeEnd : timelineEnd;
  header.style.minWidth = ((end - start) * 30) + "px";

  header.style.minWidth = "0";
  header.style.position = "relative";
  header.style.height = "18px";
  const step = Math.max(5, Math.round((end - start) / 50) * 5);
  for (let h = Math.ceil(start / step) * step; h <= end; h += step) {
    const span = document.createElement("span");
    span.textContent = h + "h";
    span.style.position = "absolute";
    span.style.left = (((h - start) / (end - start)) * 100) + "%";
    span.style.width = "auto";
    span.style.flex = "none";
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
          const totalSpan = end - start;
          const leftPct = ((d.start - start) / totalSpan) * 100;
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

function isoToHours(iso, t0) {
  return (new Date(iso) - t0) / (1000 * 60 * 60);
}

function convertApiSchedule(apiData) {
  if (apiData.length === 0) return { data: [], start: 0, end: 1 };
  const t0 = new Date(Math.min(...apiData.map(d => new Date(d.start_time))));
  const jobColorsLocal = {};
  const paletteLocal = ["#4da3ff", "#ff9f4d", "#4dff88", "#ff4d4d", "#c74dff", "#ffe14d", "#4de9ff", "#ff7eb6"];
  let idx = 0;
  const converted = apiData.map(op => {
    if (!jobColorsLocal[op.job_id]) {
      jobColorsLocal[op.job_id] = paletteLocal[idx % paletteLocal.length];
      idx++;
    }
    return {
      machine: op.machine_id,
      job: op.job_id,
      start: isoToHours(op.start_time, t0),
      end: isoToHours(op.end_time, t0),
      color: jobColorsLocal[op.job_id]
    };
  });
  const start = Math.floor(Math.min(...converted.map(d => d.start)));
  const end = Math.ceil(Math.max(...converted.map(d => d.end)));
  return { data: converted, start, end };
}

simulateBtn.addEventListener("click", function() {
  reasonText.textContent = "Loading real rescheduled data...";

  // "Before" reuses the original schedule already loaded for the main Gantt chart
  renderGanttInto(scheduleData, "beforeGanttHeader", "beforeGanttRows", timelineStart, timelineEnd);

  fetch("http://127.0.0.1:8000/schedule")
    .then(res => res.json())
    .then(afterRaw => {
      const after = convertApiSchedule(afterRaw);
      renderGanttInto(after.data, "afterGanttHeader", "afterGanttRows", after.start, after.end);

      const m2Before = scheduleData.filter(d => d.machine === "M2").length;
      const m2After = after.data.filter(d => d.machine === "M2").length;

      reasonText.textContent = `⚠️ M2 breakdown: had ${m2Before} operations on M2 before, ${m2After} after real rescheduling.`;
    })
    .catch(err => {
      reasonText.textContent = "Could not load the live schedule — make sure the backend server (uvicorn) is running.";
      console.error(err);
    });
});

async function loadComparison() {
  const box = document.getElementById("comparison-table");
  try {
    const res = await fetch("../scheduler_comparison.json");
    const d = await res.json();

    const rows = [
      ["Makespan (h)", "makespan", false],
      ["Total tardiness (h)", "total_tardiness", false],
      ["Jobs late", "jobs_late", false],
      ["Idle time (h)", "idle_time", false],
      ["Utilization (%)", "utilization", true],
      ["Risk exposure", "risk_exposure", false],
      ["Total cost (fitness)", "fitness", false]
    ];
    const names = ["FCFS", "Priority", "GA"];

    let html = "<table class='cmp'><tr><th>Metric</th><th>FCFS</th><th>Priority</th><th>GA</th></tr>";
    rows.forEach(([label, key, higherBetter]) => {
      const vals = names.map(n => d[n][key]);
      const best = higherBetter ? Math.max(...vals) : Math.min(...vals);
      html += "<tr><td>" + label + "</td>";
      vals.forEach(v => {
        const shown = key === "utilization" ? (v * 100).toFixed(1) : v;
        html += "<td class='" + (v === best ? "best" : "") + "'>" + shown + "</td>";
      });
      html += "</tr>";
    });
    html += "</table>";
    box.innerHTML = html;
  } catch (err) {
    console.error("Comparison error:", err);
    box.textContent = "Could not load the comparison data.";
  }
}
loadComparison();

document.getElementById("totalJobs").textContent = overview.totalJobs;
document.getElementById("completedJobs").textContent = overview.completedJobs;
document.getElementById("inProgressJobs").textContent = overview.inProgressJobs;
document.getElementById("delayedJobs").textContent = overview.delayedJobs;

const machineList = document.getElementById("machineList");
const statusIcons = {
  Available: "🟢",
  Running: "🟢",
  Maintenance: "🟡",
  Breakdown: "🔴"
};
machineList.innerHTML = "";
machines.forEach(m => {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = "<span>" + m.id + "</span><p>" +
    (statusIcons[m.status] || "⚪") + " " + m.status + "</p>";
  machineList.appendChild(card);
});