import type { Metadata, Viewport } from "next";
import { notoSans, wenkai } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "麥醬 mAIjong",
  description: "台灣十六張麻將：線上對戰、AI 對手與牌技練習",
};

export const viewport: Viewport = {
  themeColor: "#12302b",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant-TW" className={`${wenkai.variable} ${notoSans.variable}`}>
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
