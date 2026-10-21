import { GameIcon } from "@/components/Game/GameIcon";
import { SearchX } from "lucide-react";
import { NotFoundBody } from "./NotFoundBody";

export const metadata = { title: "找不到頁面 · 麥醬 mAIjong" };

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-5 py-8 text-center">
      <span className="animate-float"><GameIcon icon={SearchX} tone="slate" size={96} /></span>
      <NotFoundBody />
    </main>
  );
}
