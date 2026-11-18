import { ExternalLink, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { useKanbanCards } from "@/lib/sentinel/telemetry";
import type { KanbanColumn } from "@/lib/sentinel/types";
import { AgentFigure } from "./AgentFigure";
import { AGENT_BY_ID, agentClass, type AgentColor } from "./agents";

const COLUMN_TONE: Record<KanbanColumn, string> = {
  Backlog: "bg-agent-purple",
  Investigando: "bg-agent-blue",
  "Aguardando aprovação": "bg-agent-yellow",
  Corrigindo: "bg-agent-orange",
  Concluído: "bg-agent-green",
};

function MiniAvatar({ color }: { color: AgentColor }) {
  return (
    <div
      className={cn(
        "flex h-7 w-7 shrink-0 items-end justify-center overflow-hidden rounded-full bg-muted agent-ring",
        agentClass(color),
      )}
    >
      <div className="translate-y-[3px]">
        <AgentFigure color={color} size={0.36} />
      </div>
    </div>
  );
}

/** Incidentes em andamento (e o último concluído), vindos do WebSocket. */
export function KanbanOverlay() {
  const cards = useKanbanCards();
  const open = cards.filter((c) => c.column !== "Concluído");
  const lastDone = cards.find((c) => c.column === "Concluído");
  const visible = [...open.slice(0, 3), ...(lastDone && open.length < 3 ? [lastDone] : [])];

  return (
    <div className="anim-float pointer-events-auto absolute left-6 top-6 z-30 w-[300px] max-w-[calc(100%-3rem)]">
      <div className="glass-panel rounded-2xl border border-border/80 p-3 shadow-float">
        <div className="mb-2.5 flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                open.length ? "bg-agent-orange anim-led" : "bg-success",
              )}
            />
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground">
              Incidentes
            </span>
          </div>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
            {open.length} abertos
          </span>
        </div>

        {visible.length === 0 ? (
          <div className="flex items-center gap-2.5 rounded-xl border border-border bg-card p-3 shadow-card">
            <ShieldCheck className="h-4 w-4 text-success" />
            <p className="text-[12px] leading-snug text-muted-foreground">
              Nenhum incidente. O Monitor vigia o cluster sem gastar IA.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {visible.map((c) => {
              const agent = c.agentId ? AGENT_BY_ID[c.agentId] : undefined;
              const color = agent?.color ?? "green";
              return (
                <article
                  key={c.cardId}
                  className={cn(
                    "anim-bubble-in rounded-xl border border-border bg-card p-3 shadow-card",
                    agentClass(color),
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] font-semibold leading-snug text-foreground">
                        <span className="agent-text font-mono text-[11px]">{c.cardId}</span>
                        <br />
                        {c.title}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                        <span
                          className={cn(
                            "rounded-full px-1.5 py-[1px] font-semibold text-white",
                            COLUMN_TONE[c.column],
                          )}
                        >
                          {c.column}
                        </span>
                        {agent && <span>{agent.name}</span>}
                        {c.url && (
                          <a
                            href={c.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-0.5 text-primary hover:underline"
                          >
                            issue <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        )}
                      </div>
                    </div>
                    <MiniAvatar color={color} />
                  </div>
                  <div className="mt-2.5">
                    <div className="mb-1 flex justify-between text-[10px] font-medium text-muted-foreground">
                      <span>Progresso</span>
                      <span className="text-foreground">{c.progress}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      {/* scaleX em vez de width: a barra anima na GPU */}
                      <div
                        className="progress-agent h-full origin-left rounded-full transition-transform duration-700 ease-[cubic-bezier(0.23,1,0.32,1)]"
                        style={{
                          transform: `scaleX(${Math.max(0, Math.min(100, c.progress)) / 100})`,
                        }}
                      />
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
