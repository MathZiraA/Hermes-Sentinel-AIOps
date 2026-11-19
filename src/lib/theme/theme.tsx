import { createContext, useCallback, useContext, useEffect, type ReactNode } from "react";

import { createStoredValue } from "@/lib/storage/stored-value";

export type Theme = "light" | "dark";
const STORAGE_KEY = "sentinel.theme";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);
const themeStore = createStoredValue<Theme>(STORAGE_KEY, "dark", ["dark", "light"]);

/** Tema escuro por padrão (centro de operações); a escolha fica salva neste navegador. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = themeStore.use();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const toggle = useCallback(() => {
    themeStore.set(themeStore.get() === "dark" ? "light" : "dark");
  }, []);

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme precisa de <ThemeProvider>");
  return ctx;
}
