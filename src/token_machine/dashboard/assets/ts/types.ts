export type CountMap = Record<string, number>;
export type TextMap = Record<string, string>;
export type JsonScalar = string | number | boolean | null;
export type JsonValue = JsonScalar | JsonValue[] | { [key: string]: JsonValue };

export interface TokenUsage {
  input_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
  total_tokens: number;
}

export interface DashboardSummary {
  generated_at: string;
  event_count: number;
  sessions: number;
  sources: CountMap;
  models: CountMap;
  skill_calls: number;
  command_calls: number;
  tools: CountMap;
  skills: CountMap;
  executables: CountMap;
  clis: CountMap;
  event_types: CountMap;
  tokens: TokenUsage;
  descriptions: TextMap;
}

export interface DailySummary {
  day: string;
  summary: DashboardSummary;
}

export interface ToolMixItem {
  category: string;
  count: number;
  percent: number;
  description?: string;
}

export interface ModelIntelligenceBadge {
  category: string;
  label: string;
  tier: number;
  score: number;
  metric: string;
}

export interface SessionRollup {
  session_id: string;
  source: string;
  source_path: string;
  project_path: string;
  started_at: string;
  ended_at: string;
  event_count: number;
  model_calls: number;
  tool_calls: number;
  skill_calls: number;
  command_calls: number;
  cli_commands: number;
  messages: number;
  models: CountMap;
  tools: CountMap;
  skills: CountMap;
  executables: CountMap;
  clis: CountMap;
  tokens: TokenUsage;
}

export interface SessionProfile {
  rollup: SessionRollup;
  duration_seconds: number;
  time_to_first_tool_seconds: number;
  time_to_first_edit_seconds: number;
  tool_mix: ToolMixItem[];
  workflow_role: string;
  scouting_report: string;
}

export interface ModelProfile {
  model: string;
  model_family: string;
  source: string;
  sources: CountMap;
  intelligence_level: string;
  intelligence_badges: ModelIntelligenceBadge[];
  reasoning_level: string;
  session_count: number;
  project_count: number;
  projects: Array<Record<string, JsonValue>>;
  model_calls: number;
  tool_calls: number;
  skill_calls: number;
  command_calls: number;
  cli_commands: number;
  tokens: TokenUsage;
  tools: CountMap;
  skills: CountMap;
  executables: CountMap;
  clis: CountMap;
  tool_mix: ToolMixItem[];
  workflow_role: string;
  scouting_report: string;
  stats: Record<string, number | string>;
}

export interface DashboardData {
  generated_at: string;
  summary: DashboardSummary;
  daily: DailySummary[];
  hourly: DailySummary[];
  model_profiles: ModelProfile[];
  recent_sessions: SessionProfile[];
}

export interface LiveContextWindow {
  window_tokens: number;
  used_tokens: number;
  used_percent: number;
  origin: string;
}

export interface LiveRateLimit {
  name: string;
  used_percent: number;
  remaining_percent?: number;
  resets_at: string;
  limit_id?: string;
  plan_type?: string;
  origin: string;
}

export interface LiveCompaction {
  count: number;
  last_at: string;
  trigger: string;
  pre_tokens: number;
  post_tokens: number;
  duration_ms: number;
  origin: string;
}

export interface LiveToolCall {
  name: string;
  status: string;
  command: string;
  kind: string;
  executable: string;
  started_at: string;
  updated_at: string;
}

export interface LiveUsageSnapshot {
  source: string;
  session_id: string;
  source_path: string;
  session_name: string;
  project_path: string;
  model: string;
  updated_at: string;
  observed_at: string;
  status: "active" | "stale" | "missing" | "error" | string;
  user_queries: Record<string, number | string>;
  context: LiveContextWindow;
  current_metrics: Record<string, number | string>;
  live_tool_calls: LiveToolCall[];
  live_actions: LiveToolCall[];
  rate_limits: LiveRateLimit[];
  session_limits: LiveRateLimit[];
  compaction: LiveCompaction;
  token_usage: TokenUsage;
  origin: string;
  error: string;
}

export interface LiveData {
  generated_at: string;
  active_count: number;
  stale_count: number;
  snapshots: LiveUsageSnapshot[];
}

export interface ReloadState {
  reload_token?: string;
  css_reload_token?: string;
  script_reload_token?: string;
  live?: JsonValue;
}

export interface MetricElement extends HTMLElement {
  __metricValue?: number;
  __metricRaf?: number | null;
}

export interface ChartElement extends HTMLElement {
  __chartMeta?: ChartMeta;
}

export interface ChartMeta {
  pad?: { top: number; right: number; bottom: number; left: number };
  innerW?: number;
  innerH?: number;
  viewW?: number;
  viewH?: number;
  xy?: Array<[number, number]>;
  values?: number[];
  max?: number;
  lineColor?: string;
}

declare global {
  interface HTMLElement {
    __metricValue?: number;
    __metricRaf?: number | null;
    __chartMeta?: ChartMeta;
  }
}
