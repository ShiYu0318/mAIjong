/**
 * Lightweight i18n (SPEC P11-6): Traditional Chinese is the source language and the key;
 * English strings live in EN. Missing entries fall back to Chinese.
 *
 *   const t = useT();
 *   t("座位 {n}", { n: 2 })
 */
import { useCallback } from "react";
import { create } from "zustand";

export type Locale = "zh-TW" | "en";
const STORAGE_KEY = "maijong.locale";

interface LocaleState {
  locale: Locale;
  setLocale: (l: Locale) => void;
  load: () => void;
}

export const useLocale = create<LocaleState>((set) => ({
  locale: "zh-TW",
  setLocale: (locale) => {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      /* private mode */
    }
    if (typeof document !== "undefined") document.documentElement.lang = locale === "en" ? "en" : "zh-Hant-TW";
    set({ locale });
  },
  load: () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "zh-TW") {
        document.documentElement.lang = saved === "en" ? "en" : "zh-Hant-TW";
        set({ locale: saved });
      }
    } catch {
      /* ignore */
    }
  },
}));

export type Vars = Record<string, string | number>;

const fill = (s: string, vars?: Vars) =>
  vars ? s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`)) : s;

export function translate(zh: string, vars?: Vars, locale: Locale = useLocale.getState().locale): string {
  return fill(locale === "en" ? EN[zh] ?? zh : zh, vars);
}

/** Re-renders the caller when the locale changes. */
export function useT() {
  const locale = useLocale((s) => s.locale);
  return useCallback((zh: string, vars?: Vars) => translate(zh, vars, locale), [locale]);
}

/** Tai (scoring item) names by engine id; Chinese names come from the server. */
export const TAI_EN: Record<string, string> = {
  T00: "Chicken hand", T01: "Dealer", T02: "Dealer streak", T03: "Declared ready",
  T04: "Self-draw", T05: "Concealed hand", T06: "Concealed self-draw", T07: "Round wind pung",
  T08: "Seat wind pung", T09: "Dragon pung", T10: "Own flower", T11: "Flower kong",
  T12: "Dealt flower win", T13: "Eight immortals", T14: "Seven robs one", T15: "Heavenly hand",
  T16: "Earthly hand", T17: "Human hand", T18: "Ready from the deal", T19: "Big four winds",
  T20: "Little four winds", T21: "Big three dragons", T22: "Little three dragons",
  T23: "All honors", T24: "Full flush", T25: "Half flush", T26: "Five concealed pungs",
  T27: "Four concealed pungs", T28: "Three concealed pungs", T29: "All pungs", T30: "All chows",
  T31: "Fully exposed", T32: "Half exposed", T33: "Closed wait", T34: "Edge wait",
  T35: "Pair wait", T36: "Robbing the kong", T37: "Win on kong replacement",
  T38: "Last tile draw",
};

export function taiName(id: string, zhName: string, locale: Locale = useLocale.getState().locale) {
  return locale === "en" ? TAI_EN[id] ?? zhName : zhName;
}

const EN: Record<string, string> = {
  // lobby
  "麥醬": "mAIjong",
  "台灣十六張麻將。和 AI 對手同桌練功，或開一桌邀朋友來打。":
    "Taiwanese 16-tile mahjong. Practise against AI opponents or open a table for friends.",
  "第一次玩？從 AI 教練開始": "New to the game? Start with the AI coach",
  "單人練習": "Practice",
  "排行榜": "Leaderboard",
  "社群 AI": "Community AI",
  "實驗室": "Lab",
  "你的暱稱": "Your nickname",
  "不填就用訪客名稱": "Leave blank to play as a guest",
  "平胡牌型範例": "Sample all-chows hand",
  "快速配對": "Quick match",
  "和正在等待的玩家湊一桌；30 秒內沒湊滿就由 AI 補位。":
    "Join players who are waiting; AI fills empty seats after 30 seconds.",
  "配對中…": "Matching…",
  "開始配對": "Find a table",
  "開一桌": "Open a table",
  "座位": "Seats",
  "座位 {n}": "Seat {n}",
  "你": "You",
  "留給玩家": "Open for a player",
  "AI {level}": "AI {level}",
  "初學": "Beginner",
  "入門": "Novice",
  "普通": "Intermediate",
  "進階": "Advanced",
  "高手": "Expert",
  "每次行動時限": "Time per action",
  "{n} 秒": "{n} s",
  "不限時": "No limit",
  "打幾圈": "Length",
  "東風圈": "East round",
  "東南兩圈": "East + South",
  "三圈": "Three rounds",
  "一將（四圈）": "Full game (4 rounds)",
  "開桌中…": "Opening…",
  "開桌": "Open table",
  "用房間碼加入": "Join with a code",
  "六碼房間碼": "Six-character room code",
  "加入": "Join",
  "連不上伺服器，請確認後端已啟動。": "Can't reach the server. Make sure the backend is running.",
  "找不到這個房間，請確認房間碼。": "No room with that code. Check the code and try again.",
  "無法加入：{msg}": "Can't join: {msg}",
  "發生錯誤：{msg}": "Something went wrong: {msg}",
  "English": "English",
  "中文": "中文",
  "切換語言": "Switch language",
  "開啟音效": "Turn sound on",
  "關閉音效": "Turn sound off",
  // account
  "登出": "Sign out",
  "登入": "Sign in",
  "註冊": "Register",
  "建立帳號": "Create an account",
  "暱稱（2-30 字）": "Nickname (2–30 characters)",
  "暱稱": "Nickname",
  "電子信箱": "Email",
  "密碼（至少 6 碼）": "Password (at least 6 characters)",
  "密碼": "Password",
  "信箱或密碼不正確。": "Wrong email or password.",
  "這個名稱或信箱已經註冊過。": "That name or email is already registered.",
  "連不上伺服器。": "Can't reach the server.",
  // waiting room & room
  "等待開局": "Waiting to start",
  "把房間碼給朋友，或直接開始，空位會由 AI 補上。":
    "Share the room code with friends, or start now and AI will fill the empty seats.",
  "已複製連結": "Link copied",
  "複製邀請連結": "Copy invite link",
  "（你）": " (you)",
  "空位": "Empty",
  "無法開始": "Couldn't start",
  "開局中…": "Starting…",
  "開始": "Start",
  "加入這一桌": "Join this table",
  "入座": "Take a seat",
  "無法加入": "Couldn't join",
  "回大廳": "Back to lobby",
  "連線中…": "Connecting…",
  "連線中斷，重新連線中…": "Connection lost, reconnecting…",
  "已離線": "Offline",
  "載入中…": "Loading…",
  "房間": "Room",
  "{wind}風圈・第 {n} 手": "{wind} round · hand {n}",
  "牌桌": "Table",
  "{wind}風圈": "{wind} round",
  // actions
  "可執行的動作": "Available actions",
  "點一張牌選取，再點一次打出（鍵盤：← → 選牌、Enter 打出）。":
    "Tap a tile to select it, tap again to discard (keyboard: ← → to choose, Enter to discard).",
  "吃": "Chow",
  "碰": "Pung",
  "槓": "Kong",
  "胡": "Win",
  "自摸": "Self-draw",
  "過": "Pass",
  "打出 {tile} 並宣告聽牌": "Discard {tile} and declare ready",
  "打出 {tile}": "Discard {tile}",
  "提示": "Hint",
  "延長 15 秒": "+15 s",
  "剩餘 {n} 秒": "{n} seconds left",
  // hint & coach
  "打牌提示": "Discard hint",
  "關閉提示": "Close hint",
  "本場還能用 {n} 次提示": "{n} hints left this game",
  "聽牌": "Ready",
  "{n} 向聽": "{n} away",
  "可胡 {n} 張": "{n} winning tiles",
  "進張 {n} 張": "{n} useful tiles",
  "・約 {n} 台": " · about {n} tai",
  "有放槍風險": "Risky discard",
  "教練解說": "Coach",
  "教練　": "Coach  ",
  "收起": "Hide",
  "為什麼？": "Why?",
  // side panel
  "牌局紀錄": "Log",
  "聊天": "Chat",
  "聊天訊息": "Chat message",
  "說點什麼": "Say something",
  "送出": "Send",
  // log lines
  "{who} 打出 {tile}": "{who} discards {tile}",
  "{who} 打出 {tile} 並宣告聽牌": "{who} discards {tile} and declares ready",
  "{who} 碰 {tile}": "{who} pungs {tile}",
  "{who} 吃 {tile}": "{who} chows {tile}",
  "{who} 暗槓": "{who} declares a concealed kong",
  "{who} 槓 {tile}": "{who} kongs {tile}",
  "{who} 補花 {tile}": "{who} replaces flower {tile}",
  "{who} 搶花 {tile}": "{who} robs flower {tile}",
  // result
  "本手結果": "Hand result",
  "{who} 花牌胡": "{who} wins on flowers",
  "{who} 自摸": "{who} wins by self-draw",
  "{who} 胡牌": "{who} wins",
  "{who} 放槍": "{who} dealt in",
  "{n} 台": "{n} tai",
  "莊家與連莊": "Dealer and streak",
  "付 {n} 台": "pays {n} tai",
  "海底流局": "Exhaustive draw",
  "沒有人胡牌，莊家連莊。": "Nobody won; the dealer keeps the deal.",
  "最終名次": "Final standings",
  "第 {n} 名　{who}": "#{n}  {who}",
  "下一手即將開始。": "The next hand starts shortly.",
  "看這手錄影": "Watch the replay",
  "看牌桌": "View table",
  // accessibility
  "你的手牌": "Your hand",
  "鍵盤：← → 選牌、Enter 打出、T 打出並聽牌、H 胡、P 碰、K 槓、C 吃、X 過、? 提示":
    "Keys: ← → choose, Enter discard, T discard & declare, H win, P pung, K kong, C chow, X pass, ? hint",
  "（剛摸）": " (just drawn)",
  "副露：{m}": "Melds: {m}",
  "花牌：{f}": "Flowers: {f}",
  "暗": "concealed",
  "輪到你。可以：{list}": "Your turn. You can: {list}",
  "選取 {tile}": "Selected {tile}",
  "打牌": "discard",
  "宣告聽牌": "declare ready",
  "{who} 自摸，共 {n} 台": "{who} wins by self-draw, {n} tai",
  "{who} 胡牌，共 {n} 台": "{who} wins, {n} tai",
  "流局": "Draw",
  "、": ", ",
  // offline
  "暫時連不上": "You're offline",
  "重新整理": "Reload",
};
