import Link from "next/link";

import { ConfidenceBar, SeverityPill, StatusPill } from "@/components/ui";
import { formatDateTime, shortId } from "@/lib/format";
import type { IncidentSummary } from "@/lib/types";

export function IncidentTable({ incidents, compact = false }: { incidents: IncidentSummary[]; compact?: boolean }) {
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className={`w-full text-left text-sm ${compact ? "min-w-[560px]" : "min-w-[860px]"}`}>
        <thead>
          <tr className="border-b border-line text-xs text-ink-3">
            <th className="px-5 py-3 font-medium">ID</th>
            <th className="px-3 py-3 font-medium">Service</th>
            {!compact && <th className="px-3 py-3 font-medium">Description</th>}
            <th className="px-3 py-3 font-medium">Severity</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 font-medium">Confidence</th>
            {!compact && <th className="px-5 py-3 font-medium">Submitted</th>}
          </tr>
        </thead>
        <tbody>
          {incidents.map((i) => (
            <tr key={i.id} className="border-b border-line/60 last:border-0 hover:bg-panel-hover">
              <td className="px-5 py-3">
                <Link href={`/incidents/${i.id}`} className="font-mono text-xs text-accent-cyan hover:underline">
                  {shortId(i.id)}
                </Link>
              </td>
              <td className="whitespace-nowrap px-3 py-3 text-ink">{i.service_name ?? <span className="text-ink-3">Unknown</span>}</td>
              {!compact && (
                <td className="max-w-[320px] truncate px-3 py-3 text-ink-2" title={i.description}>
                  {i.description}
                </td>
              )}
              <td className="px-3 py-3">
                <SeverityPill severity={i.severity} />
              </td>
              <td className="px-3 py-3">
                <StatusPill status={i.status} />
              </td>
              <td className="px-3 py-3">
                {i.confidence != null ? <ConfidenceBar value={i.confidence} /> : <span className="text-ink-3">-</span>}
              </td>
              {!compact && <td className="whitespace-nowrap px-5 py-3 text-ink-2">{formatDateTime(i.created_at)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
