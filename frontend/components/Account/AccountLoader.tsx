"use client";

import { useEffect } from "react";
import { useAccount } from "@/store/accountStore";

/** Loads (or creates) the player's account on every page, so a table opened directly
 * still gets cosmetics and progress events. load() runs once per page session. */
export function AccountLoader() {
  useEffect(() => {
    void useAccount.getState().load();
  }, []);
  return null;
}
