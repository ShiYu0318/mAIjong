import type { AgentStats } from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export function agentLabel(spec: string): string {
  const names: Record<string, string> = {
    random: "隨機", rule: "規則型（T=0）", lv1: "Lv1 初學", lv2: "Lv2 入門", lv3: "Lv3 普通",
    lv4: "Lv4 進階", lv5: "Lv5 高手",
  };
  if (names[spec]) return names[spec];
  if (spec.startsWith("rule:")) return `規則型（T=${spec.slice(5)}）`;
  const [kind, path] = spec.split(":");
  return `${kind.toUpperCase()} ${path?.split("/").pop() ?? ""}`;
}

export function StatsTable({ rows, showP = false }: { rows: (AgentStats & { hands?: number })[]; showP?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="text-mist">
          <tr className="border-b border-felt-line">
            <th className="py-2 font-normal">代理程式</th>
            <th className="font-normal">胡牌率</th>
            <th className="font-normal">自摸率</th>
            <th className="font-normal">放槍率</th>
            <th className="font-normal">胡牌平均台數</th>
            <th className="font-normal">平均得分</th>
            {showP && <th className="font-normal">胡牌占比（p 值）</th>}
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-felt-line/50">
              <td className="py-2">{agentLabel(r.agent)}</td>
              <td>{pct(r.win_rate)}</td>
              <td>{pct(r.self_draw_rate)}</td>
              <td>{pct(r.deal_in_rate)}</td>
              <td>{r.avg_tai_on_win.toFixed(2)}</td>
              <td>{r.avg_score.toFixed(1)}</td>
              {showP && r.win_share !== undefined && (
                <td>
                  {pct(r.win_share)}（{(r.p_value ?? 1) < 0.001 ? "<0.001" : (r.p_value ?? 1).toFixed(3)}）
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function toCsv(rows: (AgentStats & { hands?: number })[]): string {
  const head = "agent,hands,win_rate,self_draw_rate,deal_in_rate,avg_tai_on_win,avg_score";
  const lines = rows.map((r) => [r.agent, r.hands ?? "", r.win_rate, r.self_draw_rate, r.deal_in_rate,
    r.avg_tai_on_win, r.avg_score].join(","));
  return [head, ...lines].join("\n");
}
