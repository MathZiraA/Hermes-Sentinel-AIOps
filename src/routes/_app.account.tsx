import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader, Panel } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth";
import { useI18n } from "@/lib/i18n/i18n";

export const Route = createFileRoute("/_app/account")({
  head: () => ({ meta: [{ title: "Minha conta · Hermes Sentinel" }] }),
  component: Account,
});

function PasswordForm() {
  const { t } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/api/auth/password", { current, new: next });
      setCurrent("");
      setNext("");
      setMsg({ ok: true, text: t("account.saved") });
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    }
  };
  return (
    <form onSubmit={submit} className="grid max-w-sm gap-3">
      <div className="space-y-1.5">
        <Label htmlFor="pw-cur">{t("account.current")}</Label>
        <Input
          id="pw-cur"
          type="password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="pw-new">{t("account.new")}</Label>
        <Input
          id="pw-new"
          type="password"
          autoComplete="new-password"
          required
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
      </div>
      <Button type="submit" className="justify-self-start">
        {t("common.save")}
      </Button>
      {msg && (
        <p role="status" className={`text-sm ${msg.ok ? "text-success" : "text-destructive"}`}>
          {msg.text}
        </p>
      )}
    </form>
  );
}

function MfaPanel() {
  const { t } = useI18n();
  const { user, refresh } = useAuth();
  const [setup, setSetup] = useState<{ secret: string; otpauthUri: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="max-w-md space-y-3">
      <p className="flex items-center gap-2 text-sm">
        {user?.mfa ? (
          <ShieldCheck className="h-4 w-4 text-success" />
        ) : (
          <ShieldOff className="h-4 w-4 text-muted-foreground" />
        )}
        {user?.mfa ? t("account.mfaOn") : t("account.mfaOff")}
      </p>
      {!user?.mfa && !setup && (
        <Button
          variant="outline"
          onClick={() => void act(async () => setSetup(await api.post("/api/auth/totp/setup")))}
        >
          {t("account.mfaStart")}
        </Button>
      )}
      {(setup || user?.mfa) && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await api.post(user?.mfa ? "/api/auth/totp/disable" : "/api/auth/totp/enable", {
                code,
              });
              setSetup(null);
              setCode("");
            });
          }}
          className="space-y-3"
        >
          {setup && (
            <>
              <p className="text-sm text-muted-foreground">{t("account.mfaScan")}</p>
              <code className="block break-all rounded-lg bg-muted px-3 py-2 font-mono text-sm tracking-wider">
                {setup.secret}
              </code>
              <a href={setup.otpauthUri} className="text-xs text-primary hover:underline">
                otpauth://
              </a>
            </>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="mfa-code">{t("account.code")}</Label>
            <Input
              id="mfa-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          <Button type="submit" variant={user?.mfa ? "outline" : "default"}>
            {user?.mfa ? t("account.mfaDisable") : t("account.mfaConfirm")}
          </Button>
        </form>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function Account() {
  const { t } = useI18n();
  const { user } = useAuth();
  return (
    <>
      <PageHeader
        title={t("account.title")}
        subtitle={user ? `${user.name} · ${user.email} · ${user.roleLabel}` : undefined}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={t("account.password")}>
          <PasswordForm />
        </Panel>
        <Panel title={t("account.mfa")}>
          <MfaPanel />
        </Panel>
      </div>
      {user && !user.unrestricted && (
        <Panel title="Escopo" className="mt-6">
          <ul className="flex flex-wrap gap-2">
            {user.scopes.length ? (
              user.scopes.map((s) => (
                <li
                  key={`${s.cluster}/${s.namespace}`}
                  className="rounded-md bg-muted px-2 py-1 font-mono text-xs"
                >
                  {s.cluster}/{s.namespace}
                </li>
              ))
            ) : (
              <li className="text-sm text-muted-foreground">—</li>
            )}
          </ul>
        </Panel>
      )}
    </>
  );
}
