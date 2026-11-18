import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Markdown } from "@/components/brain/Markdown";

describe("Markdown do Hermes Brain", () => {
  it("transforma [[wikilinks]] em links que abrem a nota", () => {
    const onLink = vi.fn();
    render(<Markdown source={"Ver [[OOMKilled]] e [[relatorios|o serviço]]."} onLink={onLink} />);
    fireEvent.click(screen.getByRole("button", { name: "o serviço" }));
    expect(onLink).toHaveBeenCalledWith("relatorios");
    expect(screen.getByRole("button", { name: "OOMKilled" })).toBeInTheDocument();
  });

  it("nunca interpreta HTML vindo da nota (sem XSS)", () => {
    const { container } = render(
      <Markdown source={'<img src=x onerror="alert(1)"> **negrito**'} onLink={() => undefined} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">');
    expect(container.querySelector("strong")?.textContent).toBe("negrito");
  });

  it("esconde o frontmatter e desenha tabelas e listas", () => {
    const md = "---\ntags: [x]\n---\n# Título\n| A | B |\n|---|---|\n| 1 | 2 |\n- item";
    const { container } = render(<Markdown source={md} onLink={() => undefined} />);
    expect(container.textContent).not.toContain("tags:");
    expect(container.querySelectorAll("td")).toHaveLength(4);
    expect(container.querySelector("li")?.textContent).toBe("item");
  });
});
