"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, Suspense, useState } from "react";

import {
  IconCpu,
  IconList,
  IconMenu,
  IconOverview,
  IconPlus,
  IconShield,
  IconX,
  LogoMark,
} from "@/components/icons";

type NavItem = { href: string; label: string; icon: ReactNode; match: (path: string) => boolean };

const SECTIONS: { title?: string; items: NavItem[] }[] = [
  {
    items: [{ href: "/", label: "Overview", icon: <IconOverview />, match: (p) => p === "/" }],
  },
  {
    title: "Investigations",
    items: [
      {
        href: "/incidents",
        label: "All investigations",
        icon: <IconList />,
        match: (p) => p === "/incidents" || (/^\/incidents\/[^/]+$/.test(p) && p !== "/incidents/new"),
      },
      {
        href: "/incidents/new",
        label: "New investigation",
        icon: <IconPlus />,
        match: (p) => p === "/incidents/new",
      },
      { href: "/approvals", label: "Approvals", icon: <IconShield />, match: (p) => p === "/approvals" },
    ],
  },
  {
    title: "Platform",
    items: [{ href: "/system", label: "Agents & system", icon: <IconCpu />, match: (p) => p === "/system" }],
  },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-2">
      <LogoMark />
      <span className="text-xl font-semibold tracking-tight text-ink">
        Atlas<span className="text-accent-cyan"> AI</span>
      </span>
    </Link>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  // The active pathname is request data on dynamic routes; stream it in behind Suspense.
  return (
    <Suspense fallback={<NavLinks pathname="" onNavigate={onNavigate} />}>
      <ActiveNav onNavigate={onNavigate} />
    </Suspense>
  );
}

function ActiveNav({ onNavigate }: { onNavigate?: () => void }) {
  return <NavLinks pathname={usePathname()} onNavigate={onNavigate} />;
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="mt-8 flex flex-col gap-6" aria-label="Main">
      {SECTIONS.map((section, index) => (
        <div key={section.title ?? index}>
          {section.title && (
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">
              {section.title}
            </p>
          )}
          <ul className="flex flex-col gap-1">
            {section.items.map((item) => {
              const active = item.match(pathname);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                      active
                        ? "nav-active font-medium text-white"
                        : "text-ink-2 hover:bg-panel-hover hover:text-ink"
                    }`}
                  >
                    <span className={active ? "text-white" : "text-ink-3"}>{item.icon}</span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({ userCard }: { userCard: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {/* Mobile top bar */}
      <div className="glass sticky top-0 z-30 flex items-center justify-between rounded-none border-x-0 border-t-0 px-4 py-3 lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-lg p-2 text-ink-2 hover:bg-panel-hover"
          aria-label="Open navigation"
        >
          <IconMenu size={20} />
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
          <div className="glass absolute inset-y-0 left-0 flex w-72 flex-col rounded-r-2xl p-5">
            <div className="flex items-center justify-between">
              <Brand />
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg p-2 text-ink-2 hover:bg-panel-hover"
                aria-label="Close navigation"
              >
                <IconX />
              </button>
            </div>
            <Nav onNavigate={() => setOpen(false)} />
            <div className="mt-auto pt-6">{userCard}</div>
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="glass sticky top-4 m-4 mr-0 hidden h-[calc(100vh-2rem)] w-64 shrink-0 flex-col rounded-2xl p-5 lg:flex">
        <Brand />
        <Nav />
        <div className="mt-auto pt-6">{userCard}</div>
      </aside>
    </>
  );
}
