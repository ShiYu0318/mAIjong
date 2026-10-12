/** Tile ids mirror engine/tiles.py: 0-26 suits, 27-33 honors, 34-41 flowers. */
import { useLocale } from "./i18n";


export const SUIT_CHARS = ["萬", "條", "筒"] as const;
export const NUMERALS = ["一", "二", "三", "四", "五", "六", "七", "八", "九"] as const;
export const WINDS = ["東", "南", "西", "北"] as const;
export const DRAGONS = ["中", "發", "白"] as const;
export const FLOWERS = ["春", "夏", "秋", "冬", "梅", "蘭", "菊", "竹"] as const;

const SUITS_EN = ["Character", "Bamboo", "Dot"] as const;
const WINDS_EN = ["East", "South", "West", "North"] as const;
const DRAGONS_EN = ["Red Dragon", "Green Dragon", "White Dragon"] as const;
const FLOWERS_EN = ["Spring", "Summer", "Autumn", "Winter", "Plum", "Orchid", "Chrysanthemum", "Bamboo flower"] as const;

/** Name in the current UI language (tile faces always use the Chinese characters). */
export function tileName(id: number): string {
  return useLocale.getState().locale === "en" ? tileNameEn(id) : tileNameZh(id);
}

export function tileNameEn(id: number): string {
  if (id < 27) return `${(id % 9) + 1} ${SUITS_EN[Math.floor(id / 9)]}`;
  if (id < 31) return WINDS_EN[id - 27];
  if (id < 34) return DRAGONS_EN[id - 31];
  return FLOWERS_EN[id - 34];
}

export function windName(i: number): string {
  return useLocale.getState().locale === "en" ? WINDS_EN[i] : WINDS[i];
}

export function tileNameZh(id: number): string {
  if (id < 27) return `${(id % 9) + 1}${SUIT_CHARS[Math.floor(id / 9)]}`;
  if (id < 31) return WINDS[id - 27];
  if (id < 34) return DRAGONS[id - 31];
  return FLOWERS[id - 34];
}

export const isFlower = (id: number) => id >= 34 && id <= 41;
export const isNumber = (id: number) => id >= 0 && id <= 26;
export const suitOf = (id: number) => Math.floor(id / 9);
export const rankOf = (id: number) => (id % 9) + 1;
