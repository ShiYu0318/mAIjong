"use client";

import { useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { coachNoteEn } from "@/lib/explain";
import { localName, useLocale, useT } from "@/lib/i18n";
import { useGame } from "@/store/gameStore";

export function CoachNote() {
  const note = useGame((s) => s.coach);
  const [open, setOpen] = useState(false);
  const t = useT();
  const en = useLocale((s) => s.locale) === "en";
  if (!note) return null;
  const text = en && note.chosen
    ? coachNoteEn(note.candidates, note.chosen, localName(note.who ?? "", "en"), note.human ?? false) : note.text;
  return (
    <section aria-label={t("教練解說")} aria-live="polite"
      className="absolute bottom-[118px] left-3 z-10 w-96 max-w-[calc(100%-1.5rem)] rounded-xl border border-jade/60 bg-felt-deep/95 p-3 text-sm">
      <p className="leading-relaxed"><span className="font-display text-jade">{t("教練　")}</span>{text}</p>
      <button onClick={() => setOpen(!open)} className="mt-1 text-xs text-mist underline">
        {open ? t("收起") : t("為什麼？")}
      </button>
      {open && (
        <ol className="mt-2 space-y-1">
          {note.candidates.map((c, i) => (
            <li key={c.tile} className="flex items-center gap-2">
              <span className="tabular w-4 text-mist">{i + 1}</span>
              <TileImage id={c.tile} width={20} />
              <span>{c.shanten_after === 0 ? t("聽牌") : t("{n} 向聽", { n: c.shanten_after })}</span>
              <span className="tabular text-mist">{t("進張 {n} 張", { n: c.uke_count })}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
