import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { useAiUsage, useSummary } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/reports")({
  head: () => ({ meta: [{ title: "Relatórios · Hermes Sentinel" }] }),
  component: Reports,
});

const SEV_COLORS: Record<string, string> = {
  SEV1: "var(--sev1)",
  SEV2: "var(--sev2)",
  SEV3: "var(--sev3)",
  SEV4: "var(--sev4)",
};

function HBars({
  data,
  color = "var(--primary)",
}: {
  data: Record<string, number>;
  color?: string;
}) {
  const rows = Object.entries(data).map(([name, value]) => ({ name, value }));
  if (!rows.length) return <StateMessage>—</StateMessage>;
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 34)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
        <XAxis type="number" allowDecimals={false} hide />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "var(--accent)" }}
          contentStyle={{
            background: "var(--popover)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--popover-foreground)",
          }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} fill={color} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function AiPanel({ days }: { days: number }) {
  const { t } = useI18n();
  const { data } = useAiUsage(days);
  if (!data) return null;
  const tokens = data.days.reduce((n, d) => n + d.tokensIn + d.tokensOut, 0);
  return (
    <Panel
      title={`${t("reports.ai")} · ${data.provider}${data.model ? ` (${data.model})` : ""}`}
      className="lg:col-span-2"
    >
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">{t("reports.aiToday")}</dt>
          <dd className="font-semibold tabular-nums">
            {data.today.calls}
            {data.limits.callsPerDay ? ` / ${data.limits.callsPerDay}` : ""}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("reports.aiBlocked")}</dt>
          <dd className={cn("font-semibold tabular-nums", data.today.blocked > 0 && "text-sev2")}>
            {data.today.blocked}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("reports.aiTokens")}</dt>
          <dd className="font-semibold tabular-nums">{tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("reports.aiCost")}</dt>
          <dd className="font-semibold tabular-nums">US$ {data.totalCost.toFixed(2)}</dd>
        </div>
      </dl>
      {data.days.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-xs text-muted-foreground">{t("reports.callsPerDay")}</p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={data.days}>
              <XAxis
                dataKey="day"
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                width={28}
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              />
              <Tooltip
                cursor={{ fill: "var(--accent)" }}
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="calls" stackId="a" fill="var(--primary)" />
              <Bar dataKey="blocked" stackId="a" fill="var(--sev2)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

function Reports() {
  const { t } = useI18n();
  const [days, setDays] = useState(30);
  const { data, isLoading } = useSummary(days);
  const min = (v: number | null | undefined) => (v == null ? "—" : `${v} ${t("common.minutes")}`);
  const sevRows = (["SEV1", "SEV2", "SEV3", "SEV4"] as const).map((s) => ({
    name: s,
    value: data?.bySev[s] ?? 0,
  }));
  const decided = (data?.decisions.approved ?? 0) + (data?.decisions.rejected ?? 0);

  return (
    <>
      <PageHeader
        title={t("reports.title")}
        subtitle={t("reports.subtitle")}
        actions={
          <div className="flex gap-1" role="group" aria-label={t("reports.period")}>
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={days === d}
                onClick={() => setDays(d)}
                className={cn(
                  "rounded-md border px-3 py-1 text-xs font-medium",
                  days === d
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-border text-muted-foreground",
                )}
              >
                {d} {t("reports.days")}
              </button>
            ))}
          </div>
        }
      />
      {isLoading || !data ? (
        <StateMessage>{t("common.loading")}</StateMessage>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              [t("nav.incidents"), String(data.incidents)],
              [t("overview.open"), String(data.open)],
              [t("overview.mtta"), min(data.mttaMinutes)],
              [t("overview.mttr"), min(data.mttrMinutes)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border bg-card p-4">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-1.5 text-2xl font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Panel title={t("reports.bySev")}>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={sevRows}>
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    width={28}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--accent)" }}
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                    }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {sevRows.map((r) => (
                      <Cell key={r.name} fill={SEV_COLORS[r.name]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Panel>
            <Panel title={t("reports.decisions")}>
              {decided === 0 ? (
                <StateMessage>{t("common.empty")}</StateMessage>
              ) : (
                <div className="space-y-3 py-4">
                  <div className="flex h-3 overflow-hidden rounded-full bg-muted">
                    <div
                      className="bg-success"
                      style={{ width: `${(data.decisions.approved / decided) * 100}%` }}
                    />
                    <div
                      className="bg-sev2"
                      style={{ width: `${(data.decisions.rejected / decided) * 100}%` }}
                    />
                  </div>
                  <p className="text-sm">
                    <b className="text-success">{data.decisions.approved}</b>{" "}
                    {t("reports.approved")} · <b className="text-sev2">{data.decisions.rejected}</b>{" "}
                    {t("reports.rejected")}
                  </p>
                </div>
              )}
            </Panel>
            <Panel title={t("reports.accuracy")}>
              {data.rca.rated === 0 ? (
                <StateMessage>{t("common.empty")}</StateMessage>
              ) : (
                <div className="py-4">
                  <p className="text-3xl font-semibold tabular-nums">
                    {Math.round((data.rca.accuracy ?? 0) * 100)}%
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {data.rca.correct}/{data.rca.rated} {t("reports.rated")}
                  </p>
                </div>
              )}
            </Panel>
            <AiPanel days={days} />
            <Panel title={t("reports.byService")}>
              <HBars data={data.byService} />
            </Panel>
            <Panel title={t("reports.byType")}>
              <HBars data={data.byType} color="var(--agent-purple)" />
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
