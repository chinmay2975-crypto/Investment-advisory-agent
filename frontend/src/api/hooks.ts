import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";

import { API_BASE, ApiError, authFetch, describeError } from "./auth";
import { api, type Schemas, unwrap } from "./client";

export type Country = Schemas["CountryOut"];
export type Profile = Schemas["InvestorProfileRead"];
export type Holding = Schemas["HoldingRead"];
export type Goal = Schemas["GoalRead"];
export type Recommendation = Schemas["RecommendationRead"];
export type Analysis = Schemas["PortfolioAnalyzeResponse"];
export type AnalyzeRequest = Schemas["PortfolioAnalyzeRequest"];

function useInvestorId(): number {
  const { investorId } = useAuth();
  if (investorId === null) throw new Error("Not logged in");
  return investorId;
}

const path = (investor_id: number) => ({ params: { path: { investor_id } } });

// --- countries & profile ---------------------------------------------------------------

export function useCountries() {
  return useQuery({
    queryKey: ["countries"],
    queryFn: () => unwrap(api.GET("/countries")),
    staleTime: Infinity,
  });
}

export function useInferCountry(tickers: string[]) {
  return useQuery({
    queryKey: ["infer", tickers],
    queryFn: () =>
      unwrap(api.POST("/countries/infer", { body: { holdings: tickers.map((ticker) => ({ ticker })) } })),
    enabled: tickers.length > 0,
  });
}

export function useProfile() {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["profile", investorId],
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/investors/{investor_id}/profile", path(investorId)));
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null; // no profile yet
        throw err;
      }
    },
  });
}

export function useSaveProfile() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["InvestorProfileUpsert"]) =>
      unwrap(api.PUT("/investors/{investor_id}/profile", { ...path(investorId), body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", investorId] });
      qc.invalidateQueries({ queryKey: ["allocation-template", investorId] });
      qc.invalidateQueries({ queryKey: ["analysis"] });
    },
  });
}

export function useAllocationTemplate(enabled: boolean) {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["allocation-template", investorId],
    queryFn: async () =>
      (await unwrap(api.GET("/investors/{investor_id}/profile/allocation-template", path(investorId)))) as Record<
        string,
        number
      >,
    enabled,
  });
}

// --- holdings & analysis -------------------------------------------------------------------

export function useHoldings() {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["holdings", investorId],
    queryFn: () => unwrap(api.GET("/investors/{investor_id}/holdings/", path(investorId))),
  });
}

export type HoldingDraft = { id?: number; ticker: string; quantity: number; cost_basis: number | null };

/** The backend has create + delete only, so an edited row is saved as delete-then-create. */
export function useSaveHoldings() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ current, next }: { current: Holding[]; next: HoldingDraft[] }) => {
      const unchanged = (draft: HoldingDraft, saved: Holding) =>
        draft.ticker === saved.ticker &&
        draft.quantity === saved.quantity &&
        (draft.cost_basis ?? null) === (saved.cost_basis ?? null);
      const keep = new Set(
        next.filter((d) => d.id !== undefined && current.some((s) => s.id === d.id && unchanged(d, s))).map((d) => d.id),
      );
      for (const saved of current.filter((s) => !keep.has(s.id))) {
        await unwrap(
          api.DELETE("/investors/{investor_id}/holdings/{holding_id}", {
            params: { path: { investor_id: investorId, holding_id: saved.id } },
          }),
        );
      }
      for (const draft of next.filter((d) => d.id === undefined || !keep.has(d.id))) {
        await unwrap(
          api.POST("/investors/{investor_id}/holdings/", {
            ...path(investorId),
            body: { ticker: draft.ticker, quantity: draft.quantity, cost_basis: draft.cost_basis },
          }),
        );
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings", investorId] });
      qc.invalidateQueries({ queryKey: ["analysis"] });
    },
  });
}

export type ImportResult = Schemas["PortfolioImportResult"];

/** Multipart upload, so this bypasses openapi-fetch's JSON body handling and uses authFetch directly. */
export function useImportPortfolio() {
  return useMutation({
    mutationFn: async ({ file, text, defaultCountry }: { file?: File; text?: string; defaultCountry?: string | null }) => {
      const form = new FormData();
      if (file) form.append("file", file);
      if (text) form.append("text", text);
      if (defaultCountry) form.append("default_country", defaultCountry);
      const res = await authFetch(`${API_BASE}/portfolio/import`, { method: "POST", body: form });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(res.status, describeError(body, `Import failed (${res.status})`));
      return body as ImportResult;
    },
  });
}

export function useAnalysis(request: AnalyzeRequest | null) {
  return useQuery({
    queryKey: ["analysis", request],
    queryFn: () => unwrap(api.POST("/portfolio/analyze", { body: request! })),
    enabled: request !== null,
    staleTime: 5 * 60_000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

// --- goals ---------------------------------------------------------------------------------

export function useGoals() {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["goals", investorId],
    queryFn: () => unwrap(api.GET("/investors/{investor_id}/goals/", path(investorId))),
  });
}

export function useCreateGoal() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["GoalCreate"]) =>
      unwrap(api.POST("/investors/{investor_id}/goals/", { ...path(investorId), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", investorId] }),
  });
}

export function useGoalAnalysis(goalId: number | null, assumedReturn: number) {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["goal-analysis", goalId, assumedReturn],
    queryFn: () =>
      unwrap(
        api.GET("/investors/{investor_id}/goals/{goal_id}/analysis", {
          params: { path: { investor_id: investorId, goal_id: goalId! }, query: { assumed_annual_return: assumedReturn } },
        }),
      ),
    enabled: goalId !== null,
    retry: false,
  });
}

// --- recommendations, refinement, approval -----------------------------------------------

export function useRecommendations() {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["recommendations", investorId],
    queryFn: async () => {
      const list = await unwrap(api.GET("/investors/{investor_id}/recommendations/", path(investorId)));
      return [...list].sort((a, b) => b.generated_at.localeCompare(a.generated_at));
    },
  });
}

export function useRecommendationAction() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "confirm" }) => {
      const params = { params: { path: { investor_id: investorId, recommendation_id: id } } };
      return unwrap(
        action === "approve"
          ? api.POST("/investors/{investor_id}/recommendations/{recommendation_id}/approve", params)
          : api.POST("/investors/{investor_id}/recommendations/{recommendation_id}/confirm", params),
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations", investorId] }),
  });
}

export function useRefinementSession(recommendationId: number | null) {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["refinement", recommendationId],
    queryFn: async () => {
      try {
        return await unwrap(
          api.GET("/investors/{investor_id}/recommendations/{recommendation_id}/refinement-session", {
            params: { path: { investor_id: investorId, recommendation_id: recommendationId! } },
          }),
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: recommendationId !== null,
  });
}

export function useRefine() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, message }: { id: number; message: string }) =>
      unwrap(
        api.POST("/investors/{investor_id}/recommendations/{recommendation_id}/refine", {
          params: { path: { investor_id: investorId, recommendation_id: id } },
          body: { message },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recommendations", investorId] });
      qc.invalidateQueries({ queryKey: ["refinement"] });
    },
  });
}

export async function downloadRecommendationPdf(investorId: number, recommendationId: number) {
  const res = await authFetch(
    `${API_BASE}/investors/${investorId}/recommendations/${recommendationId}/export-pdf`,
  );
  if (!res.ok) throw new ApiError(res.status, res.status === 400 ? "PDF export needs a goal-linked suggestion" : "PDF export failed");
  const url = URL.createObjectURL(await res.blob());
  const link = Object.assign(document.createElement("a"), {
    href: url,
    download: `investment-target-sheet-${recommendationId}.pdf`,
  });
  link.click();
  URL.revokeObjectURL(url);
}

// --- scenarios, tax, market, self-assessment ---------------------------------------------

export function useScenarios(goalId: number | null) {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["scenarios", goalId],
    queryFn: () =>
      unwrap(
        api.GET("/investors/{investor_id}/goals/{goal_id}/scenarios/", {
          params: { path: { investor_id: investorId, goal_id: goalId! } },
        }),
      ),
    enabled: goalId !== null,
  });
}

export function useRunScenario() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (goalId: number) =>
      unwrap(
        api.POST("/investors/{investor_id}/goals/{goal_id}/scenarios/", {
          params: { path: { investor_id: investorId, goal_id: goalId } },
        }),
      ),
    onSuccess: (_, goalId) => qc.invalidateQueries({ queryKey: ["scenarios", goalId] }),
  });
}

export function useUsTaxAnalysis() {
  const investorId = useInvestorId();
  return useMutation({
    mutationFn: (body: Schemas["TaxAnalysisRequest"]) =>
      unwrap(api.POST("/investors/{investor_id}/holdings/tax-analysis", { ...path(investorId), body })),
  });
}

export type MarketDoc = { text: string; metadata: Record<string, unknown>; distance: number };

export function useMarketRefresh() {
  return useMutation({
    mutationFn: async () =>
      (await unwrap(api.POST("/market-intelligence/refresh"))) as {
        documents_ingested: number;
        by_category: Record<string, number>;
      },
  });
}

export function useMarketQuery() {
  return useMutation({
    mutationFn: async ({ q, n }: { q: string; n: number }) =>
      ((await unwrap(api.GET("/market-intelligence/query", { params: { query: { q, n_results: n } } }))) as {
        results: MarketDoc[];
      }).results,
  });
}

export function useEvaluations(recommendationId: number | null) {
  const investorId = useInvestorId();
  return useQuery({
    queryKey: ["evaluations", recommendationId],
    queryFn: () =>
      unwrap(
        api.GET("/investors/{investor_id}/recommendations/{recommendation_id}/evaluations/", {
          params: { path: { investor_id: investorId, recommendation_id: recommendationId! } },
        }),
      ),
    enabled: recommendationId !== null,
  });
}

export function useRunEvaluation() {
  const investorId = useInvestorId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (recommendationId: number) =>
      unwrap(
        api.POST("/investors/{investor_id}/recommendations/{recommendation_id}/evaluations/", {
          params: { path: { investor_id: investorId, recommendation_id: recommendationId } },
        }),
      ),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ["evaluations", id] }),
  });
}
