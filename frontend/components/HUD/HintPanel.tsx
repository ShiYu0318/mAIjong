"use client";

import { TileImage } from "@/components/Hand/TileImage";
import { useGame } from "@/store/gameStore";

function shantenLabel(sh: number) {
  return sh === 0 ? "聽牌" : `${sh} 向聽`;
}

export function HintButton() {
  const view = useGame((s) => s.view);
  const seat = useGame((s) => s.seat);
  const legal = useGame((s) => s.legal);
  const request = useGame((s) => s.requestHint);
  const canDiscard = legal.some((a) => a.action_type === "DISCARD");
  if (!view || view.phase !== "DISCARD" || view.turn !== seat || !canDiscard) return null;
  return (
    <button onClick={request} className="rounded-lg border border-jade bg-felt-deep px-4 py-2.5 text-ivory hover:bg-jade/30">
      提示
    </button>
  );
}

export function HintPanel() {
  const hint = useGame((s) => s.hint);
  const close = useGame((s) => s.closeHint);
  const select = useGame((s) => s.select);
  const selected = useGame((s) => s.selected);
  if (!hint) return null;
  return (
    <section aria-label="打牌提示"
      className="absolute top-3 left-3 z-10 max-h-[70%] w-80 overflow-y-auto rounded-xl border border-felt-line bg-felt-deep/95 p-4 text-sm shadow-xl">
      <div className="flex items-start justify-between gap-2">
        <p className="leading-relaxed">{hint.explanation}</p>
        <button onClick={close} aria-label="關閉提示" className="shrink-0 text-mist hover:text-ivory">✕</button>
      </div>
      {hint.remaining !== null && (
        <p className="mt-1 text-xs text-mist">本場還能用 {hint.remaining} 次提示</p>
      )}
      <ol className="mt-3 space-y-1">
        {hint.candidates.map((c, i) => (
          <li key={c.tile}>
            <button onClick={() => select(c.tile)}
              className={`flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-ivory/10 ${
                selected === c.tile ? "bg-ivory/10" : ""} ${i === 0 ? "ring-1 ring-jade" : ""}`}>
              <TileImage id={c.tile} width={28} />
              <span className="flex-1">
                <span className={c.shanten_after === 0 ? "text-ivory" : "text-mist"}>
                  {shantenLabel(c.shanten_after)}
                </span>
                <span className="ml-2 tabular text-mist">
                  {c.shanten_after === 0 ? `可胡 ${c.uke_count} 張` : `進張 ${c.uke_count} 張`}
                  {c.best_tai !== null ? `・約 ${c.best_tai} 台` : ""}
                </span>
                <span className="mt-1 flex flex-wrap gap-[1px]">
                  {(c.shanten_after === 0 ? c.waits : c.uke_ire).slice(0, 9).map((t) => (
                    <TileImage key={t} id={t} width={14} />
                  ))}
                </span>
              </span>
              {c.danger >= 0.5 && (
                <span className="size-2.5 rounded-full bg-zhong" title="有放槍風險" aria-label="有放槍風險" />
              )}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
