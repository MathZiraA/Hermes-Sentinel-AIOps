import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";
import { SevBadge, SlaBadge, StatusBadge } from "@/components/incidents/badges";
import { PageHeader, StateMessage } from "@/components/layout/PageHeader";
import { Input } from "@/components/ui/input";
import { useIncidents } from "@/lib/api/hooks";
import { OPEN_STATUSES, type IncidentStatus, type Sev } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

type View = "open" | "closed" | "all" | IncidentStatus;
interface Search {
  status?: View | undefined;
  sev?: Sev | undefined;
  q?: string | undefined;
}

export const Route = createFileRoute("/_app/incidents/")({
  head: () => ({ meta: [{ title: "Incidentes · Hermes Sentinel" }] }),
  validateSearch: (s: Record<string, unknown>): Search => ({
    ...(typeof s["status"] === "string" ? { status: s["status"] as View } : {}),
    ...(typeof s["sev"] === "string" ? { sev: s["sev"] as Sev } : {}),
    ...(typeof s["q"] === "string" ? { q: s["q"] } : {}),
  }),
  component: Incidents,
});

const CLOSED: IncidentStatus[] = ["resolved", "postmortem", "closed", "failed"];
const SEVS: Sev[] = ["SEV1", "SEV2", "SEV3", "SEV4"];

function statusFilter(view: View | undefined): string[] | undefined {
  if (!view || view === "all") return undefined;
  if (view === "open") return OPEN_STATUSES;
  if (view === "closed") return CLOSED;
  return [view];
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary/15 text-primary"
          : "border-border text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function Incidents() {
  const { t, formatDate, formatRelative } = useI18n();
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const view = search.status ?? "open";
  const [q, setQ] = useState(search.q ?? "");
  const status = statusFilter(view);
  const { data, isLoading, isError, refetch } = useIncidents({
    ...(status ? { status } : {}),
    ...(search.sev ? { sev: [search.sev] } : {}),
    ...(search.q ? { q: search.q } : {}),
    limit: 100,
  });
  const set = (patch: Partial<Search>) =>
    void navigate({ search: (prev: Search) => ({ ...prev, ...patch }) });

  return (
    <>
      <PageHeader title={t("incidents.title")} subtitle={t("incidents.subtitle")} />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div
          className="flex flex-wrap gap-1.5"
          role="group"
          aria-label={t("incidents.filter.status")}
        >
          <Chip active={view === "open"} onClick={() => set({ status: "open" })}>
            {t("incidents.filter.open")}
          </Chip>
          <Chip
            active={view === "waiting_approval"}
            onClick={() => set({ status: "waiting_approval" })}
          >
            {t("overview.pending")}
          </Chip>
          <Chip active={view === "closed"} onClick={() => set({ status: "closed" })}>
            {t("incidents.filter.closed")}
          </Chip>
          <Chip active={view === "all"} onClick={() => set({ status: "all" })}>
            {t("common.all")}
          </Chip>
          <span className="mx-1 hidden w-px bg-border sm:block" />
          {SEVS.map((s) => (
            <Chip
              key={s}
              active={search.sev === s}
              onClick={() => set(search.sev === s ? { sev: undefined } : { sev: s })}
            >
              {s}
            </Chip>
          ))}
        </div>
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            set(q.trim() ? { q: q.trim() } : { q: undefined });
          }}
          className="relative w-full lg:w-72"
        >
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={`${t("common.search")}: serviço, tipo, INC-…`}
            aria-label={t("common.search")}
            className="pl-8"
          />
        </form>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {isLoading ? (
          <StateMessage>{t("common.loading")}</StateMessage>
        ) : isError ? (
          <StateMessage>
            {t("common.error")}{" "}
            <button type="button" className="text-primary underline" onClick={() => void refetch()}>
              {t("common.retry")}
            </button>
          </StateMessage>
        ) : !data?.items.length ? (
          <StateMessage>{t("incidents.none")}</StateMessage>
        ) : (
          <>
            {/* Tabela no desktop */}
            <table className="hidden w-full text-sm md:table">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-medium">{t("incidents.col.incident")}</th>
                  <th className="px-4 py-2.5 font-medium">{t("incidents.col.target")}</th>
                  <th className="px-4 py-2.5 font-medium">{t("incidents.col.status")}</th>
                  <th className="px-4 py-2.5 font-medium">{t("incidents.col.sla")}</th>
                  <th className="px-4 py-2.5 text-right font-medium">
                    {t("incidents.col.detected")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((inc) => (
                  <tr key={inc.id} className="hover:bg-accent/50">
                    <td className="px-4 py-3">
                      <Link
                        to="/incidents/$incidentId"
                        params={{ incidentId: inc.id }}
                        className="flex items-center gap-2 font-medium text-foreground hover:text-primary"
                      >
                        <SevBadge sev={inc.sev} />
                        {inc.type}
                      </Link>
                      <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                        {inc.id}
                        {inc.simulated && ` · ${t("common.simulated")}`}
                      </p>
                    </td>
                    <td className="max-w-[220px] truncate px-4 py-3 text-muted-foreground">
                      {inc.namespace}/{inc.deployment ?? inc.pod}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={inc.status} label={inc.statusLabel} />
                    </td>
                    <td className="px-4 py-3">
                      <SlaBadge sla={inc.sla} open={OPEN_STATUSES.includes(inc.status)} />
                    </td>
                    <td
                      className="px-4 py-3 text-right text-xs text-muted-foreground"
                      title={formatDate(inc.detectedAt)}
                    >
                      {formatRelative(inc.detectedAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Cartões no celular */}
            <ul className="divide-y divide-border md:hidden">
              {data.items.map((inc) => (
                <li key={inc.id}>
                  <Link
                    to="/incidents/$incidentId"
                    params={{ incidentId: inc.id }}
                    className="flex flex-col gap-1.5 px-4 py-3"
                  >
                    <span className="flex items-center gap-2 text-sm font-medium">
                      <SevBadge sev={inc.sev} /> {inc.type}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {inc.namespace}/{inc.deployment ?? inc.pod} · {formatRelative(inc.detectedAt)}
                    </span>
                    <span className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={inc.status} label={inc.statusLabel} />
                      <SlaBadge sla={inc.sla} open={OPEN_STATUSES.includes(inc.status)} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
      {data && data.total > data.items.length && (
        <p className="mt-3 text-xs text-muted-foreground">
          {data.items.length} / {data.total}
        </p>
      )}
    </>
  );
}
