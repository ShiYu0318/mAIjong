/** Rounded progress bar; shines when full. */
export function ProgressBar({ value, max, color = "linear-gradient(90deg, #ffcc3d, #ff9f1c)", label, className = "" }: {
  value: number; max: number; color?: string; label?: string; className?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className={`h-3 overflow-hidden rounded-full bg-black/30 ${className}`} role="progressbar"
      aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
      <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${pct >= 100 ? "shine animate-shine" : ""}`}
        style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}
