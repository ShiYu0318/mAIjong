import { rankFor } from "@/lib/progression";

/** Shield badge for a rating, with the tier name. */
export function RankBadge({ rating, size = 28, showName = true }: { rating: number; size?: number; showName?: boolean }) {
  const { tier } = rankFor(rating);
  const [hi, lo] = tier.colors;
  const id = `rank-${tier.id}`;
  return (
    <span className="inline-flex items-center gap-1.5" title={`${tier.name}（rating ${Math.round(rating)}）`}>
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
      {showName && <span className="font-black">{tier.name}</span>}
    </span>
  );
}
