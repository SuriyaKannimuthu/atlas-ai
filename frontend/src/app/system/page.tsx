import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/shell";
import { ErrorNotice, Panel, Skeleton } from "@/components/ui";
import { atlas, attempt } from "@/lib/atlas";

export const metadata: Metadata = { title: "Agents & system" };

const AGENTS = [
  { name: "Triage", tools: ["services.list", "deployments.list_recent"], llm: "Extraction (validated)" },
  { name: "Planner", tools: [], llm: "Deterministic" },
  { name: "Log analysis", tools: ["logs.search", "deployments.get"], llm: "Deterministic statistics" },
  { name: "Code & commits", tools: ["deployments.get", "deployments.list_recent", "github.get_commit"], llm: "Deterministic" },
  { name: "Knowledge retrieval", tools: ["knowledge.search"], llm: "BM25 retrieval" },
  { name: "Root cause review", tools: [], llm: "Hypothesis review (gated)" },
  { name: "Reporting", tools: [], llm: "Narrative only" },
  { name: "Action executor", tools: ["ticketing.create_ticket", "ticketing.notify", "deploy.rollback"], llm: "None - policy gated" },
];

export default function SystemPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Agents & system" subtitle="Runtime configuration, agent responsibilities, and tool permissions." />
      <Suspense fallback={<Skeleton className="h-[120px]" />}>
        <Health />
      </Suspense>
      <Panel title="Agents and least-privilege tool access" bodyClassName="px-0 pb-2">
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-ink-3">
                <th className="px-5 py-3 font-medium">Agent</th>
                <th className="px-3 py-3 font-medium">Allowed tools</th>
                <th className="px-5 py-3 font-medium">Model role</th>
              </tr>
            </thead>
            <tbody>
              {AGENTS.map((agent) => (
                <tr key={agent.name} className="border-b border-line/60 last:border-0">
                  <td className="px-5 py-3 font-medium text-ink">{agent.name}</td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      {agent.tools.length ? (
                        agent.tools.map((tool) => (
                          <code key={tool} className="rounded-md border border-line bg-white/4 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">
                            {tool}
                          </code>
                        ))
                      ) : (
                        <span className="text-ink-3">No tools</span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-ink-2">{agent.llm}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

async function Health() {
  const result = await attempt(atlas.health());
  if (!result.ok) return <ErrorNotice message={result.error.message} />;
  const health = result.data;
  const items = [
      { label: "API status", value: health.status === "ok" ? "Healthy" : "Degraded", good: health.status === "ok" },
      { label: "Database", value: health.database ? "Connected" : "Unavailable", good: health.database },
      { label: "Model gateway", value: health.model, good: true },
      { label: "Checkpointer", value: health.checkpointer, good: true },
      { label: "LangSmith tracing", value: health.langsmith_tracing ? "Enabled" : "Disabled", good: health.langsmith_tracing },
      { label: "Version", value: health.version, good: true },
    ];
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {items.map((item) => (
          <div key={item.label} className="glass rounded-2xl p-4">
            <p className="text-xs text-ink-3">{item.label}</p>
            <p className="mt-1.5 flex items-center gap-2 truncate text-sm font-medium text-ink">
              <span className={`size-2 shrink-0 rounded-full ${item.good ? "bg-st-green" : "bg-st-amber"}`} aria-hidden="true" />
              {item.value}
            </p>
          </div>
        ))}
      </div>
    );
}
