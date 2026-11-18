import type { AgentId, AgentStatus, Zone } from "@/lib/sentinel/types";

export type AgentColor = "blue" | "orange" | "purple" | "green" | "yellow";
export type Accessory = "headset" | "key" | "marker" | "papers" | "cap";

export type Agent = {
  id: AgentId;
  name: string;
  color: AgentColor;
  role: string;
  /** Texto padrão do balão quando o backend ainda não falou nada. */
  activity: string;
  home: Zone;
  accessory: Accessory;
  delay: number;
};

/** Os 5 agentes do Hermes Sentinel e a zona "de casa" de cada um. */
export const AGENTS: Agent[] = [
  {
    id: "supervisor",
    name: "Supervisor",
    color: "green",
    role: "Coordenador",
    activity: "Coordenando a equipe",
    home: "CENTRAL_HUB",
    accessory: "papers",
    delay: 0,
  },
  {
    id: "monitor",
    name: "Monitor",
    color: "yellow",
    role: "Watcher do cluster",
    activity: "Vigiando o cluster k8s",
    home: "AGENT_FACTORY",
    accessory: "cap",
    delay: 0.4,
  },
  {
    id: "investigator",
    name: "Investigator",
    color: "purple",
    role: "Causa raiz (RCA)",
    activity: "Revisando runbooks",
    home: "WHITEBOARD",
    accessory: "marker",
    delay: 0.8,
  },
  {
    id: "executor",
    name: "Executor",
    color: "blue",
    role: "Remediação",
    activity: "Pronto para corrigir",
    home: "WORKSTATION",
    accessory: "headset",
    delay: 1.2,
  },
  {
    id: "itsm",
    name: "ITSM",
    color: "orange",
    role: "Kanban · Issues · Post-Mortem",
    activity: "Organizando o cofre",
    home: "VAULT",
    accessory: "key",
    delay: 1.6,
  },
];

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<
  AgentId,
  Agent
>;

/** Ponto de chegada (floor px) de cada zona da cena isométrica. */
export const ZONES: Record<Zone, { x: number; y: number; z?: number; label: string }> = {
  WORKSTATION: { x: 190, y: 200, label: "Workstation" },
  WHITEBOARD: { x: 500, y: 130, label: "Whiteboard" },
  AGENT_FACTORY: { x: 585, y: 245, label: "Agent Factory" },
  CENTRAL_HUB: { x: 360, y: 370, label: "Central Hub" },
  VAULT: { x: 520, y: 560, label: "Vault" },
  KANBAN_WALL: { x: 165, y: 430, label: "Kanban Wall" },
};

/** Deslocamento de quem visita uma zona que não é a sua, para não sobrepor o dono. */
const VISIT_OFFSET: Record<AgentId, { x: number; y: number }> = {
  supervisor: { x: -48, y: 40 },
  monitor: { x: -40, y: -40 },
  investigator: { x: 44, y: -12 },
  executor: { x: 40, y: 44 },
  itsm: { x: 46, y: 30 },
};

export function agentPosition(
  agent: Agent,
  zone: Zone,
): { x: number; y: number; z: number; seated: boolean } {
  const base = ZONES[zone];
  if (zone === agent.home) {
    // O Executor trabalha sentado no banco da workstation.
    const seated = agent.id === "executor" && zone === "WORKSTATION";
    return { x: base.x, y: base.y, z: seated ? 30 : 0, seated };
  }
  const o = VISIT_OFFSET[agent.id];
  return { x: base.x + o.x, y: base.y + o.y, z: 0, seated: false };
}

export const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: "Ocioso",
  monitoring: "Vigiando",
  walking: "Caminhando",
  alert: "Alerta",
  talking: "Falando",
  investigating: "Investigando",
  thinking: "Pensando",
  waiting_approval: "Aguardando aprovação",
  executing: "Executando",
  writing: "Escrevendo",
  done: "Concluído",
  error: "Erro",
};

/** Tom do badge de status (classes Tailwind). */
export function statusTone(s: AgentStatus): string {
  switch (s) {
    case "alert":
    case "error":
      return "bg-destructive text-white";
    case "waiting_approval":
      return "bg-agent-yellow text-ink-soft";
    case "executing":
    case "investigating":
    case "thinking":
      return "bg-agent-blue text-white";
    case "done":
      return "bg-success text-white";
    case "walking":
    case "talking":
    case "writing":
      return "bg-agent-purple text-white";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export const agentClass = (c: AgentColor) => `agent-${c}`;
