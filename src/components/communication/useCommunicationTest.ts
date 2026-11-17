import { useCallback, useEffect, useState } from "react";

export type CommPhase = "idle" | "walking" | "talking" | "returning";

/** Walk takes 1.5s each way; the speech bubble stays up for 2.5s. */
export const COMM_TIMING = { walkMs: 1500, talkMs: 2500 } as const;

/**
 * Drives the communication test: idle → walking → talking → returning → idle.
 * Each phase schedules exactly one timeout, cleared on phase change or unmount,
 * so a fast unmount or re-render never leaves a stray timer behind.
 */
export function useCommunicationTest(timing: { walkMs: number; talkMs: number } = COMM_TIMING) {
  const [phase, setPhase] = useState<CommPhase>("idle");

  useEffect(() => {
    const next: Partial<Record<CommPhase, [CommPhase, number]>> = {
      walking: ["talking", timing.walkMs],
      talking: ["returning", timing.talkMs],
      returning: ["idle", timing.walkMs],
    };
    const step = next[phase];
    if (!step) return;
    const id = setTimeout(() => setPhase(step[0]), step[1]);
    return () => clearTimeout(id);
  }, [phase, timing.walkMs, timing.talkMs]);

  const start = useCallback(() => {
    setPhase((p) => (p === "idle" ? "walking" : p));
  }, []);

  return {
    phase,
    start,
    isWalking: phase === "walking" || phase === "returning",
    isTalking: phase === "talking",
    isBusy: phase !== "idle",
  };
}
