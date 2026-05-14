import { appColor, hideTooltip, showTooltip } from "./charts.js";
import { compactNumber, escapeHtml, fmt, formatDuration, projectName, text, topEntries, } from "./format.js";
import { appDisplayName, renderAppIcon } from "./icons.js";
let sessionsPrimed = false;
const knownSessions = new Set();
export function renderSessions(sessions) {
    text("session-count", `${sessions.length} shown`);
    const root = document.getElementById("recent-sessions");
    if (!root)
        return;
    if (!sessions.length) {
        root.innerHTML = '<div class="viz-empty"><span>No sessions yet</span></div>';
        knownSessions.clear();
        sessionsPrimed = true;
        return;
    }
    root.innerHTML = sessions
        .map((session) => {
        const rollup = session.rollup || {};
        const project = projectName(rollup.project_path);
        const color = appColor(rollup.source);
        const ended = (rollup.ended_at || rollup.started_at || "").slice(0, 16);
        const models = topEntries(rollup.models, 2)
            .map(([name, count]) => `${escapeHtml(name)} <span class="model-count">${fmt.format(count)} calls</span>`)
            .join(" - ");
        const tools = topEntries(rollup.tools, 2)
            .map(([name, count]) => `${escapeHtml(name)} ${fmt.format(count)}`)
            .join(" - ");
        const skills = topEntries(rollup.skills, 2)
            .map(([name, count]) => `${escapeHtml(name)} ${fmt.format(count)}`)
            .join(" - ");
        const executables = topEntries(rollup.executables || rollup.clis, 2)
            .map(([name, count]) => `${escapeHtml(name)} ${fmt.format(count)}`)
            .join(" - ");
        const appLabel = appDisplayName(rollup.source);
        const duration = formatDuration(session.duration_seconds);
        const firstTool = formatDuration(session.time_to_first_tool_seconds);
        const role = session.workflow_role || "Session";
        const sessionKey = stableSessionKey(session);
        const isNew = sessionsPrimed && !knownSessions.has(sessionKey);
        const isCurrent = session === sessions[0];
        return `
      <div class="timeline-item session-item${isNew ? " session-item-new" : ""}${isCurrent ? " session-item-current" : ""}" style="--project-color:${color}" data-session-key="${escapeHtml(sessionKey)}">
        <div class="time-label">${escapeHtml(ended.replace("T", " "))}</div>
        <div class="timeline-card" data-tip="<strong>${escapeHtml(project)}</strong>${escapeHtml(role)} · ${escapeHtml(appLabel)}<br>${fmt.format(rollup.model_calls || 0)} model calls, ${fmt.format(rollup.tool_calls || 0)} tool calls, ${fmt.format(rollup.skill_calls || 0)} skill calls<br>${fmt.format(rollup.command_calls || rollup.cli_commands || 0)} command actions · ${duration} duration<br>Tools: ${escapeHtml(tools || "none")}<br>Skills: ${escapeHtml(skills || "none")}<br>Executables: ${escapeHtml(executables || "none")}<br>First action: ${firstTool}<br>${fmt.format(rollup.tokens?.total_tokens || 0)} tokens">
          <div class="session-copy">
            <div class="timeline-main">
              <div class="timeline-project">${escapeHtml(project)}</div>
              <span class="app-pill icon-only app-pill-${escapeHtml(String(rollup.source || "unknown").toLowerCase())}" style="--app-color:${color}" title="${escapeHtml(appLabel)}">${renderAppIcon(rollup.source)}</span>
            </div>
            <div class="timeline-stats">
              <span><strong class="flip-count">${fmt.format(rollup.model_calls || 0)}</strong> model</span>
              <span><strong class="flip-count">${fmt.format(rollup.tool_calls || 0)}</strong> tools</span>
              <span><strong class="flip-count">${fmt.format(rollup.skill_calls || 0)}</strong> skills</span>
              <span><strong class="flip-count">${compactNumber(rollup.tokens?.total_tokens || 0)}</strong> tokens</span>
              <span>${escapeHtml(role)}</span>
            </div>
            <div class="model-line">${models || escapeHtml([tools, skills, executables].filter(Boolean).join(" - ") || "No model details")}</div>
          </div>
        </div>
      </div>
    `;
    })
        .join("");
    commitSessionKeys(sessions);
    root.querySelectorAll(".timeline-card").forEach((card) => {
        card.addEventListener("mousemove", (event) => showTooltip(event, card.dataset.tip || ""));
        card.addEventListener("mouseleave", hideTooltip);
    });
}
function stableSessionKey(session) {
    const rollup = session.rollup || {};
    return [
        rollup.source || "",
        rollup.project_path || "",
        rollup.started_at || "",
        rollup.ended_at || "",
        rollup.model_calls || 0,
        rollup.tool_calls || 0,
        rollup.skill_calls || 0,
        rollup.command_calls || rollup.cli_commands || 0,
    ].join("|");
}
function commitSessionKeys(sessions) {
    knownSessions.clear();
    sessions.forEach((session) => {
        knownSessions.add(stableSessionKey(session));
    });
    sessionsPrimed = true;
}
