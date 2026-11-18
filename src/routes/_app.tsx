import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { TelemetryProvider, useTelemetry } from "@/lib/sentinel/telemetry";

/** Área logada: exige sessão, mantém a telemetria ao vivo e desenha a navegação. */
export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

/** Cada evento ao vivo (agente, aprovação) atualiza as telas na hora, sem esperar o polling. */
function LiveInvalidation() {
  const qc = useQueryClient();
  const { events, approvals } = useTelemetry();
  const last = events.at(-1)?.timestamp;
  const pending = Object.keys(approvals).join(",");
  useEffect(() => {
    void qc.invalidateQueries({ queryKey: ["incidents"] });
    void qc.invalidateQueries({ queryKey: ["incident"] });
    void qc.invalidateQueries({ queryKey: ["summary"] });
  }, [qc, last, pending]);
  return null;
}

function AppLayout() {
  return (
    <RequireAuth>
      <TelemetryProvider>
        <LiveInvalidation />
        <AppShell>
          <Outlet />
        </AppShell>
      </TelemetryProvider>
    </RequireAuth>
  );
}
