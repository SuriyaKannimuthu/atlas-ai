"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { cancelIncident, decideApproval } from "@/app/actions";
import {
  IconAlert,
  IconBook,
  IconCheck,
  IconCommit,
  IconLock,
  IconLogs,
  IconRocket,
  IconShield,
  IconTarget,
  IconX,
} from "@/components/icons";
import { ConfidenceBar, EmptyState, Panel, ReportPill, RiskPill, SeverityPill, StatusPill } from "@/components/ui";
import { KIND_LABEL, NODE_LABEL, formatDateTime, formatDuration, formatTime, shortId, titleCase } from "@/lib/format";
import { type Evidence, type IncidentBundle, type ProposedAction, type Report, TERMINAL, type WorkflowEvent } from "@/lib/types";

const PIPELINE = ["triage", "plan", "log_analysis", "code_analysis", "knowledge_retrieval", "review", "report", "policy_gate", "human_approval", "execute_actions"];

export function IncidentLive({ initial }: { initial: IncidentBundle }) {
  const [bundle, setBundle] = useState(initial);
  const { incident, events, report } = bundle;
  const id = incident.id;

  const reload = useCallback(async () => {
    const response = await fetch(`/api/incidents/${id}`, { cache: "no-store" });
    if (response.ok) setBundle(await response.json());
  }, [id]);

  // Poll quickly while the workflow runs, slowly while it waits for a human, never once terminal.
  useEffect(() => {
    if (TERMINAL.includes(incident.status)) return;
    const interval = incident.status === "awaiting_approval" ? 5000 : 1200;
    const timer = setTimeout(reload, interval);
    return () => clearTimeout(timer);
  }, [bundle, incident.status, reload]);

  return (
    <div className="space-y-5">
      <Header bundle={bundle} onChanged={reload} />
      <Pipeline events={events} status={incident.status} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="min-w-0 space-y-5 xl:col-span-2">
          {incident.pending_approval && <ApprovalPanel id={id} actions={incident.pending_approval.actions} onDecided={reload} />}
          {incident.error && (
            <div className="glass flex gap-3 rounded-2xl p-5 text-sm">
              <IconAlert className="shrink-0 text-st-red" />
              <div>
                <p className="font-medium text-ink">Investigation failed</p>
                <p className="mt-1 font-mono text-xs text-ink-2">{incident.error}</p>
              </div>
            </div>
          )}
          {report ? (
            <ReportView report={report.report} final={report.final} />
          ) : (
            !incident.error && (
              <Panel>
                <EmptyState title={incident.status === "cancelled" ? "Investigation cancelled" : "Gathering evidence…"}>
                  {incident.status === "cancelled"
                    ? "No report was produced."
                    : "Agents are querying logs, commits, and runbooks. The report appears here when the review completes."}
                </EmptyState>
              </Panel>
            )
          )}
        </div>
        <div className="min-w-0 space-y-5">
          <Metrics bundle={bundle} />
          <Timeline events={events} />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Header({ bundle, onChanged }: { bundle: IncidentBundle; onChanged: () => void }) {
  const { incident, report } = bundle;
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const cancellable = !TERMINAL.includes(incident.status) && !incident.cancel_requested;

  return (
    <section className="glass rounded-2xl p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-accent-cyan">{shortId(incident.id)}</span>
            <StatusPill status={incident.status} />
            <SeverityPill severity={incident.severity} />
            {report && <ReportPill status={report.report.status} />}
          </div>
          <h1 className="mt-3 text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            {report?.report.title ?? incident.description.slice(0, 120)}
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-ink-2">{incident.description}</p>
          <p className="mt-3 text-xs text-ink-3">
            {incident.service_name ?? "Service pending triage"}
            {incident.deployment_id && ` · ${incident.deployment_id}`} · Submitted by {incident.created_by} ·{" "}
            {formatDateTime(incident.created_at)}
          </p>
        </div>
        {cancellable && (
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const result = await cancelIncident(incident.id);
                setError(result.error);
                onChanged();
              })
            }
            className="flex h-9 shrink-0 items-center gap-2 self-start rounded-xl border border-line px-3 text-sm text-ink-2 hover:border-st-red/40 hover:text-st-red disabled:opacity-60"
          >
            <IconX size={14} /> {pending ? "Cancelling…" : "Cancel investigation"}
          </button>
        )}
        {incident.cancel_requested && incident.status === "running" && (
          <span className="text-xs text-st-amber">Cancellation requested - stopping at the next step.</span>
        )}
      </div>
      {error && <p className="mt-3 text-sm text-st-red">{error}</p>}
    </section>
  );
}

/* ---------------------------------------------------------------- pipeline */

function Pipeline({ events, status }: { events: WorkflowEvent[]; status: string }) {
  const state = useMemo(() => {
    const started = new Set<string>();
    const completed = new Set<string>();
    const failed = new Set<string>();
    for (const e of events) {
      if (!e.node) continue;
      if (e.type === "node_started") started.add(e.node);
      if (e.type === "node_completed") completed.add(e.node);
      if (e.type === "node_failed" || e.type === "step_failed") failed.add(e.node);
    }
    return { started, completed, failed };
  }, [events]);
  const done = status === "completed";

  return (
    <section className="glass scrollbar-thin overflow-x-auto rounded-2xl px-5 py-4" aria-label="Investigation progress">
      <ol className="flex min-w-[860px] items-center gap-1">
        {PIPELINE.map((node, index) => {
          const isFailed = state.failed.has(node);
          const isDone = state.completed.has(node) || (done && state.started.has(node));
          const isActive = !isDone && state.started.has(node) && !TERMINAL.includes(status as never);
          const skipped = done && !state.started.has(node);
          const tone = isFailed
            ? "border-st-amber/50 text-st-amber"
            : isDone
              ? "border-st-green/40 bg-st-green/10 text-st-green"
              : isActive
                ? "border-accent bg-accent/15 text-st-blue"
                : "border-line text-ink-3";
          return (
            <li key={node} className="flex flex-1 items-center gap-1">
              <div className="flex flex-col items-center gap-1.5 text-center">
                <span className={`flex size-7 items-center justify-center rounded-full border text-[11px] font-semibold ${tone}`}>
                  {isDone && !isFailed ? <IconCheck size={13} /> : isActive ? <span className="pulse-dot size-2 rounded-full bg-st-blue" /> : index + 1}
                </span>
                <span className={`text-[11px] leading-tight ${isActive ? "text-ink" : skipped ? "text-ink-3/60" : "text-ink-2"}`}>
                  {NODE_LABEL[node]}
                  {skipped && <span className="block text-[10px]">not needed</span>}
                  {isFailed && <span className="block text-[10px] text-st-amber">degraded</span>}
                </span>
              </div>
              {index < PIPELINE.length - 1 && <span className="mb-5 h-px flex-1 bg-line-strong" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/* ---------------------------------------------------------------- approval */

function ApprovalPanel({ id, actions, onDecided }: { id: string; actions: ProposedAction[]; onDecided: () => void }) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const decide = (decision: "approved" | "rejected") =>
    start(async () => {
      const result = await decideApproval(id, decision, comment);
      setError(result.error);
      onDecided();
    });

  return (
    <section id="approval" className="glass rounded-2xl border-st-amber/30 p-5 shadow-[0_0_40px_-20px_rgba(251,191,36,0.6)]">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-xl border border-st-amber/40 bg-st-amber/10 text-st-amber">
          <IconShield size={18} />
        </span>
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Approval required</h2>
          <p className="text-xs text-ink-2">These actions are gated by policy. Nothing runs until an approver decides.</p>
        </div>
      </div>
      <ul className="mt-4 space-y-3">
        {actions.map((action) => (
          <li key={action.id} className="rounded-xl border border-line bg-black/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium text-ink">
                {action.type === "rollback_deployment" ? <IconRocket size={15} className="text-st-red" /> : <IconLock size={15} className="text-st-amber" />}
                {titleCase(action.type)}
              </span>
              <RiskPill risk={action.risk} />
            </div>
            <p className="mt-1.5 text-xs text-ink-2">{action.rationale}</p>
            <ActionParams params={action.params} />
          </li>
        ))}
      </ul>
      <label htmlFor="approval-comment" className="mt-4 block text-xs text-ink-3">
        Comment (recorded in the audit trail)
      </label>
      <textarea
        id="approval-comment"
        rows={2}
        maxLength={2000}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        className="field mt-1.5 w-full rounded-xl px-3 py-2 text-sm text-ink"
      />
      {error && <p className="mt-2 text-sm text-st-red">{error}</p>}
      <div className="mt-4 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={() => decide("rejected")}
          className="h-10 rounded-xl border border-line px-4 text-sm text-ink-2 hover:text-ink disabled:opacity-60"
        >
          Reject
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => decide("approved")}
          className="btn-primary h-10 rounded-xl px-5 text-sm font-medium text-white disabled:opacity-60"
        >
          {pending ? "Submitting…" : `Approve ${actions.length} action${actions.length === 1 ? "" : "s"}`}
        </button>
      </div>
    </section>
  );
}

function ActionParams({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params).filter(([key]) => key !== "body" && key !== "message");
  return (
    <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-1.5">
          <dt className="text-ink-3">{titleCase(key)}:</dt>
          <dd className="max-w-[340px] truncate font-mono text-ink-2">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ report */

const SOURCE_ICON: Record<Evidence["source"], ReactNode> = {
  logs: <IconLogs size={14} />,
  code: <IconCommit size={14} />,
  deployment: <IconRocket size={14} />,
  knowledge: <IconBook size={14} />,
};

function EvidenceChip({ id }: { id: string }) {
  return (
    <a
      href={`#ev-${id}`}
      className="inline-flex rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[11px] text-st-blue hover:bg-accent/20"
    >
      {id}
    </a>
  );
}

function ReportView({ report, final }: { report: Report; final: boolean }) {
  const [source, setSource] = useState<"all" | Evidence["source"]>("all");
  const evidence = source === "all" ? report.evidence : report.evidence.filter((e) => e.source === source);

  return (
    <>
      <Panel
        title="Findings"
        action={
          <span className="text-xs text-ink-3">
            {final ? "Final report" : "Draft - awaiting approval"} · {report.generated_by}
          </span>
        }
      >
        <p className="text-sm leading-relaxed text-ink-2">{report.summary}</p>
        {report.root_cause && (
          <div className="mt-5 rounded-xl border border-accent/30 bg-gradient-to-br from-accent/12 to-accent-violet/8 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-st-blue">
                <IconTarget size={14} /> {report.status === "root_cause_identified" ? "Root cause" : "Leading hypothesis"} ·{" "}
                {KIND_LABEL[report.root_cause.kind] ?? report.root_cause.kind}
              </span>
              <ConfidenceBar value={report.root_cause.confidence} />
            </div>
            <p className="mt-2 text-sm text-ink">{report.root_cause.statement}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {report.root_cause.evidence_ids.map((id) => (
                <EvidenceChip key={id} id={id} />
              ))}
            </div>
          </div>
        )}
        <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Impact</h3>
            <p className="mt-2 text-sm text-ink-2">{report.impact}</p>
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">Remediation</h3>
            <ol className="mt-2 list-decimal space-y-1.5 pl-4 text-sm text-ink-2">
              {report.remediation.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        </div>
        {report.unknowns.length > 0 && (
          <div className="mt-5 rounded-xl border border-st-amber/25 bg-st-amber/5 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-st-amber">Open questions</h3>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-ink-2">
              {report.unknowns.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          </div>
        )}
        {report.security_notes.length > 0 && (
          <div className="mt-4 flex gap-3 rounded-xl border border-st-red/25 bg-st-red/5 p-4 text-sm">
            <IconShield size={16} className="mt-0.5 shrink-0 text-st-red" />
            <div>
              <p className="font-medium text-ink">Untrusted content flagged</p>
              {report.security_notes.map((n) => (
                <p key={n.evidence_id} className="mt-1 text-ink-2">
                  <EvidenceChip id={n.evidence_id} /> {n.note}
                </p>
              ))}
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Hypotheses" action={<span className="text-xs text-ink-3">{report.investigation.rounds} investigation round(s)</span>}>
        <ul className="space-y-3">
          {report.hypotheses.map((h, index) => (
            <li key={h.id} className={`rounded-xl border p-4 ${index === 0 ? "border-accent/30 bg-accent/5" : "border-line"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-ink-3">
                  {h.id} · {KIND_LABEL[h.kind] ?? h.kind}
                </span>
                <ConfidenceBar value={h.confidence} />
              </div>
              <p className="mt-2 text-sm text-ink">{h.statement}</p>
              <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-ink-3">
                Supports: {h.supporting_evidence.map((id) => <EvidenceChip key={id} id={id} />)}
                {h.contradicting_evidence.length > 0 && (
                  <>
                    <span className="ml-2">Contradicts:</span>
                    {h.contradicting_evidence.map((id) => <EvidenceChip key={id} id={id} />)}
                  </>
                )}
              </div>
            </li>
          ))}
          {report.hypotheses.length === 0 && <EmptyState title="No hypothesis could be formed from the available evidence" />}
        </ul>
      </Panel>

      {report.actions && report.actions.length > 0 && (
        <Panel title="Actions">
          <ul className="space-y-2">
            {report.actions.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line px-4 py-3 text-sm">
                <span className="text-ink">{titleCase(a.type)}</span>
                <span className="flex items-center gap-3 text-xs">
                  {a.outcome?.result && "ticket_id" in a.outcome.result && (
                    <span className="font-mono text-ink-2">{String(a.outcome.result.ticket_id)}</span>
                  )}
                  <OutcomePill status={a.outcome?.status ?? "skipped"} />
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel
        title={`Evidence (${report.evidence.length})`}
        action={
          <div className="flex flex-wrap gap-1">
            {(["all", "logs", "code", "deployment", "knowledge"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSource(s)}
                className={`rounded-lg px-2.5 py-1 text-xs capitalize ${source === s ? "nav-active text-white" : "text-ink-3 hover:text-ink"}`}
              >
                {s}
              </button>
            ))}
          </div>
        }
      >
        <ul className="space-y-2.5">
          {evidence.map((e) => (
            <li key={e.id} id={`ev-${e.id}`} className="scroll-mt-24 rounded-xl border border-line p-3.5 target:border-accent target:bg-accent/10">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono font-semibold text-st-blue">{e.id}</span>
                <span className="flex items-center gap-1 text-ink-3">
                  {SOURCE_ICON[e.source]} {e.source} · {titleCase(e.kind)}
                </span>
                {e.flags.map((f) => (
                  <span key={f} className="rounded-md bg-st-red/10 px-1.5 py-0.5 text-st-red ring-1 ring-inset ring-st-red/30">
                    {titleCase(f)}
                  </span>
                ))}
                {e.timestamp && <span className="ml-auto text-ink-3">{formatDateTime(e.timestamp)}</span>}
              </div>
              <p className="mt-1.5 break-words text-sm text-ink-2">{e.summary}</p>
              {e.references[0] && <p className="mt-1 truncate font-mono text-[11px] text-ink-3">{e.references[0]}</p>}
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}

function OutcomePill({ status }: { status: string }) {
  const cls =
    status === "executed"
      ? "text-st-green bg-st-green/10 ring-st-green/30"
      : status === "failed"
        ? "text-st-red bg-st-red/10 ring-st-red/30"
        : "text-st-gray bg-st-gray/10 ring-st-gray/25";
  return <span className={`rounded-md px-2 py-0.5 font-medium capitalize ring-1 ring-inset ${cls}`}>{status}</span>;
}

/* ------------------------------------------------------- metrics & timeline */

function Metrics({ bundle }: { bundle: IncidentBundle }) {
  const m = bundle.incident.metrics;
  const tokens = (m.input_tokens ?? 0) + (m.output_tokens ?? 0);
  const items = [
    { label: "Execution time", value: formatDuration(m.execution_ms) },
    { label: "Tool calls", value: m.tool_calls ?? 0 },
    { label: "Model calls", value: m.model_calls ?? 0 },
    { label: "Tokens", value: tokens.toLocaleString() },
  ];
  return (
    <Panel title="Run metrics" action={<span className="truncate font-mono text-[11px] text-ink-3">{m.model ?? "-"}</span>}>
      <dl className="grid grid-cols-2 gap-4">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="text-xs text-ink-3">{item.label}</dt>
            <dd className="mt-1 text-lg font-semibold text-ink">{item.value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

const EVENT_TEXT: Record<string, (e: WorkflowEvent) => string> = {
  workflow_queued: () => "Investigation queued",
  workflow_started: (e) => (e.payload.resumed ? "Resumed from checkpoint" : "Workflow started"),
  workflow_recovered: () => "Recovered after restart",
  node_started: (e) => `${NODE_LABEL[e.node ?? ""] ?? e.node} started`,
  node_completed: (e) => `${NODE_LABEL[e.node ?? ""] ?? e.node} completed in ${formatDuration(Number(e.payload.duration_ms))}`,
  node_failed: (e) => `${NODE_LABEL[e.node ?? ""] ?? e.node} failed`,
  tool_called: (e) => `${e.payload.tool} (${e.payload.duration_ms} ms)`,
  tool_retry: (e) => `Retrying ${e.payload.tool} - attempt ${e.payload.attempt}`,
  tool_failed: (e) => `${e.payload.tool} failed`,
  tool_denied: (e) => `Denied ${e.payload.tool} for ${e.payload.caller}`,
  step_failed: (e) => `Evidence source unavailable: ${e.payload.step}`,
  plan_created: (e) => `Plan for round ${e.payload.round}: ${(e.payload.steps as { agent: string }[]).map((s) => NODE_LABEL[s.agent]).join(", ") || "no new steps"}`,
  evidence_aggregated: (e) => `Round ${e.payload.round}: ${e.payload.new_items} new evidence items`,
  review_completed: (e) => `Review: ${Math.round(Number(e.payload.confidence) * 100)}% confidence, ${e.payload.sufficient ? "sufficient" : "needs more evidence"}`,
  model_called: (e) => `Model call ${e.payload.call} (${e.payload.latency_ms} ms)`,
  model_failed: (e) => `Model call ${e.payload.call} failed - using fallback`,
  approval_requested: () => "Waiting for human approval",
  approval_decided: (e) => `Approval ${e.payload.decision} by ${e.payload.by}`,
  workflow_completed: () => "Investigation completed",
  workflow_failed: () => "Investigation failed",
  workflow_cancelled: () => "Investigation cancelled",
  cancel_requested: () => "Cancellation requested",
};

function eventTone(type: string) {
  if (type.includes("failed") || type === "tool_denied") return "bg-st-red";
  if (type.includes("retry") || type.startsWith("approval") || type.includes("cancel")) return "bg-st-amber";
  if (type === "workflow_completed" || type === "node_completed") return "bg-st-green";
  if (type === "tool_called" || type === "model_called") return "bg-st-violet";
  return "bg-st-blue";
}

function Timeline({ events }: { events: WorkflowEvent[] }) {
  const [showTools, setShowTools] = useState(false);
  const visible = events.filter((e) => showTools || !["tool_called", "node_started", "model_called"].includes(e.type));
  return (
    <Panel
      title="Activity"
      action={
        <label className="flex items-center gap-2 text-xs text-ink-3">
          <input type="checkbox" checked={showTools} onChange={(e) => setShowTools(e.target.checked)} className="accent-[var(--accent)]" />
          Show all events
        </label>
      }
    >
      <ol className="scrollbar-thin max-h-[640px] space-y-3 overflow-y-auto pr-1">
        {visible
          .slice()
          .reverse()
          .map((e) => (
            <li key={e.seq} className="flex gap-3 text-sm">
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${eventTone(e.type)}`} aria-hidden="true" />
              <div className="min-w-0">
                <p className="break-words text-ink-2">{(EVENT_TEXT[e.type] ?? (() => titleCase(e.type)))(e)}</p>
                <p className="font-mono text-[11px] text-ink-3">{formatTime(e.created_at)}</p>
              </div>
            </li>
          ))}
      </ol>
    </Panel>
  );
}
