"use client";

import { useEffect } from "react";
import { useT } from "@/lib/i18n";
import { sfx, useSound } from "@/lib/sfx";
import { Volume2, VolumeX } from "lucide-react";

export function SoundToggle({ className = "" }: { className?: string }) {
  const muted = useSound((s) => s.muted);
  const setMuted = useSound((s) => s.setMuted);
  const load = useSound((s) => s.load);
  const t = useT();
  useEffect(() => {
    load();
  }, [load]);
  return (
    <button type="button" aria-pressed={!muted} aria-label={t(muted ? "開啟音效" : "關閉音效")}
      onClick={() => {
        setMuted(!muted);
        if (muted) sfx.tap();
      }}
      className={`flex size-9 items-center justify-center rounded-full bg-black/25 text-lg hover:bg-black/40 ${className}`}>
      {muted ? <VolumeX size={18} strokeWidth={2.4} aria-hidden="true" /> : <Volume2 size={18} strokeWidth={2.4} aria-hidden="true" />}
    </button>
  );
}
