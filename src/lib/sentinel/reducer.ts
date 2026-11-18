import type {
  AgentEvent,
  AgentId,
  AgentLive,
  ApprovalRequest,
  ConnectionState,
  Health,
  KanbanAction,
  KanbanCard,
  ServerMessage,
} from "./types";

export type TelemetryState = {
  connection: ConnectionState;
  agents: Record<AgentId, AgentLive>;
  kanban: Record<string, KanbanCard>;
  approvals: Record<string, ApprovalRequest>;
  health: Health;
  events: AgentEvent[];
};

export type TelemetryAction =
  { kind: "message"; msg: ServerMessage } | { kind: "connection"; state: ConnectionState };

const MAX_EVENTS = 40;

/** Estado inicial (antes do WebSocket): agentes nas suas zonas de casa. */
export const INITIAL_AGENTS: Record<AgentId, AgentLive> = {
  monitor: {
    agentId: "monitor",
    agentName: "Monitor",
    role: "Watcher do cluster",
    status: "monitoring",
    zone: "AGENT_FACTORY",
    bubbleMessage: "",
    updatedAt: "",
  },
  supervisor: {
    agentId: "supervisor",
    agentName: "Supervisor",
    role: "Coordenador",
    status: "idle",
    zone: "CENTRAL_HUB",
    bubbleMessage: "",
    updatedAt: "",
  },
  investigator: {
    agentId: "investigator",
    agentName: "Investigator",
    role: "Análise de causa raiz",
    status: "idle",
    zone: "WHITEBOARD",
    bubbleMessage: "",
    updatedAt: "",
  },
  executor: {
    agentId: "executor",
    agentName: "Executor",
    role: "Remediação",
    status: "idle",
    zone: "WORKSTATION",
    bubbleMessage: "",
    updatedAt: "",
  },
  itsm: {
    agentId: "itsm",
    agentName: "ITSM",
    role: "Kanban, Issues e Post-Mortem",
    status: "idle",
    zone: "VAULT",
    bubbleMessage: "",
    updatedAt: "",
  },
};

export const initialTelemetry: TelemetryState = {
  connection: "connecting",
  agents: INITIAL_AGENTS,
  kanban: {},
  approvals: {},
  health: {},
  events: [],
};

function applyKanban(
  kanban: Record<string, KanbanCard>,
  a: KanbanAction,
  at: string,
): Record<string, KanbanCard> {
  const prev = kanban[a.cardId] ?? {
    cardId: a.cardId,
    title: a.title ?? a.cardId,
    column: "Backlog",
    progress: 0,
  };
  const next: KanbanCard = { ...prev };
  if (a.title != null) next.title = a.title;
  if (a.column != null) next.column = a.column;
  if (a.progress != null) next.progress = a.progress;
  if (a.agentId != null) next.agentId = a.agentId;
  if (a.url != null) next.url = a.url;
  next.updatedAt = at;
  return { ...kanban, [a.cardId]: next };
}

export function telemetryReducer(state: TelemetryState, action: TelemetryAction): TelemetryState {
  if (action.kind === "connection") return { ...state, connection: action.state };
  const msg = action.msg;
  switch (msg.type) {
    case "snapshot": {
      const agents = { ...INITIAL_AGENTS };
      for (const a of msg.agents) agents[a.agentId] = a;
      return {
        ...state,
        agents,
        kanban: Object.fromEntries(msg.kanban.map((c) => [c.cardId, c])),
        health: msg.health ?? {},
        events: msg.events.slice(-MAX_EVENTS),
        approvals: {},
      };
    }
    case "agent": {
      const agents = {
        ...state.agents,
        [msg.agentId]: {
          ...state.agents[msg.agentId],
          status: msg.status,
          zone: msg.targetZone,
          bubbleMessage: msg.bubbleMessage,
          updatedAt: msg.timestamp,
        },
      };
      const kanban = msg.kanbanAction
        ? applyKanban(state.kanban, msg.kanbanAction, msg.timestamp)
        : state.kanban;
      const approvals = msg.approvalRequest
        ? { ...state.approvals, [msg.approvalRequest.incidentId]: msg.approvalRequest }
        : state.approvals;
      return {
        ...state,
        agents,
        kanban,
        approvals,
        events: [...state.events, msg].slice(-MAX_EVENTS),
      };
    }
    case "health":
      return { ...state, health: msg.health };
    case "approval_pending":
      return {
        ...state,
        approvals: { ...state.approvals, [msg.approvalRequest.incidentId]: msg.approvalRequest },
      };
    case "approval_resolved": {
      const { [msg.incidentId]: _done, ...rest } = state.approvals;
      return { ...state, approvals: rest };
    }
    default:
      return state;
  }
}
