"use client";

import Script from "next/script";

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const ENVIRONMENT = process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "production";

type SentryGlobal = { init: (opts: { dsn: string; environment: string }) => void };

/** Browser error tracking (SPEC 12), only when NEXT_PUBLIC_SENTRY_DSN is set at build time.
 * Loads Sentry's pinned CDN bundle, so the app has no Sentry dependency otherwise. */
export function SentryInit() {
  if (!DSN) return null;
  return (
    <Script src="https://browser.sentry-cdn.com/8.55.0/bundle.min.js" crossOrigin="anonymous"
      strategy="afterInteractive"
      onLoad={() => {
        const sentry = (window as unknown as { Sentry?: SentryGlobal }).Sentry;
        sentry?.init({ dsn: DSN, environment: ENVIRONMENT });
      }} />
  );
}
