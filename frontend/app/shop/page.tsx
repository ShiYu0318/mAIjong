"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PlayerBar } from "@/components/Account/PlayerBar";
import { CoinIcon } from "@/components/Game/CoinCounter";
import { GameButton } from "@/components/Game/GameButton";
import { TileImage } from "@/components/Hand/TileImage";
import { ApiError, type CosmeticSlot, profileApi, type ShopItem } from "@/lib/api";
import { SLOT_NAMES, TABLE_CLOTHS, WIN_EFFECTS } from "@/lib/cosmetics";
import { useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import type { TileBack } from "@/lib/tilePainter";
import { useAccount } from "@/store/accountStore";

const SLOTS: CosmeticSlot[] = ["tile_back", "table", "win_effect"];

function Preview({ slot, id }: { slot: CosmeticSlot; id: string }) {
  if (slot === "tile_back") {
    return (
      <span className="flex gap-1">
        <TileImage id={null} width={46} back={id as TileBack} />
        <TileImage id={31} width={46} back={id as TileBack} />
      </span>
    );
  }
  if (slot === "table") {
    const [a, b] = TABLE_CLOTHS[id] ?? TABLE_CLOTHS.emerald;
    return <span className="block h-16 w-28 rounded-2xl ring-4 ring-[#6b4423] shadow-inner"
      style={{ background: `radial-gradient(circle at 50% 40%, ${a}, ${b})` }} />;
  }
  const fx = WIN_EFFECTS[id] ?? WIN_EFFECTS.gold;
  return (
    <span className="flex h-16 w-28 items-center justify-center rounded-2xl text-4xl"
      style={{ background: `radial-gradient(circle, ${fx.colors[0]}55, transparent 70%)` }}>{fx.icon}</span>
  );
}

export default function ShopPage() {
  const t = useT();
  const loaded = useAccount((s) => s.loaded);
  const refresh = useAccount((s) => s.refreshProfile);
  const [slot, setSlot] = useState<CosmeticSlot>("tile_back");
  const [items, setItems] = useState<Record<CosmeticSlot, ShopItem[]> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loaded) profileApi.shop().then((d) => setItems(d.items)).catch(() => setError(t("無法載入商店。")));
  }, [loaded, t]);

  const act = async (fn: () => Promise<unknown>, sound: () => void) => {
    setError(null);
    try {
      await fn();
      sound();
      const d = await profileApi.shop();
      setItems(d.items);
      await refresh();
    } catch (e) {
      sfx.error();
      setError(e instanceof ApiError && e.status === 409 ? t("金幣不足或已經擁有。") : t("操作失敗，請再試一次。"));
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 pt-4 pb-12 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="font-bold text-mist hover:text-ivory">← {t("大廳")}</Link>
        <PlayerBar compact />
      </header>
      <h1 className="mt-6 font-display text-5xl font-black">{t("外觀商店")}</h1>
      <p className="mt-2 text-mist">{t("用遊玩得到的金幣解鎖外觀；金幣不能兌現，也沒有抽獎。")}</p>
      <div className="mt-6 flex gap-2" role="tablist">
        {SLOTS.map((s) => (
          <button key={s} role="tab" aria-selected={slot === s} onClick={() => { sfx.tap(); setSlot(s); }}
            className={`rounded-full px-5 py-2 font-black transition ${slot === s ? "bg-ivory text-ink" : "bg-black/25 text-mist hover:text-ivory"}`}>
            {t(SLOT_NAMES[s])}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="mt-4 animate-wiggle font-bold text-zhong">{error}</p>}
      <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {(items?.[slot] ?? []).map((it, i) => (
          <article key={it.id} className={`panel flex animate-rise flex-col items-center gap-4 p-6 ${it.equipped ? "ring-2 ring-jade" : ""}`}
            style={{ animationDelay: `${i * 50}ms` }}>
            <Preview slot={slot} id={it.id} />
            <h2 className="font-display text-xl font-black">{t(it.name)}</h2>
            {it.equipped ? (
              <span className="rounded-full bg-jade/25 px-4 py-2 font-black text-jade">✓ {t("使用中")}</span>
            ) : it.owned ? (
              <GameButton variant="green" onClick={() => act(() => profileApi.equip(slot, it.id), sfx.select)}>
                {t("裝備")}
              </GameButton>
            ) : (
              <GameButton onClick={() => act(() => profileApi.buy(slot, it.id), sfx.coin)}>
                <CoinIcon size={18} /> {it.price.toLocaleString("zh-TW")}
              </GameButton>
            )}
          </article>
        ))}
      </div>
    </main>
  );
}
