"use client";

import { useEffect, useRef, useState } from "react";
import { sfx } from "@/lib/sfx";

export function CoinIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="11" fill="#e5a50c" />
      <circle cx="12" cy="11" r="10" fill="#ffd34d" />
      <circle cx="12" cy="11" r="6.5" fill="none" stroke="#e5a50c" strokeWidth="1.6" />
      <text x="12" y="14.6" textAnchor="middle" fontSize="9" fontWeight="900" fill="#b97a04">麥</text>
    </svg>
  );
}

/** Coin amount that rolls to new values and chimes when it grows. */
export function CoinCounter({ value, className = "" }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = from.current;
    if (start === value) return;
    if (value > start) sfx.coin();
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / 700);
      const eased = 1 - (1 - k) ** 3;
      setShown(Math.round(start + (value - start) * eased));
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-black/25 py-1 pr-3 pl-1 font-black tabular ${className}`}
      aria-label={`金幣 ${value}`}>
      <CoinIcon />
      {shown.toLocaleString("zh-TW")}
    </span>
  );
}
