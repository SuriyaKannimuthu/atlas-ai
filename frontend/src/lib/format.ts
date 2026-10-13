import type { IncidentStatus, ReportStatus } from "@/lib/types";

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  queued: "Queued",
  running: "Investigating",
  awaiting_approval: "Awaiting approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const REPORT_LABEL: Record<ReportStatus, string> = {
  root_cause_identified: "Root cause identified",
  probable_cause: "Probable cause",
  inconclusive: "Inconclusive",
};

export const KIND_LABEL: Record<string, string> = {
  config_change: "Configuration change",
  code_change: "Code change",
  dependency_upgrade: "Dependency upgrade",
  infrastructure: "Infrastructure dependency",
  traffic: "Traffic",
  unknown: "Unknown",
};

export const NODE_LABEL: Record<string, string> = {
  triage: "Triage",
  plan: "Planner",
  log_analysis: "Log analysis",
  code_analysis: "Code & commits",
  knowledge_retrieval: "Knowledge retrieval",
  aggregate: "Evidence aggregation",
  review: "Root cause review",
  report: "Report",
  policy_gate: "Policy gate",
  human_approval: "Human approval",
  execute_actions: "Actions",
};

export function shortId(id: string): string {
  return id.replace(/^inc_/, "").slice(0, 8).toUpperCase();
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(new Date(value)) + " UTC";
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms / 60_000)} min`;
}

export function percent(value: number | null | undefined, digits = 0): string {
  return value == null ? "-" : `${(value * 100).toFixed(digits)}%`;
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
