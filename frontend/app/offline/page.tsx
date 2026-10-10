import Link from "next/link";

export const metadata = { title: "離線中 · 麥醬 mAIjong" };

export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-8">
      <h1 className="font-display text-5xl">暫時連不上</h1>
      <p className="mt-4 leading-relaxed text-ivory-dim">
        線上對戰與 AI 分析需要網路。恢復連線後重新整理即可回到大廳；已經看過的課程頁面仍可離線瀏覽。
      </p>
      <Link href="/" className="mt-8 self-start rounded-md bg-ivory px-5 py-2.5 font-medium text-ink hover:bg-ivory-dim">
        重新整理
      </Link>
    </main>
  );
}
