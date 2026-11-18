/** Contratos REST do backend (espelham backend/api e backend/schemas). */

export type Sev = "SEV1" | "SEV2" | "SEV3" | "SEV4";
export type IncidentStatus =
  | "detected"
  | "acknowledged"
  | "investigating"
  | "waiting_approval"
  | "remediating"
  | "monitoring"
  | "resolved"
  | "postmortem"
  | "closed"
  | "failed";

export const OPEN_STATUSES: IncidentStatus[] = [
  "detected",
  "acknowledged",
  "investigating",
  "waiting_approval",
  "remediating",
  "monitoring",
];

export interface Sla {
  ackDueAt: string;
  resolveDueAt: string;
  ackBreached: boolean;
  resolveBreached: boolean;
}

export interface Rca {
  rootCause?: string;
  evidence?: string[];
  confidence?: string;
  source?: string;
  learning?: string | null;
  stakeholderSummary?: string;
  followUps?: string[];
  runbooks?: string[];
  recommendedAction?: { type?: string; replicas?: number | null; reason?: string };
}

export interface IncidentSummary {
  id: string;
  cluster: string;
  type: string;
  namespace: string;
  pod: string;
  container: string | null;
  deployment: string | null;
  resourceKind: string;
  sev: Sev;
  reason: string;
  detectedAt: string;
  acknowledgedAt: string | null;
  acknowledgedBy: string | null;
  resolvedAt: string | null;
  simulated: boolean;
  status: IncidentStatus;
  statusLabel: string;
  proposedBy: string;
  decision: "approved" | "rejected" | null;
  decisionBy: string | null;
  decisionReason: string | null;
  decidedAt: string | null;
  rca: Rca | null;
  related: string[];
  approval: {
    incidentId: string;
    action: string;
    command: string;
    description: string;
    target: string;
    risk: string;
    simulated: boolean;
  } | null;
  remediationResult: string | null;
  assignedTo: string[];
  escalationLevel: number;
  reopenCount: number;
  autoRemediatedBy: string | null;
  rollout: {
    revision: string | null;
    previousRevision: string | null;
    images: string[];
    previousImages: string[];
    ageMinutes: number | null;
    commits?: { sha: string; message: string; author: string; url: string }[];
  } | null;
  source: string;
  ticket: { system: string; key: string; url: string } | null;
  links: { grafana?: string; logs?: string; ticket?: string; source?: string };
  postmortemPath: string | null;
  issueUrl: string | null;
  sla: Sla;
}

export interface TimelineEntry {
  ts: string;
  actor: string;
  kind: string;
  text: string;
}

export interface IncidentDetail extends IncidentSummary {
  logs: string;
  events: string;
  memory: string;
  timeline: TimelineEntry[];
}

export interface Page<T> {
  total: number;
  items: T[];
}

export interface ReportSummary {
  periodDays: number;
  incidents: number;
  open: number;
  mttaMinutes: number | null;
  mttrMinutes: number | null;
  bySev: Record<string, number>;
  byStatus: Record<string, number>;
  byService: Record<string, number>;
  byType: Record<string, number>;
  decisions: { approved: number; rejected: number };
}

export interface ClusterInfo {
  id: string;
  name: string;
  context: string | null;
  openIncidents: number;
  lastSeenAt: string | null;
}

export interface ClusterStatus {
  nodes: {
    name: string;
    ready: boolean;
    pressure: string[];
    kubelet: string;
    cpu: string;
    memory: string;
    unschedulable: boolean;
  }[];
  workloads: { kind: string; namespace: string; name: string; desired: number; ready: number }[];
  pods: { total: number; healthy: number };
  namespaces: string[];
  watcher: string;
  lastSweep: string | null;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor: string;
  action: string;
  target: string;
  ip: string | null;
  details: Record<string, unknown>;
  prevHash: string;
  hash: string;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "operator" | "viewer" | "auditor";
  active: boolean;
  mfa: boolean;
  sso: boolean;
  teams: string[];
  createdAt: string | null;
  lastLoginAt: string | null;
}

export interface AdminTeam {
  id: string;
  name: string;
  members: string[];
  scopes: { cluster: string; namespace: string }[];
}

export interface BrainGraph {
  nodes: { id: string; group: string; folder: string }[];
  links: { source: string; target: string }[];
}

export interface HealthCheck {
  ok: boolean;
  detail?: string;
}

export interface Silence {
  id: string;
  cluster: string;
  namespace: string;
  workload: string;
  type: string;
  startsAt: string;
  endsAt: string;
  active: boolean;
  reason: string;
  createdBy: string;
}

export interface Policy {
  id: string;
  cluster: string;
  namespace: string;
  workload: string;
  type: string;
  action: string;
  maxPerHour: number;
  enabled: boolean;
  createdBy: string;
}

export interface Shift {
  id: number;
  teamId: string;
  team: string;
  user: string;
  level: number;
  startsAt: string;
  endsAt: string;
}

export interface ActionInfo {
  id: string;
  label: string;
  risk: string;
  autoEligible: boolean;
  description: string;
}
