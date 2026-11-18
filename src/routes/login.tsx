import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Entrar · Hermes Sentinel" }] }),
  component: LoginPage,
});

type Step = "credentials" | "mfa";

function LoginPage() {
  const { user, config, loading, login, setup, ssoUrl } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstRun = !!config?.needsSetup;
  const ssoError =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("erro") === "sso";

  useEffect(() => {
    if (!loading && user) void navigate({ to: "/" });
  }, [loading, user, navigate]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (firstRun) await setup(email, name, password);
      else await login(email, password, step === "mfa" ? code : undefined);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.code === "mfa_required") {
        setStep("mfa");
      } else {
        setError(apiErr.message || "Não foi possível entrar.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-card">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </span>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-foreground">
              Hermes Sentinel
            </p>
            <p className="text-sm text-muted-foreground">AIOps para Kubernetes</p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-border bg-card p-6 shadow-card"
          aria-describedby={error ? "login-error" : undefined}
        >
          <div>
            <h1 className="text-lg font-semibold text-foreground">
              {firstRun
                ? "Configuração inicial"
                : step === "mfa"
                  ? "Verificação em duas etapas"
                  : "Entrar"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {firstRun
                ? "Crie a conta de administrador desta instalação."
                : step === "mfa"
                  ? "Digite o código de 6 dígitos do seu aplicativo autenticador."
                  : "Use sua conta corporativa."}
            </p>
          </div>

          {step === "credentials" && (
            <>
              {firstRun && (
                <div className="space-y-1.5">
                  <Label htmlFor="name">Nome</Label>
                  <Input
                    id="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="email">E-mail</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Senha</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete={firstRun ? "new-password" : "current-password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {firstRun && (
                  <p className="text-xs text-muted-foreground">
                    Mínimo de 12 caracteres, com maiúsculas, minúsculas e números.
                  </p>
                )}
              </div>
            </>
          )}

          {step === "mfa" && (
            <div className="space-y-1.5">
              <Label htmlFor="code">Código</Label>
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </div>
          )}

          {(error || ssoError) && (
            <p id="login-error" role="alert" className="text-sm text-destructive">
              {error ??
                "Não foi possível entrar pelo SSO. Tente de novo ou fale com o administrador."}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={busy || loading}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            {firstRun ? "Criar administrador" : step === "mfa" ? "Verificar" : "Entrar"}
          </Button>

          {config?.oidc && !firstRun && step === "credentials" && (
            <Button asChild variant="outline" className="w-full">
              <a href={ssoUrl}>
                <KeyRound className="h-4 w-4" aria-hidden /> Entrar com SSO
              </a>
            </Button>
          )}
        </form>
      </div>
    </main>
  );
}
