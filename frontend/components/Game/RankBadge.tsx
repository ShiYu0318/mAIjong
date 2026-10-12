import { translate } from "@/lib/i18n";
import { rankFor } from "@/lib/progression";

/** Shield badge for a rating, with the tier name and, optionally, progress to the next tier. */
export function RankBadge({ rating, size = 28, showName = true, showProgress = false }: {
  rating: number; size?: number; showName?: boolean; showProgress?: boolean;
}) {
  const { tier, next, progress } = rankFor(rating);
  const toNext = next ? Math.max(0, Math.ceil(next.min - rating)) : 0;
  const hint = next ? translate("距離 {name} 還差 {n} 分", { name: translate(next.name), n: toNext }) : "";
  const [hi, lo] = tier.colors;
  const id = `rank-${tier.id}`;
  return (
    <span className="inline-flex items-center gap-1.5"
      title={`${translate(tier.name)} (rating ${Math.round(rating)})${hint ? ` · ${hint}` : ""}`}>
      <svg width={size} height={size * 1.15} viewBox="0 0 24 28" aria-hidden="true">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={hi} />
            <stop offset="1" stopColor={lo} />
          </linearGradient>
        </defs>
        <path d="M12 1 22 5v8c0 6.5-4.3 11.3-10 14C6.3 24.3 2 19.5 2 13V5z" fill={`url(#${id})`}
          stroke="rgb(255 255 255 / 0.6)" strokeWidth="1" />
        <path d="M12 7l1.8 3.7 4 .6-2.9 2.8.7 4L12 16.2 8.4 18.1l.7-4-2.9-2.8 4-.6z" fill="white" opacity="0.9" />
      </svg>
      {showName && !showProgress && <span className="font-black">{translate(tier.name)}</span>}
      {showName && showProgress && (
        <span className="flex flex-col leading-tight">
          <span className="font-black">{translate(tier.name)}</span>
          {next && (
            <span className="mt-0.5 block h-1.5 w-16 overflow-hidden rounded-full bg-black/40" role="progressbar"
              aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} aria-label={hint}>
              <span className="block h-full rounded-full" style={{ width: `${progress * 100}%`,
                background: `linear-gradient(90deg, ${hi}, ${lo})` }} />
            </span>
          )}
        </span>
      )}
    </span>
  );
}
