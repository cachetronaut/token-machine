import { appColor, hideTooltip, modelColor, showTooltip, vizEmpty } from "./charts.js";
import {
  colorFor,
  compactNumber,
  escapeHtml,
  fmt,
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
    root.innerHTML = vizEmpty(`No ${options.noun || "activity"} yet`);
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
    root.innerHTML = `<div class="card">${vizEmpty("No model data yet")}</div>`;
    return;
  }
  root.innerHTML = visibleRows
    .slice(0, 12)
    .map((row, index) => {
      const color = modelCardColor(row);
      const effort =
        row.reasoning_level && row.reasoning_level !== "not in log"
          ? row.reasoning_level
          : "";
      const tokensPerCall = row.model_calls
        ? Math.round((row.tokens.total_tokens || 0) / row.model_calls)
        : 0;
      const tokensPerSession = row.session_count
        ? Math.round((row.tokens.total_tokens || 0) / row.session_count)
        : 0;
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
            ${renderRankMedallions(row, 3)}
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
              <div class="mini-stats back-usage-stats">
                <div class="mini-stat"><strong>${compactNumber(tokensPerCall)}</strong><span>avg tokens / call</span></div>
                <div class="mini-stat"><strong>${compactNumber(tokensPerSession)}</strong><span>avg tokens / session</span></div>
              </div>
              <div class="back-rank-panels">
                ${renderTopList("skills", row.skills, row.skill_calls, 2)}
                ${renderTopList("executables", row.executables || row.clis, row.command_calls, 2)}
              </div>
              ${effort ? `<div class="model-effort">effort ${escapeHtml(effort)}</div>` : ""}
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

function renderRankMedallions(row, limit = 3) {
  const badges = row.intelligence_badges?.slice(0, limit) || [];
  if (!badges.length) return '<div class="rank-medallion-strip"></div>';
  return `
    <div class="rank-medallion-strip" aria-label="Model rank badges">
      ${badges
        .map((badge) => {
          const category = String(badge.category || "rank").toLowerCase();
          const letters = categoryCode(category);
          const label = `${badge.label || ""} - ${badge.metric || ""}: ${compactNumber(badge.score || 0)}`;
          return `<span class="rank-medallion category-${escapeHtml(category)} tier-${escapeHtml(badge.tier || 1)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"><span>${escapeHtml(letters)}</span></span>`;
        })
        .join("")}
    </div>
  `;
}

function categoryCode(category) {
  const codes = {
    tools: "TL",
    commands: "CM",
    skills: "SK",
    context: "CX",
    model: "AI",
  };
  return codes[category] || "RK";
}

function renderTopList(title, values, total, limit = 3) {
  const rows = topEntries(values, limit);
  if (!rows.length) return "";
  const max = Math.max(...rows.map(([, count]) => count), 1);
  return `
    <div class="back-rank-panel">
      <div class="back-rank-title">${escapeHtml(title)}</div>
      ${rows
        .map(
          ([name, count]) => {
            const width = Math.max(6, (count / max) * 100);
            const share = total ? Math.round((count / total) * 100) : 0;
            return `
        <div class="back-rank-row" title="${escapeHtml(name)}: ${fmt.format(count)}">
          <div class="back-rank-copy"><span>${escapeHtml(name)}</span><strong>${compactNumber(count)}${share ? ` · ${share}%` : ""}</strong></div>
          <div class="back-rank-track"><span style="width:${width}%"></span></div>
        </div>
      `;
          },
        )
        .join("")}
    </div>
  `;
}
