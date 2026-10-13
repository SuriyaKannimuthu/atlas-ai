import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { IconPlus } from "@/components/icons";
import { IncidentTable } from "@/components/incident-table";
import { PageHeader } from "@/components/shell";
import { EmptyState, ErrorNotice, Panel, Skeleton } from "@/components/ui";
import { atlas, attempt } from "@/lib/atlas";
import { STATUS_LABEL } from "@/lib/format";
import type { IncidentStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Investigations" };

const FILTERS: (IncidentStatus | "all")[] = [
  "all",
  "running",
  "awaiting_approval",
  "completed",
  "failed",
  "cancelled",
];

export default function IncidentsPage({ searchParams }: PageProps<"/incidents">) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Investigations"
        subtitle="Every investigation, its status, and how confident Atlas is in the outcome."
        actions={
          <Link
            href="/incidents/new"
            className="btn-primary flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-medium text-white"
          >
            <IconPlus size={16} /> New investigation
          </Link>
        }
      />
      <Suspense fallback={<Skeleton className="h-[420px]" />}>
        <Results searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Results({ searchParams }: { searchParams: PageProps<"/incidents">["searchParams"] }) {
  const params = await searchParams;
  const status = typeof params.status === "string" ? params.status : undefined;
  const query = typeof params.q === "string" ? params.q.trim().toLowerCase() : "";

  const result = await attempt(atlas.listIncidents(status && status !== "all" ? status : undefined));
  if (!result.ok) return <ErrorNotice message={result.error.message} />;
  const data = result.data;
  const items = query
    ? data.items.filter((i) =>
        [i.id, i.description, i.service_name, i.root_cause].some((v) => v?.toLowerCase().includes(query)),
      )
    : data.items;
  const total = Object.values(data.counts).reduce((a, b) => a + (b ?? 0), 0);

  return (
    <Panel bodyClassName="px-0 pb-2">
      <div className="-mt-1 flex flex-wrap items-center gap-2 px-5 pb-4">
        {FILTERS.map((f) => {
          const active = (status ?? "all") === f;
          const n = f === "all" ? total : (data.counts[f] ?? 0);
          return (
            <Link
              key={f}
              href={f === "all" ? "/incidents" : `/incidents?status=${f}`}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                active ? "nav-active text-white" : "border border-line text-ink-2 hover:text-ink"
              }`}
            >
              {f === "all" ? "All" : STATUS_LABEL[f]} <span className="opacity-70">{n}</span>
            </Link>
          );
        })}
        {query && (
          <span className="ml-auto text-xs text-ink-3">
            {items.length} match{items.length === 1 ? "" : "es"} for “{query}” ·{" "}
            <Link href="/incidents" className="text-accent-cyan hover:underline">
              clear
            </Link>
          </span>
        )}
      </div>
      {items.length ? (
        <IncidentTable incidents={items} />
      ) : (
        <EmptyState title="No investigations match">Try another filter or start a new investigation.</EmptyState>
      )}
    </Panel>
  );
}
