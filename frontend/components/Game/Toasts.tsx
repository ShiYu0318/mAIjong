"use client";

import { create } from "zustand";
import type { LucideIcon } from "lucide-react";
import { GameIcon, type IconTone } from "@/components/Game/GameIcon";


export interface Toast {
  id: number;
  icon: LucideIcon;
  tone?: IconTone;
  title: string;
  body?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

let seq = 0;

export const useToasts = create<ToastState>((set, get) => ({
  toasts: [],
  push: (t) => {
    const id = ++seq;
    set({ toasts: [...get().toasts.slice(-3), { ...t, id }] });
    setTimeout(() => get().dismiss(id), 4200);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((x) => x.id !== id) }),
}));

/** Top-right notifications for missions, achievements and level-ups. */
export function Toasts() {
  const toasts = useToasts((s) => s.toasts);
  const dismiss = useToasts((s) => s.dismiss);
  return (
    <div className="pointer-events-none fixed top-4 right-4 z-50 flex w-80 max-w-[calc(100%-2rem)] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} type="button" onClick={() => dismiss(t.id)}
          className="panel pointer-events-auto flex animate-pop-in items-center gap-3 p-3 text-left">
          <GameIcon icon={t.icon} tone={t.tone ?? "gold"} size={40} />
          <span>
            <span className="block font-black">{t.title}</span>
            {t.body && <span className="block text-sm text-mist">{t.body}</span>}
          </span>
        </button>
      ))}
    </div>
  );
}
