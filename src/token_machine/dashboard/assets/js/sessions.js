import { appColor, hideTooltip, showTooltip } from "./charts.js";
import {
  compactNumber,
  escapeHtml,
  fmt,
  formatDuration,
  projectName,
  text,
  topEntries,
} from "./format.js";

export function renderSessions(sessions) {
  text("session-count", `${sessions.length} shown`);
  const root = document.getElementById("recent-sessions");
  if (!sessions.length) {
    root.innerHTML = '<div class="eyebrow">No sessions yet</div>';
    return;
  }
  root.innerHTML = sessions
    .map((session) => {
      const rollup = session.rollup || {};
      const project = projectName(rollup.project_path);
      const color = appColor(rollup.source);
      const ended = (rollup.ended_at || rollup.started_at || "").slice(0, 16);
      const models = topEntries(rollup.models, 2)
        .map(
          ([name, count]) =>
            `${escapeHtml(name)} <span class="model-count">${fmt.format(count)} calls</span>`,
        )
        .join(" - ");
      const tools = topEntries(rollup.tools, 2)
        .map(([name, count]) => `${escapeHtml(name)} ${fmt.format(count)}`)
        .join(" - ");
      const appLabel = appDisplayName(rollup.source);
      const duration = formatDuration(session.duration_seconds);
      const firstTool = formatDuration(session.time_to_first_tool_seconds);
      const role = session.workflow_role || "Session";
      return `
      <div class="timeline-item" style="--project-color:${color}">
        <div class="time-label">${escapeHtml(ended.replace("T", " "))}</div>
        <div class="timeline-card" data-tip="<strong>${escapeHtml(project)}</strong>${escapeHtml(role)} · ${escapeHtml(appLabel)}<br>${fmt.format(rollup.model_calls || 0)} model calls, ${fmt.format(rollup.tool_calls || 0)} tool calls<br>${fmt.format(rollup.cli_commands || 0)} CLI commands · ${duration} duration<br>First action: ${firstTool}<br>${fmt.format(rollup.tokens?.total_tokens || 0)} tokens">
          <div class="timeline-main"><div class="timeline-project">${escapeHtml(project)}</div><span class="app-pill icon-only" style="--app-color:${color}" title="${escapeHtml(appLabel)}">${renderAppIcon(rollup.source)}</span></div>
          <div class="timeline-stats">
            <span>${fmt.format(rollup.model_calls || 0)} model</span>
            <span>${fmt.format(rollup.tool_calls || 0)} tools</span>
            <span>${compactNumber(rollup.tokens?.total_tokens || 0)} tokens</span>
            <span>${escapeHtml(role)}</span>
          </div>
          <div class="model-line">${models || escapeHtml(tools || "No model details")}</div>
        </div>
      </div>
    `;
    })
    .join("");
  root.querySelectorAll(".timeline-card").forEach((card) => {
    card.addEventListener("mousemove", (event) =>
      showTooltip(event, card.dataset.tip || ""),
    );
    card.addEventListener("mouseleave", hideTooltip);
  });
}

function appDisplayName(source) {
  const value = String(source || "unknown").toLowerCase();
  if (value === "codex") return "Codex CLI";
  if (value === "claude") return "Claude Code";
  if (value === "gemini") return "Gemini CLI";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function sourceIconName(source) {
  const key = String(source || "").toLowerCase();
  if (key.includes("codex")) return "codex.svg";
  if (key.includes("claude")) return "claude.svg";
  if (key.includes("gemini")) return "gemini.svg";
  if (key.includes("openai")) return "openai.svg";
  return "";
}

function renderAppIcon(source) {
  const icon = sourceIconName(source);
  if (!icon) return '<span class="app-dot"></span>';
  return `<img class="app-icon" src="/assets/icons/${encodeURIComponent(icon)}" alt="" loading="lazy" decoding="async" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="app-dot" hidden></span>`;
}
