import type { LucideIcon } from "lucide-react";

/** Gradient stops (top → bottom) and the darker lip under the badge. */
export const ICON_TONES = {
  gold: ["#ffe27a", "#f0a91a", "#9a6406"],
  orange: ["#ffb547", "#ff6a3d", "#a83a14"],
  red: ["#ff7a8f", "#e3274a", "#7d0f26"],
  pink: ["#ff8fc6", "#e8408c", "#86184d"],
  violet: ["#b59cff", "#7454ff", "#3a2496"],
  blue: ["#7fb2ff", "#2f63e8", "#173a8f"],
  cyan: ["#8ee8ff", "#1fa3c9", "#0b5670"],
  green: ["#7df0bd", "#16a874", "#0a5a3d"],
  slate: ["#a8b0de", "#545e9e", "#272d5c"],
} as const;

export type IconTone = keyof typeof ICON_TONES;

/** Game-style icon: a glossy gradient tile with a white glyph, like an app badge.
 * Decorative by default; pass `label` when the icon carries meaning on its own. */
export function GameIcon({ icon: Icon, tone = "gold", size = 48, label, className = "" }: {
  icon: LucideIcon; tone?: IconTone; size?: number; label?: string; className?: string;
}) {
  const [top, bottom, lip] = ICON_TONES[tone];
  return (
    <span role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden ${className}`}
      style={{
        width: size, height: size, borderRadius: size * 0.3,
        background: `linear-gradient(160deg, ${top} 0%, ${bottom} 75%)`,
        boxShadow: `0 ${Math.max(2, size * 0.06)}px 0 ${lip}, 0 ${size * 0.14}px ${size * 0.3}px rgb(5 6 25 / 0.45), inset 0 1px 0 rgb(255 255 255 / 0.55)`,
      }}>
      {/* glossy highlight across the top half */}
      <span className="pointer-events-none absolute inset-x-[8%] top-[5%] h-[45%] rounded-[40%] bg-gradient-to-b from-white/45 to-white/0" />
      <Icon size={size * 0.56} strokeWidth={2.4} color="white" className="relative"
        style={{ filter: `drop-shadow(0 ${Math.max(1, size * 0.03)}px 0 ${lip})` }} />
    </span>
  );
}
