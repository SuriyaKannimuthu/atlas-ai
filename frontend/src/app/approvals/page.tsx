import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { IconArrowRight, IconLock } from "@/components/icons";
import { PageHeader } from "@/components/shell";
import { EmptyState, ErrorNotice, Panel, RiskPill, SeverityPill, Skeleton } from "@/components/ui";
import { atlas, attempt } from "@/lib/atlas";
import { formatDateTime, shortId, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Approvals"
        subtitle="Sensitive actions proposed by investigations wait here for a human decision."
      />
      <Suspense fallback={<Skeleton className="h-[320px]" />}>
        <PendingApprovals />
      </Suspense>
    </div>
  );
}

async function PendingApprovals() {
  const result = await attempt(
    atlas
      .listIncidents("awaiting_approval", 50)
      .then(({ items }) => Promise.all(items.map((i) => atlas.getIncident(i.id)))),
  );
  if (!result.ok) return <ErrorNotice message={result.error.message} />;
  const details = result.data;
  if (!details.length) {
    return (
      <Panel>
        <EmptyState title="Nothing awaiting approval">
          Actions that need sign-off - tickets, rollbacks - will appear here when an investigation proposes them.
        </EmptyState>
      </Panel>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
      {details.map((incident) => (
        <Panel
          key={incident.id}
          title={
            <span className="flex items-center gap-2">
              <span className="font-mono text-xs text-accent-cyan">{shortId(incident.id)}</span>
              {incident.service_name ?? "Unknown service"}
            </span>
          }
          action={<SeverityPill severity={incident.severity} />}
        >
          <p className="line-clamp-2 text-sm text-ink-2">{incident.root_cause ?? incident.description}</p>
          <ul className="mt-4 space-y-2">
            {incident.pending_approval?.actions.map((action) => (
              <li key={action.id} className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2.5">
                <span className="flex items-center gap-2 text-sm text-ink">
                  <IconLock size={14} className="text-st-amber" />
                  {titleCase(action.type)}
                </span>
                <RiskPill risk={action.risk} />
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center justify-between text-xs text-ink-3">
            <span>Requested {formatDateTime(incident.pending_approval?.requested_at)}</span>
            <Link
              href={`/incidents/${incident.id}#approval`}
              className="inline-flex items-center gap-1 text-sm font-medium text-accent-cyan hover:underline"
            >
              Review & decide <IconArrowRight size={14} />
            </Link>
          </div>
        </Panel>
      ))}
    </div>
  );
}
