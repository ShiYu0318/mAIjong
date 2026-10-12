/** Level curve and rank tiers (docs design 8.1–8.2); mirrors backend/progression.py. */

export const MAX_LEVEL = 99;

/** Experience needed to go from `level` to `level + 1`. */
export const xpForNext = (level: number) => 100 + 40 * (level - 1);

export interface RankTier {
  id: string;
  name: string;
  min: number;
  colors: [string, string];
}

export const RANKS: RankTier[] = [
  { id: "novice", name: "新手", min: -Infinity, colors: ["#d08b5b", "#8a4f2a"] },
  { id: "adept", name: "熟手", min: 1450, colors: ["#e3e8f4", "#8a93ad"] },
  { id: "skilled", name: "好手", min: 1550, colors: ["#ffe27a", "#d39a12"] },
  { id: "expert", name: "高手", min: 1650, colors: ["#b8f3ff", "#4fa8c8"] },
  { id: "king", name: "雀王", min: 1750, colors: ["#8fd3ff", "#3d63ff"] },
  { id: "god", name: "雀神", min: 1900, colors: ["#ff7ad9", "#7a5cff"] },
];

export function rankFor(rating: number): { tier: RankTier; next: RankTier | null; progress: number } {
  let i = 0;
  while (i + 1 < RANKS.length && rating >= RANKS[i + 1].min) i++;
  const tier = RANKS[i];
  const next = RANKS[i + 1] ?? null;
  const lo = Number.isFinite(tier.min) ? tier.min : 1350;
  const progress = next ? Math.max(0, Math.min(1, (rating - lo) / (next.min - lo))) : 1;
  return { tier, next, progress };
}
