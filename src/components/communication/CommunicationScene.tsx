import { useEffect, useRef, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import atlasImg from "@/assets/agent-atlas.png";
import emberImg from "@/assets/agent-ember.png";
import { useCommunicationTest, type CommPhase } from "./useCommunicationTest";

/** Space (px) left between the two agents when Agent A arrives. */
const MEET_GAP = 16;
const EASE_OUT = "ease-[cubic-bezier(0.23,1,0.32,1)]";

const STATUS: Record<CommPhase, string> = {
  idle: "Pronto para testar",
  walking: "Supervisor está indo até o Monitor…",
  talking: "Trocando dados…",
  returning: "Supervisor está voltando ao Central Hub…",
};

type TokenProps = {
  name: string;
  role: string;
  src: string;
  ring: string;
  glow: string;
  walking?: boolean;
  highlight?: boolean;
};

/** Transparent agent: no card, no white fill, no overflow clipping. */
function AgentToken({ name, role, src, ring, glow, walking, highlight }: TokenProps) {
  return (
    <figure className="flex w-28 flex-col items-center gap-2 bg-transparent">
      <div className={cn("relative bg-transparent", walking && "anim-walk")}>
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute -inset-2 rounded-full ring-4 opacity-0 transition-opacity duration-500",
            EASE_OUT,
            glow,
            highlight && "opacity-100",
          )}
        />
        <div className={cn("relative aspect-square w-24 rounded-full bg-transparent ring-2", ring)}>
          <img
            src={src}
            alt={`Avatar de ${name}`}
            width={96}
            height={96}
            draggable={false}
            decoding="async"
            className="aspect-square h-full w-full select-none rounded-full bg-transparent object-cover object-top"
          />
        </div>
      </div>
      <div aria-hidden className="h-2 w-14 rounded-full bg-foreground/10" />
      <figcaption className="text-center">
        <p className="text-sm font-semibold text-foreground">{name}</p>
        <p className="text-xs text-muted-foreground">{role}</p>
      </figcaption>
    </figure>
  );
}

export function CommunicationScene() {
  const { phase, start, isWalking, isTalking, isBusy } = useCommunicationTest();
  const rowRef = useRef<HTMLDivElement>(null);
  const aRef = useRef<HTMLDivElement>(null);
  const bRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState({ distance: 0, bubbleX: 0 });

  // offsetLeft ignores transforms, so measuring mid-walk still gives the resting layout.
  useEffect(() => {
    const row = rowRef.current;
    const a = aRef.current;
    const b = bRef.current;
    if (!row || !a || !b) return;
    const measure = () =>
      setLayout({
        distance: Math.max(0, b.offsetLeft - (a.offsetLeft + a.offsetWidth) - MEET_GAP),
        bubbleX: b.offsetLeft - MEET_GAP / 2,
      });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(row);
    return () => ro.disconnect();
  }, []);

  const atB = phase === "walking" || phase === "talking";

  return (
    <div className="relative flex min-h-[500px] w-full flex-col items-center justify-center gap-10 overflow-x-clip rounded-3xl border border-border bg-muted/50 px-4 py-12">
      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={start}
          disabled={isBusy}
          className={cn(
            "inline-flex items-center gap-2 rounded-full bg-linear-to-br from-primary to-agent-blue px-6 py-3",
            "text-sm font-semibold text-primary-foreground shadow-card",
            "transform-gpu transition-[transform,opacity] duration-200",
            EASE_OUT,
            "hover:-translate-y-0.5 hover:brightness-105 active:scale-95",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0",
          )}
        >
          <MessagesSquare className="h-4 w-4" />
          {isBusy ? "Testando…" : "Testar Comunicação"}
        </button>
        <p aria-live="polite" className="text-xs font-medium text-muted-foreground">
          {STATUS[phase]}
        </p>
      </div>

      {/* Row is the positioning parent for the bubble, so the bubble lives outside both agents. */}
      <div
        ref={rowRef}
        className="relative mt-16 flex w-full max-w-4xl justify-between px-4 sm:px-10"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-16 top-12 border-t-2 border-dashed border-border sm:inset-x-24"
        />

        {/* Agent A: moves, so it sits on the highest layer. */}
        <div
          ref={aRef}
          className="relative z-50 shrink-0 transform-gpu will-change-transform transition-transform duration-[1500ms] ease-in-out motion-reduce:duration-0"
          style={{ transform: `translate3d(${atB ? layout.distance : 0}px, 0, 0)` }}
        >
          <AgentToken
            name="Supervisor"
            role="Agente A · Coordenador"
            src={atlasImg}
            ring="ring-agent-blue/40"
            glow="ring-agent-blue/25"
            walking={isWalking}
            highlight={isTalking}
          />
        </div>

        <div ref={bRef} className="relative z-10 shrink-0">
          <AgentToken
            name="Monitor"
            role="Agente B · Watcher do cluster"
            src={emberImg}
            ring="ring-agent-orange/40"
            glow="ring-agent-orange/30"
            highlight={isTalking}
          />
        </div>

        {/* Speech bubble: positioned wrapper (static) + animated inner (opacity/scale only). */}
        <div
          className="pointer-events-none absolute top-0 z-[60] -translate-x-1/2 -translate-y-[calc(100%+14px)]"
          style={{ left: layout.bubbleX }}
        >
          <div
            role="status"
            aria-hidden={!isTalking}
            className={cn(
              "relative w-64 max-w-[calc(100vw-2rem)] origin-bottom rounded-2xl border border-border bg-card px-4 py-3 shadow-card",
              "transform-gpu transition-[opacity,transform] duration-300",
              EASE_OUT,
              isTalking
                ? "translate-y-0 scale-100 opacity-100"
                : "translate-y-2 scale-90 opacity-0",
            )}
          >
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <span className="anim-led h-1.5 w-1.5 rounded-full bg-success" />
              Troca de dados
            </div>
            <p className="mt-1.5 text-[13px] font-medium leading-snug text-foreground">
              Supervisor: “Monitor, como está o cluster?”
            </p>
            <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              Monitor: “Tudo vigiado! Conferindo os pods
              <span className="inline-flex gap-0.5">
                <span className="anim-type h-1 w-1 rounded-full bg-muted-foreground" />
                <span className="anim-type h-1 w-1 rounded-full bg-muted-foreground [animation-delay:0.15s]" />
                <span className="anim-type h-1 w-1 rounded-full bg-muted-foreground [animation-delay:0.3s]" />
              </span>
              ”
            </p>
            <span
              aria-hidden
              className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-border bg-card"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
