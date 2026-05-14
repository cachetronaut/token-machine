export const fmt = new Intl.NumberFormat();

import { optionalElement, setText } from "./dom.js";
import type { CountMap } from "./types.js";

export function text(id: string, value: string) {
  setText(id, value);
}

export function compactNumber(value: number | string | null | undefined) {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`;
  if (Math.abs(number) >= 10_000) return `${(number / 1_000).toFixed(1)}K`;
  return fmt.format(number);
}

export function formatDuration(seconds: number | string | null | undefined) {
  const value = Number(seconds || 0);
  if (value < 0) return "n/a";
  if (!value) return "0s";
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.round(value / 60)}m`;
  const hours = Math.floor(value / 3600);
  const minutes = Math.round((value % 3600) / 60);
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

const METRIC_TICK_DURATION = 880;
const reduceMotion =
  typeof window !== "undefined" && window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

export function metric(id: string, value: number | string | null | undefined) {
  const element = optionalElement(id);
  if (!element) return;
  const target = Number(value || 0);
  element.title = fmt.format(target);
  const initial = element.dataset.ready !== "true";
  const previous = Number.isFinite(element.__metricValue)
    ? Number(element.__metricValue)
    : initial
      ? 0
      : target;
  element.__metricValue = target;
  if (initial || reduceMotion || previous === target) {
    if (element.__metricRaf) cancelAnimationFrame(element.__metricRaf);
    element.__metricRaf = null;
    element.textContent = compactNumber(target);
    element.dataset.ready = "true";
    return;
  }
  element.dataset.ready = "true";
  if (element.__metricRaf) cancelAnimationFrame(element.__metricRaf);
  const start = performance.now();
  const delta = target - previous;
  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / METRIC_TICK_DURATION);
    const eased = 1 - (1 - t) ** 4;
    const current = previous + delta * eased;
    element.textContent = compactNumber(current);
    if (t < 1) {
      element.__metricRaf = requestAnimationFrame(tick);
    } else {
      element.__metricRaf = null;
      element.textContent = compactNumber(target);
      element.classList.remove("metric-value-tick");
      void element.offsetWidth;
      element.classList.add("metric-value-tick");
    }
  };
  element.__metricRaf = requestAnimationFrame(tick);
}

export function escapeHtml(value: unknown) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char] || char,
  );
}

export function projectName(path: string | null | undefined) {
  if (!path) return "";
  const parts = String(path).split("/").filter(Boolean);
  return parts.length ? `/${parts[parts.length - 1]}` : path;
}

export function topEntries(values: CountMap | null | undefined, limit = 8) {
  return Object.entries(values || {})
    .map(([key, value]) => [key, Number(value || 0)] as [string, number])
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

export function colorFor(value: string | null | undefined) {
  const fallbackPalette = [
    "#43c7b7",
    "#f6c453",
    "#ff7f6e",
    "#6ba6ff",
    "#b48cff",
    "#75d66f",
    "#f28fb5",
    "#9bc8ff",
  ];
  let hash = 0;
  for (const char of String(value || "")) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return fallbackPalette[hash % fallbackPalette.length];
}
