/** Generated avatar: colour from the name, first character, optional level ring. */

const PALETTE = [
  ["#ff9a5a", "#ff5c7a"], ["#5ea2ff", "#7a5cff"], ["#43e0a3", "#1fa3c9"],
  ["#ffcc3d", "#ff7a3d"], ["#ff86bd", "#a35cff"], ["#38d0ff", "#3b82f6"],
];

function hash(s: string): number {
  let h = 0;
  for (const ch of s) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
  return h;
}

type Props = { name: string; size?: number; progress?: number; ringColor?: string; active?: boolean };

export function Avatar({ name, size = 48, progress, ringColor = "#ffcc3d", active }: Props) {
  const [a, b] = PALETTE[hash(name) % PALETTE.length];
  const initial = [...(name.trim() || "?")][0];
  const stroke = 4;
  const r = size / 2 + stroke;
  const c = 2 * Math.PI * (r - stroke / 2);
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center"
      style={{ width: size + stroke * 2 + 4, height: size + stroke * 2 + 4 }} aria-hidden="true">
      {progress !== undefined && (
        <svg className="absolute inset-0 -rotate-90" viewBox={`0 0 ${r * 2 + 4} ${r * 2 + 4}`}>
          <circle cx={r + 2} cy={r + 2} r={r - stroke / 2} fill="none" stroke="rgb(255 255 255 / 0.12)" strokeWidth={stroke} />
          <circle cx={r + 2} cy={r + 2} r={r - stroke / 2} fill="none" stroke={ringColor} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={`${c * Math.max(0.02, Math.min(1, progress))} ${c}`} />
        </svg>
      )}
      <span className={`relative flex items-center justify-center rounded-full font-black text-white shadow-lg ${active ? "animate-pulse-glow" : ""}`}
        style={{ width: size, height: size, background: `linear-gradient(135deg, ${a}, ${b})`, fontSize: size * 0.46,
          textShadow: "0 2px 0 rgb(0 0 0 / 0.2)" }}>
        {initial}
      </span>
    </span>
  );
}
