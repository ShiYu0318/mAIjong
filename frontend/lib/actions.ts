import { tileName } from "./tiles";

/** Human label for a flat action id (engine/actions.py layout). */
export function actionLabel(id: number): string {
  if (id < 34) return `打 ${tileName(id)}`;
  if (id < 68) return `槓 ${tileName(id - 34)}`;
  if (id === 68) return "碰";
  if (id === 69) return "吃（低）";
  if (id === 70) return "吃（中）";
  if (id === 71) return "吃（高）";
  if (id === 72) return "胡";
  if (id === 73) return "過";
  return `打 ${tileName(id - 74)} 並聽牌`;
}

const TYPE_LABEL: Record<string, string> = {
  DISCARD: "打出", TING: "打出並宣告聽牌", PON: "碰", KONG: "槓", HU: "胡",
  PASS: "過", CHI_LOW: "吃", CHI_MID: "吃", CHI_HIGH: "吃",
};

export function describeAction(a: { action_type: string; tile: number | null }): string {
  const verb = TYPE_LABEL[a.action_type] ?? a.action_type;
  return a.tile === null ? verb : `${verb} ${tileName(a.tile)}`;
}
