// Run detail page. Polls every second until the run is finished.

const runId = document.body.dataset.runId;
const STATUSES = ["success", "failed", "skipped", "running", "pending"];
let timer = null;

// A Bootstrap progress bar showing when the task ran, relative to the whole run:
// an empty segment (time before it started) followed by a coloured segment.
function timelineBar(task, runStart, runEnd) {
  if (!task.started_at || !runStart) return `<div class="progress" style="height:10px"></div>`;
  const total = Math.max(runEnd - runStart, 1);
  const start = new Date(task.started_at) - runStart;
  const end = (task.finished_at ? new Date(task.finished_at) : new Date()) - runStart;
  const before = (start / total) * 100;
  const width = Math.max(((end - start) / total) * 100, 1.5);
  const animated = task.status === "running" ? "progress-bar-striped progress-bar-animated" : "";
  return `
    <div class="progress-stacked" style="height:10px">
      <div class="progress" style="width:${before}%"><div class="progress-bar bg-transparent"></div></div>
      <div class="progress" style="width:${width}%">
        <div class="progress-bar bg-${STATUS_COLOR[task.status]} ${animated}"></div>
      </div>
    </div>`;
}

async function loadRun() {
  try {
    const run = await api(`/api/runs/${runId}/`);
    const finished = run.status === "success" || run.status === "failed";

    document.title = `${run.pipeline.name} · Run #${run.id}`;
    document.getElementById("run-title").textContent = `${run.pipeline.name} — Run #${run.id}`;
    document.getElementById("run-status").innerHTML = badge(run.status, "fs-6");

    let info = `Queued ${formatTime(run.created_at)}`;
    if (run.started_at) info += ` · Started ${formatTime(run.started_at)}`;
    if (run.finished_at) {
      const secs = (new Date(run.finished_at) - new Date(run.started_at)) / 1000;
      info += ` · Finished ${formatTime(run.finished_at)} · Took ${secs.toFixed(1)}s`;
    }
    document.getElementById("run-info").textContent = info;

    // Overall progress bar + counts
    const counts = Object.fromEntries(STATUSES.map((s) => [s, 0]));
    run.tasks.forEach((t) => counts[t.status]++);
    const total = run.tasks.length || 1;
    document.getElementById("progress").innerHTML = ["success", "failed", "skipped", "running"]
      .map((s) => `
        <div class="progress" style="width:${(counts[s] / total) * 100}%">
          <div class="progress-bar bg-${STATUS_COLOR[s]} ${s === "running" ? "progress-bar-striped progress-bar-animated" : ""}"></div>
        </div>`).join("");
    document.getElementById("legend").innerHTML = STATUSES
      .map((s) => `<span class="text-body-secondary"><span class="fw-bold text-${STATUS_COLOR[s]}">${counts[s]}</span> ${s}</span>`)
      .join("");

    const failedTask = run.tasks.find((t) => t.status === "failed");
    let alertText = run.error;
    if (!alertText && failedTask) alertText = `Task "${failedTask.name}" failed: ${failedTask.error}`;
    document.getElementById("run-error").innerHTML =
      finished && alertText ? `<div class="alert alert-danger mt-3 mb-0 py-2">${escapeHtml(alertText)}</div>` : "";

    // Task table
    const runStart = run.started_at ? new Date(run.started_at) : null;
    const runEnd = run.finished_at ? new Date(run.finished_at) : new Date();
    document.getElementById("task-rows").innerHTML = run.tasks.map((t) => `
      <tr>
        <td class="ps-3 fw-semibold">${escapeHtml(t.name)}</td>
        <td>${badge(t.status)}</td>
        <td class="text-body-secondary">${escapeHtml(t.depends_on.join(", ")) || "—"}</td>
        <td>${formatTime(t.started_at)}</td>
        <td>${t.duration != null ? t.duration + "s" : "—"}</td>
        <td>${timelineBar(t, runStart, runEnd)}</td>
        <td class="text-danger small">${escapeHtml(t.error)}</td>
      </tr>`).join("");

    if (finished) {
      clearInterval(timer); // nothing more will change
      document.getElementById("live-note").textContent = "Finished";
    }
  } catch (err) {
    document.getElementById("run-info").textContent = err.message;
  }
}

loadRun();
timer = setInterval(loadRun, 1000);
