"use client";

import { useEffect, useId, useRef, useState } from "react";

function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/* ---------------------------------------------------------------- Sparkline */

export function Sparkline({ values, color = "#3987e5" }: { values: number[]; color?: string }) {
  const id = useId();
  const [ref, width] = useWidth<HTMLDivElement>(0);
  const height = 40;
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((v, i) => [i * step, height - 3 - (v / max) * (height - 8)] as const);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  return (
    <div ref={ref} className="h-10 w-full min-w-0 overflow-hidden" aria-hidden="true">
      <svg width={width} height={height} className="overflow-visible">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.35" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {values.length > 1 && (
          <>
            <path d={area} fill={`url(#${id})`} />
            <path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
          </>
        )}
      </svg>
    </div>
  );
}

/* ---------------------------------------------------------------- Bar chart */

export type Bar = { label: string; sublabel?: string; value: number };

export function BarChart({ data, unit = "investigations" }: { data: Bar[]; unit?: string }) {
  const id = useId();
  const [ref, width] = useWidth<HTMLDivElement>(0);
  const [active, setActive] = useState<number | null>(null);

  const height = 240;
  const pad = { top: 16, right: 8, bottom: 30, left: 34 };
  const plotW = Math.max(0, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(4, ...data.map((d) => d.value));
  const niceMax = Math.ceil(max / 4) * 4;
  const ticks = [0, 1, 2, 3, 4].map((i) => (niceMax / 4) * i);
  const slot = data.length ? plotW / data.length : 0;
  const barW = Math.min(44, Math.max(8, slot * 0.5));
  const y = (v: number) => pad.top + plotH - (v / niceMax) * plotH;

  const activeBar = active != null ? data[active] : null;
  const tipX = active != null ? pad.left + slot * active + slot / 2 : 0;

  return (
    <div ref={ref} className="relative w-full min-w-0" onMouseLeave={() => setActive(null)}>
      <svg width={width} height={height} role="img" aria-label={`Bar chart of ${unit} per day`}>
        <defs>
          <linearGradient id={`${id}-bar`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#4f9cf0" />
            <stop offset="1" stopColor="#1d4ed8" stopOpacity="0.55" />
          </linearGradient>
          <linearGradient id={`${id}-active`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#22d3ee" />
            <stop offset="1" stopColor="#2563eb" stopOpacity="0.7" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" />
            <text x={pad.left - 10} y={y(t)} dy="0.32em" textAnchor="end" className="fill-ink-3 text-[11px] tabular-nums">
              {t}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = pad.left + slot * i + (slot - barW) / 2;
          const top = y(d.value);
          const h = pad.top + plotH - top;
          const r = Math.min(4, h);
          const isActive = active === i;
          return (
            <g
              key={d.label}
              tabIndex={0}
              role="img"
              aria-label={`${d.sublabel ?? d.label}: ${d.value} ${unit}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="cursor-default outline-none"
            >
              {/* Hit target larger than the mark */}
              <rect x={pad.left + slot * i} y={pad.top} width={slot} height={plotH} fill="transparent" />
              {d.value > 0 && (
                <path
                  d={`M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + h} Z`}
                  fill={`url(#${id}-${isActive ? "active" : "bar"})`}
                  style={isActive ? { filter: "drop-shadow(0 0 10px rgba(34,211,238,0.55))" } : undefined}
                />
              )}
              <text
                x={pad.left + slot * i + slot / 2}
                y={height - 8}
                textAnchor="middle"
                className={`text-[11px] ${isActive ? "fill-ink font-medium" : "fill-ink-3"}`}
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
      {activeBar && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-lg border border-line-strong bg-[#0b1029]/95 px-3 py-2 text-center shadow-xl"
          style={{ left: tipX, top: Math.max(0, y(activeBar.value) - 8) }}
        >
          <p className="text-[11px] text-ink-3">{activeBar.sublabel ?? activeBar.label}</p>
          <p className="text-base font-semibold text-ink">
            {activeBar.value} <span className="text-xs font-normal text-ink-2">{unit}</span>
          </p>
        </div>
      )}
      <table className="sr-only">
        <caption>{unit} per day</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <th scope="row">{d.sublabel ?? d.label}</th>
              <td>{d.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- Donut */

export type Segment = { label: string; value: number; color: string };

export function Donut({ segments, centerLabel }: { segments: Segment[]; centerLabel: string }) {
  const [active, setActive] = useState<number | null>(null);
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const size = 200;
  const radius = 80;
  const stroke = 26;
  const circumference = 2 * Math.PI * radius;
  const gap = total > 0 && segments.filter((s) => s.value > 0).length > 1 ? 4 : 0; // ~2px each side

  const lengths = segments.map((s) => (total ? (s.value / total) * circumference : 0));
  const arcs = segments.map((s, i) => ({
    ...s,
    index: i,
    dash: Math.max(0, lengths[i] - gap),
    offset: lengths.slice(0, i).reduce((sum, l) => sum + l, 0),
  }));
  const focus = active != null ? segments[active] : null;

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-around xl:flex-col 2xl:flex-row">
      <div className="relative shrink-0" onMouseLeave={() => setActive(null)}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${centerLabel}: ${total}`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={stroke} />
          {arcs.map((a) =>
            a.dash > 0 ? (
              <circle
                key={a.label}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={a.color}
                strokeWidth={active === a.index ? stroke + 6 : stroke}
                strokeDasharray={`${a.dash} ${circumference - a.dash}`}
                strokeDashoffset={-a.offset}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
                opacity={active == null || active === a.index ? 1 : 0.45}
                onMouseEnter={() => setActive(a.index)}
                className="transition-[opacity,stroke-width] duration-150"
              />
            ) : null,
          )}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-ink-2">{focus ? focus.label : "Total"}</span>
          <span className="text-3xl font-semibold text-ink">{focus ? focus.value : total}</span>
          <span className="text-xs text-ink-3">{focus ? `${pct(focus.value, total)} of ${centerLabel.toLowerCase()}` : centerLabel}</span>
        </div>
      </div>
      <ul className="w-full max-w-sm space-y-2.5">
        {segments.map((s, i) => (
          <li
            key={s.label}
            tabIndex={0}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
            className="flex items-center justify-between gap-4 rounded-lg px-2 py-1 text-sm outline-none hover:bg-panel-hover focus-visible:bg-panel-hover"
          >
            <span className="flex items-center gap-2.5 whitespace-nowrap text-ink">
              <span className="size-2.5 rounded-full" style={{ background: s.color }} aria-hidden="true" />
              {s.label}
            </span>
            <span className="whitespace-nowrap tabular-nums text-ink-2">
              {s.value} <span className="text-ink-3">({pct(s.value, total)})</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function pct(value: number, total: number) {
  return total ? `${((value / total) * 100).toFixed(1)}%` : "0%";
}
