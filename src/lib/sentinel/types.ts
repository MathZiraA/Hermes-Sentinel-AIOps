/** Contratos do backend Hermes Sentinel (espelham backend/schemas/events.py). */

export type AgentId = "monitor" | "supervisor" | "investigator" | "executor" | "itsm";
export type Zone =
  "AGENT_FACTORY" | "CENTRAL_HUB" | "WHITEBOARD" | "WORKSTATION" | "VAULT" | "KANBAN_WALL";
export type AgentStatus =
  | "idle"
  | "monitoring"
  | "walking"
  | "alert"
  | "talking"
  | "investigating"
  | "thinking"
  | "waiting_approval"
  | "executing"
  | "writing"
  | "done"
  | "error";
export type IncidentType = "OOMKilled" | "CrashLoopBackOff" | "ImagePullBackOff";
export type KanbanColumn =
  "Backlog" | "Investigando" | "Aguardando aprovação" | "Corrigindo" | "Concluído";

export const KANBAN_COLUMNS: KanbanColumn[] = [
  "Backlog",
  "Investigando",
  "Aguardando aprovação",
  "Corrigindo",
  "Concluído",
];

export type KanbanAction = {
  op: "create" | "move" | "update";
  cardId: string;
  title?: string | null;
  column?: KanbanColumn | null;
  agentId?: AgentId | null;
  progress?: number | null;
  url?: string | null;
};

export type ApprovalRequest = {
  incidentId: string;
  action: "rollout_restart" | "scale" | "delete_pod" | "none";
  command: string;
  description: string;
  target: string;
  risk: "baixo" | "médio" | "alto";
  simulated: boolean;
};

export type AgentEvent = {
  type: "agent";
  timestamp: string;
  agentId: AgentId;
  agentName: string;
  role: string;
  status: AgentStatus;
  targetZone: Zone;
  bubbleMessage: string;
  technicalLog: string;
  incidentId?: string | null;
  kanbanAction?: KanbanAction | null;
  approvalRequest?: ApprovalRequest | null;
};

export type AgentLive = {
  agentId: AgentId;
  agentName: string;
  role: string;
  status: AgentStatus;
  zone: Zone;
  bubbleMessage: string;
  updatedAt: string;
};

export type KanbanCard = {
  cardId: string;
  title: string;
  column: KanbanColumn;
  progress: number;
  agentId?: AgentId;
  url?: string | null;
  updatedAt?: string;
};

export type HealthItem = { ok: boolean; detail?: string; [k: string]: unknown };
export type Health = {
  checkedAt?: string;
  kubernetes?: HealthItem;
  hermesGateway?: HealthItem;
  obsidian?: HealthItem;
  github?: HealthItem;
};

export type ServerMessage =
  | {
      type: "snapshot";
      timestamp: string;
      agents: AgentLive[];
      kanban: KanbanCard[];
      health: Health;
      events: AgentEvent[];
    }
  | AgentEvent
  | { type: "health"; timestamp: string; health: Health }
  | { type: "approval_pending"; timestamp: string; approvalRequest: ApprovalRequest }
  | {
      type: "approval_resolved";
      timestamp: string;
      incidentId: string;
      decision: "approved" | "rejected";
    }
  | { type: "pong"; timestamp: string };

export type ConnectionState = "connecting" | "open" | "closed";
