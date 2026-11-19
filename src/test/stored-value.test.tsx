import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createStoredValue } from "@/lib/storage/stored-value";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("createStoredValue", () => {
  it("usa o padrão quando nada foi salvo e ignora valores fora da lista", () => {
    const store = createStoredValue("t.a", "dark", ["dark", "light"] as const);
    expect(store.get()).toBe("dark");
    localStorage.setItem("t.a", "<script>");
    expect(store.get()).toBe("dark");
  });

  it("salva, lê de volta e avisa os componentes", () => {
    const store = createStoredValue("t.b", "pt", ["pt", "en"] as const);
    function Show() {
      return <span>{store.use()}</span>;
    }
    render(<Show />);
    expect(screen.getByText("pt")).toBeInTheDocument();
    act(() => store.set("en"));
    expect(screen.getByText("en")).toBeInTheDocument();
    expect(localStorage.getItem("t.b")).toBe("en");
  });

  it("continua funcionando em memória quando o armazenamento está bloqueado", () => {
    const store = createStoredValue("t.c", "dark", ["dark", "light"] as const);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    store.set("light");
    expect(store.get()).toBe("light");
  });
});
