import type { DashboardData, LiveData, ReloadState } from "./types.js";

export const livePollMs = 5000;
export const summaryPollMs = 60000;
export const reloadPollMs = 30000;

type FetchOptions = RequestInit & { signal?: AbortSignal };
type PollCallback = (signal: AbortSignal) => Promise<void> | void;
type StopPolling = () => void;

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function fetchSummary(options: FetchOptions = {}): Promise<DashboardData> {
  const response = await fetch("/api/summary", { cache: "no-store", ...options });
  if (!response.ok) {
    throw new Error(`summary request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchLive(options: FetchOptions = {}): Promise<LiveData> {
  const response = await fetch("/api/live", { cache: "no-store", ...options });
  if (!response.ok) {
    throw new Error(`live request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchReloadState(options: FetchOptions = {}): Promise<ReloadState> {
  const response = await fetch("/api/debug/reload", { cache: "no-store", ...options });
  if (!response.ok) {
    throw new Error(`reload state request failed: ${response.status}`);
  }
  return response.json();
}

export function startPolling(
  callback: PollCallback,
  { intervalMs = livePollMs }: { intervalMs?: number } = {},
): StopPolling {
  let stopped = false;
  let running = false;
  let controller: AbortController | null = null;

  async function tick() {
    if (stopped || running || document.visibilityState === "hidden") return;
    running = true;
    controller = new AbortController();
    try {
      await callback(controller.signal);
    } catch (error: unknown) {
      if (!isAbortError(error)) throw error;
    } finally {
      running = false;
      controller = null;
    }
  }

  const interval = window.setInterval(tick, intervalMs);
  const stop = () => {
    stopped = true;
    window.clearInterval(interval);
    if (controller) controller.abort();
  };
  window.addEventListener("pagehide", stop, { once: true });
  window.addEventListener("beforeunload", stop, { once: true });
  tick();
  return stop;
}

export function startDebugReloadPolling(
  onChange: (state: ReloadState) => void,
): StopPolling | null {
  if (!window.location.hostname.match(/^(localhost|127\.0\.0\.1|0\.0\.0\.0)$/)) {
    return null;
  }

  let stopped = false;
  let running = false;
  let controller: AbortController | null = null;
  let lastToken = "";
  let lastCssToken = "";
  let lastScriptToken = "";
  async function checkReload() {
    if (stopped || running || document.visibilityState === "hidden") return;
    running = true;
    controller = new AbortController();
    try {
      const state = await fetchReloadState({ signal: controller.signal });
      if (!lastToken) {
        lastToken = state.reload_token || "";
        lastCssToken = state.css_reload_token || "";
        lastScriptToken = state.script_reload_token || "";
        return;
      }
      if (
        state.script_reload_token &&
        lastScriptToken &&
        state.script_reload_token !== lastScriptToken
      ) {
        window.location.reload();
        return;
      }
      if (state.css_reload_token && state.css_reload_token !== lastCssToken) {
        lastCssToken = state.css_reload_token;
        refreshStylesheets(state.css_reload_token);
      }
      if (state.reload_token && state.reload_token !== lastToken) {
        lastToken = state.reload_token;
        if (onChange) onChange(state);
      }
    } catch {
      // Debug reload is best-effort and should not interrupt dashboard polling.
    } finally {
      running = false;
      controller = null;
    }
  }

  const interval = window.setInterval(checkReload, reloadPollMs);
  const stop = () => {
    stopped = true;
    window.clearInterval(interval);
    if (controller) controller.abort();
  };
  window.addEventListener("pagehide", stop, { once: true });
  window.addEventListener("beforeunload", stop, { once: true });
  checkReload();
  return stop;
}

function refreshStylesheets(token: string): void {
  document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]').forEach((link) => {
    const href = new URL(link.href);
    if (!href.pathname.startsWith("/assets/css/")) return;
    href.searchParams.set("v", token);
    link.href = href.toString();
  });
}
