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
  claudecode: "#d97757",
  gemini: "#8ab4f8",
  opencode: "#f5f7fa",
  openai: "#0169cc",
  zed: "#1348dc",
  unknown: "#b1ada1",
};

const chartMotionFrames = new WeakMap();
let chartMotionBatchStart = 0;
let chartMotionBatchExpires = 0;

export function appColor(source) {
  return appColors[String(source || "").toLowerCase()] || appColors.unknown;
}

export function modelColor(model) {
  const key = String(model || "").toLowerCase();
  if (modelColors[key]) return modelColors[key];
  if (key.includes("claude")) return appColors.claudecode;
  if (key.includes("gemini")) return appColors.gemini;
  if (key.includes("opencode")) return appColors.opencode;
  if (key.includes("openrouter")) return "#f5f7fa";
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
    donut.innerHTML = `
      <svg class="donut-svg" viewBox="0 0 200 200" aria-hidden="true">
        <path class="donut-segment" style="--seg-index:0" d="${donutSlicePath(0, 99.999, 92, 46)}" fill="rgba(255, 255, 255, .065)"></path>
      </svg>
      <div class="donut-total"><span>No data</span></div>
    `;
    legend.innerHTML = vizEmpty("No model calls yet");
    setInsight("models-insight", "No model traffic recorded yet.");
    return;
  }

  let cursor = 0;
  const segments = [];
  entries.forEach(([name, count]) => {
    const start = cursor;
    cursor += (count / total) * 100;
    const end = cursor;
    segments.push({ name, count, start, end, provider: providerForModel(name) });
  });

  const leaderColor = modelColor(entries[0][0]);
  const leaderCount = entries[0][1];
  donut.style.setProperty("--chart-color", leaderColor);
  donut.innerHTML = `
    <div class="donut-aura" aria-hidden="true"></div>
    ${donutSvg(segments)}
    <div class="donut-total"><div><strong>${compactNumber(total)}</strong><span>calls</span><span class="donut-leader-tag"><span class="donut-leader-text">${escapeHtml(providerForModel(entries[0][0]))} lead</span></span></div></div>
  `;
  replayDonutAnimation(donut);

  const segmentNodes = donut.querySelectorAll(".donut-segment");
  legend.innerHTML = entries.map(([name, count], index) => {
    const share = total ? (count / total) * 100 : 0;
    const leader = index === 0 ? " dist-row-leader" : "";
    const color = modelColor(name);
    return `
    <div class="dist-row${leader}" data-model="${escapeHtml(name)}" style="--row-color:${color}; --share:${share.toFixed(1)}%">
      <span class="dist-rank">${String(index + 1).padStart(2, "0")}</span>
      <span class="dist-name">${escapeHtml(name)}</span>
      <span class="dist-value">${compactNumber(count)}<span class="dist-share">${share.toFixed(1)}%</span></span>
      <span class="dist-track"><span class="dist-fill"></span></span>
    </div>
  `;
  }).join("");
  const rowNodes = legend.querySelectorAll(".dist-row");

  const setActive = (name) => {
    donut.classList.toggle("has-hover", Boolean(name));
    segmentNodes.forEach((node) => {
      node.classList.toggle("is-active", node.dataset.model === name);
    });
    rowNodes.forEach((node) => {
      node.classList.toggle("is-active", node.dataset.model === name);
    });
  };

  const tooltipFor = (segment, event) => {
    const share = segment.count / total * 100;
    const rank = segments.findIndex((item) => item.name === segment.name) + 1;
    const vsLeader = segment.count === leaderCount
      ? "leader"
      : `${(((leaderCount - segment.count) / leaderCount) * 100).toFixed(0)}% below leader`;
    const color = modelColor(segment.name);
    showTooltip(event, `
      <strong><span class="tooltip-swatch" style="background:${color}"></span>${escapeHtml(segment.name)}</strong>
      <div class="tooltip-row"><span>provider</span><em>${escapeHtml(segment.provider)}</em></div>
      <div class="tooltip-row"><span>rank</span><em>#${rank} of ${segments.length}</em></div>
      <div class="tooltip-row"><span>calls</span><em>${fmt.format(segment.count)}</em></div>
      <div class="tooltip-row"><span>share</span><em>${share.toFixed(1)}%</em></div>
      <div class="tooltip-bar"><span style="width:${share.toFixed(1)}%; background:${color}"></span></div>
      <div class="tooltip-foot">${escapeHtml(vsLeader)}</div>
    `);
  };

  donut.onmousemove = (event) => {
    const rect = donut.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;
    let degrees = Math.atan2(y, x) * 180 / Math.PI + 90;
    if (degrees < 0) degrees += 360;
    const percent = degrees / 360 * 100;
    const segment = segments.find((item) => percent >= item.start && percent <= item.end) || segments[0];
    setActive(segment.name);
    tooltipFor(segment, event);
  };
  donut.onmouseleave = () => {
    setActive(null);
    hideTooltip();
  };

  rowNodes.forEach((row) => {
    row.addEventListener("mouseenter", (event) => {
      const segment = segments.find((s) => s.name === row.dataset.model);
      if (!segment) return;
      setActive(segment.name);
      tooltipFor(segment, event);
    });
    row.addEventListener("mousemove", (event) => {
      const segment = segments.find((s) => s.name === row.dataset.model);
      if (segment) tooltipFor(segment, event);
    });
    row.addEventListener("mouseleave", () => {
      setActive(null);
      hideTooltip();
    });
  });
}

function donutSvg(segments) {
  const outerRadius = 92;
  const innerRadius = 46;
  const slices = segments.map((segment, index) => {
    const leader = index === 0 ? " donut-segment-leader" : "";
    return `
      <path
        class="donut-segment${leader}"
        style="--seg-index:${index}"
        data-model="${escapeHtml(segment.name)}"
        d="${donutSlicePath(segment.start, segment.end, outerRadius, innerRadius)}"
        fill="${modelColor(segment.name)}"
      ></path>
    `;
  }).join("");
  const overlay = `<path class="donut-depth" d="${donutSlicePath(0, 99.999, outerRadius, innerRadius)}" fill="url(#donut-depth-grad)"></path>`;
  return `
    <svg class="donut-svg" viewBox="0 0 200 200" aria-hidden="true">
      <defs>
        <radialGradient id="donut-depth-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(0,0,0,0)"/>
          <stop offset="46%" stop-color="rgba(0,0,0,0.35)"/>
          <stop offset="60%" stop-color="rgba(0,0,0,0.12)"/>
          <stop offset="78%" stop-color="rgba(255,255,255,0.02)"/>
          <stop offset="92%" stop-color="rgba(255,255,255,0.22)"/>
          <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
        </radialGradient>
      </defs>
      <g class="donut-segments">
        ${slices}
      </g>
      ${overlay}
    </svg>
  `;
}

export function replayDonutAnimation(root) {
  const donut = root || document.getElementById("models-donut");
  if (!donut) return;
  donut.classList.remove("donut-animate-in");
  void donut.offsetWidth;
  donut.classList.add("donut-animate-in");
}

export function vizEmpty(label) {
  return `<div class="viz-empty"><span>${escapeHtml(label)}</span></div>`;
}

function chartSkeletonSvg(width = 760, height = 260) {
  const pad = { top: 28, right: 30, bottom: 44, left: 62 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const midY = pad.top + innerH * 0.58;
  const grid = [0, .25, .5, .75, 1].map((tick) => {
    const y = pad.top + innerH - tick * innerH;
    return `<line class="chart-grid-line" x1="${pad.left}" y1="${y}" x2="${pad.left + innerW}" y2="${y}"/>`;
  }).join("");
  const wave = [];
  const steps = 24;
  for (let i = 0; i <= steps; i += 1) {
    const x = pad.left + (innerW * i) / steps;
    const y = midY + Math.sin(i / 2.4) * 14;
    wave.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${grid}
      <polyline class="chart-skeleton-line" points="${wave.join(" ")}"></polyline>
      <circle class="chart-skeleton-dot" cx="${pad.left + innerW}" cy="${midY}" r="5"></circle>
    </svg>
  `;
}

function donutSlicePath(startPercent, endPercent, outerRadius, innerRadius) {
  const startAngle = startPercent / 100 * 360 - 90;
  const endAngle = endPercent / 100 * 360 - 90;
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  const outerStart = polarPoint(100, 100, outerRadius, startAngle);
  const outerEnd = polarPoint(100, 100, outerRadius, endAngle);
  const innerEnd = polarPoint(100, 100, innerRadius, endAngle);
  const innerStart = polarPoint(100, 100, innerRadius, startAngle);
  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

function polarPoint(cx, cy, radius, angle) {
  const radians = angle * Math.PI / 180;
  return {
    x: (cx + radius * Math.cos(radians)).toFixed(3),
    y: (cy + radius * Math.sin(radians)).toFixed(3),
  };
}

export function renderChart(id, points, getValue, lineColor, fillColor, labelKey, options = {}) {
  const root = document.getElementById(id);
  root.style.setProperty("--chart-color", lineColor);
  root.classList.remove("chart-refresh", "chart-tab-switch");
  void root.offsetWidth;
  const meta = {};
  root.innerHTML = chartSvg(id, points, getValue, lineColor, fillColor, labelKey, options, meta);
  root.__chartMeta = meta;
  animateSignalChart(root);
  root.classList.add("chart-refresh");
  const hit = root.querySelector(".chart-hit");
  const dots = root.querySelectorAll(".chart-dot");
  if (hit && points.length) {
    hit.addEventListener("mousemove", (event) => {
      const rect = root.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
      const index = Math.round(ratio * (points.length - 1));
      dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
      showChartTooltip(event, id, points[index], getValue, labelKey, options);
    });
    hit.addEventListener("mouseleave", () => {
      dots.forEach((dot) => dot.classList.remove("is-active"));
      hideTooltip();
    });
  }
  if (options.insightId) {
    setInsight(options.insightId, chartInsight(points, getValue, options));
  }
}

function chartSvg(id, points, getValue, lineColor, fillColor, labelKey, options, meta) {
  const width = 760;
  const height = 260;
  const pad = { top: 28, right: 30, bottom: 44, left: 62 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const values = points.map(getValue);
  const max = Math.max(...values, 1);
  if (!points.length) {
    return chartSkeletonSvg(width, height);
  }
  const step = points.length > 1 ? innerW / (points.length - 1) : innerW;
  const xy = values.map((value, index) => [
    pad.left + (points.length > 1 ? index * step : innerW / 2),
    pad.top + innerH - (value / max) * innerH,
  ]);
  const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad.left},${pad.top + innerH} ${line} ${pad.left + innerW},${pad.top + innerH}`;
  const slug = id.replace(/[^\w-]/g, "-");
  const clipId = `${slug}-progress-clip`;
  const areaGradId = `${slug}-area-grad`;
  const sheenGradId = `${slug}-sheen-grad`;
  const grid = [0, .25, .5, .75, 1].map((tick) => {
    const y = pad.top + innerH - tick * innerH;
    return `<line class="chart-grid-line" x1="${pad.left}" y1="${y}" x2="${pad.left + innerW}" y2="${y}"/>`;
  }).join("");
  const dots = xy.map(([x, y], index) => `<circle class="chart-dot" data-index="${index}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.6" fill="${lineColor}"></circle>`).join("");
  const tickCount = Math.min(points.length, points.length >= 7 ? 5 : points.length);
  const tickIndices = [];
  if (tickCount === 1) {
    tickIndices.push(0);
  } else {
    for (let t = 0; t < tickCount; t += 1) {
      tickIndices.push(Math.round((points.length - 1) * (t / (tickCount - 1))));
    }
  }
  const seenTicks = new Set();
  const xTicks = tickIndices
    .filter((i) => { if (seenTicks.has(i)) return false; seenTicks.add(i); return true; })
    .map((i) => {
      const x = xy[i][0];
      const label = points[i]?.[labelKey] || "";
      const anchor = i === 0 ? "start" : i === points.length - 1 ? "end" : "middle";
      return `
        <line class="chart-x-tick" x1="${x.toFixed(1)}" y1="${(pad.top + innerH).toFixed(1)}" x2="${x.toFixed(1)}" y2="${(pad.top + innerH + 5).toFixed(1)}"></line>
        <text class="chart-axis-label chart-x-label" x="${x.toFixed(1)}" y="${(pad.top + innerH + 18).toFixed(1)}" text-anchor="${anchor}">${escapeHtml(formatTickLabel(label))}</text>
      `;
    }).join("");
  if (meta) {
    meta.pad = pad;
    meta.innerW = innerW;
    meta.values = values;
    meta.max = max;
    meta.lineColor = lineColor;
  }
  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs>
        <clipPath id="${clipId}">
          <rect class="chart-progress-clip" x="${pad.left}" y="0" width="0" height="${height}"></rect>
        </clipPath>
        <linearGradient id="${areaGradId}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="${lineColor}" stop-opacity="0.55"></stop>
          <stop offset="55%" stop-color="${lineColor}" stop-opacity="0.18"></stop>
          <stop offset="100%" stop-color="${lineColor}" stop-opacity="0"></stop>
        </linearGradient>
        <linearGradient id="${sheenGradId}" x1="-0.4" x2="-0.1" y1="0" y2="0">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0"></stop>
          <stop offset="50%" stop-color="#ffffff" stop-opacity="0.9"></stop>
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0"></stop>
          <animate attributeName="x1" values="-0.4;1.0;1.0" keyTimes="0;0.55;1" dur="5.5s" repeatCount="indefinite"></animate>
          <animate attributeName="x2" values="-0.1;1.3;1.3" keyTimes="0;0.55;1" dur="5.5s" repeatCount="indefinite"></animate>
        </linearGradient>
      </defs>
      ${grid}
      <text class="chart-axis-title chart-axis-y" x="16" y="${pad.top + innerH / 2}" transform="rotate(-90 16 ${pad.top + innerH / 2})">${escapeHtml(options.unit || "value")}</text>
      <text class="chart-axis-label" x="${pad.left - 8}" y="${pad.top + 4}" text-anchor="end">${fmt.format(max)}</text>
      <text class="chart-axis-label" x="${pad.left - 8}" y="${pad.top + innerH}" text-anchor="end">0</text>
      <polygon class="chart-area" points="${area}" fill="url(#${areaGradId})" clip-path="url(#${clipId})"></polygon>
      <g class="chart-dots" clip-path="url(#${clipId})">${dots}</g>
      <polyline class="chart-line chart-line-progress" points="${line}" stroke="${lineColor}" clip-path="url(#${clipId})"></polyline>
      <polyline class="chart-line chart-line-sheen" points="${line}" stroke="url(#${sheenGradId})" clip-path="url(#${clipId})"></polyline>
      <g class="chart-value-tag" transform="translate(${xy[0][0].toFixed(1)} ${xy[0][1].toFixed(1)})">
        <line class="chart-value-guide" x1="${(pad.left - xy[0][0]).toFixed(1)}" y1="0" x2="0" y2="0" stroke="${lineColor}"></line>
        <g class="chart-value-pill">
          <rect class="chart-value-bg" x="10" y="-12" rx="6" ry="6" width="60" height="22" fill="#0c0f14" stroke="${lineColor}"></rect>
          <text class="chart-value-text" x="40" y="3" text-anchor="middle">${escapeHtml(compactNumber(values[0] || 0))}</text>
        </g>
      </g>
      <g class="chart-ball" transform="translate(${xy[0][0].toFixed(1)} ${xy[0][1].toFixed(1)})">
        <circle class="chart-ball-halo" r="8" fill="${lineColor}"></circle>
        <circle class="chart-ball-dot" r="5.5" fill="${lineColor}"></circle>
      </g>
      ${xTicks}
      <text class="chart-axis-title chart-x-axis-title" x="${pad.left + innerW / 2}" y="${height - 4}" text-anchor="middle">${escapeHtml(options.xAxis || labelKey)}</text>
      <rect class="chart-hit" x="0" y="0" width="${width}" height="${height}" fill="transparent"></rect>
    </svg>
  `;
}

function animateSignalChart(root) {
  const previousFrame = chartMotionFrames.get(root);
  if (previousFrame) cancelAnimationFrame(previousFrame);

  root.classList.remove("chart-motion-done");
  const line = root.querySelector(".chart-line-progress");
  const clip = root.querySelector(".chart-progress-clip");
  const ball = root.querySelector(".chart-ball");
  const valueTag = root.querySelector(".chart-value-tag");
  const valueGuide = root.querySelector(".chart-value-guide");
  const valuePill = root.querySelector(".chart-value-pill");
  const valueText = root.querySelector(".chart-value-text");
  const points = parsePolylinePoints(line?.getAttribute("points") || "");
  if (!line || !clip || !ball || points.length === 0) return;

  const meta = root.__chartMeta || {};
  const values = meta.values || [];
  const pad = meta.pad || { left: 62 };
  const innerW = meta.innerW || 0;
  const flipThresholdX = pad.left + innerW - 80;

  const duration = cssTimeToMs(getComputedStyle(document.documentElement).getPropertyValue("--motion-fill"), 3600);
  const startTime = nextChartMotionStart();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const update = (progress) => {
    const point = pointAtProgress(points, progress);
    const firstX = points[0].x;
    const lastX = points[points.length - 1].x;
    const visibleWidth = Math.max(0, point.x - firstX + 2);
    const finalWidth = Math.max(0, lastX - firstX + 2);
    clip.setAttribute("width", `${(progress >= 1 ? finalWidth : visibleWidth).toFixed(2)}`);
    ball.setAttribute("transform", `translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})`);
    if (valueTag) {
      valueTag.setAttribute("transform", `translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})`);
    }
    if (valueGuide) {
      valueGuide.setAttribute("x1", (pad.left - point.x).toFixed(2));
    }
    if (valuePill) {
      const flip = point.x > flipThresholdX;
      valuePill.setAttribute("transform", flip ? "translate(-80 0)" : "");
    }
    if (valueText && values.length) {
      const fractional = progress * (values.length - 1);
      const idx = Math.floor(fractional);
      const t = fractional - idx;
      const v = idx >= values.length - 1
        ? values[values.length - 1]
        : values[idx] + (values[idx + 1] - values[idx]) * t;
      valueText.textContent = compactNumber(Math.max(0, v));
    }
  };

  if (reducedMotion) {
    update(1);
    root.classList.add("chart-motion-done");
    return;
  }

  update(0);
  const tick = (now) => {
    const elapsed = Math.max(0, now - startTime);
    const progress = Math.min(1, elapsed / duration);
    update(progress);
    if (progress < 1) {
      chartMotionFrames.set(root, requestAnimationFrame(tick));
    } else {
      chartMotionFrames.delete(root);
      root.classList.add("chart-motion-done");
    }
  };
  chartMotionFrames.set(root, requestAnimationFrame(tick));
}

function nextChartMotionStart() {
  const now = performance.now();
  if (!chartMotionBatchStart || now > chartMotionBatchExpires) {
    chartMotionBatchStart = now + 64;
    chartMotionBatchExpires = now + 180;
  }
  return chartMotionBatchStart;
}

function parsePolylinePoints(points) {
  return points.trim().split(/\s+/).filter(Boolean).map((pair) => {
    const [x, y] = pair.split(",").map(Number);
    return { x, y };
  }).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
}

function pointAtProgress(points, progress) {
  if (points.length === 1) return points[0];
  const firstX = points[0].x;
  const lastX = points[points.length - 1].x;
  const x = firstX + (lastX - firstX) * progress;
  const nextIndex = points.findIndex((point) => point.x >= x);
  if (nextIndex <= 0) return points[0];
  const next = points[nextIndex];
  const previous = points[nextIndex - 1];
  const span = Math.max(next.x - previous.x, 1);
  const localProgress = Math.max(0, Math.min(1, (x - previous.x) / span));
  return {
    x,
    y: previous.y + (next.y - previous.y) * localProgress,
  };
}

function cssTimeToMs(value, fallback) {
  const match = String(value || "").trim().match(/^([\d.]+)(ms|s)$/);
  if (!match) return fallback;
  const amount = Number(match[1]);
  if (!Number.isFinite(amount)) return fallback;
  return match[2] === "s" ? amount * 1000 : amount;
}

function formatTickLabel(label) {
  const text = String(label || "");
  const dateMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (dateMatch) return `${dateMatch[2]}/${dateMatch[3]}`;
  const hourMatch = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}):/);
  if (hourMatch) return `${hourMatch[2]}:00`;
  return text.length > 10 ? `${text.slice(0, 9)}…` : text;
}

function showChartTooltip(event, id, row, getValue, labelKey, options = {}) {
  const value = getValue(row);
  const eventTypes = row.summary?.event_types || {};
  const modelCalls = eventTypes.model_call || 0;
  const toolCalls = eventTypes.tool_call || 0;
  const unit = options.unit || (id === "daily-chart" ? "tokens" : "events");
  showTooltip(event, `<strong>${escapeHtml(row[labelKey])}</strong>${fmt.format(value)} ${unit}<br>${fmt.format(modelCalls)} model calls<br>${fmt.format(toolCalls)} tool calls`);
}

function chartInsight(points, getValue, options) {
  if (!points.length) return options.emptyInsight || "No local agent activity in this window.";
  const entries = points.map((point) => ({ point, value: getValue(point) }));
  const total = entries.reduce((sum, item) => sum + item.value, 0);
  if (!total) return options.emptyInsight || "No local agent activity in this window.";
  const peak = entries.reduce((best, item) => item.value > best.value ? item : best, entries[0]);
  const label = peak.point?.[options.labelKey || "day"] || "window";
  const unit = options.unit || "events";
  return `${options.subject || "Local agents"} peaked at ${compactNumber(peak.value)} ${unit} on ${escapeHtml(label)}.`;
}

function setInsight(id, text) {
  const element = document.getElementById(id);
  if (element) element.textContent = text;
}

function providerForModel(model) {
  const key = String(model || "").toLowerCase();
  if (key.includes("claude")) return "Claude";
  if (key.includes("gemini")) return "Gemini";
  if (key.includes("gpt") || key.includes("openai")) return "OpenAI";
  if (key.includes("qwen")) return "Qwen";
  return "Other";
}
