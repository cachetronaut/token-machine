import {
  fetchLive,
  fetchSummary,
  livePollMs,
  startDebugReloadPolling,
  startPolling,
  summaryPollMs,
} from "./api.js";
import { renderChart, renderModelDistribution } from "./charts.js";
import { datasetValue, optionalElement, optionalQuery, queryAll } from "./dom.js";
import { metric, text } from "./format.js";
import { playIntro } from "./intro.js";
import { renderLive, renderLiveError } from "./live.js";
import { renderAppLegend, renderBars, renderModelProfiles } from "./models.js";
import { initSectionToggles } from "./sections.js";
import { renderSessions } from "./sessions.js";
import type { DailySummary, DashboardData } from "./types.js";

type ChartId = "daily-chart" | "hourly-chart";
type ChartMode = "tokens" | "skills" | "commands" | "events" | "tools";
type ChartMetricConfig = {
  value: (row: DailySummary) => number;
  color: string;
  unit: string;
  subject: string;
};

const chartModes: Record<ChartId, ChartMode> = {
  "daily-chart": "tokens",
  "hourly-chart": "events",
};

let latestSummaryData: DashboardData | null = null;

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isChartId(value: string | null): value is ChartId {
  return value === "daily-chart" || value === "hourly-chart";
}

function isChartModeFor(chartId: ChartId, value: string | null): value is ChartMode {
  return Boolean(value && chartMetricConfig[chartId][value as ChartMode]);
}

const chartMetricConfig: Record<ChartId, Partial<Record<ChartMode, ChartMetricConfig>>> = {
  "daily-chart": {
    tokens: {
      value: (row) => row.summary?.tokens?.total_tokens || 0,
      color: "#43c7b7",
      unit: "tokens",
      subject: "Token flow",
    },
    skills: {
      value: (row) => row.summary?.skill_calls || 0,
      color: "#9bc2ff",
      unit: "skill calls",
      subject: "Field-agent skill usage",
    },
    commands: {
      value: (row) => row.summary?.command_calls || 0,
      color: "#ff7f6e",
      unit: "commands",
      subject: "Command substrate",
    },
  },
  "hourly-chart": {
    events: {
      value: (row) => row.summary?.event_count || 0,
      color: "#f6c453",
      unit: "events",
      subject: "Recent activity",
    },
    tools: {
      value: (row) => row.summary?.event_types?.tool_call || 0,
      color: "#58d68d",
      unit: "tool calls",
      subject: "Tool usage",
    },
    commands: {
      value: (row) => row.summary?.command_calls || 0,
      color: "#ff7f6e",
      unit: "commands",
      subject: "Command substrate",
    },
  },
};

function setStatusState(state: "connecting" | "live" | "disconnected") {
  const status = optionalQuery<HTMLElement>(".status");
  if (!status) return;
  status.classList.remove("status-connecting", "status-live", "status-disconnected");
  status.classList.add(`status-${state}`);
}

async function refresh(signal?: AbortSignal) {
  try {
    const data = await fetchSummary(signal ? { signal } : {});
    document.body.classList.remove("is-loading");
    setStatusState("live");
    latestSummaryData = data;
    const summary = data.summary;
    metric("sessions", summary.sessions);
    metric("events", summary.event_count);
    metric("model-calls", summary.event_types.model_call || 0);
    metric("tokens", summary.tokens.total_tokens || 0);
    renderMetricChart("daily-chart", data.daily, "day", "daily-chart-insight");
    renderMetricChart("hourly-chart", data.hourly, "hour", "hourly-chart-insight");
    renderModelDistribution(summary.models);
    renderAppLegend(summary.sources);
    renderBars("tools", summary.tools, {
      descriptions: summary.descriptions,
      insightId: "tools-insight",
      noun: "tool",
      subject: "Harness surface",
    });
    renderBars("skills", summary.skills || {}, {
      descriptions: summary.descriptions,
      insightId: "skills-insight",
      noun: "skill",
      subject: "Field-agent pattern",
    });
    renderBars("executables", summary.executables || summary.clis, {
      descriptions: summary.descriptions,
      insightId: "executables-insight",
      noun: "executable",
      subject: "Command substrate",
    });
    renderModelProfiles(data.model_profiles);
    renderSessions(data.recent_sessions);
    const updatedAt = new Date(data.generated_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    text("status", `Live · updated ${updatedAt}`);
  } catch (error) {
    if (isAbortError(error)) return;
    setStatusState("disconnected");
    text("status", "Disconnected");
  }
}

function renderMetricChart(
  id: ChartId,
  points: DailySummary[],
  labelKey: "day" | "hour",
  insightId: string,
) {
  const mode = chartModes[id];
  const config = chartMetricConfig[id][mode];
  if (!config) return;
  renderChart(id, points, config.value, config.color, config.color, labelKey, {
    insightId,
    labelKey,
    unit: config.unit,
    subject: config.subject,
    xAxis: labelKey === "day" ? "day" : "hour",
  });
  queryAll<HTMLElement>(`[data-chart-mode="${id}"]`).forEach((button) => {
    button.classList.toggle("active", datasetValue(button, "chartValue") === mode);
    (button.closest(".ops-card") as HTMLElement | null)?.style.setProperty(
      "--ops-color",
      config.color,
    );
  });
}

function renderChangedMetricChart(id: ChartId) {
  if (!latestSummaryData) {
    void refresh();
    return;
  }
  if (id === "daily-chart") {
    renderMetricChart(id, latestSummaryData.daily, "day", "daily-chart-insight");
    return;
  }
  if (id === "hourly-chart") {
    renderMetricChart(id, latestSummaryData.hourly, "hour", "hourly-chart-insight");
  }
}

async function refreshLive(signal?: AbortSignal) {
  try {
    renderLive(await fetchLive(signal ? { signal } : {}));
  } catch (error) {
    if (isAbortError(error)) return;
    renderLiveError();
  }
}

playIntro();
startPolling(refresh, { intervalMs: summaryPollMs });
startPolling(refreshLive, { intervalMs: livePollMs });
startDebugReloadPolling(() => {
  void refresh();
  void refreshLive();
});
initSectionToggles();
queryAll<HTMLElement>("[data-chart-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    const chartId = datasetValue(button, "chartMode");
    if (!isChartId(chartId)) return;
    const nextMode = datasetValue(button, "chartValue");
    if (chartModes[chartId] === nextMode) return;
    if (!isChartModeFor(chartId, nextMode)) return;
    chartModes[chartId] = nextMode;
    const chart = optionalElement(chartId);
    chart?.classList.add("chart-tab-switch");
    const card = chart?.closest(".ops-card");
    if (card) {
      const fadeTargets = card.querySelectorAll<HTMLElement>(
        ".insight-line, .chart-head .eyebrow, .metric-toggle",
      );
      fadeTargets.forEach((node) => {
        node.classList.remove("chart-tab-fade");
        void node.offsetWidth;
        node.classList.add("chart-tab-fade");
      });
    }
    renderChangedMetricChart(chartId);
  });
});
