/**
 * Token handling. The access token lives in memory only; the refresh token and investor id
 * are in localStorage so a reload can restore the session. localStorage is readable by any
 * script on the page (XSS risk) -- a known trade-off; httpOnly refresh cookies would be safer
 * but need backend changes.
 */

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "/api";

const REFRESH_KEY = "investad.refreshToken";
const INVESTOR_KEY = "investad.investorId";

let accessToken: string | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

export const tokenStore = {
  getAccess: () => accessToken,
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  getInvestorId: (): number | null => {
    const value = localStorage.getItem(INVESTOR_KEY);
    return value ? Number(value) : null;
  },
  setSession(access: string, refresh: string, investorId: number) {
    accessToken = access;
    localStorage.setItem(REFRESH_KEY, refresh);
    localStorage.setItem(INVESTOR_KEY, String(investorId));
    notify();
  },
  setAccess(access: string) {
    accessToken = access;
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(INVESTOR_KEY);
    notify();
  },
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function describeError(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
        .join("; ");
    }
  }
  return fallback;
}

let refreshing: Promise<boolean> | null = null;

/** Single-flight refresh: concurrent 401s share one /auth/refresh call. */
export function refreshAccessToken(): Promise<boolean> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return Promise.resolve(false);
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  })
    .then(async (res) => {
      if (!res.ok) {
        tokenStore.clear();
        return false;
      }
      tokenStore.setAccess((await res.json()).access_token);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

function withAuth(request: Request): Request {
  const token = tokenStore.getAccess();
  if (token) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

/** fetch() that attaches the bearer token and transparently refreshes + retries once on 401. */
export async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = new Request(input, init);
  const retry = request.clone();
  if (!tokenStore.getAccess() && tokenStore.getRefresh()) await refreshAccessToken();

  const response = await fetch(withAuth(request));
  if (response.status !== 401 || !tokenStore.getRefresh()) return response;
  if (!(await refreshAccessToken())) return response;
  return fetch(withAuth(retry));
}

export async function login(email: string, password: string): Promise<number> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describeError(body, "Login failed"));
  tokenStore.setSession(body.access_token, body.refresh_token, body.investor_id);
  return body.investor_id;
}

export async function signup(email: string, password: string, fullName?: string): Promise<number> {
  const res = await fetch(`${API_BASE}/investors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName || null }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, describeError(await res.json().catch(() => null), "Sign-up failed"));
  }
  return login(email, password);
}
