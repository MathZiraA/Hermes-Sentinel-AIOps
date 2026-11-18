import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import { initialTelemetry, telemetryReducer, type TelemetryState } from "./reducer";
import type { IncidentType, ServerMessage } from "./types";

/** Backend local. Sobrescreva com VITE_SENTINEL_API_URL / VITE_SENTINEL_WS_URL. */
function apiBase(): string {
  const env = import.meta.env["VITE_SENTINEL_API_URL"] as string | undefined;
  if (env) return env.replace(/\/$/, "");
  const host = typeof window !== "undefined" ? window.location.hostname : "localhost";
  return `http://${host}:8000`;
}

function wsUrl(): string {
  const env = import.meta.env["VITE_SENTINEL_WS_URL"] as string | undefined;
  return env ?? apiBase().replace(/^http/, "ws") + "/ws/telemetry";
}

async function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: "POST" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${apiBase()}${path}`, init);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const sentinelApi = {
  testCommunication: () => post("/api/test-communication"),
  simulateIncident: (type: IncidentType, useAi: boolean) =>
    post("/api/simulate/incident", { type, useAi }),
  approve: (incidentId: string) => post(`/api/agents/approve/${encodeURIComponent(incidentId)}`),
  reject: (incidentId: string) => post(`/api/agents/reject/${encodeURIComponent(incidentId)}`),
  refreshHealth: () => fetch(`${apiBase()}/api/health`).then((r) => r.json()),
};

const TelemetryContext = createContext<TelemetryState>(initialTelemetry);

/**
 * Mantém uma conexão com /ws/telemetry e reconecta sozinha (backoff 1s → 10s).
 * Um ping a cada 25s mantém a conexão viva atrás de proxies.
 */
export function TelemetryProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(telemetryReducer, initialTelemetry);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      dispatch({ kind: "connection", state: "connecting" });
      try {
        ws = new WebSocket(wsUrl());
      } catch {
        scheduleReconnect();
        return;
      }
      ws.onopen = () => {
        retry = 0;
        dispatch({ kind: "connection", state: "open" });
        pingTimer = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send("ping"), 25_000);
      };
      ws.onmessage = (ev) => {
        try {
          dispatch({ kind: "message", msg: JSON.parse(ev.data as string) as ServerMessage });
        } catch {
          /* mensagem inválida: ignora */
        }
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        dispatch({ kind: "connection", state: "closed" });
        scheduleReconnect();
      };
      ws.onerror = () => ws?.close();
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      const delay = Math.min(10_000, 1000 * 2 ** retry++);
      reconnectTimer = setTimeout(connect, delay);
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      clearInterval(pingTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  return <TelemetryContext.Provider value={state}>{children}</TelemetryContext.Provider>;
}

export function useTelemetry(): TelemetryState {
  return useContext(TelemetryContext);
}

/** Cards do Kanban em ordem de atualização (mais recentes primeiro). */
export function useKanbanCards() {
  const { kanban } = useTelemetry();
  return useMemo(
    () =>
      Object.values(kanban).sort((a, b) => (b.updatedAt ?? "").localeCompare(a.updatedAt ?? "")),
    [kanban],
  );
}
