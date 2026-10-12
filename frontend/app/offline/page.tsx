import Link from "next/link";

export const metadata = { title: "離線中 · 麥醬 mAIjong" };

export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-5 py-8 text-center">
      <span className="animate-float text-7xl" aria-hidden="true">📡</span>
      <h1 className="mt-4 font-display text-5xl font-black">暫時連不上</h1>
      <p className="mt-4 leading-relaxed text-ivory-dim">
        線上對戰與 AI 分析需要網路。恢復連線後重新整理即可回到大廳；已經看過的課程頁面仍可離線瀏覽。
      </p>
      <Link href="/" className="btn-game mt-8 bg-gradient-to-b from-[#ffb547] to-[#ff7a3d] px-8 py-3 text-lg">
        重新整理
      </Link>
    </main>
  );
}
