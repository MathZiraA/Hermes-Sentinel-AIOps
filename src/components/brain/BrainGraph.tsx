import { useEffect, useRef } from "react";
import type { BrainGraph as Graph } from "@/lib/api/types";

/** Cores por pasta do Hermes Brain (as mesmas do grafo do Obsidian). */
export const GROUP_COLOR: Record<string, string> = {
  incidente: "#e5484d",
  padrao: "#f76b15",
  servico: "#3e63dd",
  licao: "#30a46c",
  runbook: "#8e4ec6",
  equipe: "#ffc53d",
  diario: "#8b8d98",
  cluster: "#12a594",
  outro: "#8b8d98",
};

interface Node {
  id: string;
  group: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  degree: number;
}

/**
 * Grafo de forças em canvas, sem dependências: repulsão entre nós, molas nas ligações e
 * gravidade para o centro. Clique num nó para abrir a nota.
 */
export function BrainGraph({
  data,
  selected,
  onSelect,
}: {
  data: Graph;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const degree: Record<string, number> = {};
    for (const l of data.links) {
      degree[l.source] = (degree[l.source] ?? 0) + 1;
      degree[l.target] = (degree[l.target] ?? 0) + 1;
    }
    const nodes: Node[] = data.nodes.map((n, i) => {
      const a = (i / Math.max(1, data.nodes.length)) * Math.PI * 2;
      return {
        id: n.id,
        group: n.group,
        x: Math.cos(a) * 200,
        y: Math.sin(a) * 200,
        vx: 0,
        vy: 0,
        degree: degree[n.id] ?? 0,
      };
    });
    const index = new Map(nodes.map((n) => [n.id, n]));
    const links = data.links
      .map((l) => [index.get(l.source), index.get(l.target)] as const)
      .filter((p): p is readonly [Node, Node] => !!p[0] && !!p[1]);
    nodesRef.current = nodes;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let alpha = 1;
    let frame = 0;

    const radius = (n: Node) => 3 + Math.min(9, Math.sqrt(n.degree) * 1.8);

    const step = () => {
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]!;
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]!;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = Math.max(25, dx * dx + dy * dy);
          const f = (1400 / d2) * alpha;
          a.vx += dx * f * 0.05;
          a.vy += dy * f * 0.05;
          b.vx -= dx * f * 0.05;
          b.vy -= dy * f * 0.05;
        }
      }
      for (const [a, b] of links) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = ((d - 70) / d) * 0.02 * alpha;
        a.vx += dx * f;
        a.vy += dy * f;
        b.vx -= dx * f;
        b.vy -= dy * f;
      }
      for (const n of nodes) {
        n.vx -= n.x * 0.004 * alpha;
        n.vy -= n.y * 0.004 * alpha;
        n.vx *= 0.82;
        n.vy *= 0.82;
        n.x += n.vx;
        n.y += n.vy;
      }
      alpha = Math.max(0.02, alpha * 0.985);
    };

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, (w / 2) * dpr, (h / 2) * dpr);
      ctx.clearRect(-w / 2, -h / 2, w, h);
      const sel = selectedRef.current;
      const style = getComputedStyle(canvas);
      ctx.strokeStyle = style.getPropertyValue("--border") || "#888";
      ctx.lineWidth = 1;
      for (const [a, b] of links) {
        ctx.globalAlpha = sel && (a.id === sel || b.id === sel) ? 0.9 : 0.35;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      for (const n of nodes) {
        ctx.fillStyle = GROUP_COLOR[n.group] ?? GROUP_COLOR["outro"]!;
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius(n) + (n.id === sel ? 3 : 0), 0, Math.PI * 2);
        ctx.fill();
        if (n.id === sel || n.degree >= 6) {
          ctx.fillStyle = style.getPropertyValue("--foreground") || "#ddd";
          ctx.font = "11px Inter, sans-serif";
          ctx.fillText(
            n.id.length > 28 ? `${n.id.slice(0, 27)}…` : n.id,
            n.x + radius(n) + 3,
            n.y + 4,
          );
        }
      }
    };

    const loop = () => {
      if (!reduceMotion || alpha > 0.5) step();
      draw();
      frame = requestAnimationFrame(loop);
    };
    if (reduceMotion) for (let i = 0; i < 300; i++) step();
    loop();
    return () => cancelAnimationFrame(frame);
  }, [data]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    let best: Node | null = null;
    let bestD = 14 * 14;
    for (const n of nodesRef.current) {
      const d = (n.x - x) ** 2 + (n.y - y) ** 2;
      if (d < bestD) {
        best = n;
        bestD = d;
      }
    }
    if (best) onSelect(best.id);
  };

  return (
    <canvas
      ref={canvasRef}
      onClick={pick}
      role="img"
      aria-label={`Grafo com ${data.nodes.length} notas e ${data.links.length} ligações`}
      className="h-full w-full cursor-pointer"
    />
  );
}
