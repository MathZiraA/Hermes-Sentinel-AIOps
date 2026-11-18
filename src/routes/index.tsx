import { createFileRoute } from "@tanstack/react-router";
import { KanbanOverlay } from "@/components/office/KanbanOverlay";
import { OfficeScene } from "@/components/office/OfficeScene";
import { SystemSidebar } from "@/components/office/SystemSidebar";
import { TelemetryProvider } from "@/lib/sentinel/telemetry";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Hermes Sentinel — AIOps para Kubernetes" },
      {
        name: "description",
        content:
          "Cinco agentes de IA vigiam, diagnosticam e corrigem seu cluster Kubernetes num escritório isométrico, com aprovação humana.",
      },
      { property: "og:title", content: "Hermes Sentinel — AIOps para Kubernetes" },
      {
        property: "og:description",
        content:
          "AIOps gamificado: Monitor, Supervisor, Investigator, Executor e ITSM trabalhando ao vivo no seu cluster.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <TelemetryProvider>
      <main className="flex h-screen w-screen overflow-hidden bg-background">
        <section
          className="relative h-full w-3/4 min-w-0"
          aria-label="Escritório isométrico dos agentes"
        >
          <OfficeScene />
          <KanbanOverlay />
        </section>
        <div className="h-full w-1/4 min-w-[300px]">
          <SystemSidebar />
        </div>
      </main>
    </TelemetryProvider>
  );
}
