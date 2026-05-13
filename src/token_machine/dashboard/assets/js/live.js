import { appColor } from "./charts.js";
import { compactNumber, escapeHtml, fmt, projectName } from "./format.js";
import { appDisplayName, renderAppIcon } from "./icons.js";

let liveDisclosureReady = false;
let liveToolsPrimed = false;
const knownLiveTools = new Set();

export function renderLive(data) {
  ensureLiveDisclosure();
  const lanesRoot = document.getElementById("live-lanes");
  const snapshots = (data.snapshots || []).slice().sort(compareSnapshots);
  const activeSnapshots = snapshots.filter((snapshot) => snapshot.status === "active");
  const totals = summarize(snapshots);
  const signature = liveSignature(snapshots);

  setText("live-active", data.active_count || activeSnapshots.length);
  setText("live-queries", totals.queries);
  setText("live-tools", totals.tools);
  setText("live-agents", totals.subagents);
  setText("live-tokens", compactNumber(totals.tokens));
  setStatusLine(data, activeSnapshots, snapshots);

  if (!snapshots.length) {
    updateLanes(lanesRoot, '<div class="live-empty">No live sessions detected</div>', signature);
    commitRenderedToolKeys(snapshots);
    return;
  }

  updateLanes(lanesRoot, snapshots.slice(0, 8).map(renderLane).join(""), signature);
  commitRenderedToolKeys(snapshots);
}

export function renderLiveError() {
  ensureLiveDisclosure();
  setText("live-active", "0");
  setText("live-queries", "0");
  setText("live-tools", "0");
  setText("live-agents", "0");
  setText("live-tokens", "0");
  setText("live-subline", "Live probe disconnected");
  const led = document.getElementById("live-led");
  if (led) led.className = "live-led live-led-error";
  const lanesRoot = document.getElementById("live-lanes");
  lanesRoot.innerHTML = '<div class="live-empty">Live endpoint unavailable</div>';
}

function summarize(snapshots) {
  return snapshots.reduce(
    (total, snapshot) => ({
      queries: total.queries + Number(snapshot.user_queries?.count || 0),
      tools: total.tools + liveActions(snapshot).length,
      subagents: total.subagents + snapshotSubagentCount(snapshot),
      tokens: total.tokens + sessionTokens(snapshot),
    }),
    { queries: 0, tools: 0, subagents: 0, tokens: 0 },
  );
}

function setStatusLine(data, activeSnapshots, snapshots) {
  const led = document.getElementById("live-led");
  if (led) {
    led.className = `live-led ${activeSnapshots.length ? "" : "live-led-idle"}`.trim();
  }

  const generatedAt = data.generated_at
    ? new Date(data.generated_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
  const activeApps = [...new Set(activeSnapshots.map((item) => appDisplayName(item.source)))]
    .slice(0, 3)
    .join(" / ");
  const staleCount = Number(data.stale_count || 0);
  const parts = [];
  if (activeSnapshots.length) parts.push(`${fmt.format(activeSnapshots.length)} active`);
  if (activeApps) parts.push(activeApps);
  if (staleCount) parts.push(`${fmt.format(staleCount)} stale`);
  if (!parts.length && snapshots.length) parts.push("No active sessions");
  if (!parts.length) parts.push("Awaiting sessions");
  if (generatedAt) parts.push(`updated ${generatedAt}`);
  setText("live-subline", parts.join(" · "));
}

function renderLane(snapshot) {
  const color = appColor(snapshot.source);
  const context = snapshot.context || {};
  const contextPercent = Number(context.used_percent || 0);
  const hasWindow = Number(context.window_tokens || 0) > 0;
  const usedTokens = Number(context.used_tokens || 0);
  const contextLabel = contextUsageLabel(context);
  const width = hasWindow ? Math.max(3, Math.min(100, contextPercent)) : 0;
  const level = contextLevel(contextPercent, hasWindow);
  const sourceName = appDisplayName(snapshot.source);
  const model = snapshot.model || "model pending";
  const sessionName = snapshot.session_name || snapshot.session_id || "session pending";
  const project = projectName(snapshot.project_path) || "workspace pending";
  const tools = liveActions(snapshot);
  const subagents = snapshotSubagentCount(snapshot);
  const sessionLimits = sessionUsageLimits(snapshot);
  const compaction = snapshot.compaction || {};
  const status = snapshot.status || "missing";

  return `
    <article class="live-lane live-lane-${escapeHtml(status)}" style="--live-color:${color}">
      <div class="live-lane-head">
        <div class="live-source">
          <span class="live-source-icon">${renderAppIcon(snapshot.source)}</span>
          <span>${escapeHtml(sourceName)}</span>
        </div>
        <span class="live-state live-state-${escapeHtml(status)}" aria-label="${escapeHtml(status)}" title="${escapeHtml(status)}"></span>
      </div>
      <div class="live-model" title="${escapeHtml(model)}">${escapeHtml(model)}</div>
      <div class="live-session" title="${escapeHtml(snapshot.session_id || "")}">${escapeHtml(sessionName)}</div>
      <div class="live-project" title="${escapeHtml(snapshot.project_path || "")}">${escapeHtml(project)}</div>
      <div class="live-signal-row">
        <span class="live-signal">tools ${compactNumber(tools.length)}</span>
        <span class="live-signal ${subagents ? "live-signal-hot" : ""}">agents ${compactNumber(subagents)}</span>
        ${compaction.count ? `<span class="live-signal live-signal-compact" title="${escapeHtml(compactionTitle(compaction))}">compact ${compactNumber(compaction.count)}</span>` : ""}
      </div>
      <div class="live-context-row">
        <span>context</span>
        <strong>${escapeHtml(contextLabel)}</strong>
      </div>
      <div class="live-context-track ${level}" title="${escapeHtml(contextTitle(context))}">
        <div class="live-context-fill" style="width:${width}%"></div>
      </div>
      <div class="live-microgrid">
        <div><span>prompts</span><strong>${compactNumber(snapshot.user_queries?.count || 0)}</strong></div>
        <div><span>latest</span><strong>${compactNumber(snapshot.current_metrics?.latest_turn_tokens || 0)}</strong></div>
        <div><span>session</span><strong>${compactNumber(sessionTokens(snapshot))}</strong></div>
      </div>
      ${renderSessionLimits(sessionLimits)}
      ${renderTools(tools, snapshot)}
    </article>
  `;
}

function renderSessionLimits(sessionLimits) {
  if (!sessionLimits.length) return "";
  return `
    <div class="live-rate-row">
      ${sessionLimits
        .slice(0, 3)
        .map((limit) => {
          const name = limitDisplayName(limit.name || "limit");
          const percent = Number(limit.used_percent || 0);
          const remaining = Number(limit.remaining_percent || Math.max(0, 100 - percent));
          return `
            <span class="live-rate" title="${escapeHtml(limitTitle(limit))}">
              <span>${escapeHtml(name)}</span>
              <strong>${fmt.format(remaining)}% left</strong>
              ${limit.resets_at ? `<em>${escapeHtml(resetLabel(limit.resets_at))}</em>` : ""}
            </span>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderTools(tools, snapshot) {
  if (!tools.length) {
    return '<div class="live-tools-empty">No live tools</div>';
  }
  const orderedTools = tools.slice().sort(compareTools);
  const toolKeys = orderedTools.map((tool) => liveToolKey(snapshot, tool));
  return `
    <div class="live-tools" aria-label="Live tool calls">
      ${orderedTools
        .map((tool, index) => {
          const command = tool.command || "";
          const kind = tool.kind || "tool";
          const executable = tool.executable || "";
          const label = command ? commandLabel(command) : executable || tool.name || kind;
          const subagentClass = isSubagentTool(tool) ? " live-tool-agent" : "";
          const kindClass = ["tool", "skill", "command"].includes(kind)
            ? ` live-tool-${kind}`
            : " live-tool-tool";
          const key = toolKeys[index];
          const newClass = liveToolsPrimed && !knownLiveTools.has(key) ? " live-tool-new" : "";
          const currentClass = index === 0 ? " live-tool-current" : "";
          return `
            <div class="live-tool${kindClass}${subagentClass}${currentClass}${newClass}" title="${escapeHtml(toolTitle(tool))}" style="--tool-index:${index}">
              <span class="live-tool-dot" aria-hidden="true"></span>
              <div class="live-tool-copy">
                <span>${escapeHtml(kindLabel(kind, tool.name || executable || "tool"))}</span>
                <strong>${escapeHtml(label)}</strong>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function commitRenderedToolKeys(snapshots) {
  for (const snapshot of snapshots) {
    for (const tool of snapshot.live_tool_calls || []) {
      knownLiveTools.add(liveToolKey(snapshot, tool));
    }
  }
  liveToolsPrimed = true;
}

function liveToolKey(snapshot, tool) {
  return [
    snapshot.session_id,
    snapshot.source,
    tool.name,
    tool.command,
    tool.status,
    tool.updated_at,
  ].join("::");
}

function compareTools(a, b) {
  const delta = Date.parse(b.updated_at || "") - Date.parse(a.updated_at || "");
  if (!Number.isNaN(delta) && delta) return delta;
  return String(b.command || b.name || "").localeCompare(String(a.command || a.name || ""));
}

function commandLabel(command) {
  const value = String(command || "").replace(/\s+/g, " ").trim();
  return value.length > 72 ? `${value.slice(0, 69)}...` : value;
}

function contextTitle(context) {
  const used = Number(context.used_tokens || 0);
  const windowTokens = Number(context.window_tokens || 0);
  const origin = context.origin || "missing";
  if (!used && !windowTokens) return `origin: ${origin}`;
  return `${fmt.format(used)} used / ${fmt.format(windowTokens)} window · origin: ${origin}`;
}

function limitTitle(limit) {
  const parts = [limit.origin, limit.resets_at ? `resets ${resetLabel(limit.resets_at)}` : ""].filter(Boolean);
  return parts.join(" · ") || limit.name || "rate limit";
}

function toolTitle(tool) {
  return [tool.kind, tool.status, tool.executable, tool.command, tool.updated_at]
    .filter(Boolean)
    .join(" · ");
}

function kindLabel(kind, name) {
  if (kind === "skill") return `skill ${name}`;
  if (kind === "command") return `exec ${name}`;
  return name;
}

function contextLevel(percent, hasWindow) {
  if (!hasWindow) return "live-context-missing";
  if (percent >= 95) return "live-context-critical";
  if (percent >= 75) return "live-context-warn";
  return "live-context-ok";
}

function sessionUsageLimits(snapshot) {
  if (Array.isArray(snapshot.session_limits) && snapshot.session_limits.length) {
    return snapshot.session_limits;
  }
  return (snapshot.rate_limits || []).map((limit) => ({
    ...limit,
    remaining_percent: Math.max(0, 100 - Number(limit.used_percent || 0)),
  }));
}

function contextUsageLabel(context) {
  const percent = Number(context.used_percent || 0);
  const windowTokens = Number(context.window_tokens || 0);
  const usedTokens = Number(context.used_tokens || 0);
  const computedUsed = !usedTokens && percent && windowTokens ? Math.round((windowTokens * percent) / 100) : 0;
  const amount = usedTokens || computedUsed;
  if (amount && percent) return `${compactNumber(amount)} (${fmt.format(percent)}%)`;
  if (amount) return compactNumber(amount);
  if (percent) return `${fmt.format(percent)}%`;
  return "n/a";
}

function limitDisplayName(name) {
  const key = String(name || "").toLowerCase().replace(/[\s-]+/g, "_");
  if (["primary", "five_hour", "5h", "current"].includes(key)) return "current";
  if (["secondary", "seven_day", "7d", "weekly"].includes(key)) return "weekly";
  return name || "limit";
}

function resetLabel(value) {
  const raw = Number(value);
  const resetMs = raw > 10_000_000_000 ? raw : raw * 1000;
  if (!raw || Number.isNaN(resetMs)) return String(value);
  const seconds = Math.max(0, Math.round((resetMs - Date.now()) / 1000));
  if (seconds < 60) return "<1m";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86_400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  const days = Math.floor(seconds / 86_400);
  const hours = Math.round((seconds % 86_400) / 3600);
  return hours ? `${days}d ${hours}h` : `${days}d`;
}

function compactionTitle(compaction) {
  const parts = [
    compaction.trigger || "compacted",
    compaction.last_at || "",
    compaction.pre_tokens ? `${compactNumber(compaction.pre_tokens)} before` : "",
    compaction.post_tokens ? `${compactNumber(compaction.post_tokens)} after` : "",
  ];
  return parts.filter(Boolean).join(" · ");
}

function updateLanes(root, html, signature) {
  if (root.dataset.liveSignature === signature) return;
  root.dataset.liveSignature = signature;
  root.innerHTML = html;
  root.classList.remove("live-lanes-updated");
  window.requestAnimationFrame(() => {
    root.classList.add("live-lanes-updated");
  });
}

function ensureLiveDisclosure() {
  if (liveDisclosureReady) return;
  const consoleRoot = document.getElementById("live-console");
  const toggle = document.getElementById("live-toggle");
  if (!consoleRoot || !toggle) return;
  liveDisclosureReady = true;
  toggle.addEventListener("click", () => {
    const isOpen = consoleRoot.classList.toggle("live-open");
    consoleRoot.classList.toggle("live-collapsed", !isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
  });
}

function liveSignature(snapshots) {
  return snapshots
    .slice(0, 8)
    .map((snapshot) =>
      [
        snapshot.source,
        snapshot.session_id,
        snapshot.session_name,
        snapshot.status,
        snapshot.updated_at,
        snapshot.model,
        snapshot.context?.used_percent,
        snapshot.context?.used_tokens,
        snapshot.user_queries?.count,
        snapshot.current_metrics?.latest_turn_tokens,
        snapshot.current_metrics?.session_total_tokens,
        (snapshot.session_limits || [])
          .map((limit) => [limit.name, limit.used_percent, limit.remaining_percent, limit.resets_at].join(":"))
          .join("|"),
        [
          snapshot.compaction?.count,
          snapshot.compaction?.last_at,
          snapshot.compaction?.trigger,
          snapshot.compaction?.pre_tokens,
          snapshot.compaction?.post_tokens,
        ].join(":"),
        liveActions(snapshot)
          .map((tool) => [tool.name, tool.status, tool.command, tool.updated_at].join(":"))
          .join("|"),
      ].join("~"),
    )
    .join("||");
}

function subagentCount(tools) {
  return tools.filter(isSubagentTool).length;
}

function snapshotSubagentCount(snapshot) {
  return Math.max(
    subagentCount(liveActions(snapshot)),
    Number(snapshot.current_metrics?.subagent_sessions || 0),
  );
}

function isSubagentTool(tool) {
  const name = String(tool.name || "").toLowerCase();
  return [
    "spawn_agent",
    "send_input",
    "wait_agent",
    "close_agent",
    "resume_agent",
    "task",
  ].includes(name);
}

function liveActions(snapshot) {
  return snapshot.live_actions || snapshot.live_tool_calls || [];
}

function sessionTokens(snapshot) {
  return Number(
    snapshot.current_metrics?.session_total_tokens ||
      snapshot.token_usage?.total_tokens ||
      snapshot.current_metrics?.latest_turn_tokens ||
      0,
  );
}

function compareSnapshots(a, b) {
  const statusRank = { active: 0, stale: 1, error: 2, missing: 3 };
  const statusDelta = (statusRank[a.status] ?? 4) - (statusRank[b.status] ?? 4);
  if (statusDelta) return statusDelta;
  return timestamp(b) - timestamp(a);
}

function timestamp(snapshot) {
  const raw = snapshot.updated_at || snapshot.observed_at || "";
  const value = Date.parse(raw);
  return Number.isNaN(value) ? 0 : value;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}
