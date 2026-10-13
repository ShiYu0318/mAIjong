const MEDALS = [
  { face: ["#fff2a8", "#f6b81c", "#b97a04"], ribbon: ["#ff5c7a", "#2f63e8"] },
  { face: ["#ffffff", "#c9cfe4", "#7d86a8"], ribbon: ["#38d0ff", "#7454ff"] },
  { face: ["#ffd1a6", "#d98945", "#8a4f2a"], ribbon: ["#43e0a3", "#16a874"] },
  { face: ["#b8d3ff", "#5b86e8", "#2a4ea8"], ribbon: ["#a8b0de", "#545e9e"] },
];

/** Placement medal (1-4) drawn as SVG: ribbon, rimmed disc and the place number. */
export function Medal({ place, size = 32, label }: { place: number; size?: number; label?: string }) {
  const m = MEDALS[Math.min(4, Math.max(1, place)) - 1];
  const id = `medal-${place}`;
  return (
    <svg width={size} height={size * 1.25} viewBox="0 0 32 40" role={label ? "img" : undefined}
      aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={m.face[0]} />
          <stop offset="0.6" stopColor={m.face[1]} />
          <stop offset="1" stopColor={m.face[2]} />
        </linearGradient>
      </defs>
      <path d="M8 0h7l3 12h-7z" fill={m.ribbon[0]} />
      <path d="M24 0h-7l-3 12h7z" fill={m.ribbon[1]} />
      <circle cx="16" cy="26" r="13" fill={m.face[2]} />
      <circle cx="16" cy="25" r="12" fill={`url(#${id})`} />
      <circle cx="16" cy="25" r="8.5" fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="1.4" />
      <text x="16" y="29.5" textAnchor="middle" fontSize="13" fontWeight="900" fill="white"
        stroke={m.face[2]} strokeWidth="0.8" paintOrder="stroke">{place}</text>
    </svg>
  );
}
