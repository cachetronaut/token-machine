export const fmt = new Intl.NumberFormat();

export function text(id, value) {
  document.getElementById(id).textContent = value;
}

export function compactNumber(value) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`;
  if (Math.abs(number) >= 10_000) return `${(number / 1_000).toFixed(1)}K`;
  return fmt.format(number);
}

export function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (value < 0) return "n/a";
  if (!value) return "0s";
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.round(value / 60)}m`;
  const hours = Math.floor(value / 3600);
  const minutes = Math.round((value % 3600) / 60);
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function metric(id, value) {
  const element = document.getElementById(id);
  const nextValue = compactNumber(value);
  if (element.dataset.ready === "true" && element.textContent !== nextValue) {
    element.classList.remove("metric-value-refresh");
    void element.offsetWidth;
    element.classList.add("metric-value-refresh");
  }
  element.textContent = nextValue;
  element.dataset.ready = "true";
  element.title = fmt.format(value || 0);
}

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

export function projectName(path) {
  if (!path) return "";
  const parts = String(path).split("/").filter(Boolean);
  return parts.length ? `/${parts[parts.length - 1]}` : path;
}

export function topEntries(values, limit = 8) {
  return Object.entries(values || {}).sort((a, b) => b[1] - a[1]).slice(0, limit);
}

export function colorFor(value) {
  const fallbackPalette = ["#43c7b7", "#f6c453", "#ff7f6e", "#6ba6ff", "#b48cff", "#75d66f", "#f28fb5", "#9bc8ff"];
  let hash = 0;
  for (const char of String(value || "")) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return fallbackPalette[hash % fallbackPalette.length];
}
