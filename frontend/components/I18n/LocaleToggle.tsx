"use client";

import { useEffect } from "react";
import { useLocale, useT } from "@/lib/i18n";

/** Loads the saved language once on the client. */
export function LocaleSync() {
  const load = useLocale((s) => s.load);
  useEffect(() => {
    load();
  }, [load]);
  return null;
}

export function LocaleToggle({ className = "" }: { className?: string }) {
  const locale = useLocale((s) => s.locale);
  const setLocale = useLocale((s) => s.setLocale);
  const t = useT();
  const next = locale === "en" ? "zh-TW" : "en";
  return (
    <button type="button" onClick={() => setLocale(next)} aria-label={t("切換語言")}
      lang={next === "en" ? "en" : "zh-Hant-TW"}
      className={`rounded-md border border-ivory/30 px-2.5 py-1 text-sm text-mist hover:bg-ivory/10 hover:text-ivory ${className}`}>
      {next === "en" ? "English" : "中文"}
    </button>
  );
}
