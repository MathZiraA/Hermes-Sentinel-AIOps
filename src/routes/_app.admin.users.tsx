import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader, Panel, StateMessage } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api/client";
import { useUsers } from "@/lib/api/hooks";
import type { AdminUser } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth";
import { useI18n, type MessageKey } from "@/lib/i18n/i18n";

export const Route = createFileRoute("/_app/admin/users")({
  head: () => ({ meta: [{ title: "Usuários · Hermes Sentinel" }] }),
  component: UsersPage,
});

const ROLES: AdminUser["role"][] = ["viewer", "operator", "auditor", "admin"];
const SELECT =
  "h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

function NewUserForm({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ name: "", email: "", role: "viewer", password: "" });
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/admin/users", { ...form, password: form.password || null });
      setForm({ name: "", email: "", role: "viewer", password: "" });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
      <div className="space-y-1.5">
        <Label htmlFor="nu-name">{t("users.name")}</Label>
        <Input
          id="nu-name"
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="nu-email">{t("users.email")}</Label>
        <Input
          id="nu-email"
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="nu-role">{t("users.role")}</Label>
        <select
          id="nu-role"
          className={`${SELECT} w-full`}
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value })}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`role.${r}` as MessageKey)}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="nu-pw">{t("users.password")}</Label>
        <Input
          id="nu-pw"
          type="password"
          autoComplete="new-password"
          placeholder="vazio = só SSO"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
      </div>
      <Button type="submit">
        <Plus className="h-4 w-4" /> {t("common.create")}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive sm:col-span-2 lg:col-span-5">
          {error}
        </p>
      )}
    </form>
  );
}

function UsersPage() {
  const { t, formatRelative } = useI18n();
  const { user: me } = useAuth();
  const { data, isLoading } = useUsers();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["users"] });
  const patch = async (id: string, body: Record<string, unknown>) => {
    setError(null);
    try {
      await api.patch(`/api/admin/users/${id}`, body);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader title={t("users.title")} subtitle={t("users.subtitle")} />
      <Panel title={t("users.new")} className="mb-6">
        <NewUserForm onDone={refresh} />
      </Panel>
      {error && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        {isLoading ? (
          <StateMessage>{t("common.loading")}</StateMessage>
        ) : (
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 font-medium">{t("users.name")}</th>
                <th className="px-4 py-2.5 font-medium">{t("users.role")}</th>
                <th className="px-4 py-2.5 font-medium">{t("nav.teams")}</th>
                <th className="px-4 py-2.5 font-medium">{t("users.lastLogin")}</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.map((u) => (
                <tr key={u.id} className={u.active ? "" : "opacity-60"}>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5 font-medium">
                      {u.name}
                      {u.mfa && (
                        <ShieldCheck className="h-3.5 w-3.5 text-success" aria-label="2FA" />
                      )}
                      {u.sso && (
                        <KeyRound className="h-3.5 w-3.5 text-muted-foreground" aria-label="SSO" />
                      )}
                    </span>
                    <span className="text-xs text-muted-foreground">{u.email}</span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      aria-label={`${t("users.role")}: ${u.email}`}
                      className={SELECT}
                      value={u.role}
                      disabled={u.id === me?.id}
                      onChange={(e) => void patch(u.id, { role: e.target.value })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {t(`role.${r}` as MessageKey)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{u.teams.join(", ") || "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatRelative(u.lastLoginAt)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== me?.id && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void patch(u.id, { active: !u.active })}
                      >
                        {u.active ? t("users.deactivate") : t("users.activate")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
