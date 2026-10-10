import { LXGW_WenKai_TC, Noto_Sans_TC } from "next/font/google";

/** Calligraphic face used for headings and the characters printed on tiles. */
export const wenkai = LXGW_WenKai_TC({
  weight: ["400", "700"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-wenkai",
  preload: false,
});

export const notoSans = Noto_Sans_TC({
  weight: ["400", "500", "700"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  preload: false,
});
