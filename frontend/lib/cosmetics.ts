/** Cosmetic catalogue visuals (docs design §8.6); ids match backend/progression.py SHOP. */

export const TABLE_CLOTHS: Record<string, [string, string]> = {
  emerald: ["#13805d", "#0a4a39"],
  ocean: ["#1d64b0", "#0d2f5c"],
  wine: ["#9a2347", "#4a0d22"],
  amethyst: ["#7445c9", "#351c6e"],
};

export const WIN_EFFECTS: Record<string, { icon: string; colors: string[] }> = {
  gold: { icon: "✨", colors: ["#ffcc3d", "#ff9f1c", "#fff3b0"] },
  fireworks: { icon: "🎆", colors: ["#ff5c9a", "#38d0ff", "#ffcc3d", "#43e0a3"] },
  sakura: { icon: "🌸", colors: ["#ffb7d5", "#ff86bd", "#fff0f6"] },
  thunder: { icon: "⚡", colors: ["#9fe8ff", "#38d0ff", "#ffffff"] },
};

export const SLOT_NAMES = { tile_back: "牌背", table: "桌布", win_effect: "胡牌特效" } as const;
