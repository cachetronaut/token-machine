export const livePollMs = 5000;
export const summaryPollMs = 60000;
export const reloadPollMs = 30000;
function isAbortError(error) {
    return error instanceof DOMException && error.name === "AbortError";
}
function isRecord(payload) {
    return typeof payload === "object" && payload !== null && !Array.isArray(payload);
}
function assertRecord(payload, label) {
    if (!isRecord(payload)) {
        throw new Error(`${label} payload must be an object`);
    }
}
function assertArray(payload, label) {
    if (!Array.isArray(payload)) {
        throw new Error(`${label} payload must be an array`);
    }
}
function assertString(payload, label) {
    if (typeof payload !== "string") {
        throw new Error(`${label} payload must be a string`);
    }
}
function assertNumber(payload, label) {
    if (typeof payload !== "number") {
        throw new Error(`${label} payload must be a number`);
    }
}
async function readJson(response, validator, endpoint) {
    const payload = await response.json();
    try {
        validator(payload);
    }
    catch (error) {
        if (error instanceof Error) {
            throw new Error(`${endpoint} contract mismatch: ${error.message}`);
        }
        throw error;
    }
    return payload;
}
function assertTokenUsage(payload, label) {
    assertRecord(payload, label);
    assertNumber(payload.input_tokens, `${label}.input_tokens`);
    assertNumber(payload.cached_input_tokens, `${label}.cached_input_tokens`);
    assertNumber(payload.cache_creation_input_tokens, `${label}.cache_creation_input_tokens`);
    assertNumber(payload.output_tokens, `${label}.output_tokens`);
    assertNumber(payload.reasoning_output_tokens, `${label}.reasoning_output_tokens`);
    assertNumber(payload.total_tokens, `${label}.total_tokens`);
}
function assertDashboardSummary(payload, label) {
    assertRecord(payload, label);
    assertString(payload.generated_at, `${label}.generated_at`);
    assertNumber(payload.event_count, `${label}.event_count`);
    assertNumber(payload.sessions, `${label}.sessions`);
    assertNumber(payload.skill_calls, `${label}.skill_calls`);
    assertNumber(payload.command_calls, `${label}.command_calls`);
    assertRecord(payload.sources, `${label}.sources`);
    assertRecord(payload.models, `${label}.models`);
    assertRecord(payload.tools, `${label}.tools`);
    assertRecord(payload.skills, `${label}.skills`);
    assertRecord(payload.executables, `${label}.executables`);
    assertRecord(payload.clis, `${label}.clis`);
    assertRecord(payload.event_types, `${label}.event_types`);
    assertRecord(payload.descriptions, `${label}.descriptions`);
    assertTokenUsage(payload.tokens, `${label}.tokens`);
}
function assertDailySummary(payload, label) {
    assertRecord(payload, label);
    assertString(payload.day, `${label}.day`);
    if (payload.hour !== undefined)
        assertString(payload.hour, `${label}.hour`);
    assertDashboardSummary(payload.summary, `${label}.summary`);
}
function assertDashboardData(payload) {
    assertRecord(payload, "summary");
    assertString(payload.generated_at, "summary.generated_at");
    assertDashboardSummary(payload.summary, "summary.summary");
    assertArray(payload.daily, "summary.daily");
    payload.daily.forEach((item, index) => {
        assertDailySummary(item, `summary.daily[${index}]`);
    });
    assertArray(payload.hourly, "summary.hourly");
    payload.hourly.forEach((item, index) => {
        assertDailySummary(item, `summary.hourly[${index}]`);
    });
    assertArray(payload.model_profiles, "summary.model_profiles");
    assertArray(payload.recent_sessions, "summary.recent_sessions");
}
function assertLiveToolCall(payload, label) {
    assertRecord(payload, label);
    assertString(payload.name, `${label}.name`);
    assertString(payload.status, `${label}.status`);
    assertString(payload.command, `${label}.command`);
    assertString(payload.kind, `${label}.kind`);
    assertString(payload.executable, `${label}.executable`);
    assertString(payload.started_at, `${label}.started_at`);
    assertString(payload.updated_at, `${label}.updated_at`);
}
function assertLiveSnapshot(payload, label) {
    assertRecord(payload, label);
    assertString(payload.source, `${label}.source`);
    assertString(payload.session_id, `${label}.session_id`);
    assertString(payload.source_path, `${label}.source_path`);
    assertString(payload.status, `${label}.status`);
    assertRecord(payload.context, `${label}.context`);
    assertRecord(payload.current_metrics, `${label}.current_metrics`);
    assertArray(payload.live_tool_calls, `${label}.live_tool_calls`);
    payload.live_tool_calls.forEach((item, index) => {
        assertLiveToolCall(item, `${label}.live_tool_calls[${index}]`);
    });
    assertArray(payload.live_actions, `${label}.live_actions`);
    payload.live_actions.forEach((item, index) => {
        assertLiveToolCall(item, `${label}.live_actions[${index}]`);
    });
    assertArray(payload.rate_limits, `${label}.rate_limits`);
    assertArray(payload.session_limits, `${label}.session_limits`);
    assertRecord(payload.compaction, `${label}.compaction`);
    assertTokenUsage(payload.token_usage, `${label}.token_usage`);
}
function assertLiveData(payload) {
    assertRecord(payload, "live");
    assertString(payload.generated_at, "live.generated_at");
    assertNumber(payload.active_count, "live.active_count");
    assertNumber(payload.stale_count, "live.stale_count");
    assertArray(payload.snapshots, "live.snapshots");
    payload.snapshots.forEach((item, index) => {
        assertLiveSnapshot(item, `live.snapshots[${index}]`);
    });
}
function assertReloadState(payload) {
    assertRecord(payload, "reload");
    if (payload.reload_token !== undefined)
        assertString(payload.reload_token, "reload.reload_token");
    if (payload.css_reload_token !== undefined) {
        assertString(payload.css_reload_token, "reload.css_reload_token");
    }
    if (payload.script_reload_token !== undefined) {
        assertString(payload.script_reload_token, "reload.script_reload_token");
    }
}
export async function fetchSummary(options = {}) {
    const response = await fetch("/api/summary", { cache: "no-store", ...options });
    if (!response.ok) {
        throw new Error(`summary request failed: ${response.status}`);
    }
    return readJson(response, assertDashboardData, "/api/summary");
}
export async function fetchLive(options = {}) {
    const response = await fetch("/api/live", { cache: "no-store", ...options });
    if (!response.ok) {
        throw new Error(`live request failed: ${response.status}`);
    }
    return readJson(response, assertLiveData, "/api/live");
}
export async function fetchReloadState(options = {}) {
    const response = await fetch("/api/debug/reload", { cache: "no-store", ...options });
    if (!response.ok) {
        throw new Error(`reload state request failed: ${response.status}`);
    }
    return readJson(response, assertReloadState, "/api/debug/reload");
}
export function startPolling(callback, { intervalMs = livePollMs } = {}) {
    let stopped = false;
    let running = false;
    let controller = null;
    async function tick() {
        if (stopped || running || document.visibilityState === "hidden")
            return;
        running = true;
        controller = new AbortController();
        try {
            await callback(controller.signal);
        }
        catch (error) {
            if (!isAbortError(error))
                throw error;
        }
        finally {
            running = false;
            controller = null;
        }
    }
    const interval = window.setInterval(tick, intervalMs);
    const stop = () => {
        stopped = true;
        window.clearInterval(interval);
        if (controller)
            controller.abort();
    };
    window.addEventListener("pagehide", stop, { once: true });
    window.addEventListener("beforeunload", stop, { once: true });
    tick();
    return stop;
}
export function startDebugReloadPolling(onChange) {
    if (!window.location.hostname.match(/^(localhost|127\.0\.0\.1|0\.0\.0\.0)$/)) {
        return null;
    }
    let stopped = false;
    let running = false;
    let controller = null;
    let lastToken = "";
    let lastCssToken = "";
    let lastScriptToken = "";
    async function checkReload() {
        if (stopped || running || document.visibilityState === "hidden")
            return;
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
            if (state.script_reload_token &&
                lastScriptToken &&
                state.script_reload_token !== lastScriptToken) {
                window.location.reload();
                return;
            }
            if (state.css_reload_token && state.css_reload_token !== lastCssToken) {
                lastCssToken = state.css_reload_token;
                refreshStylesheets(state.css_reload_token);
            }
            if (state.reload_token && state.reload_token !== lastToken) {
                lastToken = state.reload_token;
                if (onChange)
                    onChange(state);
            }
        }
        catch {
            // Debug reload is best-effort and should not interrupt dashboard polling.
        }
        finally {
            running = false;
            controller = null;
        }
    }
    const interval = window.setInterval(checkReload, reloadPollMs);
    const stop = () => {
        stopped = true;
        window.clearInterval(interval);
        if (controller)
            controller.abort();
    };
    window.addEventListener("pagehide", stop, { once: true });
    window.addEventListener("beforeunload", stop, { once: true });
    checkReload();
    return stop;
}
function refreshStylesheets(token) {
    document.querySelectorAll('link[rel="stylesheet"]').forEach((link) => {
        const href = new URL(link.href);
        if (!href.pathname.startsWith("/assets/css/"))
            return;
        href.searchParams.set("v", token);
        link.href = href.toString();
    });
}
