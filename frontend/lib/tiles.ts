/** Tile ids mirror engine/tiles.py: 0-26 suits, 27-33 honors, 34-41 flowers. */

export const SUIT_CHARS = ["萬", "條", "筒"] as const;
export const NUMERALS = ["一", "二", "三", "四", "五", "六", "七", "八", "九"] as const;
export const WINDS = ["東", "南", "西", "北"] as const;
export const DRAGONS = ["中", "發", "白"] as const;
export const FLOWERS = ["春", "夏", "秋", "冬", "梅", "蘭", "菊", "竹"] as const;

export function tileName(id: number): string {
  if (id < 27) return `${(id % 9) + 1}${SUIT_CHARS[Math.floor(id / 9)]}`;
  if (id < 31) return WINDS[id - 27];
  if (id < 34) return DRAGONS[id - 31];
  return FLOWERS[id - 34];
}

export const isFlower = (id: number) => id >= 34 && id <= 41;
export const isNumber = (id: number) => id >= 0 && id <= 26;
export const suitOf = (id: number) => Math.floor(id / 9);
export const rankOf = (id: number) => (id % 9) + 1;
