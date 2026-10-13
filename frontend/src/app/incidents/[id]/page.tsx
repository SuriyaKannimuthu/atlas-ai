import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { IncidentLive } from "@/components/incident-live";
import { ErrorNotice, Skeleton } from "@/components/ui";
import { AtlasApiError, attempt, loadIncidentBundle } from "@/lib/atlas";

export const metadata: Metadata = { title: "Investigation" };

export default function IncidentPage({ params }: PageProps<"/incidents/[id]">) {
  return (
    <div className="space-y-6">
      <Link href="/incidents" className="text-sm text-ink-3 hover:text-ink">
        ← All investigations
      </Link>
      <Suspense fallback={<DetailSkeleton />}>
        <Detail params={params} />
      </Suspense>
    </div>
  );
}

async function Detail({ params }: { params: PageProps<"/incidents/[id]">["params"] }) {
  const { id } = await params;
  const result = await attempt(loadIncidentBundle(id));
  if (!result.ok) {
    if (result.error instanceof AtlasApiError && result.error.status === 404) notFound();
    return <ErrorNotice message={result.error.message} />;
  }
  return <IncidentLive initial={result.data} />;
}

function DetailSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-[120px]" />
      <Skeleton className="h-[90px]" />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Skeleton className="h-[480px] xl:col-span-2" />
        <Skeleton className="h-[480px]" />
      </div>
    </div>
  );
}
