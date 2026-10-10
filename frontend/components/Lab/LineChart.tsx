"use client";

import { useId, useRef, useState } from "react";

export interface Point {
  x: number;
  y: number;
}

interface Props {
  title: string;
  points: Point[];
  format?: (v: number) => string;
  xLabel?: string;
}

const W = 320;
const H = 140;
const PAD = { l: 44, r: 14, t: 12, b: 22 };

/** Single-series line chart with crosshair tooltip; one measure per chart (no dual axes). */
export function LineChart({ title, points, format = (v) => v.toFixed(3), xLabel = "步數" }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const id = useId();
  if (points.length === 0) {
    return (
      <figure className="rounded-lg border border-felt-line p-3">
        <figcaption className="text-sm">{title}</figcaption>
        <p className="py-8 text-center text-sm text-mist">尚無資料</p>
      </figure>
    );
  }
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  let y0 = Math.min(...ys);
  let y1 = Math.max(...ys);
  if (y0 === y1) {
    y0 -= Math.abs(y0) * 0.1 || 1;
    y1 += Math.abs(y1) * 0.1 || 1;
  }
  const sx = (x: number) => PAD.l + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - PAD.l - PAD.r);
  const sy = (y: number) => PAD.t + (1 - (y - y0) / (y1 - y0)) * (H - PAD.t - PAD.b);
  const path = points.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");
  const last = points[points.length - 1];
  const h = hover !== null ? points[hover] : null;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = ref.current!.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(sx(points[i].x) - x) < Math.abs(sx(points[best].x) - x)) best = i;
    }
    setHover(best);
  };

  return (
    <figure className="rounded-lg border border-felt-line p-3">
      <figcaption className="flex items-baseline justify-between text-sm">
        <span>{title}</span>
        <span className="tabular text-mist">{format(last.y)}</span>
      </figcaption>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full touch-none" role="img"
        aria-labelledby={id} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        <title id={id}>{`${title}：最新值 ${format(last.y)}`}</title>
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="#24493f" />
        <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t} y2={PAD.t} stroke="#24493f" strokeDasharray="2 4" />
        <text x={PAD.l - 6} y={PAD.t + 4} textAnchor="end" fontSize="10" fill="#a9bdb4">{format(y1)}</text>
        <text x={PAD.l - 6} y={H - PAD.b} textAnchor="end" fontSize="10" fill="#a9bdb4">{format(y0)}</text>
        <text x={PAD.l} y={H - 6} fontSize="10" fill="#a9bdb4">{x0}</text>
        <text x={W - PAD.r} y={H - 6} textAnchor="end" fontSize="10" fill="#a9bdb4">{`${xLabel} ${x1}`}</text>
        <path d={path} fill="none" stroke="#f4efe1" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={sx(last.x)} cy={sy(last.y)} r={4} fill="#f4efe1" stroke="#12302b" strokeWidth={2} />
        {h && (
          <g>
            <line x1={sx(h.x)} x2={sx(h.x)} y1={PAD.t} y2={H - PAD.b} stroke="#a9bdb4" strokeWidth={1} />
            <circle cx={sx(h.x)} cy={sy(h.y)} r={4} fill="#f4efe1" stroke="#12302b" strokeWidth={2} />
            <g transform={`translate(${Math.min(sx(h.x) + 6, W - 96)},${PAD.t + 2})`}>
              <rect width={90} height={30} rx={4} fill="#0c221e" stroke="#24493f" />
              <text x={6} y={12} fontSize="10" fill="#a9bdb4">{`${xLabel} ${h.x}`}</text>
              <text x={6} y={25} fontSize="11" fill="#f4efe1">{format(h.y)}</text>
            </g>
          </g>
        )}
      </svg>
    </figure>
  );
}
