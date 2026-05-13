import { escapeHtml } from "./format.js";

export function appDisplayName(source) {
  const value = String(source || "unknown").toLowerCase();
  if (value === "codex") return "Codex CLI";
  if (value === "claudecode" || value === "claude") return "Claude Code";
  if (value === "gemini") return "Gemini CLI";
  if (value === "opencode") return "OpenCode";
  if (value === "zed") return "Zed";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function sourceIconName(source) {
  const key = String(source || "").toLowerCase();
  if (key.includes("codex")) return "codex.svg";
  if (key.includes("claudecode") || key.includes("claude")) return "claudecode.svg";
  if (key.includes("gemini")) return "geminicli.svg";
  if (key.includes("opencode")) return "opencode.svg";
  if (key.includes("zed")) return "zed.svg";
  if (key.includes("openai")) return "openai.svg";
  return "";
}

export function modelIconName(row) {
  const key = String(row.model || "").toLowerCase();
  if (key.includes("claude")) return "claude.svg";
  if (key.includes("gemini")) return "gemini.svg";
  if (key.includes("qwen")) return "qwen.svg";
  if (key.includes("deepseek")) return "deepseek.svg";
  if (key.includes("llama") || key.includes("meta")) return "meta.svg";
  if (key.includes("mistral") || key.includes("mixtral")) return "mistral.svg";
  if (key.includes("grok") || key.includes("x-ai") || key.includes("xai")) {
    return "xai.svg";
  }
  if (key.includes("cohere") || key.includes("command-r")) return "cohere.svg";
  if (key.includes("perplexity") || key.includes("sonar")) return "perplexity.svg";
  if (key.includes("kimi") || key.includes("moonshot")) return "moonshot.svg";
  if (key.includes("gpt") || key.includes("openai")) return "openai.svg";
  if (key.includes("opencode") || row.source === "opencode") return "opencode.svg";
  if (key.includes("openrouter") || row.source === "zed") return "openrouter.svg";
  return "";
}

export function modelInitials(row) {
  const key = String(row.model || "").toLowerCase();
  if (key.includes("opencode") || row.source === "opencode") return "OC";
  if (key.includes("openrouter") || row.source === "zed") return "OR";
  if (row.model_family === "OpenAI") return "AI";
  if (row.model_family === "Claude") return "C";
  if (row.model_family === "Gemini") return "G";
  if (row.model_family === "Qwen") return "Q";
  return "?";
}

export function iconUrl(name) {
  return `/assets/icons/${encodeURIComponent(name)}`;
}

export function iconClassName(name, baseClass) {
  const key = String(name || "").toLowerCase();
  const contrastClass =
    key === "openai.svg" || key === "openrouter.svg" || key === "opencode.svg"
      ? " icon-on-dark"
      : "";
  return `${baseClass}${contrastClass}`;
}

export function renderAppIcon(source) {
  const icon = sourceIconName(source);
  if (!icon) return '<span class="app-dot"></span>';
  return `<img class="${iconClassName(icon, "app-icon")}" src="${iconUrl(icon)}" alt="" loading="lazy" decoding="async" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="app-dot" hidden></span>`;
}

export function renderModelIcon(row) {
  const initials = escapeHtml(modelInitials(row));
  const icon = modelIconName(row);
  if (!icon) return `<div class="model-glyph">${initials}</div>`;
  return `<img class="${iconClassName(icon, "model-icon")}" src="${iconUrl(icon)}" alt="" loading="lazy" decoding="async" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><div class="model-glyph" hidden>${initials}</div>`;
}

export function renderModelBadgeIcon(row) {
  const initials = escapeHtml(modelInitials(row));
  const icon = modelIconName(row);
  if (!icon) return `<span class="provider-glyph">${initials}</span>`;
  return `<img class="${iconClassName(icon, "provider-icon")}" src="${iconUrl(icon)}" alt="" loading="lazy" decoding="async" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="provider-glyph" hidden>${initials}</span>`;
}
