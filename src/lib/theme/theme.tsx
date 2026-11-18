import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "sentinel.theme";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

/** Tema escuro por padrão (centro de operações); a escolha fica salva neste navegador. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch {
      /* armazenamento indisponível */
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* ignora */
      }
      return next;
    });
  }, []);

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme precisa de <ThemeProvider>");
  return ctx;
}
