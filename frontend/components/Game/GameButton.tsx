"use client";

import type { ButtonHTMLAttributes } from "react";
import { sfx } from "@/lib/sfx";

const VARIANTS = {
  primary: { bg: "linear-gradient(180deg, #ffb547 0%, #ff7a3d 100%)", lip: "#b8481c" },
  blue: { bg: "linear-gradient(180deg, #5ea2ff 0%, #2f63e8 100%)", lip: "#1c3c9a" },
  green: { bg: "linear-gradient(180deg, #43e0a3 0%, #16a874 100%)", lip: "#0c6b49" },
  danger: { bg: "linear-gradient(180deg, #ff6f86 0%, #e3274a 100%)", lip: "#8e1430" },
  pink: { bg: "linear-gradient(180deg, #ff86bd 0%, #e83f88 100%)", lip: "#931f56" },
  ghost: { bg: "linear-gradient(180deg, #3a4384 0%, #2b3270 100%)", lip: "#171b45" },
} as const;

const SIZES = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-base",
  lg: "px-6 py-3.5 text-lg",
  xl: "px-8 py-5 text-2xl",
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
      style={{ background: v.bg, ["--btn-lip" as string]: v.lip, ...style }}
    />
  );
}
