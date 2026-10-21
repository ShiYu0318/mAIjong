"use client";

import { MissingState } from "@/components/Game/MissingState";
import { useT } from "@/lib/i18n";

export function NotFoundBody() {
  const t = useT();
  return <MissingState title={t("找不到這個頁面")} message={t("網址可能打錯了，或這個頁面已經移除。")} linkLabel={t("回大廳")} />;
}
