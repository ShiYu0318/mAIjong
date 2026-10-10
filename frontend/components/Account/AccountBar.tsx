"use client";

import { useEffect, useState } from "react";
import { account, ApiError } from "@/lib/api";
import { useAccount } from "@/store/accountStore";

const field = "rounded-md border border-felt-line bg-felt-deep px-3 py-2";

export function AccountBar() {
  const { user, loaded, load, signIn, signOut } = useAccount();
  const [open, setOpen] = useState<"login" | "register" | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, [load]);

  if (!loaded) return null;
  if (user) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span>{user.username}</span>
        <span className="tabular text-mist">rating {user.elo_human.toFixed(0)}</span>
        <button onClick={signOut} className="text-mist underline">登出</button>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const r = open === "register"
        ? await account.register(username, email, password)
        : await account.login(email, password);
      signIn(r.token, r.user);
      setOpen(null);
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.status === 401 ? "信箱或密碼不正確。" : err.status === 409 ? "這個名稱或信箱已經註冊過。" : err.message)
        : "連不上伺服器。");
    }
  };

  return (
    <div className="relative text-sm">
      <div className="flex gap-3">
        <button onClick={() => setOpen(open === "login" ? null : "login")} className="underline">登入</button>
        <button onClick={() => setOpen(open === "register" ? null : "register")} className="underline">註冊</button>
      </div>
      {open && (
        <form onSubmit={submit} className="absolute right-0 z-30 mt-2 grid w-72 gap-2 rounded-xl border border-felt-line bg-felt p-4 shadow-xl">
          <p className="font-display text-xl">{open === "register" ? "建立帳號" : "登入"}</p>
          {open === "register" && (
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="暱稱（2-30 字）"
              aria-label="暱稱" required minLength={2} className={field} />
          )}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="電子信箱"
            aria-label="電子信箱" required className={field} />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密碼（至少 6 碼）"
            aria-label="密碼" required minLength={6} className={field} />
          {error && <p role="alert" className="text-zhong">{error}</p>}
          <button className="rounded-md bg-ivory px-3 py-2 text-ink">{open === "register" ? "註冊" : "登入"}</button>
        </form>
      )}
    </div>
  );
}
