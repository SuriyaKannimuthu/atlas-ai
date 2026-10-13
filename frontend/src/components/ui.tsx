import type { ReactNode } from "react";

import { IconAlert, IconCheck, IconClock, IconShield, IconX } from "@/components/icons";
import { REPORT_LABEL, STATUS_LABEL } from "@/lib/format";
import type { IncidentStatus, ReportStatus } from "@/lib/types";

export function Panel({
  title,
  action,
  children,
  className = "",
  bodyClassName = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`glass min-w-0 rounded-2xl ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 px-5 pt-5">
          {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
          {action}
        </header>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

const STATUS_STYLE: Record<IncidentStatus, { cls: string; icon: ReactNode }> = {
  queued: { cls: "text-st-gray bg-st-gray/10 ring-st-gray/25", icon: <IconClock size={12} /> },
  running: {
    cls: "text-st-blue bg-st-blue/10 ring-st-blue/30",
    icon: <span className="pulse-dot size-1.5 rounded-full bg-st-blue" />,
  },
  awaiting_approval: {
    cls: "text-st-amber bg-st-amber/10 ring-st-amber/30",
    icon: <IconShield size={12} />,
  },
  completed: { cls: "text-st-green bg-st-green/10 ring-st-green/30", icon: <IconCheck size={12} /> },
  failed: { cls: "text-st-red bg-st-red/10 ring-st-red/30", icon: <IconAlert size={12} /> },
  cancelled: { cls: "text-st-gray bg-st-gray/10 ring-st-gray/25", icon: <IconX size={12} /> },
};

export function StatusPill({ status }: { status: IncidentStatus }) {
  const style = STATUS_STYLE[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.cls}`}
    >
      {style.icon}
      {STATUS_LABEL[status]}
    </span>
  );
}

const REPORT_STYLE: Record<ReportStatus, string> = {
  root_cause_identified: "text-st-green bg-st-green/10 ring-st-green/30",
  probable_cause: "text-st-amber bg-st-amber/10 ring-st-amber/30",
  inconclusive: "text-st-gray bg-st-gray/10 ring-st-gray/25",
};

export function ReportPill({ status }: { status: ReportStatus }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${REPORT_STYLE[status]}`}
    >
      {REPORT_LABEL[status]}
    </span>
  );
}

const SEVERITY_STYLE: Record<string, string> = {
  sev1: "text-st-red bg-st-red/10 ring-st-red/30",
  sev2: "text-st-amber bg-st-amber/10 ring-st-amber/30",
  sev3: "text-st-blue bg-st-blue/10 ring-st-blue/30",
  sev4: "text-st-gray bg-st-gray/10 ring-st-gray/25",
};

export function SeverityPill({ severity }: { severity: string | null }) {
  if (!severity) return <span className="text-ink-3">-</span>;
  return (
    <span
      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold uppercase ring-1 ring-inset ${SEVERITY_STYLE[severity] ?? SEVERITY_STYLE.sev4}`}
    >
      {severity}
    </span>
  );
}

export function RiskPill({ risk }: { risk: string }) {
  const cls =
    risk === "high"
      ? "text-st-red bg-st-red/10 ring-st-red/30"
      : risk === "medium"
        ? "text-st-amber bg-st-amber/10 ring-st-amber/30"
        : "text-st-green bg-st-green/10 ring-st-green/30";
  return (
    <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${cls}`}>
      {risk} risk
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/8" aria-hidden="true">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-cyan"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-ink-2">{pct}%</span>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-sm text-ink-3">{children}</div>}
    </div>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="glass flex items-start gap-3 rounded-2xl border-st-red/30 p-5 text-sm">
      <IconAlert className="mt-0.5 shrink-0 text-st-red" />
      <div>
        <p className="font-medium text-ink">Could not reach the Atlas API</p>
        <p className="mt-1 text-ink-2">{message}</p>
        <p className="mt-2 text-ink-3">
          Start the backend with <code className="font-mono text-ink-2">uvicorn app.main:app --reload</code> and
          check <code className="font-mono text-ink-2">ATLAS_API_URL</code> /{" "}
          <code className="font-mono text-ink-2">ATLAS_API_KEY</code> in <code className="font-mono">.env.local</code>.
        </p>
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-white/5 ${className}`} />;
}
