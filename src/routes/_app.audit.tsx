import { createFileRoute } from "@tanstack/react-router";
import { Download, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";
import { PageHeader, StateMessage } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { api, apiBase } from "@/lib/api/client";
import { useAudit } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n/i18n";

export const Route = createFileRoute("/_app/audit")({
  head: () => ({ meta: [{ title: "Auditoria · Hermes Sentinel" }] }),
  component: Audit,
});

type Verify = { ok: boolean; entries: number; brokenAt?: number };

function Audit() {
  const { t, formatDate } = useI18n();
  const [page, setPage] = useState(0);
  const size = 50;
  const { data, isLoading } = useAudit(size, page * size);
  const [verify, setVerify] = useState<Verify | null>(null);

  return (
    <>
      <PageHeader
        title={t("audit.title")}
        subtitle={t("audit.subtitle")}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => setVerify(await api.get<Verify>("/api/audit/verify"))}
            >
              <ShieldCheck className="h-4 w-4" /> {t("audit.verify")}
            </Button>
            {(["csv", "json"] as const).map((f) => (
              <Button key={f} asChild variant="outline" size="sm">
                <a href={`${apiBase()}/api/audit/export?format=${f}`}>
                  <Download className="h-4 w-4" /> {f.toUpperCase()}
                </a>
              </Button>
            ))}
          </>
        }
      />
      {verify && (
        <p
          role="status"
          className={`mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
            verify.ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"
          }`}
        >
          {verify.ok ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
          {verify.ok ? t("audit.intact") : `${t("audit.broken")} #${verify.brokenAt}`} ·{" "}
          {verify.entries} {t("audit.entries")}
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        {isLoading ? (
          <StateMessage>{t("common.loading")}</StateMessage>
        ) : !data?.items.length ? (
          <StateMessage>{t("common.empty")}</StateMessage>
        ) : (
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 font-medium">#</th>
                <th className="px-4 py-2.5 font-medium">{t("audit.when")}</th>
                <th className="px-4 py-2.5 font-medium">{t("audit.who")}</th>
                <th className="px-4 py-2.5 font-medium">{t("audit.action")}</th>
                <th className="px-4 py-2.5 font-medium">{t("audit.target")}</th>
                <th className="px-4 py-2.5 font-medium">Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.items.map((e) => (
                <tr key={e.id} className="align-top">
                  <td className="px-4 py-2.5 tabular-nums text-muted-foreground">{e.id}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{formatDate(e.ts)}</td>
                  <td className="px-4 py-2.5">
                    {e.actor}
                    {e.ip && <span className="block text-xs text-muted-foreground">{e.ip}</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs">{e.action}</td>
                  <td className="px-4 py-2.5">
                    {e.target}
                    {Object.keys(e.details).length > 0 && (
                      <span className="mt-0.5 block max-w-sm truncate font-mono text-[11px] text-muted-foreground">
                        {JSON.stringify(e.details)}
                      </span>
                    )}
                  </td>
                  <td
                    className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground"
                    title={e.hash}
                  >
                    {e.hash.slice(0, 10)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {data && data.total > size && (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            ←
          </Button>
          {page + 1} / {Math.ceil(data.total / size)}
          <Button
            variant="outline"
            size="sm"
            disabled={(page + 1) * size >= data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            →
          </Button>
        </div>
      )}
    </>
  );
}
