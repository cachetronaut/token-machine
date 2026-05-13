import { appColor, hideTooltip, modelColor, showTooltip } from "./charts.js";
import {
  colorFor,
  compactNumber,
  escapeHtml,
  fmt,
  formatDuration,
  projectName,
  topEntries,
} from "./format.js";
import {
  appDisplayName,
  iconClassName,
  iconUrl,
  renderAppIcon,
  renderModelBadgeIcon,
  renderModelIcon,
  sourceIconName,
} from "./icons.js";

export function renderBars(
  id,
  values,
  includeDescriptions = false,
  descriptions = {},
) {
  const root = document.getElementById(id);
  const entries = topEntries(values);
  if (!entries.length) {
    root.innerHTML = '<div class="eyebrow">No data yet</div>';
    return;
  }
  const max = Math.max(...entries.map(([, count]) => count), 1);
  root.innerHTML = entries
    .map(
      ([name, count]) => `
    <div class="bar-row" title="${escapeHtml(name)}">
      <div>
        <div class="bar-label">${escapeHtml(name)}</div>
        ${includeDescriptions && descriptions[name] ? `<div class="bar-desc">${escapeHtml(descriptions[name])}</div>` : ""}
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, (count / max) * 100)}%"></div></div>
      <div>${fmt.format(count)}</div>
    </div>
  `,
    )
    .join("");
}

export function renderAppLegend(sources) {
  const root = document.getElementById("app-legend");
  const entries = Object.entries(sources || {}).sort((a, b) => b[1] - a[1]);
  root.innerHTML = entries
    .map(([source, count]) => {
      const color = appColor(source);
      const appLabel = appDisplayName(source);
      return `
      <span class="app-pill icon-only" style="--app-color:${color}" title="${escapeHtml(appLabel)}: ${fmt.format(count)} events">
        ${renderAppIcon(source)}
      </span>
    `;
    })
    .join("");
}

export function renderModelProfiles(rows) {
  const root = document.getElementById("model-profiles");
  const visibleRows = rows.filter(
    (row) =>
      row.model !== "unknown" &&
      (row.model_calls ||
        row.tool_calls ||
        row.skill_calls ||
        row.command_calls ||
        row.tokens.total_tokens),
  );
  if (!visibleRows.length) {
    root.innerHTML =
      '<div class="card"><div class="eyebrow">No model data yet</div></div>';
    return;
  }
  root.innerHTML = visibleRows
    .slice(0, 12)
    .map((row, index) => {
      const executables = topEntries(row.executables || row.clis, 3)
        .map(([name, count]) => `${name} ${fmt.format(count)}`)
        .join(" - ");
      const skills = topEntries(row.skills, 3)
        .map(([name, count]) => `${name} ${fmt.format(count)}`)
        .join(" - ");
      const projects = (row.projects || [])
        .map((project) => `${projectName(project.path)} ${project.count}`)
        .join(" - ");
      const color = modelCardColor(row);
      const effort =
        row.reasoning_level && row.reasoning_level !== "not in log"
          ? row.reasoning_level
          : "";
      const firstEdit = formatDuration(
        rowStat(row, "median_time_to_first_edit_seconds"),
      );
      return `
      <div class="card model-card" style="--card-color:${color}">
        <div class="model-inner">
          <div class="card-face">
            <div class="card-topline">
              <div class="provider-logo">${renderProviderLogo(row)}</div>
              <div class="card-number">#${String(index + 1).padStart(3, "0")}</div>
            </div>
            <div class="model-art">${renderModelHero(row)}</div>
            <div>
              <div class="model-title">${escapeHtml(row.model)}</div>
              <div class="mini-stats">
                <div class="mini-stat"><strong>${compactNumber(row.model_calls)}</strong><span>calls</span></div>
                <div class="mini-stat"><strong>${compactNumber(row.session_count || 0)}</strong><span>sessions</span></div>
                <div class="mini-stat"><strong>${compactNumber(row.tokens.total_tokens || 0)}</strong><span>tokens</span></div>
              </div>
              <div class="role-ribbon">${escapeHtml(row.workflow_role || "Captured Activity")}</div>
              ${renderMix(row.tool_mix)}
            </div>
            ${levelIcon(row.intelligence_level)}
          </div>
          <div class="card-face card-back">
            <div class="card-topline">
              <div class="provider-logo">${renderModelBadgeIcon(row)}</div>
              <div class="card-number">stats</div>
            </div>
            <div class="card-back-body">
              <div>
                <div class="model-title">${escapeHtml(row.model)}</div>
                <div class="model-subtitle">${fmt.format(row.session_count || 0)} sessions across ${fmt.format(row.project_count || 0)} projects</div>
              </div>
              <div class="mini-stats">
                <div class="mini-stat"><strong>${escapeHtml(row.workflow_role || "Activity")}</strong><span>inferred role</span></div>
                <div class="mini-stat"><strong>${escapeHtml(firstEdit)}</strong><span>median first action</span></div>
              </div>
              ${renderBackStatMatrix(row)}
              ${renderToolMatrix(row)}
              <div class="stat-table front-stats">
                ${effort ? `<div class="stat-row"><span>effort</span><strong>${escapeHtml(effort)}</strong></div>` : ""}
                <div class="stat-row"><span>skills</span><strong>${escapeHtml(skills || "none")}</strong></div>
                <div class="stat-row"><span>executables</span><strong>${escapeHtml(executables || "none")}</strong></div>
                <div class="stat-row"><span>projects</span><strong>${escapeHtml(projects || "none")}</strong></div>
              </div>
              <div class="model-tools">${escapeHtml(row.scouting_report || "")}</div>
              <div class="provenance"><span class="provenance-dot"></span>recorded + computed + inferred</div>
            </div>
            ${levelIcon(row.intelligence_level)}
          </div>
        </div>
      </div>
    `;
    })
    .join("");
}

function renderProviderLogo(row) {
  const icon = sourceIconName(row.source);
  if (!icon) return "";
  return `<img class="${iconClassName(icon, "provider-icon")}" src="${iconUrl(icon)}" alt="" loading="lazy" decoding="async" onerror="this.hidden=true">`;
}

function renderModelHero(row) {
  return renderModelIcon(row);
}

function modelCardColor(row) {
  const key = String(row.model || "").toLowerCase();
  const color = modelColor(key);
  if (color) return color;
  if (key.includes("qwen")) return "#8b7cff";
  if (key.includes("gpt") && row.source === "codex") return appColor("codex");
  return appColor(row.source) || colorFor(key);
}

function levelIcon(level) {
  const key = String(level || "unclassified").toLowerCase();
  const icons = {
    fast: '<path d="M11.251.068a.5.5 0 0 1 .227.58L9.677 6.5H13a.5.5 0 0 1 .364.843l-8 8.5a.5.5 0 0 1-.842-.49L6.323 9.5H3a.5.5 0 0 1-.364-.843l8-8.5a.5.5 0 0 1 .615-.09z"/>',
    frontier:
      '<path d="M7.657 6.247c.11-.33.576-.33.686 0l.645 1.937a2.89 2.89 0 0 0 1.829 1.828l1.936.645c.33.11.33.576 0 .686l-1.937.645a2.89 2.89 0 0 0-1.828 1.829l-.645 1.936a.361.361 0 0 1-.686 0l-.645-1.937a2.89 2.89 0 0 0-1.828-1.828l-1.937-.645a.361.361 0 0 1 0-.686l1.937-.645a2.89 2.89 0 0 0 1.828-1.828zM3.794 1.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387A1.73 1.73 0 0 0 4.593 5.69l-.387 1.162a.217.217 0 0 1-.412 0L3.407 5.69A1.73 1.73 0 0 0 2.31 4.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387A1.73 1.73 0 0 0 3.407 2.31z"/>',
    balanced:
      '<path d="M8 4a.5.5 0 0 1 .5.5V6a.5.5 0 0 1-1 0V4.5A.5.5 0 0 1 8 4M3.732 5.732a.5.5 0 0 1 .707 0l.915.914a.5.5 0 1 1-.708.708l-.914-.915a.5.5 0 0 1 0-.707M2 10a.5.5 0 0 1 .5-.5h1.586a.5.5 0 0 1 0 1H2.5A.5.5 0 0 1 2 10m9.5 0a.5.5 0 0 1 .5-.5h1.5a.5.5 0 0 1 0 1H12a.5.5 0 0 1-.5-.5m.754-4.268a.5.5 0 0 1 0 .707l-.915.915a.5.5 0 0 1-.707-.708l.914-.914a.5.5 0 0 1 .708 0"/><path d="M6.664 10.89a.5.5 0 0 1-.11-.696l2.5-3.5a.5.5 0 0 1 .806.592l-2.5 3.5a.5.5 0 0 1-.696.104"/><path fill-rule="evenodd" d="M8 1a7 7 0 0 0-7 7c0 1.676.59 3.216 1.574 4.42.18.22.452.33.736.33h9.38c.284 0 .556-.11.736-.33A6.97 6.97 0 0 0 15 8a7 7 0 0 0-7-7m0 1a6 6 0 0 1 4.889 9.474l-.15.276H3.26l-.15-.276A6 6 0 0 1 8 2"/>',
    unclassified:
      '<path d="M5.255 5.786a.237.237 0 0 0 .241.247h.825c.138 0 .248-.113.266-.25.09-.656.54-1.134 1.342-1.134.686 0 1.314.343 1.314 1.168 0 .635-.374.927-.965 1.371-.673.489-1.206 1.06-1.168 1.987l.003.217a.25.25 0 0 0 .25.246h.811a.25.25 0 0 0 .25-.25v-.105c0-.718.273-.927 1.01-1.486.609-.463 1.244-.977 1.244-2.056 0-1.511-1.276-2.241-2.673-2.241-1.267 0-2.655.59-2.75 2.29m1.557 5.763c0 .533.425.927 1.01.927.609 0 1.028-.394 1.028-.927 0-.552-.42-.94-1.029-.94-.584 0-1.009.388-1.009.94"/>',
  };
  const path = icons[key] || icons.unclassified;
  const label = key.charAt(0).toUpperCase() + key.slice(1);
  return `<span class="level-badge level-${escapeHtml(key)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"><svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">${path}</svg></span>`;
}

function rowStat(row, key) {
  return row.stats?.[key] || 0;
}

function renderMix(mix) {
  const rows = (mix || []).slice(0, 5);
  if (!rows.length)
    return '<div class="model-tools">No tool mix recorded</div>';
  return `<div class="mix-row">${rows
    .map(
      (item) => `
    <div class="mix-pill" title="${escapeHtml(item.category)}: ${fmt.format(item.count)} actions&#10;${escapeHtml(item.description || "")}">
      <strong>${escapeHtml(mixIcon(item.category))}</strong>
      <span>${escapeHtml(item.category)}</span>
      <span>${fmt.format(item.percent || 0)}%</span>
    </div>
  `,
    )
    .join("")}</div>`;
}

function renderBackStatMatrix(row) {
  const modeProject = projectName(row.stats?.mode_project || "") || "none";
  return `
    <div class="stat-matrix">
      <div class="matrix-row matrix-head"><div class="matrix-cell"></div><div class="matrix-cell">mean</div><div class="matrix-cell">median</div><div class="matrix-cell">mode</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">calls</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_model_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_model_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.model_calls)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">tools</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_tool_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_tool_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.tool_calls)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">skills</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_skill_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_skill_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.skill_calls || 0)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">tokens</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_tokens_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_tokens_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.tokens.total_tokens || 0)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">time</div><div class="matrix-cell matrix-value">${formatDuration(rowStat(row, "median_duration_seconds"))}</div><div class="matrix-cell matrix-value">${formatDuration(rowStat(row, "median_time_to_first_tool_seconds"))}</div><div class="matrix-cell matrix-value" title="${escapeHtml(modeProject)}">${escapeHtml(modeProject)}</div></div>
    </div>
  `;
}

function renderToolMatrix(row) {
  const rows = (row.tool_mix || []).slice(0, 3);
  if (!rows.length) return "";
  return `
    <div class="tool-matrix">
      <div class="matrix-row matrix-head"><div class="matrix-cell">tool</div><div class="matrix-cell">count</div><div class="matrix-cell">share</div></div>
      ${rows
        .map(
          (item) => `
        <div class="matrix-row" title="${escapeHtml(item.description || "")}"><div class="matrix-cell matrix-label">${escapeHtml(item.category)}</div><div class="matrix-cell matrix-value">${fmt.format(item.count || 0)}</div><div class="matrix-cell matrix-value">${fmt.format(item.percent || 0)}%</div></div>
      `,
        )
        .join("")}
    </div>
  `;
}

function mixIcon(category) {
  const value = String(category || "?").trim();
  if (!value) return "?";
  if (value.startsWith("/") || value.includes("sh")) return ">_";
  return value.slice(0, 1).toUpperCase();
}
