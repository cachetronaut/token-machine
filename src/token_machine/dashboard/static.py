"""Generated dashboard assets."""

CSS = """
:root {
  color-scheme: dark;
  --bg: #101114;
  --panel: #181b20;
  --line: #2d333b;
  --text: #f6f7f9;
  --muted: #9aa3ad;
  --accent: #45c7b7;
  --amber: #f4c85c;
  --coral: #ff806f;
  --blue: #77aaff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}
main { max-width: 1180px; margin: 0 auto; padding: 28px 20px 40px; }
header { display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 20px; }
h1 { margin: 0; font-size: 26px; }
h2 { margin: 0 0 10px; font-size: 15px; }
.sub, .status, .label, .empty { color: var(--muted); font-size: 13px; }
.grid { display: grid; gap: 12px; }
.metrics { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-bottom: 12px; }
.columns { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-bottom: 12px; }
.card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 14px;
  min-width: 0;
}
.value { margin-top: 7px; font-size: 25px; font-weight: 760; }
.bar { display: grid; grid-template-columns: minmax(0, 1fr) 70px; gap: 10px; align-items: center; margin: 9px 0; }
.bar-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { height: 8px; border-radius: 999px; overflow: hidden; background: #252b33; }
.bar-fill { height: 100%; background: var(--accent); }
.timeline { display: grid; gap: 8px; }
.session { display: grid; grid-template-columns: 130px minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.session strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pill { color: var(--muted); font-size: 12px; }
@media (max-width: 800px) {
  header, .session { grid-template-columns: 1fr; display: grid; align-items: start; }
  .columns { grid-template-columns: 1fr; }
}
"""

JS = """
const fmt = new Intl.NumberFormat();
const pollMs = 5000;

function compact(value) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`;
  if (Math.abs(number) >= 10_000) return `${(number / 1_000).toFixed(1)}K`;
  return fmt.format(number);
}

function text(id, value) {
  document.getElementById(id).textContent = value;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
}

function entries(values, limit = 8) {
  return Object.entries(values || {}).sort((a, b) => b[1] - a[1]).slice(0, limit);
}

function renderMetric(id, value) {
  const element = document.getElementById(id);
  element.textContent = compact(value);
  element.title = fmt.format(value || 0);
}

function renderBars(id, values) {
  const root = document.getElementById(id);
  const rows = entries(values);
  if (!rows.length) {
    root.innerHTML = '<div class="empty">No data yet</div>';
    return;
  }
  const max = Math.max(...rows.map(([, count]) => count), 1);
  root.innerHTML = rows.map(([name, count]) => `
    <div class="bar" title="${escapeHtml(name)}">
      <div>
        <div class="bar-name">${escapeHtml(name)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, count / max * 100)}%"></div></div>
      </div>
      <div>${fmt.format(count)}</div>
    </div>
  `).join("");
}

function shortProject(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "unknown project";
}

function renderSessions(rows) {
  const root = document.getElementById("sessions-list");
  if (!rows.length) {
    root.innerHTML = '<div class="empty">No sessions yet</div>';
    return;
  }
  root.innerHTML = rows.map((row) => {
    const rollup = row.rollup;
    const ended = (rollup.ended_at || rollup.started_at || "").slice(0, 16).replace("T", " ");
    return `
      <div class="card session">
        <span class="pill">${escapeHtml(ended || "no timestamp")}</span>
        <strong>${escapeHtml(shortProject(rollup.project_path))}</strong>
        <span class="pill">${escapeHtml(rollup.source)} · ${fmt.format(rollup.tokens.total_tokens || 0)} tokens</span>
      </div>
    `;
  }).join("");
}

async function refresh() {
  try {
    const response = await fetch("/api/summary", { cache: "no-store" });
    const data = await response.json();
    const summary = data.summary;
    renderMetric("metric-sessions", summary.sessions);
    renderMetric("metric-events", summary.event_count);
    renderMetric("metric-model-calls", summary.event_types.model_call || 0);
    renderMetric("metric-tokens", summary.tokens.total_tokens || 0);
    renderBars("models", summary.models);
    renderBars("tools", summary.tools);
    renderBars("clis", summary.clis);
    renderSessions(data.recent_sessions);
    text("status", `Live · ${new Date(data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
  } catch (error) {
    text("status", "Disconnected");
  }
}

refresh();
setInterval(refresh, pollMs);
"""
