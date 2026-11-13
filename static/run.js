// Run detail page. Polls every second until the run is finished.

const runId = document.body.dataset.runId;
let timer = null;

async function loadRun() {
  try {
    const run = await api(`/api/runs/${runId}/`);

    document.getElementById("run-title").innerHTML =
      `${escapeHtml(run.pipeline.name)} — Run #${run.id} ${badge(run.status)}`;

    let info = `Queued ${formatTime(run.created_at)}`;
    if (run.started_at) info += ` · Started ${formatTime(run.started_at)}`;
    if (run.finished_at) {
      const secs = (new Date(run.finished_at) - new Date(run.started_at)) / 1000;
      info += ` · Finished ${formatTime(run.finished_at)} (${secs.toFixed(1)}s)`;
    }
    document.getElementById("run-info").textContent = info;
    document.getElementById("run-error").textContent = run.error || "";

    document.getElementById("task-rows").innerHTML = run.tasks.map((t) => `
      <tr>
        <td>${escapeHtml(t.name)}</td>
        <td>${badge(t.status)}</td>
        <td>${escapeHtml(t.depends_on.join(", ")) || "—"}</td>
        <td>${formatTime(t.started_at)}</td>
        <td>${formatTime(t.finished_at)}</td>
        <td>${t.duration != null ? t.duration + "s" : "—"}</td>
        <td class="error">${escapeHtml(t.error)}</td>
      </tr>`).join("");

    if (run.status === "success" || run.status === "failed") {
      clearInterval(timer); // nothing more will change
    }
  } catch (err) {
    document.getElementById("run-info").textContent = err.message;
  }
}

loadRun();
timer = setInterval(loadRun, 1000);
