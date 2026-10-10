"use client";

import { useEffect } from "react";

/** Registers /sw.js in production builds only (dev HMR and a cache don't mix). */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);
  return null;
}
