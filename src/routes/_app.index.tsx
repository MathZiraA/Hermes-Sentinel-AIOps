import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { SevBadge, SlaBadge, StatusBadge } from "@/components/incidents/badges";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { useClusterStatus, useClusters, useIncidents, useSummary } from "@/lib/api/hooks";
import { OPEN_STATUSES, type IncidentSummary } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/")({
  head: () => ({ meta: [{ title: "Visão geral · Hermes Sentinel" }] }),
  component: Overview,
});

function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "warn" | "ok";
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1.5 text-2xl font-semibold tabular-nums tracking-tight",
          tone === "warn" ? "text-sev2" : "text-foreground",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

const SEV_ORDER = { SEV1: 0, SEV2: 1, SEV3: 2, SEV4: 3 } as const;

function IncidentRow({ inc }: { inc: IncidentSummary }) {
  const { formatRelative } = useI18n();
  return (
    <Link
      to="/incidents/$incidentId"
      params={{ incidentId: inc.id }}
      className="flex flex-col gap-1.5 rounded-lg px-3 py-2.5 hover:bg-accent sm:flex-row sm:items-center sm:gap-3"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <SevBadge sev={inc.sev} />
        <span className="truncate text-sm font-medium text-foreground">{inc.type}</span>
        <span className="truncate text-sm text-muted-foreground">
          {inc.namespace}/{inc.deployment ?? inc.pod}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <StatusBadge status={inc.status} label={inc.statusLabel} />
        <SlaBadge sla={inc.sla} open={OPEN_STATUSES.includes(inc.status)} />
        <span className="hidden w-24 text-right text-xs text-muted-foreground md:inline">
          {formatRelative(inc.detectedAt)}
        </span>
      </div>
    </Link>
  );
}

function Overview() {
  const { t } = useI18n();
  const summary = useSummary(30);
  const open = useIncidents({ status: OPEN_STATUSES, limit: 50 });
  const clusters = useClusters();
  const clusterId = clusters.data?.[0]?.id ?? "local";
  const status = useClusterStatus(clusterId);

  const items = [...(open.data?.items ?? [])].sort(
    (a, b) => SEV_ORDER[a.sev] - SEV_ORDER[b.sev] || b.detectedAt.localeCompare(a.detectedAt),
  );
  const pending = items.filter((i) => i.status === "waiting_approval").length;
  const s = summary.data;
  const min = (v: number | null | undefined) => (v == null ? "—" : `${v} ${t("common.minutes")}`);
  const pods = status.data?.pods;

  return (
    <>
      <PageHeader title={t("overview.title")} subtitle={t("overview.subtitle")} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi
          label={t("overview.open")}
          value={String(open.data?.total ?? "—")}
          tone={(open.data?.total ?? 0) > 0 ? "warn" : "ok"}
        />
        <Kpi label={t("overview.pending")} value={String(pending)} tone={pending ? "warn" : "ok"} />
        <Kpi label={t("overview.mtta")} value={min(s?.mttaMinutes)} hint={t("overview.last30")} />
        <Kpi label={t("overview.mttr")} value={min(s?.mttrMinutes)} hint={t("overview.last30")} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel
          title={t("overview.needsAttention")}
          className="lg:col-span-2"
          actions={
            <Link
              to="/incidents"
              className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              {t("overview.viewAll")} <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        >
          {open.isLoading ? (
            <StateMessage>{t("common.loading")}</StateMessage>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center">
              <CheckCircle2 className="h-8 w-8 text-success" aria-hidden />
              <p className="text-sm text-muted-foreground">{t("overview.allClear")}</p>
            </div>
          ) : (
            <div className="-mx-1 flex flex-col">
              {items.slice(0, 8).map((inc) => (
                <IncidentRow key={inc.id} inc={inc} />
              ))}
            </div>
          )}
        </Panel>

        <Panel title={t("nav.clusters")}>
          {status.isError ? (
            <StateMessage>{t("clusters.unavailable")}</StateMessage>
          ) : (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">{t("clusters.nodes")}</dt>
                <dd className="mt-0.5 font-semibold tabular-nums">
                  {status.data
                    ? `${status.data.nodes.filter((n) => n.ready).length}/${status.data.nodes.length}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t("clusters.pods")}</dt>
                <dd className="mt-0.5 font-semibold tabular-nums">
                  {pods ? `${pods.healthy}/${pods.total}` : "—"}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-muted-foreground">{t("clusters.workloads")}</dt>
                <dd className="mt-2 flex flex-wrap gap-1.5">
                  {status.data?.workloads.map((w) => (
                    <span
                      key={`${w.namespace}/${w.name}`}
                      className={cn(
                        "rounded-md px-2 py-0.5 text-xs",
                        w.ready >= w.desired
                          ? "bg-success/15 text-success"
                          : "bg-sev2/15 text-sev2",
                      )}
                      title={`${w.kind} ${w.namespace}/${w.name}: ${w.ready}/${w.desired}`}
                    >
                      {w.name} {w.ready}/{w.desired}
                    </span>
                  ))}
                </dd>
              </div>
            </dl>
          )}
          <Link
            to="/clusters"
            className="mt-4 flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            {t("overview.viewAll")} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Panel>
      </div>
    </>
  );
}
