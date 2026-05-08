import { fetchSummary, startPolling } from "./api.js";
import { renderChart, renderModelDistribution } from "./charts.js";
import { metric, text } from "./format.js";
import { renderAppLegend, renderBars, renderModelProfiles } from "./models.js";
import { renderSessions } from "./sessions.js";

async function refresh() {
  try {
    const data = await fetchSummary();
    const summary = data.summary;
    metric("sessions", summary.sessions);
    metric("events", summary.event_count);
    metric("model-calls", summary.event_types.model_call || 0);
    metric("tokens", summary.tokens.total_tokens || 0);
    renderChart(
      "daily-chart",
      data.daily,
      (row) => row.summary?.tokens?.total_tokens || 0,
      "#43c7b7",
      "#43c7b7",
      "day",
    );
    renderChart(
      "hourly-chart",
      data.hourly,
      (row) => row.summary?.event_count || 0,
      "#f6c453",
      "#f6c453",
      "hour",
    );
    renderModelDistribution(summary.models);
    renderAppLegend(summary.sources);
    renderBars("tools", summary.tools, true, summary.descriptions);
    renderBars("clis", summary.clis, true, summary.descriptions);
    renderModelProfiles(data.model_profiles);
    renderSessions(data.recent_sessions);
    const updatedAt = new Date(data.generated_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    text("status", `Live · updated ${updatedAt}`);
  } catch (error) {
    text("status", "Disconnected");
  }
}

startPolling(refresh);
