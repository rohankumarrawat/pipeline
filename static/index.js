// ----- Pipeline list (refreshes itself every 2 seconds) -----

async function loadPipelines() {
  const tbody = document.getElementById("pipeline-rows");
  try {
    const { pipelines } = await api("/api/pipelines/");
    if (pipelines.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">No pipelines yet. Create one below.</td></tr>`;
      return;
    }
    tbody.innerHTML = pipelines.map((p) => {
      const latest = p.latest_run
        ? `<a href="/runs/${p.latest_run.id}/">${badge(p.latest_run.status)}</a>`
        : `<span class="muted">never run</span>`;
      const recent = p.recent_runs
        .map((r) => `<a href="/runs/${r.id}/" title="Run #${r.id}">#${r.id}</a>`)
        .join(" ");
      return `
        <tr>
          <td>${escapeHtml(p.name)}</td>
          <td>${p.task_count}</td>
          <td>${latest}</td>
          <td>${recent || "—"}</td>
          <td><button class="primary" onclick="runPipeline(${p.id}, this)">Run</button></td>
        </tr>`;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="error">${escapeHtml(err.message)}</td></tr>`;
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
    <td><input class="t-name" value="${escapeHtml(task.name || "")}" placeholder="build"></td>
    <td><input class="t-duration" type="number" min="0" step="0.5" value="${task.duration ?? 2}"></td>
    <td><input class="t-fail" type="number" min="0" max="100" value="${task.fail ?? 0}"></td>
    <td><input class="t-deps" value="${escapeHtml(task.deps || "")}" placeholder="e.g. build, lint"></td>
    <td><button type="button" title="Remove">✕</button></td>`;
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
    message.className = "ok";
    message.textContent = "Pipeline created.";
    event.target.reset();
    document.getElementById("task-rows").innerHTML = "";
    addTaskRow();
    loadPipelines();
  } catch (err) {
    message.className = "error";
    message.textContent = err.message;
  }
}

document.getElementById("add-task").onclick = () => addTaskRow();
document.getElementById("load-example").onclick = loadExample;
document.getElementById("pipeline-form").onsubmit = submitPipeline;

addTaskRow();
loadPipelines();
setInterval(loadPipelines, 2000);
