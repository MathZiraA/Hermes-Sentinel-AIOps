import { createFileRoute } from "@tanstack/react-router";
import { KanbanOverlay } from "@/components/office/KanbanOverlay";
import { OfficeScene } from "@/components/office/OfficeScene";
import { SystemSidebar } from "@/components/office/SystemSidebar";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Agent Factory — AI Agent Office Dashboard" },
      { name: "description", content: "Watch your AI agents work in a cozy isometric office, with live Kanban progress and system overview." },
      { property: "og:title", content: "Agent Factory — AI Agent Office Dashboard" },
      { property: "og:description", content: "A playful isometric dashboard to manage AI agents, Kanban cards and GitHub sync." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="flex h-screen w-screen overflow-hidden bg-background">
      <section className="relative h-full w-3/4 min-w-0" aria-label="Isometric agent office">
        <OfficeScene />
        <KanbanOverlay />
      </section>
      <div className="h-full w-1/4 min-w-[280px]">
        <SystemSidebar />
      </div>
    </main>
  );
}
