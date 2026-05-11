export const pollMs = 5000;

export async function fetchSummary() {
  const response = await fetch("/api/summary", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`summary request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchLive() {
  const response = await fetch("/api/live", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`live request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchReloadState() {
  const response = await fetch("/api/debug/reload", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`reload state request failed: ${response.status}`);
  }
  return response.json();
}

export function startPolling(callback) {
  callback();
  return window.setInterval(callback, pollMs);
}

export function startDebugReloadPolling(onChange) {
  if (!window.location.hostname.match(/^(localhost|127\.0\.0\.1|0\.0\.0\.0)$/)) {
    return null;
  }

  let lastToken = "";
  async function checkReload() {
    try {
      const state = await fetchReloadState();
      if (!lastToken) {
        lastToken = state.reload_token || "";
        return;
      }
      if (state.reload_token && state.reload_token !== lastToken) {
        lastToken = state.reload_token;
        refreshStylesheets(state.reload_token);
        if (onChange) onChange(state);
      }
    } catch {
      // Debug reload is best-effort and should not interrupt dashboard polling.
    }
  }

  checkReload();
  return window.setInterval(checkReload, pollMs);
}

function refreshStylesheets(token) {
  document.querySelectorAll('link[rel="stylesheet"]').forEach((link) => {
    const href = new URL(link.href);
    if (!href.pathname.startsWith("/assets/css/")) return;
    href.searchParams.set("v", token);
    link.href = href.toString();
  });
}
