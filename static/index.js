// ----- Pipeline list (refreshes itself every 2 seconds) -----

async function loadPipelines() {
  const tbody = document.getElementById("pipeline-rows");
  try {
    const { pipelines } = await api("/api/pipelines/");

    // Stat tiles
    const latest = pipelines.map((p) => p.latest_run && p.latest_run.status);
    document.getElementById("stat-total").textContent = pipelines.length;
    document.getElementById("stat-running").textContent = latest.filter((s) => s === "running" || s === "queued").length;
    document.getElementById("stat-success").textContent = latest.filter((s) => s === "success").length;
    document.getElementById("stat-failed").textContent = latest.filter((s) => s === "failed").length;

    if (pipelines.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-body-secondary py-4">No pipelines yet. Create one below 👇</td></tr>`;
      return;
    }
    tbody.innerHTML = pipelines.map((p) => {
      const latestRun = p.latest_run
        ? `<a href="/runs/${p.latest_run.id}/" class="text-decoration-none">${badge(p.latest_run.status)}</a>`
        : `<span class="text-body-secondary small">Never run</span>`;
      // oldest -> newest, left to right
      const dots = p.recent_runs.slice().reverse()
        .map((r) => `<a href="/runs/${r.id}/" class="badge rounded-pill text-bg-${STATUS_COLOR[r.status]} text-decoration-none" title="${r.status}">#${r.id}</a>`)
        .join("");
      return `
        <tr>
          <td class="ps-3 fw-semibold">${escapeHtml(p.name)}</td>
          <td><span class="badge text-bg-light border">${p.task_count}</span></td>
          <td>${latestRun}</td>
          <td><div class="d-flex gap-1">${dots || '<span class="text-body-secondary">—</span>'}</div></td>
          <td class="text-end pe-3"><button class="btn btn-sm btn-primary" onclick="runPipeline(${p.id}, this)">▶ Run</button></td>
        </tr>`;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function runPipeline(id, button) {
  button.disabled = true;
  try {
    const run = await api(`/api/pipelines/${id}/run/`, { method: "POST" });
    window.location.href = `/runs/${run.id}/`;
  } catch (err) {
    alert(err.message);
    button.disabled = false;
  }
}

// ----- Create pipeline form -----

function addTaskRow(task = {}) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input class="form-control t-name" value="${escapeHtml(task.name || "")}" placeholder="build"></td>
    <td><input class="form-control t-duration" type="number" min="0" step="0.5" value="${task.duration ?? 2}"></td>
    <td><input class="form-control t-fail" type="number" min="0" max="100" value="${task.fail ?? 0}"></td>
    <td><input class="form-control t-deps" value="${escapeHtml(task.deps || "")}" placeholder="e.g. build, lint"></td>
    <td><button type="button" class="btn btn-outline-secondary btn-sm" title="Remove">✕</button></td>`;
  tr.querySelector("button").onclick = () => tr.remove();
  document.getElementById("task-rows").appendChild(tr);
}

function loadExample() {
  document.getElementById("pipeline-name").value = "Example: build & deploy";
  document.getElementById("task-rows").innerHTML = "";
  addTaskRow({ name: "checkout", duration: 1 });
  addTaskRow({ name: "lint", duration: 2, deps: "checkout" });
  addTaskRow({ name: "unit-tests", duration: 3, fail: 20, deps: "checkout" });
  addTaskRow({ name: "build", duration: 2, deps: "checkout" });
  addTaskRow({ name: "deploy", duration: 2, deps: "lint, unit-tests, build" });
}

// "validate" always fails (100%). Everything after it gets skipped,
// while the independent "backup" branch still finishes.
function loadFailExample() {
  document.getElementById("pipeline-name").value = "Failure demo: data report";
  document.getElementById("task-rows").innerHTML = "";
  addTaskRow({ name: "fetch-data", duration: 2 });
  addTaskRow({ name: "validate", duration: 2, fail: 100, deps: "fetch-data" });
  addTaskRow({ name: "transform", duration: 2, deps: "validate" });
  addTaskRow({ name: "send-report", duration: 1, deps: "transform" });
  addTaskRow({ name: "backup", duration: 3, deps: "fetch-data" });
  addTaskRow({ name: "notify-backup-done", duration: 1, deps: "backup" });
}

async function submitPipeline(event) {
  event.preventDefault();
  const message = document.getElementById("form-message");
  const tasks = [...document.querySelectorAll("#task-rows tr")].map((row) => ({
    name: row.querySelector(".t-name").value.trim(),
    duration: Number(row.querySelector(".t-duration").value),
    fail_rate: Number(row.querySelector(".t-fail").value) / 100,
    depends_on: row.querySelector(".t-deps").value.split(",").map((s) => s.trim()).filter(Boolean),
  }));

  try {
    await api("/api/pipelines/", {
      method: "POST",
      body: JSON.stringify({ name: document.getElementById("pipeline-name").value, tasks }),
    });
    message.className = "alert alert-success py-2 mt-3 mb-0";
    message.textContent = "✓ Pipeline created. Click ▶ Run in the list above.";
    event.target.reset();
    document.getElementById("task-rows").innerHTML = "";
    addTaskRow();
    loadPipelines();
  } catch (err) {
    message.className = "alert alert-danger py-2 mt-3 mb-0";
    message.textContent = err.message;
  }
}

document.getElementById("add-task").onclick = () => addTaskRow();
document.getElementById("load-example").onclick = loadExample;
document.getElementById("load-fail-example").onclick = loadFailExample;
document.getElementById("pipeline-form").onsubmit = submitPipeline;

addTaskRow();
loadPipelines();
setInterval(loadPipelines, 2000);
