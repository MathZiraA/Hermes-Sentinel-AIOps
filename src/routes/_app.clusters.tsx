import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, CircleAlert } from "lucide-react";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { useClusterStatus, useClusters, useHealth } from "@/lib/api/hooks";
import type { HealthCheck } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/clusters")({
  head: () => ({ meta: [{ title: "Clusters · Hermes Sentinel" }] }),
  component: Clusters,
});

const INTEGRATIONS: { key: string; label: string }[] = [
  { key: "kubernetes", label: "Kubernetes" },
  { key: "hermesGateway", label: "Hermes (IA)" },
  { key: "mcp", label: "Servidor MCP" },
  { key: "database", label: "Banco de dados" },
  { key: "obsidian", label: "Hermes Brain" },
  { key: "github", label: "GitHub" },
  { key: "jira", label: "Jira" },
  { key: "zabbix", label: "Zabbix" },
  { key: "grafana", label: "Grafana" },
  { key: "loki", label: "Loki" },
  { key: "githubDeploys", label: "GitHub (deploys)" },
];

function Dot({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-label="ok" />
  ) : (
    <CircleAlert className="h-4 w-4 shrink-0 text-sev2" aria-label="problema" />
  );
}

function Clusters() {
  const { t, formatRelative } = useI18n();
  const clusters = useClusters();
  const cluster = clusters.data?.[0];
  const status = useClusterStatus(cluster?.id ?? "local");
  const health = useHealth();
  const s = status.data;

  return (
    <>
      <PageHeader
        title={t("clusters.title")}
        subtitle={t("clusters.subtitle")}
        actions={
          cluster && (
            <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
              {cluster.name} · {cluster.openIncidents} {t("incidents.filter.open").toLowerCase()}
            </span>
          )
        }
      />

      {status.isError && <StateMessage>{t("clusters.unavailable")}</StateMessage>}

      {s && (
        <div className="grid gap-6 lg:grid-cols-3">
          <Panel title={t("clusters.nodes")}>
            <ul className="space-y-3">
              {s.nodes.map((n) => (
                <li key={n.name} className="flex items-start gap-2.5">
                  <Dot ok={n.ready && !n.pressure.length} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{n.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {n.kubelet} · {n.cpu} CPU · {n.memory}
                    </p>
                    {!!n.pressure.length && (
                      <p className="text-xs text-sev2">{n.pressure.join(", ")}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">{t("clusters.pods")}</dt>
                <dd className="font-semibold tabular-nums">
                  {s.pods.healthy}/{s.pods.total}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t("clusters.watcher")}</dt>
                <dd className="font-medium">{s.watcher}</dd>
                {s.lastSweep && (
                  <dd className="text-xs text-muted-foreground">
                    {t("clusters.lastSweep")} {s.lastSweep}
                  </dd>
                )}
              </div>
            </dl>
          </Panel>

          <Panel title={t("clusters.workloads")} className="lg:col-span-2">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="pb-2 font-medium">Workload</th>
                    <th className="pb-2 font-medium">Namespace</th>
                    <th className="pb-2 text-right font-medium">Réplicas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.workloads.map((w) => {
                    const ok = w.ready >= w.desired;
                    return (
                      <tr key={`${w.namespace}/${w.name}`}>
                        <td className="py-2">
                          <span className="flex items-center gap-2">
                            <Dot ok={ok} />
                            <span className="font-medium">{w.name}</span>
                            <span className="text-xs text-muted-foreground">{w.kind}</span>
                          </span>
                        </td>
                        <td className="py-2 text-muted-foreground">{w.namespace}</td>
                        <td
                          className={cn(
                            "py-2 text-right tabular-nums",
                            !ok && "font-semibold text-sev2",
                          )}
                        >
                          {w.ready}/{w.desired}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      <Panel title={t("clusters.integrations")} className="mt-6">
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {INTEGRATIONS.map(({ key, label }) => {
            const item = (health.data?.[key] ??
              (health.data?.["integrations"] as Record<string, HealthCheck> | undefined)?.[key]) as
              HealthCheck | undefined;
            return (
              <li
                key={key}
                className="flex items-start gap-2.5 rounded-lg border border-border p-3"
              >
                <Dot ok={!!item?.ok} />
                <div className="min-w-0">
                  <p className="text-sm font-medium">{label}</p>
                  <p className="truncate text-xs text-muted-foreground" title={item?.detail}>
                    {item?.detail ?? "—"}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
        {cluster?.lastSeenAt && (
          <p className="mt-3 text-xs text-muted-foreground">{formatRelative(cluster.lastSeenAt)}</p>
        )}
      </Panel>
    </>
  );
}
