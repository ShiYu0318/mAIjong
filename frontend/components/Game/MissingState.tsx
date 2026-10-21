"use client";

import Link from "next/link";
import { SearchX } from "lucide-react";
import { GameIcon } from "@/components/Game/GameIcon";

/** Full-page notice for something that doesn't exist (or can't be opened), with one way out. */
export function MissingState({ title, message, href = "/", linkLabel }: {
  title: string; message?: string; href?: string; linkLabel: string;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-5 py-8 text-center">
      <span className="animate-float"><GameIcon icon={SearchX} tone="slate" size={96} /></span>
      <h1 className="mt-4 font-display text-4xl font-black sm:text-5xl">{title}</h1>
      {message && <p className="mt-4 leading-relaxed text-ivory-dim">{message}</p>}
      <Link href={href} className="btn-game mt-8 btn-primary px-8 py-3 text-lg">{linkLabel}</Link>
    </main>
  );
}
