// Mirrors the backend API contracts in backend/app/api/schemas.py.

export type IncidentStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type ReportStatus = "root_cause_identified" | "probable_cause" | "inconclusive";

export interface IncidentSummary {
  id: string;
  status: IncidentStatus;
  description: string;
  service_name: string | null;
  severity: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  current_node: string | null;
  report_status: ReportStatus | null;
  root_cause: string | null;
  root_cause_kind: string | null;
  confidence: number | null;
  execution_ms: number | null;
}

export interface ProposedAction {
  id: string;
  type: string;
  params: Record<string, unknown>;
  rationale: string;
  requires_approval: boolean;
  risk: string;
  tool?: string;
  description?: string;
  outcome?: {
    status: "executed" | "skipped" | "failed";
    reason?: string;
    error?: string;
    idempotency_key?: string;
    result?: Record<string, unknown>;
  } | null;
}

export interface Approval {
  id: string;
  status: "pending" | "approved" | "rejected" | "expired";
  actions: ProposedAction[];
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  comment: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  deployment_id: string | null;
  cancel_requested: boolean;
  error: string | null;
  metrics: {
    execution_ms?: number;
    tool_calls?: number;
    model_calls?: number;
    input_tokens?: number;
    output_tokens?: number;
    model?: string;
  };
  has_report: boolean;
  pending_approval: Approval | null;
  approvals: Approval[];
}

export interface IncidentList {
  items: IncidentSummary[];
  counts: Partial<Record<IncidentStatus, number>>;
}

export interface WorkflowEvent {
  seq: number;
  type: string;
  node: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Evidence {
  id: string;
  source: "logs" | "code" | "deployment" | "knowledge";
  kind: string;
  summary: string;
  details: Record<string, unknown>;
  references: string[];
  timestamp: string | null;
  flags: string[];
  round: number;
}

export interface Hypothesis {
  id: string;
  statement: string;
  kind: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  confidence: number;
  rationale: string;
}

export interface Report {
  title: string;
  status: ReportStatus;
  summary: string;
  impact: string;
  root_cause: {
    hypothesis_id: string;
    statement: string;
    kind: string;
    confidence: number;
    evidence_ids: string[];
  } | null;
  facts: { statement: string; evidence_ids: string[] }[];
  hypotheses: Hypothesis[];
  timeline: { timestamp: string; event: string; evidence_id: string }[];
  unknowns: string[];
  remediation: string[];
  security_notes: { evidence_id: string; note: string }[];
  evidence: Evidence[];
  investigation: {
    rounds: number;
    steps: { id: string; agent: string; mode: string; status: string; evidence_count: number; note: string | null }[];
    review_rationale: string;
  };
  generated_by: string;
  incident_spec: Record<string, unknown>;
  actions?: ProposedAction[];
}

export interface IncidentBundle {
  incident: IncidentDetail;
  events: WorkflowEvent[];
  report: { final: boolean; report: Report } | null;
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  database: boolean;
  model: string;
  checkpointer: string;
  langsmith_tracing: boolean;
}

export interface Me {
  subject: string;
  role: string;
  permissions: string[];
}

export const TERMINAL: IncidentStatus[] = ["completed", "failed", "cancelled"];
