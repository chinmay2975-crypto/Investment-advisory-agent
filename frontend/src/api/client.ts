import createClient from "openapi-fetch";

import { API_BASE, ApiError, authFetch, describeError } from "./auth";
import type { components, paths } from "./schema";

/** Typed client generated from the FastAPI OpenAPI schema (`npm run gen:api` to refresh). */
export const api = createClient<paths>({ baseUrl: API_BASE, fetch: authFetch });

export type Schemas = components["schemas"];

/** Unwrap an openapi-fetch result, throwing ApiError with the backend's `detail` message. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, describeError(error, `Request failed (${response.status})`));
  return data as T;
}
