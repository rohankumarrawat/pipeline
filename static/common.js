// Small helpers shared by both pages.

// Bootstrap colour for each status.
const STATUS_COLOR = {
  queued: "secondary",
  pending: "secondary",
  running: "primary",
  success: "success",
  failed: "danger",
  skipped: "warning",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function badge(status, size = "") {
  const color = STATUS_COLOR[status] || "secondary";
  const spinner = status === "running"
    ? `<span class="spinner-grow spinner-grow-sm me-1" style="width:.6rem;height:.6rem"></span>`
    : "";
  return `<span class="badge rounded-pill text-bg-${color} text-capitalize ${size}">${spinner}${status}</span>`;
}

function formatTime(iso) {
  return iso ? new Date(iso).toLocaleTimeString() : "—";
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}
