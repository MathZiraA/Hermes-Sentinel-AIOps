/**
 * Cliente HTTP do Hermes Sentinel. A sessão vai num cookie HttpOnly (`credentials: "include"`),
 * então nenhum token fica acessível ao JavaScript.
 */

/** Backend. Sobrescreva com VITE_SENTINEL_API_URL / VITE_SENTINEL_WS_URL. */
export function apiBase(): string {
  const env = import.meta.env["VITE_SENTINEL_API_URL"] as string | undefined;
  if (env) return env.replace(/\/$/, "");
  const host = typeof window !== "undefined" ? window.location.hostname : "localhost";
  return `http://${host}:8000`;
}

export function wsUrl(): string {
  const env = import.meta.env["VITE_SENTINEL_WS_URL"] as string | undefined;
  return env ?? apiBase().replace(/^http/, "ws") + "/ws/telemetry";
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** Avisado quando a sessão expira (401), para voltar à tela de login. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function messageOf(body: unknown, status: number): { message: string; code?: string } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; code?: string };
    return d.code ? { message: d.message, code: d.code } : { message: d.message };
  }
  return { message: `HTTP ${status}` };
}

export async function request<T = unknown>(
  method: Method,
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = { method, credentials: "include" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${apiBase()}${path}`, init);
  const text = await res.text();
  const data: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const { message, code } = messageOf(data, res.status);
    if (
      res.status === 401 &&
      code !== "mfa_required" &&
      code !== "invalid" &&
      !path.startsWith("/api/auth/")
    )
      onUnauthorized?.();
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

export const api = {
  get: <T = unknown>(path: string) => request<T>("GET", path),
  post: <T = unknown>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T = unknown>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T = unknown>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T = unknown>(path: string) => request<T>("DELETE", path),
};
