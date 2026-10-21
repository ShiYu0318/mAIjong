/**
 * English wording for practice scenarios. Their Chinese titles and descriptions come from
 * backend/data/scenarios.json and follow a few fixed patterns, matched here.
 */
import { tileNameEn, tileNameZh } from "./tiles";

const TITLES: Record<string, string> = {
  "一向聽：打哪張進張最多": "One away: which discard keeps the most draws",
  "聽牌選擇：聽哪裡比較好": "Getting ready: which wait is best",
  "防守：對手已宣告聽牌": "Defence: an opponent declared ready",
  "吃碰判斷：要不要叫牌": "Calls: take it or not",
  "早巡整理：先丟哪張": "Early hand: what to throw first",
};

const ZH_TO_ID = new Map(Array.from({ length: 34 }, (_, i) => [tileNameZh(i), i]));
const tileEn = (zh: string) => {
  const id = ZH_TO_ID.get(zh);
  return id === undefined ? zh : tileNameEn(id);
};

export function scenarioTitleEn(title: string): string {
  const m = title.match(/^(.+)（(\d+)）$/);
  const head = m ? TITLES[m[1]] : undefined;
  return head ? `${head} (${m![2]})` : title;
}

export function scenarioDescriptionEn(text: string): string {
  let m = text.match(/^一向聽，最好的打法有 (\d+) 張進張。/);
  if (m) return `One away; the best discard leaves ${m[1]} useful tiles. Find it.`;
  m = text.match(/^有 (\d+) 種打法都能聽牌/);
  if (m) return `${m[1]} discards all get you ready, with different waits and tai. Which one?`;
  m = text.match(/^對手打出 (\S+)，你可以(吃|碰)。要叫嗎？$/);
  if (m) return `An opponent discarded ${tileEn(m[1])} and you can ${m[2] === "吃" ? "chow" : "pung"}. Call it?`;
  if (text.startsWith("剛開局")) return "The hand just started and your tiles are scattered. Which discard costs least?";
  if (text.startsWith("有對手已經宣告聽牌")) {
    return "An opponent has declared ready and you're still some way off. What can you discard without dealing in?";
  }
  return text;
}
