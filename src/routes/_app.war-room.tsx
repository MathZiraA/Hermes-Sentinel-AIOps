import { createFileRoute } from "@tanstack/react-router";
import { KanbanOverlay } from "@/components/office/KanbanOverlay";
import { OfficeScene } from "@/components/office/OfficeScene";
import { SystemSidebar } from "@/components/office/SystemSidebar";

export const Route = createFileRoute("/_app/war-room")({
  head: () => ({ meta: [{ title: "Sala de guerra · Hermes Sentinel" }] }),
  component: WarRoom,
});

/** O escritório isométrico: os cinco agentes trabalhando ao vivo. */
function WarRoom() {
  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <section
        className="relative h-full min-w-0 flex-1"
        aria-label="Escritório isométrico dos agentes"
      >
        <OfficeScene />
        <KanbanOverlay />
      </section>
      <div className="hidden h-full w-[320px] shrink-0 xl:block">
        <SystemSidebar />
      </div>
    </div>
  );
}
