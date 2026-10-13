import Link from "next/link";
import { type ReactNode, Suspense } from "react";

import { IconBell, IconSearch } from "@/components/icons";
import { atlas, attempt } from "@/lib/atlas";

/** Page header: title block on the left, search + approvals bell + system chip on the right. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <form action="/incidents" className="field flex h-10 min-w-0 flex-1 items-center gap-2 rounded-xl px-3 sm:w-72 sm:flex-none">
          <IconSearch size={16} className="shrink-0 text-ink-3" />
          <label htmlFor="global-search" className="sr-only">
            Search investigations
          </label>
          <input
            id="global-search"
            name="q"
            placeholder="Search investigations…"
            className="min-w-0 flex-1 bg-transparent text-sm text-ink placeholder:text-ink-3 focus:outline-none"
          />
        </form>
        <Suspense fallback={<BellLink count={0} />}>
          <ApprovalsBell />
        </Suspense>
        {actions}
      </div>
    </header>
  );
}

async function ApprovalsBell() {
  const result = await attempt(atlas.listIncidents("awaiting_approval", 50));
  return <BellLink count={result.ok ? result.data.items.length : 0} />;
}

function BellLink({ count }: { count: number }) {
  return (
    <Link
      href="/approvals"
      className="glass relative flex size-10 items-center justify-center rounded-xl text-ink-2 hover:text-ink"
      aria-label={count ? `${count} investigations awaiting approval` : "Approvals"}
    >
      <IconBell size={18} />
      {count > 0 && (
        <span className="absolute -right-1 -top-1 flex min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white shadow-[0_0_10px_rgba(59,130,246,0.9)]">
          {count}
        </span>
      )}
    </Link>
  );
}

export async function UserCard() {
  const result = await attempt(atlas.me());
  if (!result.ok) {
    return <div className="glass rounded-xl p-3 text-xs text-ink-3">API offline - start the backend to sign in.</div>;
  }
  const me = result.data;
  const initials = me.subject.slice(0, 2).toUpperCase();
    return (
      <div className="glass flex items-center gap-3 rounded-xl p-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-violet text-sm font-semibold text-white">
          {initials}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink">{me.subject}</p>
          <p className="text-xs capitalize text-ink-3">{me.role}</p>
        </div>
      </div>
    );
}
