import { EventStreamContentType, fetchEventSource } from "@microsoft/fetch-event-source";

import { API_BASE, ApiError, describeError, refreshAccessToken, tokenStore } from "./auth";
import type { Schemas } from "./client";

export type AdviceStage = { stage: string; label: string; status: "started" | "completed" };
export type AdviceContext = {
  country: string;
  country_name: string;
  currency: string;
  benchmark_name: string;
  source: "inferred" | "user_selected";
  warnings: string[];
};
export type AdviceSection = { key: string; title: string; content: unknown };

export type AdviceEvent =
  | { event: "stage"; data: AdviceStage }
  | { event: "context"; data: AdviceContext }
  | { event: "section"; data: AdviceSection }
  | { event: "done"; data: { recommendation_id: number; llm_provider: string } }
  | { event: "error"; data: { message: string } };

class AuthExpired extends Error {}

/**
 * POST + Server-Sent Events. Browser EventSource only supports GET without headers, so this uses
 * fetch-event-source, which can send a JSON body and the Authorization header.
 */
export async function streamAdvice(
  body: Schemas["AdviceRequest"],
  onEvent: (event: AdviceEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const attempt = () =>
    fetchEventSource(`${API_BASE}/advice/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(tokenStore.getAccess() ? { Authorization: `Bearer ${tokenStore.getAccess()}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
      openWhenHidden: true,
      async onopen(res) {
        if (res.ok && res.headers.get("content-type")?.startsWith(EventStreamContentType)) return;
        if (res.status === 401) throw new AuthExpired();
        throw new ApiError(res.status, describeError(await res.json().catch(() => null), `HTTP ${res.status}`));
      },
      onmessage(message) {
        if (message.event) onEvent({ event: message.event, data: JSON.parse(message.data) } as AdviceEvent);
      },
      onerror(err) {
        throw err; // never auto-retry: a retry would re-run (and re-bill) the LLM call
      },
    });

  if (!tokenStore.getAccess()) await refreshAccessToken();
  try {
    await attempt();
  } catch (err) {
    if (err instanceof AuthExpired && (await refreshAccessToken())) return attempt();
    if (err instanceof AuthExpired) throw new ApiError(401, "Your session expired. Please log in again.");
    throw err;
  }
}
