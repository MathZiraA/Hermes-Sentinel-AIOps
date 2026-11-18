import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/client";
import { useTeams } from "@/lib/api/hooks";
import type { AdminTeam } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/i18n";

export const Route = createFileRoute("/_app/admin/teams")({
  head: () => ({ meta: [{ title: "Times · Hermes Sentinel" }] }),
  component: TeamsPage,
});

function parseScopes(text: string) {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const [cluster = "*", namespace = "*"] = l.split("/").map((p) => p.trim() || "*");
      return { cluster, namespace };
    });
}

function TeamCard({ team, onChange }: { team: AdminTeam; onChange: () => void }) {
  const { t } = useI18n();
  const [members, setMembers] = useState(team.members.join(", "));
  const [scopes, setScopes] = useState(
    team.scopes.map((s) => `${s.cluster}/${s.namespace}`).join("\n"),
  );
  const [status, setStatus] = useState<string | null>(null);
  const save = async () => {
    setStatus(null);
    try {
      await api.put(`/api/admin/teams/${team.id}`, {
        members: members
          .split(",")
          .map((m) => m.trim())
          .filter(Boolean),
        scopes: parseScopes(scopes),
      });
      setStatus(t("account.saved"));
      onChange();
    } catch (e) {
      setStatus((e as Error).message);
    }
  };
  return (
    <Panel
      title={team.name}
      actions={
        <button
          type="button"
          aria-label={`Excluir ${team.name}`}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
          onClick={async () => {
            if (!confirm(`Excluir o time ${team.name}?`)) return;
            await api.del(`/api/admin/teams/${team.id}`);
            onChange();
          }}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      }
    >
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`m-${team.id}`}>{t("teams.members")}</Label>
          <Textarea
            id={`m-${team.id}`}
            rows={3}
            value={members}
            onChange={(e) => setMembers(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`s-${team.id}`}>{t("teams.scopes")}</Label>
          <Textarea
            id={`s-${team.id}`}
            rows={3}
            placeholder={"local/stockflow\n*/financeiro"}
            className="font-mono text-xs"
            value={scopes}
            onChange={(e) => setScopes(e.target.value)}
          />
        </div>
      </div>
      <div className="mt-3 flex items-center justify-end gap-3">
        {status && <span className="text-xs text-muted-foreground">{status}</span>}
        <Button size="sm" onClick={() => void save()}>
          {t("common.save")}
        </Button>
      </div>
    </Panel>
  );
}

function TeamsPage() {
  const { t } = useI18n();
  const { data, isLoading } = useTeams();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["teams"] });
    void qc.invalidateQueries({ queryKey: ["users"] });
  };
  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await api.post("/api/admin/teams", { name });
    setName("");
    refresh();
  };
  return (
    <>
      <PageHeader title={t("teams.title")} subtitle={t("teams.subtitle")} />
      <form onSubmit={create} className="mb-6 flex max-w-md gap-2">
        <Input
          aria-label={t("teams.new")}
          placeholder={t("teams.new")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit">
          <Plus className="h-4 w-4" /> {t("common.create")}
        </Button>
      </form>
      {isLoading ? (
        <StateMessage>{t("common.loading")}</StateMessage>
      ) : !data?.length ? (
        <StateMessage>{t("common.empty")}</StateMessage>
      ) : (
        <div className="grid gap-4">
          {data.map((team) => (
            <TeamCard key={team.id} team={team} onChange={refresh} />
          ))}
        </div>
      )}
    </>
  );
}
