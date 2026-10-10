"use client";

import { useState } from "react";
import { TileImage } from "@/components/Hand/TileImage";
import { useGame } from "@/store/gameStore";

export function CoachNote() {
  const note = useGame((s) => s.coach);
  const [open, setOpen] = useState(false);
  if (!note) return null;
  return (
    <section aria-label="教練解說" aria-live="polite"
      className="absolute bottom-[118px] left-3 z-10 w-96 max-w-[calc(100%-1.5rem)] rounded-xl border border-jade/60 bg-felt-deep/95 p-3 text-sm">
      <p className="leading-relaxed"><span className="font-display text-jade">教練　</span>{note.text}</p>
      <button onClick={() => setOpen(!open)} className="mt-1 text-xs text-mist underline">
        {open ? "收起" : "為什麼？"}
      </button>
      {open && (
        <ol className="mt-2 space-y-1">
          {note.candidates.map((c, i) => (
            <li key={c.tile} className="flex items-center gap-2">
              <span className="tabular w-4 text-mist">{i + 1}</span>
              <TileImage id={c.tile} width={20} />
              <span>{c.shanten_after === 0 ? "聽牌" : `${c.shanten_after} 向聽`}</span>
              <span className="tabular text-mist">進張 {c.uke_count} 張</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
