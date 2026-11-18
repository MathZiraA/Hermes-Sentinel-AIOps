import { Fragment, type ReactNode } from "react";

/**
 * Renderizador mínimo para as notas do Hermes Brain (títulos, listas, citações, código, tabelas,
 * negrito, `código` e [[wikilinks]] clicáveis). Sem HTML cru: tudo vira elementos React (sem XSS).
 */
function inline(text: string, onLink: (name: string) => void): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\[\[([^\]|#]+)(?:[#|]([^\]]*))?\]\]|\*\*([^*]+)\*\*|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) {
      const target = m[1].trim();
      out.push(
        <button
          key={k++}
          type="button"
          onClick={() => onLink(target)}
          className="font-medium text-primary hover:underline"
        >
          {m[2] || target}
        </button>,
      );
    } else if (m[3]) out.push(<strong key={k++}>{m[3]}</strong>);
    else if (m[4])
      out.push(
        <code key={k++} className="rounded bg-muted px-1 font-mono text-[0.85em]">
          {m[4]}
        </code>,
      );
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ source, onLink }: { source: string; onLink: (name: string) => void }) {
  const body = source.replace(/^---\n[\s\S]*?\n---\n/, ""); // esconde o frontmatter
  const lines = body.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    if (line.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i]!.startsWith("```")) code.push(lines[i++]!);
      i++;
      blocks.push(
        <pre
          key={key++}
          className="overflow-x-auto rounded-lg bg-screen p-3 font-mono text-xs text-card"
        >
          {code.join("\n")}
        </pre>,
      );
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i]!.startsWith("|")) {
        const cells = lines[i]!.split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        if (!cells.every((c) => /^:?-+:?$/.test(c))) rows.push(cells);
        i++;
      }
      blocks.push(
        <div key={key++} className="overflow-x-auto">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => (
                    <td key={ci} className={`px-2 py-1.5 ${ri === 0 ? "font-medium" : ""}`}>
                      {inline(c, onLink)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*[-*] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*] /.test(lines[i]!))
        items.push(lines[i++]!.replace(/^\s*[-*] (\[[ x]\] )?/, ""));
      blocks.push(
        <ul key={key++} className="list-inside list-disc space-y-1 text-sm">
          {items.map((it, n) => (
            <li key={n}>{inline(it, onLink)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const h = /^(#{1,3}) (.*)$/.exec(line);
    if (h) {
      const size = h[1]!.length === 1 ? "text-lg" : h[1]!.length === 2 ? "text-base" : "text-sm";
      blocks.push(
        <p key={key++} className={`${size} mt-2 font-semibold text-foreground`}>
          {inline(h[2]!, onLink)}
        </p>,
      );
    } else if (line.startsWith("> ")) {
      blocks.push(
        <blockquote
          key={key++}
          className="border-l-2 border-primary pl-3 text-sm text-muted-foreground"
        >
          {inline(line.slice(2), onLink)}
        </blockquote>,
      );
    } else if (line.trim() && line.trim() !== "---") {
      blocks.push(
        <p key={key++} className="text-sm leading-relaxed">
          {inline(line, onLink)}
        </p>,
      );
    }
    i++;
  }
  return (
    <div className="space-y-2.5">
      {blocks.map((b, n) => (
        <Fragment key={n}>{b}</Fragment>
      ))}
    </div>
  );
}
