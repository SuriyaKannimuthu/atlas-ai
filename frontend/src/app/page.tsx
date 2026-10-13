import Link from "next/link";
import { connection } from "next/server";
import { type ReactNode, Suspense } from "react";

import { BarChart, Donut, Sparkline } from "@/components/charts";
import {
  IconActivity,
  IconArrowRight,
  IconArrowUp,
  IconClock,
  IconPlus,
  IconShield,
  IconTarget,
} from "@/components/icons";
import { PageHeader } from "@/components/shell";
import { IncidentTable } from "@/components/incident-table";
import { EmptyState, ErrorNotice, Panel, Skeleton } from "@/components/ui";
import { atlas, attempt } from "@/lib/atlas";
import { KIND_LABEL, formatDuration } from "@/lib/format";
import type { IncidentSummary } from "@/lib/types";

const DAY = 86_400_000;

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Incident command"
        subtitle="Here's what's happening across your investigations."
        actions={
          <Link
            href="/incidents/new"
            className="btn-primary flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-medium text-white"
          >
            <IconPlus size={16} /> New investigation
          </Link>
        }
      />
      <Suspense fallback={<DashboardSkeleton />}>
        <Dashboard />
      </Suspense>
    </div>
  );
}

/** Load incidents and derive dashboard statistics (kept out of render: it reads the clock). */
async function loadDashboard() {
  const result = await attempt(atlas.listIncidents(undefined, 200));
  if (!result.ok) return result;
  await connection();
  const now = Date.now();
  const incidents = result.data.items;

  const dayStart = (offset: number) => {
    const d = new Date(now - offset * DAY);
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  };
  const createdOn = (i: IncidentSummary) => new Date(i.created_at).getTime();
  const perDay = (days: number, filter: (i: IncidentSummary) => boolean = () => true) =>
    Array.from({ length: days }, (_, k) => {
      const start = dayStart(days - 1 - k);
      return incidents.filter((i) => filter(i) && createdOn(i) >= start && createdOn(i) < start + DAY).length;
    });

  const week = perDay(7);
  const thisWeek = week.reduce((a, b) => a + b, 0);
  const lastWeek = incidents.filter((i) => createdOn(i) >= dayStart(13) && createdOn(i) < dayStart(6)).length;
  const reported = incidents.filter((i) => i.report_status);
  const durations = reported.map((i) => i.execution_ms ?? 0).sort((a, b) => a - b);
  const count = (...statuses: string[]) => incidents.filter((i) => statuses.includes(i.status)).length;
  const kindCounts = reported.reduce<Record<string, number>>((acc, i) => {
    const kind = i.root_cause_kind ?? "unknown";
    acc[kind] = (acc[kind] ?? 0) + 1;
    return acc;
  }, {});

  return {
    ok: true as const,
    data: {
      incidents,
      thisWeek,
      lastWeek,
      growth: lastWeek ? (thisWeek - lastWeek) / lastWeek : null,
      reported,
      identified: reported.filter((i) => i.report_status === "root_cause_identified"),
      awaiting: incidents.filter((i) => i.status === "awaiting_approval"),
      median: durations.length ? durations[Math.floor(durations.length / 2)] : null,
      sparks: {
        all: perDay(14),
        awaiting: perDay(14, (i) => i.status === "awaiting_approval"),
        identified: perDay(14, (i) => i.report_status === "root_cause_identified"),
        durations: reported.slice(0, 14).reverse().map((i) => i.execution_ms ?? 0),
      },
      bars: week.map((value, k) => {
        const date = new Date(dayStart(6 - k));
        return {
          value,
          label: `${date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })} ${date.getUTCDate()}`,
          sublabel: date.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" }),
        };
      }),
      statusCounts: {
        active: count("queued", "running"),
        awaiting: count("awaiting_approval"),
        completed: count("completed"),
        ended: count("failed", "cancelled"),
      },
      kinds: Object.entries(kindCounts).sort((a, b) => b[1] - a[1]),
    },
  };
}

async function Dashboard() {
  const result = await loadDashboard();
  if (!result.ok) return <ErrorNotice message={result.error.message} />;
  const { incidents, thisWeek, lastWeek, growth, reported, identified, awaiting, median, sparks, bars, statusCounts, kinds } =
    result.data;
  if (incidents.length === 0) return <Welcome />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Investigations"
          value={incidents.length}
          icon={<IconActivity size={18} />}
          spark={sparks.all}
          footnote={growth == null ? `${thisWeek} in the last 7 days` : <Delta value={growth} suffix="vs previous 7 days" />}
        />
        <KpiCard
          label="Awaiting approval"
          value={awaiting.length}
          icon={<IconShield size={18} />}
          violet
          spark={sparks.awaiting}
          footnote={
            <Link href="/approvals" className="inline-flex items-center gap-1 text-accent-cyan hover:underline">
              Review pending actions <IconArrowRight size={12} />
            </Link>
          }
        />
        <KpiCard
          label="Root causes identified"
          value={identified.length}
          suffix={`/${reported.length}`}
          icon={<IconTarget size={18} />}
          spark={sparks.identified}
          footnote={`${reported.length ? Math.round((identified.length / reported.length) * 100) : 0}% of reported investigations`}
        />
        <KpiCard
          label="Median time to report"
          value={formatDuration(median)}
          icon={<IconClock size={18} />}
          violet
          spark={sparks.durations}
          footnote={`Across ${reported.length} reports`}
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Panel
          className="xl:col-span-3"
          title="Investigation activity"
          action={<span className="rounded-lg border border-line px-3 py-1 text-xs text-ink-2">Last 7 days</span>}
        >
          <p className="-mt-1 mb-3 text-2xl font-semibold text-ink">
            {thisWeek} <span className="text-sm font-normal text-ink-2">investigations</span>
          </p>
          <BarChart data={bars} />
          <div className="mt-4 grid grid-cols-3 gap-4 border-t border-line pt-4 text-sm">
            <Figure label="This week" value={String(thisWeek)} highlight />
            <Figure label="Previous week" value={String(lastWeek)} />
            <Figure label="Change" value={growth == null ? "-" : <Delta value={growth} />} />
          </div>
        </Panel>

        <Panel className="xl:col-span-2" title="Investigation status">
          <Donut
            centerLabel="Investigations"
            segments={[
              { label: "Active", value: statusCounts.active, color: "var(--series-1)" },
              { label: "Awaiting approval", value: statusCounts.awaiting, color: "var(--series-2)" },
              { label: "Completed", value: statusCounts.completed, color: "var(--series-3)" },
              { label: "Failed or cancelled", value: statusCounts.ended, color: "var(--series-4)" },
            ]}
          />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Panel
          className="xl:col-span-3"
          bodyClassName="px-0 pb-2"
          title="Recent investigations"
          action={
            <Link href="/incidents" className="text-sm text-accent-cyan hover:underline">
              View all
            </Link>
          }
        >
          <IncidentTable incidents={incidents.slice(0, 8)} compact />
        </Panel>

        <Panel className="xl:col-span-2" title="Root causes by type">
          {kinds.length === 0 ? (
            <EmptyState title="No reports yet">Root-cause types appear once investigations finish.</EmptyState>
          ) : (
            <ul className="space-y-5">
              {kinds.map(([kind, n]) => (
                <li key={kind}>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="text-ink">{KIND_LABEL[kind] ?? kind}</span>
                    <span className="tabular-nums text-ink-2">
                      {n} <span className="text-ink-3">· {Math.round((n / reported.length) * 100)}%</span>
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/6">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#2563eb] to-[#4f9cf0]"
                      style={{ width: `${(n / reported.length) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  suffix,
  icon,
  spark,
  footnote,
  violet = false,
}: {
  label: string;
  value: ReactNode;
  suffix?: string;
  icon: ReactNode;
  spark: number[];
  footnote: ReactNode;
  violet?: boolean;
}) {
  return (
    <section className="glass flex min-w-0 flex-col gap-3 rounded-2xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-ink-2">{label}</p>
          <p className="mt-1.5 text-[28px] font-semibold leading-none text-ink">
            {value}
            {suffix && <span className="text-base font-normal text-ink-3">{suffix}</span>}
          </p>
        </div>
        <span
          className={`flex size-10 items-center justify-center rounded-xl ${violet ? "icon-badge-violet text-st-violet" : "icon-badge text-st-blue"}`}
        >
          {icon}
        </span>
      </div>
      <Sparkline values={spark} color={violet ? "#9085e9" : "#3987e5"} />
      <p className="text-xs text-ink-3">{footnote}</p>
    </section>
  );
}

function Delta({ value, suffix }: { value: number; suffix?: string }) {
  const up = value >= 0;
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`inline-flex items-center gap-0.5 font-medium ${up ? "text-st-green" : "text-st-red"}`}>
        <IconArrowUp size={12} className={up ? "" : "rotate-180"} />
        {Math.abs(value * 100).toFixed(1)}%
      </span>
      {suffix && <span className="text-ink-3">{suffix}</span>}
    </span>
  );
}

function Figure({ label, value, highlight = false }: { label: string; value: ReactNode; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-ink-3">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${highlight ? "text-accent-cyan" : "text-ink"}`}>{value}</p>
    </div>
  );
}

function Welcome() {
  return (
    <Panel>
      <EmptyState title="No investigations yet">
        <p>Submit an incident and Atlas AI will triage it, gather evidence from logs, commits, and runbooks, and produce an evidence-backed report.</p>
        <Link
          href="/incidents/new"
          className="btn-primary mt-5 inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-medium text-white"
        >
          <IconPlus size={16} /> Start your first investigation
        </Link>
      </EmptyState>
    </Panel>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[150px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Skeleton className="h-[380px] xl:col-span-3" />
        <Skeleton className="h-[380px] xl:col-span-2" />
      </div>
    </div>
  );
}
