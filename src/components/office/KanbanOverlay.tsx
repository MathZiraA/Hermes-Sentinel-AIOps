import { Github } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentFigure } from "./AgentFigure";
import { agentClass, type AgentColor } from "./agents";

type Card = { id: string; title: string; agent: AgentColor; agentName: string; progress?: number; meta: string };

const CARDS: Card[] = [
  { id: "SAMS-201", title: "Build real-time agent activity engine", agent: "blue", agentName: "Atlas", progress: 72, meta: "Engine" },
  { id: "SAMS-202", title: "Kanban sync with Github Projects", agent: "green", agentName: "Moss", meta: "Integrations" },
];

function MiniAvatar({ color }: { color: AgentColor }) {
  return (
    <div className={cn("flex h-7 w-7 items-end justify-center overflow-hidden rounded-full bg-muted agent-ring", agentClass(color))}>
      <div className="translate-y-[3px]">
        <AgentFigure color={color} size={0.36} />
      </div>
    </div>
  );
}

export function KanbanOverlay() {
  return (
    <div className="anim-float pointer-events-auto absolute left-6 top-6 z-30 w-[290px]">
      <div className="glass-panel rounded-2xl border border-border/80 p-3 shadow-float">
        <div className="mb-2.5 flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-agent-blue" />
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground">In Progress</span>
          </div>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">2</span>
        </div>

        <div className="flex flex-col gap-2">
          {CARDS.map((c) => (
            <article key={c.id} className={cn("rounded-xl border border-border bg-card p-3 shadow-card", agentClass(c.agent))}>
              <div className="flex items-start gap-2.5">
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px] font-semibold leading-snug text-foreground">
                    <span className="agent-text">{c.id}:</span> {c.title}
                  </p>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    {c.agent === "green" && <Github className="h-3 w-3" />}
                    <span>{c.meta}</span>
                    <span>·</span>
                    <span>{c.agentName}</span>
                  </div>
                </div>
                <MiniAvatar color={c.agent} />
              </div>
              {c.progress !== undefined && (
                <div className="mt-2.5">
                  <div className="mb-1 flex justify-between text-[10px] font-medium text-muted-foreground">
                    <span>Progress</span>
                    <span className="text-foreground">{c.progress}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="progress-agent h-full rounded-full" style={{ width: `${c.progress}%` }} />
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
