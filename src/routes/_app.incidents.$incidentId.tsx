import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Check, Hand, Loader2, ShieldAlert, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { SevBadge, SlaBadge, StatusBadge } from "@/components/incidents/badges";
import { Panel, StateMessage } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useIncident, useIncidentActions } from "@/lib/api/hooks";
import { OPEN_STATUSES, type IncidentDetail } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/incidents/$incidentId")({
  head: ({ params }) => ({ meta: [{ title: `${params.incidentId} · Hermes Sentinel` }] }),
  component: IncidentPage,
});

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-foreground">{children}</dd>
    </div>
  );
}

function DecisionPanel({ inc }: { inc: IncidentDetail }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const { approve, reject } = useIncidentActions(inc.id);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const allowed = can("incidents:decide");
  const busy = approve.isPending || reject.isPending;

  const run = async (kind: "approve" | "reject") => {
    setError(null);
    if (kind === "reject" && !reason.trim()) {
      setError(t("incident.reasonHint"));
      return;
    }
    try {
      await (kind === "approve" ? approve : reject).mutateAsync(reason);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!inc.approval) return null;
  return (
    <section
      aria-labelledby="decision-title"
      className="rounded-xl border-2 border-sev3/60 bg-sev3/10 p-4"
    >
      <h2 id="decision-title" className="flex items-center gap-2 text-sm font-semibold">
        <ShieldAlert className="h-4 w-4 text-sev2" aria-hidden />
        {t("incident.decisionNeeded")}
        {inc.simulated && (
          <span className="ml-auto rounded-full bg-muted px-2 text-[10px] font-medium uppercase text-muted-foreground">
            {t("common.simulated")}
          </span>
        )}
      </h2>
      {inc.approval.description && (
        <p className="mt-2 text-sm text-muted-foreground">{inc.approval.description}</p>
      )}
      <pre className="mt-3 overflow-x-auto rounded-lg bg-screen px-3 py-2 font-mono text-xs text-card">
        {inc.approval.command}
      </pre>
      <p className="mt-2 text-xs text-muted-foreground">
        {inc.approval.target} · risco {inc.approval.risk}
      </p>
      {allowed ? (
        <>
          <label htmlFor="reason" className="mt-4 block text-xs font-medium text-foreground">
            {t("incident.reason")}
          </label>
          <Textarea
            id="reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={600}
            rows={3}
            className="mt-1.5 bg-card"
            aria-describedby="reason-hint"
          />
          <p id="reason-hint" className="mt-1 text-xs text-muted-foreground">
            {t("incident.reasonHint")}
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" disabled={busy} onClick={() => void run("reject")}>
              {reject.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" />
              )}
              {t("incident.reject")}
            </Button>
            <Button
              disabled={busy}
              onClick={() => void run("approve")}
              className="bg-success text-white hover:bg-success/90"
            >
              {approve.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {t("incident.approve")}
            </Button>
          </div>
        </>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">{t("incident.cannotDecide")}</p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}

function IncidentPage() {
  const { incidentId } = Route.useParams();
  const { t, formatDate } = useI18n();
  const { can } = useAuth();
  const { data: inc, isLoading, isError } = useIncident(incidentId);
  const { acknowledge } = useIncidentActions(incidentId);

  if (isLoading) return <StateMessage>{t("common.loading")}</StateMessage>;
  if (isError || !inc) return <StateMessage>{t("common.error")}</StateMessage>;

  const open = OPEN_STATUSES.includes(inc.status);
  const rca = inc.rca;

  return (
    <>
      <Link
        to="/incidents"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> {t("incident.back")}
      </Link>

      <header className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <SevBadge sev={inc.sev} />
            <StatusBadge status={inc.status} label={inc.statusLabel} />
            <SlaBadge sla={inc.sla} open={open} />
          </div>
          <h1 className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">
            {inc.type} <span className="text-muted-foreground">em</span> {inc.namespace}/
            {inc.deployment ?? inc.pod}
          </h1>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {inc.id} · {inc.resourceKind}/{inc.pod} · {formatDate(inc.detectedAt)}
          </p>
          {rca?.stakeholderSummary && <p className="mt-3 text-sm">{rca.stakeholderSummary}</p>}
        </div>
        {open && !inc.acknowledgedAt && can("incidents:ack") && (
          <Button
            variant="outline"
            onClick={() => acknowledge.mutate()}
            disabled={acknowledge.isPending}
          >
            <Hand className="h-4 w-4" /> {t("incident.ack")}
          </Button>
        )}
        {inc.acknowledgedBy && (
          <p className="text-xs text-muted-foreground">
            {t("incident.acked")} <b className="text-foreground">{inc.acknowledgedBy}</b> ·{" "}
            {formatDate(inc.acknowledgedAt)}
          </p>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          {inc.status === "waiting_approval" && <DecisionPanel inc={inc} />}

          <Panel title={t("incident.rootCause")}>
            {rca?.rootCause ? (
              <>
                <p className="text-sm leading-relaxed">{rca.rootCause}</p>
                {!!rca.evidence?.length && (
                  <>
                    <h3 className="mt-4 text-xs font-medium text-muted-foreground">
                      {t("incident.evidence")}
                    </h3>
                    <ul className="mt-1.5 space-y-1">
                      {rca.evidence.map((e, i) => (
                        <li key={i} className="rounded-md bg-muted px-2.5 py-1.5 font-mono text-xs">
                          {e}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {rca.learning && (
                  <p className="mt-4 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
                    <b>{t("incident.learning")}:</b> {rca.learning}
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{t("incident.noRca")}</p>
            )}
          </Panel>

          <Tabs defaultValue="timeline">
            <TabsList className="flex-wrap">
              <TabsTrigger value="timeline">{t("incident.timeline")}</TabsTrigger>
              <TabsTrigger value="logs">{t("incident.logs")}</TabsTrigger>
              <TabsTrigger value="events">{t("incident.events")}</TabsTrigger>
              <TabsTrigger value="memory">{t("incident.memory")}</TabsTrigger>
            </TabsList>
            <TabsContent value="timeline">
              <ol className="relative mt-2 space-y-3 border-l border-border pl-5">
                {inc.timeline.map((e, i) => (
                  <li key={i} className="relative">
                    <span
                      className={cn(
                        "absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background",
                        e.kind === "decision"
                          ? "bg-sev3"
                          : e.kind === "status"
                            ? "bg-primary"
                            : "bg-muted-foreground",
                      )}
                    />
                    <p className="text-sm">{e.text}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(e.ts)} · {e.actor}
                    </p>
                  </li>
                ))}
              </ol>
            </TabsContent>
            {(["logs", "events", "memory"] as const).map((k) => (
              <TabsContent key={k} value={k}>
                <pre className="mt-2 max-h-[420px] overflow-auto rounded-lg bg-screen p-3 font-mono text-[11px] leading-relaxed text-card">
                  {inc[k] || "—"}
                </pre>
              </TabsContent>
            ))}
          </Tabs>
        </div>

        <aside className="flex flex-col gap-6">
          <Panel>
            <dl className="grid gap-3">
              <Field label={t("incident.confidence")}>{rca?.confidence ?? "—"}</Field>
              <Field label={t("incident.source")}>{rca?.source ?? "—"}</Field>
              <Field label="Sinal">{inc.reason}</Field>
              {inc.decision && (
                <Field label={t("incident.decision")}>
                  {inc.decision === "approved" ? "✅" : "⛔"} {inc.decisionBy} ·{" "}
                  {formatDate(inc.decidedAt)}
                  {inc.decisionReason && (
                    <span className="mt-1 block text-muted-foreground">“{inc.decisionReason}”</span>
                  )}
                </Field>
              )}
              {inc.remediationResult && (
                <Field label={t("incident.result")}>{inc.remediationResult}</Field>
              )}
            </dl>
          </Panel>
          {!!inc.related.length && (
            <Panel title={t("incident.related")}>
              <ul className="space-y-1.5 text-xs text-muted-foreground">
                {inc.related.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Panel>
          )}
          {!!rca?.followUps?.length && (
            <Panel title={t("incident.followUps")}>
              <ul className="list-inside list-disc space-y-1 text-sm">
                {rca.followUps.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </Panel>
          )}
        </aside>
      </div>
    </>
  );
}
