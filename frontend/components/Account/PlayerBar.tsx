"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/Game/Avatar";
import { CoinCounter } from "@/components/Game/CoinCounter";
import { RankBadge } from "@/components/Game/RankBadge";
import { SoundToggle } from "@/components/Game/SoundToggle";
import { LocaleToggle } from "@/components/I18n/LocaleToggle";
import { account, ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useAccount } from "@/store/accountStore";

const field = "rounded-xl border border-white/10 bg-felt-deep px-3 py-2";

/** Top bar: avatar with level ring, rank, coins, sound, language and the account menu. */
export function PlayerBar({ compact = false }: { compact?: boolean }) {
  const { user, profile, loaded, load } = useAccount();
  const t = useT();
  useEffect(() => {
    if (!loaded) void load();
  }, [loaded, load]);
  const level = profile?.level ?? 1;
  const xpPct = profile ? profile.xp / profile.xp_next : 0;
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3">
      {user && (
        <Link href="/profile" className="group flex items-center gap-2 rounded-full bg-black/20 py-1 pr-4 pl-1 hover:bg-black/30"
          aria-label={t("我的檔案")}>
          <Avatar name={user.username} size={compact ? 32 : 40} progress={xpPct} />
          <span className="hidden leading-tight sm:block">
            <span className="block max-w-36 truncate font-black">{user.username}</span>
            <span className="block text-xs text-gold">Lv.{level}</span>
          </span>
        </Link>
      )}
      {user && !compact && <span className="hidden sm:inline"><RankBadge rating={user.elo_human} size={24} /></span>}
      {profile && <CoinCounter value={profile.coins} />}
      <SoundToggle />
      <LocaleToggle />
      <AccountMenu />
    </div>
  );
}

function AccountMenu() {
  const { user, signIn, signOut } = useAccount();
  const t = useT();
  const [open, setOpen] = useState<"login" | "upgrade" | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const guest = !user || user.is_guest;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const r = open === "upgrade"
        ? await account.upgrade(username, email, password)
        : await account.login(email, password);
      signIn(r.token, r.user);
      setOpen(null);
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.status === 401 ? t("信箱或密碼不正確。") : err.status === 409 ? t("這個名稱或信箱已經註冊過。") : err.message)
        : t("連不上伺服器。"));
    }
  };

  return (
    <div className="relative text-sm">
      {guest ? (
        <div className="flex items-center gap-2 whitespace-nowrap">
          <button onClick={() => setOpen(open === "upgrade" ? null : "upgrade")}
            className="rounded-full bg-gold/90 px-3 py-1.5 font-black text-ink hover:bg-gold">{t("綁定帳號")}</button>
          <button onClick={() => setOpen(open === "login" ? null : "login")} className="text-mist underline hover:text-ivory">
            {t("登入")}
          </button>
        </div>
      ) : (
        <button onClick={signOut} className="text-mist underline hover:text-ivory">{t("登出")}</button>
      )}
      {open && (
        <form onSubmit={submit} className="panel absolute right-0 z-40 mt-3 grid w-80 max-w-[calc(100vw-2rem)] animate-pop-in gap-2 p-4">
          <p className="font-display text-xl font-black">{open === "upgrade" ? t("綁定帳號") : t("登入")}</p>
          {open === "upgrade" && (
            <>
              <p className="text-mist">{t("綁定後可以在其他裝置登入，等級、金幣與外觀都會保留。")}</p>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder={t("暱稱（2-30 字）")}
                aria-label={t("暱稱")} required minLength={2} className={field} />
            </>
          )}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("電子信箱")}
            aria-label={t("電子信箱")} required className={field} />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder={t("密碼（至少 6 碼）")} aria-label={t("密碼")} required minLength={6} className={field} />
          {error && <p role="alert" className="text-zhong">{error}</p>}
          <button className="btn-game mt-1 px-4 py-2"
            style={{ background: "linear-gradient(180deg,#ffb547,#ff7a3d)", ["--btn-lip" as string]: "#b8481c" }}>
            {open === "upgrade" ? t("綁定") : t("登入")}
          </button>
        </form>
      )}
    </div>
  );
}
