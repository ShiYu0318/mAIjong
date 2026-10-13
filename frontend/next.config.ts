import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // NEXT_DIST_DIR lets a production build or test server run next to `next dev` without
  // overwriting its .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // `next dev` opened by LAN address (another device on the same Wi-Fi) may load dev assets
  allowedDevOrigins: ["127.0.0.1", "10.*.*.*", "172.*.*.*", "192.168.*.*"],
};

export default nextConfig;
