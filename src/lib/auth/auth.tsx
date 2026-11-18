import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, apiBase, setUnauthorizedHandler } from "@/lib/api/client";

export type Permission =
  | "incidents:read"
  | "incidents:ack"
  | "incidents:decide"
  | "incidents:simulate"
  | "reports:read"
  | "clusters:read"
  | "brain:read"
  | "brain:write"
  | "health:read"
  | "audit:read"
  | "users:manage"
  | "teams:manage"
  | "settings:manage"
  | "silences:manage";

export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "operator" | "viewer" | "auditor";
  roleLabel: string;
  permissions: Permission[];
  scopes: { cluster: string; namespace: string }[];
  unrestricted: boolean;
  mfa: boolean;
}

export interface AuthConfig {
  authEnabled: boolean;
  oidc: boolean;
  needsSetup: boolean;
}

interface AuthState {
  user: CurrentUser | null;
  config: AuthConfig | null;
  loading: boolean;
  can: (p: Permission) => boolean;
  login: (email: string, password: string, code?: string) => Promise<CurrentUser>;
  setup: (email: string, name: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  ssoUrl: string;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setConfig(await api.get<AuthConfig>("/api/auth/config"));
      setUser(await api.get<CurrentUser>("/api/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      config,
      loading,
      can: (p) => !!user?.permissions.includes(p),
      login: async (email, password, code) => {
        const me = await api.post<CurrentUser>("/api/auth/login", {
          email,
          password,
          ...(code ? { code } : {}),
        });
        setUser(me);
        return me;
      },
      setup: async (email, name, password) => {
        const me = await api.post<CurrentUser>("/api/auth/setup", { email, name, password });
        setUser(me);
        setConfig((c) => (c ? { ...c, needsSetup: false } : c));
        return me;
      },
      logout: async () => {
        await api.post("/api/auth/logout").catch(() => undefined);
        setUser(null);
      },
      refresh,
      ssoUrl: `${apiBase()}/api/auth/oidc/login`,
    }),
    [user, config, loading, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa de <AuthProvider>");
  return ctx;
}
