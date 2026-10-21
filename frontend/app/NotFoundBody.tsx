"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";

export function NotFoundBody() {
  const t = useT();
  return (
    <>
      <h1 className="mt-4 font-display text-5xl font-black">{t("找不到這個頁面")}</h1>
      <p className="mt-4 leading-relaxed text-ivory-dim">{t("網址可能打錯了，或這個頁面已經移除。")}</p>
      <Link href="/" className="btn-game mt-8 btn-primary px-8 py-3 text-lg">
        {t("回大廳")}
      </Link>
    </>
  );
}
