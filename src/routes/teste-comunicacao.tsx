import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { CommunicationScene } from "@/components/communication/CommunicationScene";

export const Route = createFileRoute("/teste-comunicacao")({
  head: () => ({
    meta: [
      { title: "Teste de Comunicação — Hermes Sentinel" },
      {
        name: "description",
        content:
          "Veja o Supervisor caminhar até o Monitor e trocar dados numa cena animada de teste de comunicação.",
      },
      { property: "og:title", content: "Teste de Comunicação — Hermes Sentinel" },
      {
        property: "og:description",
        content: "Cena animada em que dois agentes de IA se encontram e trocam dados.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CommunicationTestPage,
});

function CommunicationTestPage() {
  return (
    <main className="min-h-screen bg-background px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar ao escritório
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
          Teste de Comunicação
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          O Supervisor caminha até o Monitor, os dois trocam dados e o Supervisor volta ao seu
          lugar. No escritório principal, o botão “Testar Comunicação” faz o mesmo com dados reais
          do backend.
        </p>
        <div className="mt-6">
          <CommunicationScene />
        </div>
      </div>
    </main>
  );
}
