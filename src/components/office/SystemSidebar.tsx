import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  BookOpen,
  Bot,
  Check,
  Cloud,
  FlaskConical,
  Github,
  MessagesSquare,
  Server,
  ShieldAlert,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { sentinelApi, useKanbanCards, useTelemetry } from "@/lib/sentinel/telemetry";
import {
  KANBAN_COLUMNS,
  type ApprovalRequest,
  type HealthItem,
  type IncidentType,
} from "@/lib/sentinel/types";
import { AGENTS, AGENT_BY_ID, STATUS_LABEL, agentClass, statusTone } from "./agents";

const BTN =
  "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-[12.5px] font-medium transition-[transform,opacity] duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50";

const COLUMN_TONE = [
  "bg-agent-purple",
  "bg-agent-blue",
  "bg-agent-yellow",
  "bg-agent-orange",
  "bg-agent-green",
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
      {children}
    </h3>
  );
}

function timeAgo(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.round(s / 3600)}h`;
}

function HealthRow({
  icon: Icon,
  label,
  item,
  live,
}: {
  icon: typeof Server;
  label: string;
  item?: HealthItem | undefined;
  live: boolean;
}) {
  const state = !live || !item ? "unknown" : item.ok ? "ok" : "down";
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-medium text-foreground">{label}</p>
        <p className="truncate text-[10px] text-muted-foreground" title={item?.detail}>
          {state === "unknown" ? "aguardando backend…" : item?.detail}
        </p>
      </div>
      <span
        className={cn(
          "rounded-full px-1.5 py-[1px] text-[9px] font-bold uppercase tracking-wide",
          state === "ok" && "bg-success text-white",
          state === "down" && "bg-destructive text-white",
          state === "unknown" && "bg-muted text-muted-foreground",
        )}
      >
        {state === "ok" ? "online" : state === "down" ? "offline" : "—"}
      </span>
    </div>
  );
}

function ApprovalBanner({ req }: { req: ApprovalRequest }) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = async (kind: "approve" | "reject") => {
    setBusy(kind);
    setError(null);
    try {
      await (kind === "approve"
        ? sentinelApi.approve(req.incidentId)
        : sentinelApi.reject(req.incidentId));
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };
  return (
    <div
      role="alert"
      className="anim-bubble-in rounded-xl border-2 border-agent-yellow bg-agent-yellow/10 p-3 shadow-card"
    >
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-agent-orange" />
        <p className="text-[12px] font-bold text-foreground">Aprovação humana necessária</p>
        {req.simulated && (
          <span className="ml-auto rounded-full bg-muted px-1.5 text-[9px] font-semibold text-muted-foreground">
            SIMULADO
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
        O <b className="text-foreground">Executor</b> quer corrigir{" "}
        <b className="text-foreground">{req.target}</b> ({req.incidentId}). Risco: {req.risk}.
      </p>
      <code className="mt-2 block break-all rounded-md bg-screen px-2 py-1.5 font-mono text-[10.5px] text-card">
        {req.command}
      </code>
      {req.description && (
        <p className="mt-1.5 text-[10.5px] italic leading-snug text-muted-foreground">
          {req.description}
        </p>
      )}
      <div className="mt-2.5 grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={!!busy}
          onClick={() => act("reject")}
          className={cn(BTN, "border border-border bg-card text-foreground hover:bg-accent")}
        >
          <X className="h-3.5 w-3.5" /> {busy === "reject" ? "Rejeitando…" : "Rejeitar"}
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() => act("approve")}
          className={cn(
            BTN,
            "bg-success font-semibold text-white shadow-card hover:brightness-105",
          )}
        >
          <Check className="h-3.5 w-3.5" /> {busy === "approve" ? "Aplicando…" : "Aprovar"}
        </button>
      </div>
      {error && <p className="mt-1.5 text-[10px] text-destructive">{error}</p>}
    </div>
  );
}

export function SystemSidebar() {
  const { connection, agents, health, approvals, events } = useTelemetry();
  const cards = useKanbanCards();
  const live = connection === "open";
  const [incidentType, setIncidentType] = useState<IncidentType>("OOMKilled");
  const [useAi, setUseAi] = useState(false);
  const [pending, setPending] = useState<"comm" | "sim" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (kind: "comm" | "sim") => {
    setPending(kind);
    setError(null);
    try {
      await (kind === "comm"
        ? sentinelApi.testCommunication()
        : sentinelApi.simulateIncident(incidentType, useAi));
    } catch {
      setError("Backend offline. Rode ./start.sh (porta 8000).");
    } finally {
      setTimeout(() => setPending(null), 1200);
    }
  };

  const counts = KANBAN_COLUMNS.map((c) => cards.filter((k) => k.column === c).length);
  const max = Math.max(1, ...counts);
  const busyAgents = AGENTS.filter(
    (a) => !["idle", "monitoring"].includes(agents[a.id].status),
  ).length;
  const recent = events.slice(-6).reverse();

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-l border-border bg-sidebar px-6 py-7 text-sidebar-foreground">
      <header>
        <h1 className="text-[11px] font-bold uppercase tracking-[0.28em] text-foreground">
          Hermes Sentinel
        </h1>
        <div className="mt-5 flex items-baseline justify-between">
          <p className="text-[15px] font-semibold text-foreground">
            5 agentes · {busyAgents ? `${busyAgents} em ação` : "vigiando"}
          </p>
          <span className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                live
                  ? "anim-led bg-success"
                  : connection === "connecting"
                    ? "bg-agent-yellow"
                    : "bg-destructive",
              )}
            />
            {live ? "ao vivo" : connection === "connecting" ? "conectando" : "offline"}
          </span>
        </div>
        <div className="mt-2.5 flex h-2 gap-[3px] overflow-hidden rounded-full">
          {AGENTS.map((a) => (
            <div
              key={a.id}
              className={cn(
                "progress-agent flex-1 transition-opacity first:rounded-l-full last:rounded-r-full",
                agentClass(a.color),
                agents[a.id].status === "idle" && "opacity-35",
              )}
              title={`${a.name}: ${STATUS_LABEL[agents[a.id].status]}`}
            />
          ))}
        </div>
      </header>

      {Object.values(approvals).length > 0 && (
        <section className="mt-6 flex flex-col gap-2">
          {Object.values(approvals).map((r) => (
            <ApprovalBanner key={r.incidentId} req={r} />
          ))}
        </section>
      )}

      <section className="mt-7">
        <SectionLabel>Conexões</SectionLabel>
        <div className="flex flex-col gap-1.5">
          <HealthRow icon={Server} label="Kubernetes Local" item={health.kubernetes} live={live} />
          <HealthRow
            icon={Cloud}
            label="Hermes Gateway (VPS)"
            item={health.hermesGateway}
            live={live}
          />
          <HealthRow icon={BookOpen} label="Obsidian Vault" item={health.obsidian} live={live} />
          <HealthRow icon={Github} label="GitHub Issues" item={health.github} live={live} />
        </div>
      </section>

      <section className="mt-7">
        <SectionLabel>Ações</SectionLabel>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            disabled={!live || pending === "comm"}
            onClick={() => run("comm")}
            className={cn(
              BTN,
              "border border-border bg-card text-foreground hover:border-primary/40 hover:bg-accent",
            )}
          >
            <MessagesSquare className="h-3.5 w-3.5 text-primary" />
            {pending === "comm" ? "Agentes conversando…" : "Testar Comunicação"}
          </button>
          <Link
            to="/teste-comunicacao"
            className="text-center text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            ver cena de comunicação isolada
          </Link>

          <div className="mt-1 rounded-xl border border-border bg-card p-2.5">
            <div className="grid grid-cols-3 gap-1">
              {(["OOMKilled", "CrashLoopBackOff", "ImagePullBackOff"] as IncidentType[]).map(
                (t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setIncidentType(t)}
                    aria-pressed={incidentType === t}
                    className={cn(
                      "truncate rounded-md px-1 py-1 text-[9.5px] font-semibold transition-colors",
                      incidentType === t
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:text-foreground",
                    )}
                    title={t}
                  >
                    {t.replace("BackOff", "")}
                  </button>
                ),
              )}
            </div>
            <label className="mt-2 flex cursor-pointer items-center gap-2 text-[11px] text-muted-foreground">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(e) => setUseAi(e.target.checked)}
                className="accent-[var(--agent-purple)]"
              />
              <Bot className="h-3 w-3" /> Usar IA (Hermes · 1 chamada)
            </label>
            <button
              type="button"
              disabled={!live || pending === "sim"}
              onClick={() => run("sim")}
              className={cn(
                BTN,
                "mt-2 w-full bg-primary font-semibold text-primary-foreground shadow-card hover:brightness-105",
              )}
            >
              <FlaskConical className="h-3.5 w-3.5" />
              {pending === "sim" ? "Disparando…" : "Simular Incidente K8s"}
            </button>
          </div>
          {error && <p className="text-center text-[10px] text-destructive">{error}</p>}
        </div>
      </section>

      <section className="mt-7">
        <SectionLabel>Agentes</SectionLabel>
        <ul className="flex flex-col gap-1.5">
          {AGENTS.map((a) => {
            const s = agents[a.id];
            return (
              <li
                key={a.id}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2",
                  agentClass(a.color),
                )}
              >
                <span className="agent-fill h-2 w-2 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold text-foreground">{a.name}</p>
                  <p className="truncate text-[10px] text-muted-foreground">{a.role}</p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-1.5 py-[1px] text-[9px] font-bold uppercase tracking-wide",
                    statusTone(s.status),
                  )}
                >
                  {STATUS_LABEL[s.status]}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="mt-7">
        <SectionLabel>Kanban Wall</SectionLabel>
        <div className="grid grid-cols-5 gap-1.5">
          {KANBAN_COLUMNS.map((c, i) => (
            <div
              key={c}
              className="flex flex-col items-center gap-1.5 rounded-xl bg-muted/70 px-1 pb-2 pt-2.5"
            >
              <div className="flex h-12 w-2 items-end overflow-hidden rounded-full bg-border">
                <div
                  className={cn(
                    "h-full w-full origin-bottom rounded-full transition-transform duration-500",
                    COLUMN_TONE[i],
                  )}
                  style={{ transform: `scaleY(${(counts[i] ?? 0) / max})` }}
                />
              </div>
              <span className="text-[13px] font-semibold text-foreground">{counts[i]}</span>
              <span className="text-center text-[8.5px] leading-tight text-muted-foreground">
                {c}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-7">
        <SectionLabel>Eventos recentes</SectionLabel>
        {recent.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">
            Sem eventos ainda. Teste a comunicação ou simule um incidente.
          </p>
        ) : (
          <ol className="relative flex flex-col">
            {recent.map((e, i) => (
              <li
                key={`${e.timestamp}-${e.agentId}-${i}`}
                className={cn(
                  "relative flex gap-3 pb-3.5",
                  agentClass(AGENT_BY_ID[e.agentId]?.color ?? "green"),
                )}
              >
                {i < recent.length - 1 && (
                  <span className="absolute left-[4px] top-3 h-full w-px bg-border" />
                )}
                <span className="agent-fill relative mt-1 h-[9px] w-[9px] shrink-0 rounded-full ring-2 ring-card" />
                <div className="min-w-0 flex-1" title={e.technicalLog || undefined}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[12px] font-medium text-foreground">
                      {e.agentName} · {STATUS_LABEL[e.status]}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {timeAgo(e.timestamp)}
                    </span>
                  </div>
                  {e.bubbleMessage && (
                    <p className="text-[11px] leading-snug text-muted-foreground">
                      {e.bubbleMessage}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </aside>
  );
}
