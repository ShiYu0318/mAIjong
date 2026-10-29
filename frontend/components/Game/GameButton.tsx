"use client";

import type { ButtonHTMLAttributes } from "react";
import { sfx } from "@/lib/sfx";

// text colours keep >= 4.5:1 against both gradient stops (DESIGN.md §12)
const VARIANTS = {
  primary: { bg: "linear-gradient(180deg, #ffb547 0%, #ff7a3d 100%)", lip: "#b8481c", fg: "#3a1500" },
  blue: { bg: "linear-gradient(180deg, #2f6ce6 0%, #1f4fcf 100%)", lip: "#14317f", fg: "#ffffff" },
  green: { bg: "linear-gradient(180deg, #43e0a3 0%, #16a874 100%)", lip: "#0c6b49", fg: "#06291c" },
  danger: { bg: "linear-gradient(180deg, #d7304f 0%, #b31535 100%)", lip: "#6e0d22", fg: "#ffffff" },
  pink: { bg: "linear-gradient(180deg, #cc3a7c 0%, #a81f60 100%)", lip: "#64123a", fg: "#ffffff" },
  ghost: { bg: "linear-gradient(180deg, #3a4384 0%, #2b3270 100%)", lip: "#171b45", fg: "#ffffff" },
} as const;

const SIZES = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-base",
  // large sizes step down on phones, where the table and a two-row hand share the height
  lg: "px-4 py-2.5 text-base sm:px-6 sm:py-3.5 sm:text-lg",
  xl: "px-6 py-3.5 text-xl sm:px-8 sm:py-5 sm:text-2xl",
} as const;

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  silent?: boolean;
};

/** Chunky game button with a lip that sinks when pressed and a click sound. */
export function GameButton({ variant = "primary", size = "md", silent, className = "", style,
  onClick, ...rest }: Props) {
  const v = VARIANTS[variant];
  return (
    <button
      {...rest}
      onClick={(e) => {
        if (!silent) sfx.tap();
        onClick?.(e);
      }}
      className={`btn-game ${SIZES[size]} ${className}`}
      style={{ background: v.bg, color: v.fg, textShadow: v.fg === "#ffffff" ? undefined : "none",
        ["--btn-lip" as string]: v.lip, ...style }}
    />
  );
}
