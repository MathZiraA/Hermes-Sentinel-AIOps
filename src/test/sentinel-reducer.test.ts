import { describe, expect, it } from "vitest";
import { initialTelemetry, telemetryReducer } from "@/lib/sentinel/reducer";
import type { AgentEvent } from "@/lib/sentinel/types";

const ev = (over: Partial<AgentEvent>): AgentEvent => ({
  type: "agent",
  timestamp: "2026-11-17T19:00:00.000Z",
  agentId: "executor",
  agentName: "Executor",
  role: "Remediação",
  status: "waiting_approval",
  targetZone: "WORKSTATION",
  bubbleMessage: "Aguardando aprovação",
  technicalLog: "",
  ...over,
});

describe("telemetry reducer", () => {
  it("moves the agent and records the approval request", () => {
    const s = telemetryReducer(initialTelemetry, {
      kind: "message",
      msg: ev({
        approvalRequest: {
          incidentId: "INC-1",
          action: "rollout_restart",
          command: "kubectl rollout restart deployment/pedidos",
          description: "",
          target: "stockflow/pedidos",
          risk: "baixo",
          simulated: true,
        },
      }),
    });
    expect(s.agents.executor.status).toBe("waiting_approval");
    expect(Object.keys(s.approvals)).toEqual(["INC-1"]);
    const resolved = telemetryReducer(s, {
      kind: "message",
      msg: { type: "approval_resolved", timestamp: "", incidentId: "INC-1", decision: "approved" },
    });
    expect(resolved.approvals).toEqual({});
  });

  it("creates and moves kanban cards", () => {
    let s = telemetryReducer(initialTelemetry, {
      kind: "message",
      msg: ev({
        agentId: "itsm",
        kanbanAction: {
          op: "create",
          cardId: "INC-2",
          title: "OOMKilled",
          column: "Backlog",
          progress: 5,
        },
      }),
    });
    s = telemetryReducer(s, {
      kind: "message",
      msg: ev({
        agentId: "itsm",
        kanbanAction: { op: "move", cardId: "INC-2", column: "Concluído", progress: 100 },
      }),
    });
    expect(s.kanban["INC-2"]).toMatchObject({
      title: "OOMKilled",
      column: "Concluído",
      progress: 100,
    });
  });

  it("caps the event history", () => {
    let s = initialTelemetry;
    for (let i = 0; i < 60; i++)
      s = telemetryReducer(s, { kind: "message", msg: ev({ bubbleMessage: `m${i}` }) });
    expect(s.events).toHaveLength(40);
    expect(s.events.at(-1)?.bubbleMessage).toBe("m59");
  });
});
