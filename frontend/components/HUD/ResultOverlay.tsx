"use client";

import Link from "next/link";
import { TileImage } from "@/components/Hand/TileImage";
import { taiName, useT } from "@/lib/i18n";
import { useGame } from "@/store/gameStore";

export function ResultOverlay({ names }: { names: string[] }) {
  const win = useGame((s) => s.win);
  const drawn = useGame((s) => s.drawn);
  const gameEnd = useGame((s) => s.gameEnd);
  const dismiss = useGame((s) => s.dismissResult);
  const gameId = useGame((s) => s.view?.game_id);
  const t = useT();
  if (!win && !drawn && !gameEnd) return null;

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-felt-deep/80 p-4" role="dialog"
      aria-modal="true" aria-label={t("本手結果")}>
      <div className="w-full max-w-2xl rounded-2xl border border-felt-line bg-felt p-6 shadow-2xl sm:p-8">
        {win && (
          <>
            <h2 className="font-display text-4xl">
              {t(win.flower_win ? "{who} 花牌胡" : win.self_draw ? "{who} 自摸" : "{who} 胡牌", { who: names[win.winner] })}
            </h2>
            {win.loser !== null && win.loser !== undefined && !win.self_draw && (
              <p className="mt-1 text-mist">{t("{who} 放槍", { who: names[win.loser] })}</p>
            )}
            <div className="mt-5 flex flex-wrap gap-[2px]">
              {(win.hand ?? []).map((t, i) => (
                <TileImage key={i} id={t} width={34}
                  className={t === win.win_tile && i === (win.hand ?? []).lastIndexOf(t) ? "ring-2 ring-zhong rounded-md" : ""} />
              ))}
              {win.melds.map((m, i) => (
                <span key={i} className="ml-2 flex gap-[1px]">
                  {m.tiles.map((t, j) => <TileImage key={j} id={t} width={28} />)}
                </span>
              ))}
            </div>
            <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
              {(win.tai_breakdown ?? []).map((it, i) => (
                <li key={i} className="flex justify-between border-b border-felt-line/60 py-1">
                  <span>{taiName(it.id, it.name)}</span><span className="tabular">{t("{n} 台", { n: it.tai })}</span>
                </li>
              ))}
              {!!win.dealer_tai && (
                <li className="flex justify-between border-b border-felt-line/60 py-1 text-mist">
                  <span>{t("莊家與連莊")}</span><span className="tabular">{t("{n} 台", { n: win.dealer_tai })}</span>
                </li>
              )}
            </ul>
            <table className="mt-5 w-full text-left">
              <tbody>
                {win.payments.map((p, seat) => (
                  <tr key={seat} className="border-b border-felt-line/40">
                    <td className="py-1.5">{names[seat]}</td>
                    <td className="tabular py-1.5 text-mist">
                      {win.tai_by_payer?.[String(seat)] !== undefined ? t("付 {n} 台", { n: win.tai_by_payer[String(seat)] }) : ""}
                    </td>
                    <td className={`tabular py-1.5 text-right ${p > 0 ? "text-ivory" : p < 0 ? "text-zhong" : "text-mist"}`}>
                      {p > 0 ? `+${p}` : p}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {drawn && !win && (
          <>
            <h2 className="font-display text-4xl">{t("海底流局")}</h2>
            <p className="mt-2 text-mist">{t("沒有人胡牌，莊家連莊。")}</p>
          </>
        )}
        {gameEnd ? (
          <div className="mt-6">
            <h3 className="font-display text-2xl">{t("最終名次")}</h3>
            <ol className="mt-3 space-y-1">
              {[0, 1, 2, 3].sort((a, b) => gameEnd.ranks[a] - gameEnd.ranks[b]).map((seat) => (
                <li key={seat} className="flex justify-between">
                  <span>{t("第 {n} 名　{who}", { n: gameEnd.ranks[seat], who: names[seat] })}</span>
                  <span className="tabular">{gameEnd.final_scores[seat]}</span>
                </li>
              ))}
            </ol>
            <Link href="/" className="mt-6 inline-block rounded-lg bg-ivory px-5 py-2.5 text-ink">{t("回大廳")}</Link>
          </div>
        ) : (
          <div className="mt-6 flex items-center justify-between text-sm text-mist">
            <span>
              {t("下一手即將開始。")}
              {gameId && (
                <a href={`/replay/${gameId}`} target="_blank" rel="noreferrer" className="ml-3 text-ivory underline">
                  {t("看這手錄影")}
                </a>
              )}
            </span>
            <button onClick={dismiss} className="rounded-md border border-ivory/30 px-3 py-1.5 text-ivory hover:bg-ivory/10">
              {t("看牌桌")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
