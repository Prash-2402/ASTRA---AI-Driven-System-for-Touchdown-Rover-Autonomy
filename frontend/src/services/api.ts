// Thin typed client. All authoritative state lives in the backend; the UI only reads and commands.
const DEFAULT_BASE = (import.meta as any).env?.VITE_API_BASE || `${location.protocol}//${location.hostname}:8000`;

export function apiBase(): string {
  try { return localStorage.getItem("astra.apiBase") || DEFAULT_BASE; } catch { return DEFAULT_BASE; }
}
export function setApiBase(url: string) { try { localStorage.setItem("astra.apiBase", url); } catch { /* storage unavailable */ } }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiBase() + path, {
    method, headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* not json */ }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, b: unknown = {}) => request<T>("POST", p, b),
  url: (p: string) => apiBase() + p,
};

export function wsUrl(channel: string): string {
  return apiBase().replace(/^http/, "ws") + `/ws/${channel}`;
}
