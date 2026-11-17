import { useState } from "react";
import { Github, ListChecks, RefreshCw, SquareKanban } from "lucide-react";
import { cn } from "@/lib/utils";
import { AGENTS, agentClass } from "./agents";
import { AgentCard } from "@/components/agent/AgentCard";

const COLUMNS = [
  { name: "Backlog", count: 8, tone: "bg-agent-purple" },
  { name: "In Progress", count: 2, tone: "bg-agent-blue" },
  { name: "Review", count: 3, tone: "bg-agent-orange" },
  { name: "Done", count: 14, tone: "bg-agent-green" },
];

const EVENTS = [
  { title: "Assign Card", detail: "SAMS-201 → Atlas", time: "2m", color: "blue" as const },
  { title: "Change Column Mapping", detail: "Review → In QA", time: "9m", color: "purple" as const },
  { title: "Review Queue", detail: "3 cards waiting · Sunny", time: "14m", color: "yellow" as const },
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{children}</h3>;
}

export function SystemSidebar() {
  const [syncing, setSyncing] = useState(false);
  const [synced, setSynced] = useState("5 min ago");
  const max = Math.max(...COLUMNS.map((c) => c.count));

  const sync = () => {
    if (syncing) return;
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
      setSynced("just now");
    }, 1400);
  };

  const items = [
    { label: "Item Tasks", icon: ListChecks },
    { label: "Open in Board", icon: SquareKanban },
    { label: "Link Github Project", icon: Github },
  ];

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-l border-border bg-sidebar px-6 py-7 text-sidebar-foreground">
      <header>
        <h1 className="text-[11px] font-bold uppercase tracking-[0.28em] text-foreground">System Overview</h1>
        <div className="mt-5 flex items-baseline justify-between">
          <p className="text-[15px] font-semibold text-foreground">5 Agents Active</p>
          <span className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
            <span className="anim-led h-1.5 w-1.5 rounded-full bg-success" /> live
          </span>
        </div>
        <div className="mt-2.5 flex h-2 gap-[3px] overflow-hidden rounded-full">
          {AGENTS.map((a) => (
            <div key={a.id} className={cn("progress-agent flex-1 first:rounded-l-full last:rounded-r-full", agentClass(a.color))} title={a.name} />
          ))}
        </div>
      </header>

      <section className="mt-7">
        <AgentCard name="Atlas" role="Builder" />
      </section>

      <section className="mt-8">
        <SectionLabel>Kanban Wall</SectionLabel>
        <div className="grid grid-cols-4 gap-2">
          {COLUMNS.map((c) => (
            <div key={c.name} className="flex flex-col items-center gap-1.5 rounded-xl bg-muted/70 px-1 pb-2 pt-2.5">
              <div className="flex h-12 w-2 items-end overflow-hidden rounded-full bg-border">
                <div className={cn("w-full rounded-full", c.tone)} style={{ height: `${(c.count / max) * 100}%` }} />
              </div>
              <span className="text-[13px] font-semibold text-foreground">{c.count}</span>
              <span className="text-center text-[9px] leading-tight text-muted-foreground">{c.name}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <SectionLabel>Work Items</SectionLabel>
        <div className="flex flex-col gap-1.5">
          {items.map(({ label, icon: Icon }) => (
            <button
              key={label}
              type="button"
              className="group flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2 text-left text-[12.5px] font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <Icon className="h-3.5 w-3.5 text-muted-foreground transition-colors group-hover:text-primary" />
              {label}
            </button>
          ))}
          <button
            type="button"
            onClick={sync}
            className="mt-1 flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-[12.5px] font-semibold text-primary-foreground shadow-card transition hover:brightness-105 active:scale-[0.98]"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
            {syncing ? "Syncing…" : "Sync Now"}
          </button>
          <p className="text-center text-[10px] text-muted-foreground">Last synced {synced}</p>
        </div>
      </section>

      <section className="mt-8">
        <SectionLabel>Recent Events</SectionLabel>
        <ol className="relative flex flex-col">
          {EVENTS.map((e, i) => (
            <li key={e.title} className={cn("relative flex gap-3 pb-4", agentClass(e.color))}>
              {i < EVENTS.length - 1 && <span className="absolute left-[4px] top-3 h-full w-px bg-border" />}
              <span className="agent-fill relative mt-1 h-[9px] w-[9px] shrink-0 rounded-full ring-2 ring-card" />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[12.5px] font-medium text-foreground">{e.title}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{e.time}</span>
                </div>
                <p className="text-[11px] text-muted-foreground">{e.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </aside>
  );
}
