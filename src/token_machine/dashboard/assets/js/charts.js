import { compactNumber, escapeHtml, fmt } from "./format.js";

const modelColors = {
  "gpt-5.5": "#0169cc",
  "gpt-5.4": "#3388e8",
  "openai/gpt-oss-120b:free": "#10a37f",
  "claude-opus-4-7": "#c15f3c",
  "claude-sonnet-4-6": "#d8895d",
  "claude-haiku-4-5-20251001": "#e6a27f",
  "anthropic/claude-4.5-haiku-20251001": "#b89b77",
  "gemini-3-flash-preview": "#7baaf7",
  "gemini-3.1-flash-lite-preview": "#8ab4f8",
  "gemini-2.5-flash-lite": "#6da9ff",
  "qwen2.5-coder:3b": "#8b7cff",
};

const appColors = {
  codex: "#0169cc",
  claude: "#d97757",
  gemini: "#8ab4f8",
  openai: "#0169cc",
  unknown: "#b1ada1",
};

export function appColor(source) {
  return appColors[String(source || "").toLowerCase()] || appColors.unknown;
}

export function modelColor(model) {
  const key = String(model || "").toLowerCase();
  if (modelColors[key]) return modelColors[key];
  if (key.includes("claude")) return appColors.claude;
  if (key.includes("gemini")) return appColors.gemini;
  if (key.includes("gpt") || key.includes("openai")) return appColors.openai;
  return "#43c7b7";
}

export function showTooltip(event, html) {
  const tooltip = document.getElementById("tooltip");
  tooltip.innerHTML = html;
  tooltip.style.left = `${event.clientX}px`;
  tooltip.style.top = `${event.clientY}px`;
  tooltip.style.opacity = "1";
}

export function hideTooltip() {
  document.getElementById("tooltip").style.opacity = "0";
}

export function renderModelDistribution(values) {
  const entries = Object.entries(values || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  const donut = document.getElementById("models-donut");
  const legend = document.getElementById("models");
  if (!entries.length || !total) {
    donut.style.background = "conic-gradient(var(--line) 0 100%)";
    donut.innerHTML = '<div class="donut-total"><span>No data</span></div>';
    legend.innerHTML = '<div class="eyebrow">No model calls yet</div>';
    return;
  }

  let cursor = 0;
  const segments = [];
  const slices = entries.map(([name, count]) => {
    const start = cursor;
    cursor += (count / total) * 100;
    const end = cursor;
    segments.push({ name, count, start, end, provider: providerForModel(name) });
    return `${modelColor(name)} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
  });

  donut.style.background = `conic-gradient(${slices.join(", ")})`;
  donut.innerHTML = `<div class="donut-total"><div><strong>${compactNumber(total)}</strong><span>calls</span></div></div>`;
  donut.onmousemove = (event) => {
    const rect = donut.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;
    let degrees = Math.atan2(y, x) * 180 / Math.PI + 90;
    if (degrees < 0) degrees += 360;
    const percent = degrees / 360 * 100;
    const segment = segments.find((item) => percent >= item.start && percent <= item.end) || segments[0];
    const share = segment.count / total * 100;
    showTooltip(event, `<strong>${escapeHtml(segment.name)}</strong>${escapeHtml(segment.provider)}<br>${fmt.format(segment.count)} calls<br>${share.toFixed(1)}% of model calls`);
  };
  donut.onmouseleave = hideTooltip;
  legend.innerHTML = entries.map(([name, count]) => `
    <div class="legend-item" title="${escapeHtml(name)}: ${fmt.format(count)} calls">
      <span class="legend-dot" style="background:${modelColor(name)}"></span>
      <span class="legend-name">${escapeHtml(name)}</span>
      <span>${compactNumber(count)}</span>
    </div>
  `).join("");
}

export function renderChart(id, points, getValue, lineColor, fillColor, labelKey) {
  const root = document.getElementById(id);
  root.innerHTML = chartSvg(points, getValue, lineColor, fillColor, labelKey);
  const hit = root.querySelector(".chart-hit");
  if (hit && points.length) {
    hit.addEventListener("mousemove", (event) => {
      const rect = root.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
      const index = Math.round(ratio * (points.length - 1));
      showChartTooltip(event, id, points[index], getValue, labelKey);
    });
    hit.addEventListener("mouseleave", hideTooltip);
  }
  root.querySelectorAll(".chart-dot").forEach((dot) => {
    dot.addEventListener("mousemove", (event) => {
      showChartTooltip(event, id, points[Number(dot.dataset.index)], getValue, labelKey);
    });
    dot.addEventListener("mouseleave", hideTooltip);
  });
}

function chartSvg(points, getValue, lineColor, fillColor, labelKey) {
  const width = 760;
  const height = 260;
  const pad = { top: 18, right: 18, bottom: 34, left: 54 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const values = points.map(getValue);
  const max = Math.max(...values, 1);
  if (!points.length) {
    return '<text x="24" y="44" fill="#9da4ad" font-size="14">No data yet</text>';
  }
  const step = points.length > 1 ? innerW / (points.length - 1) : innerW;
  const xy = values.map((value, index) => [
    pad.left + (points.length > 1 ? index * step : innerW / 2),
    pad.top + innerH - (value / max) * innerH,
  ]);
  const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad.left},${pad.top + innerH} ${line} ${pad.left + innerW},${pad.top + innerH}`;
  const grid = [0, .25, .5, .75, 1].map((tick) => {
    const y = pad.top + innerH - tick * innerH;
    return `<line x1="${pad.left}" y1="${y}" x2="${pad.left + innerW}" y2="${y}" stroke="#27303a" stroke-width="1"/>`;
  }).join("");
  const dots = xy.map(([x, y], index) => `
    <circle class="chart-dot" data-index="${index}" cx="${x}" cy="${y}" r="5" fill="${lineColor}"></circle>
  `).join("");
  const firstLabel = points[0]?.[labelKey] || "";
  const lastLabel = points[points.length - 1]?.[labelKey] || "";
  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${grid}
      <text x="${pad.left}" y="14" fill="#9da4ad" font-size="12">${fmt.format(max)}</text>
      <polygon points="${area}" fill="${fillColor}" opacity="0.28"></polygon>
      <polyline points="${line}" fill="none" stroke="${lineColor}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
      ${dots}
      <text x="${pad.left}" y="${height - 10}" fill="#9da4ad" font-size="12">${escapeHtml(firstLabel)}</text>
      <text x="${pad.left + innerW}" y="${height - 10}" fill="#9da4ad" font-size="12" text-anchor="end">${escapeHtml(lastLabel)}</text>
      <rect class="chart-hit" x="0" y="0" width="${width}" height="${height}" fill="transparent"></rect>
    </svg>
  `;
}

function showChartTooltip(event, id, row, getValue, labelKey) {
  const value = getValue(row);
  const eventTypes = row.summary?.event_types || {};
  const modelCalls = eventTypes.model_call || 0;
  const toolCalls = eventTypes.tool_call || 0;
  const unit = id === "daily-chart" ? "tokens" : "events";
  showTooltip(event, `<strong>${escapeHtml(row[labelKey])}</strong>${fmt.format(value)} ${unit}<br>${fmt.format(modelCalls)} model calls<br>${fmt.format(toolCalls)} tool calls`);
}

function providerForModel(model) {
  const key = String(model || "").toLowerCase();
  if (key.includes("claude")) return "Claude";
  if (key.includes("gemini")) return "Gemini";
  if (key.includes("gpt") || key.includes("openai")) return "OpenAI";
  if (key.includes("qwen")) return "Qwen";
  return "Other";
}
