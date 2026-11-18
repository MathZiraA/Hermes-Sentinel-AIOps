import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api/client";
import { useActions, usePolicies, useShifts, useSilences, useTeams } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth/auth";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/operations")({
  head: () => ({ meta: [{ title: "Manutenção e plantão · Hermes Sentinel" }] }),
  component: Operations,
});

const SELECT =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

function useForm<T extends Record<string, string>>(initial: T) {
  const [v, setV] = useState(initial);
  const bind = (k: keyof T) => ({
    id: String(k),
    value: v[k],
    onChange: (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value }),
  });
  return { v, setV, bind };
}

function ErrorText({ text }: { text: string | null }) {
  return text ? (
    <p role="alert" className="text-sm text-destructive">
      {text}
    </p>
  ) : null;
}

function Filter({
  s,
}: {
  s: { cluster: string; namespace: string; workload: string; type: string };
}) {
  return (
    <span className="font-mono text-xs">
      {s.cluster}/{s.namespace}/{s.workload} · {s.type}
    </span>
  );
}

function Silences() {
  const { t, formatDate } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useSilences();
  const now = new Date();
  const f = useForm({
    namespace: "*",
    workload: "*",
    type: "*",
    startsAt: toLocalInput(now),
    endsAt: toLocalInput(new Date(now.getTime() + 2 * 3600_000)),
    reason: "",
  });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["silences"] });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/silences", {
        ...f.v,
        cluster: "*",
        startsAt: new Date(f.v.startsAt).toISOString(),
        endsAt: new Date(f.v.endsAt).toISOString(),
      });
      f.setV({ ...f.v, reason: "" });
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <Panel title={t("ops.silences")}>
      <p className="mb-4 text-sm text-muted-foreground">{t("ops.silencesHint")}</p>
      {can("silences:manage") && (
        <form onSubmit={submit} className="mb-5 grid gap-3 sm:grid-cols-3">
          <Field id="namespace" label="Namespace">
            <Input {...f.bind("namespace")} />
          </Field>
          <Field id="workload" label="Workload">
            <Input {...f.bind("workload")} placeholder="pagamentos*" />
          </Field>
          <Field id="type" label="Tipo">
            <Input {...f.bind("type")} placeholder="* ou ImagePullBackOff" />
          </Field>
          <Field id="startsAt" label={t("ops.from")}>
            <Input type="datetime-local" {...f.bind("startsAt")} />
          </Field>
          <Field id="endsAt" label={t("ops.to")}>
            <Input type="datetime-local" {...f.bind("endsAt")} />
          </Field>
          <Field id="reason" label={t("ops.reason")}>
            <Input required {...f.bind("reason")} placeholder="deploy planejado" />
          </Field>
          <div className="sm:col-span-3">
            <Button type="submit" size="sm">
              <Plus className="h-4 w-4" /> {t("common.create")}
            </Button>
          </div>
          <div className="sm:col-span-3">
            <ErrorText text={error} />
          </div>
        </form>
      )}
      {isLoading ? (
        <StateMessage>{t("common.loading")}</StateMessage>
      ) : !data?.length ? (
        <StateMessage>{t("common.empty")}</StateMessage>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((s) => (
            <li
              key={s.id}
              className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px]",
                      s.active ? "bg-sev3/20 text-foreground" : "bg-muted text-muted-foreground",
                    )}
                  >
                    {s.active ? t("ops.active") : t("ops.scheduled")}
                  </span>
                  {s.reason}
                </p>
                <p className="text-xs text-muted-foreground">
                  <Filter s={s} /> · {formatDate(s.startsAt)} → {formatDate(s.endsAt)} ·{" "}
                  {s.createdBy}
                </p>
              </div>
              {can("silences:manage") && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    await api.del(`/api/silences/${s.id}`);
                    refresh();
                  }}
                >
                  {t("ops.end")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Policies() {
  const { t } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = usePolicies();
  const actions = useActions();
  const f = useForm({
    namespace: "*",
    workload: "*",
    type: "",
    action: "rollout_restart",
    maxPerHour: "2",
  });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["policies"] });
  const admin = can("settings:manage");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/policies", { ...f.v, cluster: "*", maxPerHour: Number(f.v.maxPerHour) });
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <Panel title={t("ops.policies")}>
      <p className="mb-4 text-sm text-muted-foreground">{t("ops.policiesHint")}</p>
      {admin && (
        <form onSubmit={submit} className="mb-5 grid gap-3 sm:grid-cols-5 sm:items-end">
          <Field id="p-ns" label="Namespace">
            <Input {...f.bind("namespace")} id="p-ns" />
          </Field>
          <Field id="p-wl" label="Workload">
            <Input {...f.bind("workload")} id="p-wl" />
          </Field>
          <Field id="p-type" label="Tipo">
            <Input required {...f.bind("type")} id="p-type" placeholder="CrashLoopBackOff" />
          </Field>
          <Field id="p-action" label={t("ops.action")}>
            <select {...f.bind("action")} id="p-action" className={SELECT}>
              {actions.data
                ?.filter((a) => a.autoEligible)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
            </select>
          </Field>
          <Field id="p-max" label={t("ops.maxPerHour")}>
            <Input type="number" min={1} max={10} {...f.bind("maxPerHour")} id="p-max" />
          </Field>
          <div className="sm:col-span-5">
            <Button type="submit" size="sm">
              <Plus className="h-4 w-4" /> {t("common.create")}
            </Button>
          </div>
          <div className="sm:col-span-5">
            <ErrorText text={error} />
          </div>
        </form>
      )}
      {isLoading ? (
        <StateMessage>{t("common.loading")}</StateMessage>
      ) : !data?.length ? (
        <StateMessage>{t("common.empty")}</StateMessage>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((p) => (
            <li
              key={p.id}
              className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="text-sm font-medium">
                  {p.action} <span className="text-muted-foreground">·</span> {p.maxPerHour}/h
                </p>
                <p className="text-xs text-muted-foreground">
                  <Filter s={p} /> · {p.createdBy}
                </p>
              </div>
              {admin && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-pressed={p.enabled}
                    onClick={async () => {
                      await api.patch(`/api/policies/${p.id}`, { enabled: !p.enabled });
                      refresh();
                    }}
                  >
                    {p.enabled ? t("ops.enabled") : t("ops.disabled")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label="Apagar política"
                    onClick={async () => {
                      await api.del(`/api/policies/${p.id}`);
                      refresh();
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function OnCall() {
  const { t, formatDate } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useShifts();
  const admin = can("teams:manage");
  const teams = useTeams();
  const now = new Date();
  const f = useForm({
    teamId: "",
    user: "",
    level: "1",
    startsAt: toLocalInput(now),
    endsAt: toLocalInput(new Date(now.getTime() + 12 * 3600_000)),
  });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["oncall"] });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/oncall", {
        ...f.v,
        teamId: f.v.teamId || teams.data?.[0]?.id,
        level: Number(f.v.level),
        startsAt: new Date(f.v.startsAt).toISOString(),
        endsAt: new Date(f.v.endsAt).toISOString(),
      });
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <Panel title={t("ops.oncall")}>
      <p className="mb-4 text-sm text-muted-foreground">{t("ops.oncallHint")}</p>
      {admin && !!teams.data?.length && (
        <form onSubmit={submit} className="mb-5 grid gap-3 sm:grid-cols-5 sm:items-end">
          <Field id="o-team" label={t("ops.team")}>
            <select {...f.bind("teamId")} id="o-team" className={SELECT}>
              {teams.data.map((tm) => (
                <option key={tm.id} value={tm.id}>
                  {tm.name}
                </option>
              ))}
            </select>
          </Field>
          <Field id="o-user" label={t("ops.person")}>
            <Input type="email" required {...f.bind("user")} id="o-user" />
          </Field>
          <Field id="o-level" label={t("ops.level")}>
            <select {...f.bind("level")} id="o-level" className={SELECT}>
              <option value="1">{t("ops.primary")}</option>
              <option value="2">{t("ops.secondary")}</option>
            </select>
          </Field>
          <Field id="o-start" label={t("ops.from")}>
            <Input type="datetime-local" {...f.bind("startsAt")} id="o-start" />
          </Field>
          <Field id="o-end" label={t("ops.to")}>
            <Input type="datetime-local" {...f.bind("endsAt")} id="o-end" />
          </Field>
          <div className="sm:col-span-5">
            <Button type="submit" size="sm">
              <Plus className="h-4 w-4" /> {t("common.create")}
            </Button>
          </div>
          <div className="sm:col-span-5">
            <ErrorText text={error} />
          </div>
        </form>
      )}
      {isLoading ? (
        <StateMessage>{t("common.loading")}</StateMessage>
      ) : !data?.length ? (
        <StateMessage>{t("common.empty")}</StateMessage>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-2 py-2.5">
              <div>
                <p className="text-sm font-medium">
                  {s.user}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    · {s.team} · {s.level === 1 ? t("ops.primary") : t("ops.secondary")}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(s.startsAt)} → {formatDate(s.endsAt)}
                </p>
              </div>
              {admin && (
                <Button
                  variant="outline"
                  size="sm"
                  aria-label="Remover turno"
                  onClick={async () => {
                    await api.del(`/api/oncall/${s.id}`);
                    refresh();
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Operations() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("ops.title")} subtitle={t("ops.subtitle")} />
      <div className="grid gap-6">
        <Silences />
        <Policies />
        <OnCall />
      </div>
    </>
  );
}
