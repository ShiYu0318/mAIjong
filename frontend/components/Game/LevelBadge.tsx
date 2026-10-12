/** Level number inside an experience ring (DESIGN.md §5). */
export function LevelBadge({ level, xp, xpNext, size = 56 }: { level: number; xp: number; xpNext: number; size?: number }) {
  const stroke = Math.max(3, size * 0.09);
  const r = size / 2 - stroke / 2;
  const c = 2 * Math.PI * r;
  const k = xpNext > 0 ? Math.max(0, Math.min(1, xp / xpNext)) : 0;
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}
      role="img" aria-label={`Lv.${level} ${xp}/${xpNext} XP`}>
      <svg className="absolute inset-0 -rotate-90" viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="#141838" stroke="rgb(255 255 255 / 0.12)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="url(#lvl-ring)" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={`${c * Math.max(0.02, k)} ${c}`}
          className="transition-[stroke-dasharray] duration-700 ease-out" />
        <defs>
          <linearGradient id="lvl-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fff3b0" />
            <stop offset="1" stopColor="#ff9f1c" />
          </linearGradient>
        </defs>
      </svg>
      <span className="relative flex flex-col items-center leading-none" aria-hidden="true">
        <span className="font-black text-gold" style={{ fontSize: size * 0.18 }}>Lv</span>
        <span className="tabular font-display font-black text-ivory" style={{ fontSize: size * 0.36 }}>{level}</span>
      </span>
    </span>
  );
}
