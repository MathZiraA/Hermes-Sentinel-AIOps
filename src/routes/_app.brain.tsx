import { createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";
import { BrainGraph, GROUP_COLOR } from "@/components/brain/BrainGraph";
import { Markdown } from "@/components/brain/Markdown";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { Input } from "@/components/ui/input";
import { useBrainGraph, useBrainNote, useBrainSearch } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n/i18n";

export const Route = createFileRoute("/_app/brain")({
  head: () => ({ meta: [{ title: "Hermes Brain · Hermes Sentinel" }] }),
  component: BrainPage,
});

const LEGEND: [string, string][] = [
  ["incidente", "Incidentes"],
  ["padrao", "Padrões"],
  ["servico", "Serviços"],
  ["licao", "Lições"],
  ["runbook", "Runbooks"],
  ["equipe", "Equipe"],
  ["diario", "Diário"],
];

function BrainPage() {
  const { t } = useI18n();
  const graph = useBrainGraph();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const results = useBrainSearch(submitted);
  const note = useBrainNote(selected);

  return (
    <>
      <PageHeader title={t("brain.title")} subtitle={t("brain.subtitle")} />
      <div className="grid gap-6 xl:grid-cols-5">
        <div className="flex flex-col gap-4 xl:col-span-3">
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(query.trim());
            }}
            className="relative"
          >
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("brain.search")}
              aria-label={t("brain.search")}
              className="pl-8"
            />
          </form>
          {submitted && (
            <Panel title={t("brain.results")}>
              {results.isLoading ? (
                <StateMessage>{t("common.loading")}</StateMessage>
              ) : !results.data?.length ? (
                <StateMessage>{t("common.empty")}</StateMessage>
              ) : (
                <ul className="divide-y divide-border">
                  {results.data.map((r) => (
                    <li key={r.nota}>
                      <button
                        type="button"
                        onClick={() => setSelected(r.nota)}
                        className="w-full py-2 text-left hover:text-primary"
                      >
                        <span className="text-sm font-medium">{r.nota}</span>
                        <span className="ml-2 text-xs text-muted-foreground">{r.pasta}</span>
                        <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                          {r.trecho}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
          <Panel
            title={t("brain.graph")}
            actions={
              graph.data && (
                <span className="text-xs text-muted-foreground">
                  {graph.data.nodes.length} · {graph.data.links.length}
                </span>
              )
            }
          >
            <div className="h-[420px] sm:h-[520px]">
              {graph.data ? (
                <BrainGraph data={graph.data} selected={selected} onSelect={setSelected} />
              ) : (
                <StateMessage>
                  {graph.isError ? t("common.error") : t("common.loading")}
                </StateMessage>
              )}
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
              {LEGEND.map(([g, label]) => (
                <li key={g} className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: GROUP_COLOR[g] }}
                  />
                  {label}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
        <Panel
          title={selected ?? "Nota"}
          className="xl:col-span-2 xl:max-h-[calc(100vh-10rem)] xl:overflow-y-auto"
        >
          {!selected ? (
            <StateMessage>{t("brain.selectNote")}</StateMessage>
          ) : note.isLoading ? (
            <StateMessage>{t("common.loading")}</StateMessage>
          ) : note.data ? (
            <>
              <p className="mb-3 text-xs text-muted-foreground">{note.data.folder}</p>
              <Markdown source={note.data.markdown} onLink={setSelected} />
            </>
          ) : (
            <StateMessage>{t("common.error")}</StateMessage>
          )}
          <p className="mt-6 border-t border-border pt-3 text-xs text-muted-foreground">
            {t("brain.openInObsidian")}
          </p>
        </Panel>
      </div>
    </>
  );
}
