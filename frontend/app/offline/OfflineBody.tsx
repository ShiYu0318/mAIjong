"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";

export function OfflineBody() {
  const t = useT();
  return (
    <>
      <h1 className="mt-4 font-display text-5xl font-black">{t("暫時連不上")}</h1>
      <p className="mt-4 leading-relaxed text-ivory-dim">
        {t("線上對戰與 AI 分析需要網路。恢復連線後重新整理即可回到大廳；已經看過的課程頁面仍可離線瀏覽。")}
      </p>
      <Link href="/" className="btn-game mt-8 btn-primary px-8 py-3 text-lg">
        {t("重新整理")}
      </Link>
    </>
  );
}
