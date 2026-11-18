import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  ActionInfo,
  AiUsage,
  AdminTeam,
  AdminUser,
  AuditEntry,
  BrainGraph,
  ClusterInfo,
  ClusterStatus,
  IncidentDetail,
  IncidentSummary,
  Page,
  Policy,
  ReportSummary,
  Shift,
  Silence,
} from "./types";

export interface IncidentFilters {
  status?: string[];
  sev?: string[];
  q?: string;
  limit?: number;
  offset?: number;
}

function qs(params: Record<string, string | number | string[] | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
    else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

const LIVE = 10_000; // atualização periódica; os eventos do WebSocket também invalidam as consultas

export const useIncidents = (f: IncidentFilters) =>
  useQuery({
    queryKey: ["incidents", f],
    queryFn: () => api.get<Page<IncidentSummary>>(`/api/incidents${qs({ ...f })}`),
    refetchInterval: LIVE,
  });

export const useIncident = (id: string) =>
  useQuery({
    queryKey: ["incident", id],
    queryFn: () => api.get<IncidentDetail>(`/api/incidents/${encodeURIComponent(id)}`),
    refetchInterval: 5_000,
  });

export const useSummary = (days = 30) =>
  useQuery({
    queryKey: ["summary", days],
    queryFn: () => api.get<ReportSummary>(`/api/reports/summary?days=${days}`),
    refetchInterval: 30_000,
  });

export const useClusters = () =>
  useQuery({ queryKey: ["clusters"], queryFn: () => api.get<ClusterInfo[]>("/api/clusters") });

export const useClusterStatus = (id: string) =>
  useQuery({
    queryKey: ["cluster-status", id],
    queryFn: () => api.get<ClusterStatus>(`/api/clusters/${encodeURIComponent(id)}/status`),
    refetchInterval: 15_000,
    retry: false,
  });

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<Record<string, unknown>>("/api/health"),
    refetchInterval: 30_000,
  });

export const useAudit = (limit = 100, offset = 0) =>
  useQuery({
    queryKey: ["audit", limit, offset],
    queryFn: () => api.get<Page<AuditEntry>>(`/api/audit?limit=${limit}&offset=${offset}`),
  });

export const useUsers = () =>
  useQuery({ queryKey: ["users"], queryFn: () => api.get<AdminUser[]>("/api/admin/users") });

export const useTeams = () =>
  useQuery({ queryKey: ["teams"], queryFn: () => api.get<AdminTeam[]>("/api/admin/teams") });

export const useBrainGraph = () =>
  useQuery({ queryKey: ["brain-graph"], queryFn: () => api.get<BrainGraph>("/api/brain/graph") });

export const useBrainSearch = (q: string) =>
  useQuery({
    queryKey: ["brain-search", q],
    queryFn: () =>
      api.get<{ nota: string; pasta: string; trecho: string }[]>(
        `/api/brain/search?q=${encodeURIComponent(q)}`,
      ),
    enabled: q.trim().length >= 2,
  });

export const useBrainNote = (name: string | null) =>
  useQuery({
    queryKey: ["brain-note", name],
    queryFn: () =>
      api.get<{ name: string; folder: string; markdown: string }>(
        `/api/brain/notes/${encodeURIComponent(name ?? "")}`,
      ),
    enabled: !!name,
  });

/** Ações sobre incidentes: depois de cada uma, atualiza listas e o detalhe. */
export function useIncidentActions(id: string) {
  const qc = useQueryClient();
  const done = () => {
    void qc.invalidateQueries({ queryKey: ["incident", id] });
    void qc.invalidateQueries({ queryKey: ["incidents"] });
    void qc.invalidateQueries({ queryKey: ["summary"] });
  };
  const enc = encodeURIComponent(id);
  return {
    acknowledge: useMutation({
      mutationFn: () => api.post(`/api/incidents/${enc}/acknowledge`),
      onSuccess: done,
    }),
    approve: useMutation({
      mutationFn: (motivo: string) => api.post(`/api/agents/approve/${enc}`, { motivo }),
      onSuccess: done,
    }),
    reject: useMutation({
      mutationFn: (motivo: string) => api.post(`/api/agents/reject/${enc}`, { motivo }),
      onSuccess: done,
    }),
  };
}

export const useAiUsage = (days = 30) =>
  useQuery({
    queryKey: ["ai-usage", days],
    queryFn: () => api.get<AiUsage>(`/api/ai/usage?days=${days}`),
    refetchInterval: 60_000,
  });

export const useSilences = () =>
  useQuery({ queryKey: ["silences"], queryFn: () => api.get<Silence[]>("/api/silences") });

export const usePolicies = () =>
  useQuery({ queryKey: ["policies"], queryFn: () => api.get<Policy[]>("/api/policies") });

export const useShifts = () =>
  useQuery({ queryKey: ["oncall"], queryFn: () => api.get<Shift[]>("/api/oncall") });

export const useActions = () =>
  useQuery({
    queryKey: ["actions"],
    queryFn: () => api.get<ActionInfo[]>("/api/actions"),
    staleTime: Infinity,
  });
