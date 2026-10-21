import { GameIcon } from "@/components/Game/GameIcon";
import { WifiOff } from "lucide-react";
import { OfflineBody } from "./OfflineBody";

export const metadata = { title: "離線中 · 麥醬 mAIjong" };

export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-5 py-8 text-center">
      <span className="animate-float"><GameIcon icon={WifiOff} tone="slate" size={96} /></span>
      <OfflineBody />
    </main>
  );
}
