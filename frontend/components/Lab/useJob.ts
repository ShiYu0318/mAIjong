"use client";

import { useEffect, useState } from "react";
import { lab, type LabJob } from "@/lib/api";

/** Poll a lab job until it finishes. */
export function useJob(jobId: string | null, every = 1000): LabJob | null {
  const [job, setJob] = useState<LabJob | null>(null);
  useEffect(() => {
    setJob(null);
    if (!jobId) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const j = await lab.job(jobId);
        if (!alive) return;
        setJob(j);
        if (j.status === "QUEUED" || j.status === "RUNNING") timer = setTimeout(tick, every);
      } catch {
        if (alive) timer = setTimeout(tick, every * 3);
      }
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [jobId, every]);
  return job;
}
