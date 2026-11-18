import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import { initialTelemetry, telemetryReducer, type TelemetryState } from "./reducer";
import type { IncidentType, ServerMessage } from "./types";
import { api, wsUrl } from "@/lib/api/client";

export const sentinelApi = {
  testCommunication: () => api.post("/api/test-communication"),
  simulateIncident: (type: IncidentType, useAi: boolean) =>
    api.post("/api/simulate/incident", { type, useAi }),
  approve: (incidentId: string, motivo = "") =>
    api.post(`/api/agents/approve/${encodeURIComponent(incidentId)}`, { motivo }),
  reject: (incidentId: string, motivo = "") =>
    api.post(`/api/agents/reject/${encodeURIComponent(incidentId)}`, { motivo }),
  refreshHealth: () => api.get("/api/health"),
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
      ws.onclose = (ev) => {
        clearInterval(pingTimer);
        dispatch({ kind: "connection", state: "closed" });
        if (ev.code === 4401 || ev.code === 4403) return; // sem sessão: o RequireAuth leva ao login
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
