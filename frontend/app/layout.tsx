import type { Metadata, Viewport } from "next";
import { LocaleSync } from "@/components/I18n/LocaleToggle";
import { ServiceWorker } from "@/components/Pwa/ServiceWorker";
import { notoSans, wenkai } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "麥醬 mAIjong",
  description: "台灣十六張麻將：線上對戰、AI 對手與牌技練習",
  applicationName: "麥醬 mAIjong",
  appleWebApp: { capable: true, title: "麥醬", statusBarStyle: "black-translucent" },
  icons: {
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192" }],
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#12302b",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant-TW" className={`${wenkai.variable} ${notoSans.variable}`}>
      <body className="min-h-dvh antialiased">
        {children}
        <ServiceWorker />
        <LocaleSync />
      </body>
    </html>
  );
}
