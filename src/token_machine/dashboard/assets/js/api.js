export const pollMs = 5000;

export async function fetchSummary() {
  const response = await fetch("/api/summary", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`summary request failed: ${response.status}`);
  }
  return response.json();
}

export function startPolling(callback) {
  callback();
  return window.setInterval(callback, pollMs);
}
