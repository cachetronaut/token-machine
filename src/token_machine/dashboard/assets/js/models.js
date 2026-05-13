import { appColor, hideTooltip, modelColor, showTooltip } from "./charts.js";
import {
  colorFor,
  compactNumber,
  escapeHtml,
  fmt,
  formatDuration,
  topEntries,
} from "./format.js";
import {
  appDisplayName,
  iconClassName,
  iconUrl,
  renderAppIcon,
  renderModelIcon,
  sourceIconName,
} from "./icons.js";

export function renderBars(
  id,
  values,
  options = {},
) {
  const root = document.getElementById(id);
  const entries = topEntries(values);
  if (!entries.length) {
    root.innerHTML = '<div class="eyebrow">No data yet</div>';
    renderRankInsight(options.insightId, `No ${options.noun || "activity"} calls yet.`);
    return;
  }
  const max = Math.max(...entries.map(([, count]) => count), 1);
  root.innerHTML = entries
    .map(
      ([name, count], index) => {
        const width = Math.max(3, (count / max) * 100);
        const description = options.descriptions?.[name] || "";
        return `
    <div class="bar-row" title="${escapeHtml(name)}" style="--bar-width:${width}%; --bar-index:${index}">
      <div class="bar-main">
        <div class="bar-top">
          <div class="bar-label">${escapeHtml(name)}</div>
          <div class="bar-value">${fmt.format(count)}</div>
        </div>
        <div class="bar-track"><div class="bar-fill"></div><span class="bar-runner" aria-hidden="true"></span></div>
        ${description ? `<div class="bar-desc">${escapeHtml(description)}</div>` : ""}
      </div>
    </div>
  `;
      },
    )
    .join("");
  renderRankInsight(options.insightId, rankInsight(entries, options));
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
            <div class="model-card-header">
              <div class="card-topline">
                <div class="provider-logo">${renderProviderLogo(row)}</div>
                <div class="card-number">${escapeHtml(row.model_family || "")}</div>
              </div>
              <div>
                <div class="model-title">${escapeHtml(row.model)}</div>
                <div class="model-subtitle">${fmt.format(row.session_count || 0)} sessions</div>
              </div>
            </div>
            <div class="model-art">${renderModelHero(row)}</div>
            <div>
              <div class="mini-stats">
                <div class="mini-stat"><strong>${compactNumber(row.model_calls)}</strong><span>calls</span></div>
                <div class="mini-stat"><strong>${compactNumber(row.session_count || 0)}</strong><span>sessions</span></div>
                <div class="mini-stat"><strong>${compactNumber(row.tokens.total_tokens || 0)}</strong><span>tokens</span></div>
              </div>
            </div>
          </div>
          <div class="card-face card-back">
            <div class="model-card-header">
              <div class="card-topline">
                <div class="card-number">intelligence</div>
              </div>
              <div>
                <div class="model-title">${escapeHtml(row.model)}</div>
                <div class="model-subtitle">${fmt.format(row.session_count || 0)} sessions</div>
              </div>
            </div>
            <div class="card-back-body">
              ${renderIntelligenceBadges(row)}
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
              </div>
              <div class="model-tools">${escapeHtml(row.scouting_report || "")}</div>
              <div class="provenance"><span class="provenance-dot"></span>recorded + computed + inferred</div>
            </div>
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

function renderRankInsight(id, text) {
  const element = document.getElementById(id);
  if (element) element.textContent = text;
}

function rankInsight(entries, options) {
  const [[name, count]] = entries;
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  const share = total ? Math.round((count / total) * 100) : 0;
  return `${options.subject || "Local activity"} is led by ${name} with ${compactNumber(count)} ${options.noun || "actions"} calls (${share}% of top rows).`;
}

function modelCardColor(row) {
  const key = String(row.model || "").toLowerCase();
  const color = modelColor(key);
  if (color) return color;
  if (key.includes("qwen")) return "#8b7cff";
  if (key.includes("gpt") && row.source === "codex") return appColor("codex");
  return appColor(row.source) || colorFor(key);
}

function renderIntelligenceBadges(row) {
  const level = badgeLabel(row.intelligence_level || "unclassified");
  const role = badgeLabel(row.workflow_role || "activity");
  const toolMultiplier = multiplier(row.tool_calls, row.model_calls);
  const skillMultiplier = multiplier(row.skill_calls || 0, row.session_count || 0);
  const badges = [
    ["level", level],
    ["role", role],
    ["tools", `${toolMultiplier}x tools`],
    ["skills", `${skillMultiplier}x skills`],
  ];
  return `
    <div class="intelligence-badges" aria-label="Model intelligence badges">
      ${badges
        .map(
          ([label, value]) =>
            `<span class="intelligence-badge"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></span>`,
        )
        .join("")}
    </div>
  `;
}

function badgeLabel(value) {
  return String(value || "unknown")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function multiplier(count, base) {
  if (!count || !base) return "1.0";
  return Math.min(2, Math.max(1, count / base)).toFixed(1);
}

function rowStat(row, key) {
  return row.stats?.[key] || 0;
}

function renderBackStatMatrix(row) {
  const meanDuration = formatDuration(rowStat(row, "mean_duration_seconds"));
  const medianDuration = formatDuration(rowStat(row, "median_duration_seconds"));
  const medianFirstTool = formatDuration(rowStat(row, "median_time_to_first_tool_seconds"));
  return `
    <div class="stat-matrix">
      <div class="matrix-row matrix-head"><div class="matrix-cell"></div><div class="matrix-cell">mean</div><div class="matrix-cell">median</div><div class="matrix-cell">mode</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">calls</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_model_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_model_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.model_calls)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">tools</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_tool_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_tool_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.tool_calls)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">skills</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_skill_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_skill_calls_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.skill_calls || 0)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">tokens</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "mean_tokens_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(rowStat(row, "median_tokens_per_session"))}</div><div class="matrix-cell matrix-value">${compactNumber(row.tokens.total_tokens || 0)}</div></div>
      <div class="matrix-row"><div class="matrix-cell matrix-label">time</div><div class="matrix-cell matrix-value">${escapeHtml(meanDuration)}</div><div class="matrix-cell matrix-value">${escapeHtml(medianDuration)}</div><div class="matrix-cell matrix-value">${escapeHtml(medianFirstTool)}</div></div>
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
