import { Loader2, RefreshCcw } from "lucide-react";
import { useState } from "react";

import { useEvaluations, useRecommendations, useRunEvaluation } from "@/api/hooks";
import { EmptyState, ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { formatPct } from "@/lib/utils";

export default function SelfAssessmentPage() {
  const recommendations = useRecommendations();
  const [choice, setChoice] = useState<number | null>(null);
  const selectedId = choice ?? recommendations.data?.[0]?.id ?? null;
  const evaluations = useEvaluations(selectedId);
  const runEvaluation = useRunEvaluation();

  if (recommendations.isLoading) return <LoadingCards count={2} />;
  if (recommendations.error) return <ErrorState error={recommendations.error} onRetry={() => recommendations.refetch()} />;
  if (!recommendations.data?.length) {
    return (
      <div>
        <PageHeader title="Self-assessment" />
        <EmptyState title="Nothing to assess yet" description="Suggestions are checked against what actually happened in the market." />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader
        title="Self-assessment"
        description="Checks how a past suggestion actually played out and logs a reflection for human review. Runs automatically for suggestions older than 30 days."
        actions={
          <>
            <Select className="w-72" value={selectedId ?? ""} onChange={(e) => setChoice(Number(e.target.value))}>
              {recommendations.data.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} — {String((r.payload as { what?: string }).what ?? "").slice(0, 50)}
                </option>
              ))}
            </Select>
            <Button onClick={() => selectedId && runEvaluation.mutate(selectedId)} disabled={runEvaluation.isPending}>
              {runEvaluation.isPending ? <Loader2 className="animate-spin" /> : <RefreshCcw />} Assess now
            </Button>
          </>
        }
      />
      {runEvaluation.error && (
        <Alert variant="destructive">
          <AlertDescription>{runEvaluation.error.message}</AlertDescription>
        </Alert>
      )}
      {evaluations.isLoading && <LoadingCards count={2} />}
      {evaluations.error && <ErrorState error={evaluations.error} onRetry={() => evaluations.refetch()} />}
      {evaluations.data?.length === 0 && (
        <EmptyState title="Not assessed yet" description="Run an assessment, or wait for the scheduled job." />
      )}
      {evaluations.data?.map((e) => {
        const deviation = (e.deviation ?? {}) as {
          elapsed_days?: number;
          realized_return_pct?: number;
          expected_return_pct?: number;
          deviation_pct?: number;
          expected_return_source?: string;
          benchmark_name?: string;
          benchmark_return_pct?: number | null;
          excess_vs_benchmark_pct?: number | null;
        };
        const hasBenchmark = deviation.benchmark_return_pct != null;
        return (
          <Card key={e.id}>
            <CardHeader className="flex-row items-start justify-between">
              <div>
                <CardTitle>Assessment #{e.id}</CardTitle>
                <CardDescription>{e.evaluated_at.slice(0, 16).replace("T", " ")}</CardDescription>
              </div>
              <Badge variant={e.assumptions_held ? "success" : "destructive"}>
                {e.assumptions_held ? "Assumptions held" : "Assumptions challenged"}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className={`grid gap-3 ${hasBenchmark ? "sm:grid-cols-4" : "sm:grid-cols-3"}`}>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Realised ({deviation.elapsed_days ?? "?"} days)</p>
                  <p className="text-lg font-semibold">{formatPct((deviation.realized_return_pct ?? 0) / 100, 2)}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">
                    Expected ({deviation.expected_return_source === "simulated_allocation" ? "simulated for this mix" : "6%/yr assumption"})
                  </p>
                  <p className="text-lg font-semibold">{formatPct((deviation.expected_return_pct ?? 0) / 100, 2)}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Deviation</p>
                  <p className="text-lg font-semibold">{(deviation.deviation_pct ?? 0).toFixed(2)} pp</p>
                </div>
                {hasBenchmark && (
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground">{deviation.benchmark_name ?? "Market"} same period</p>
                    <p className="text-lg font-semibold">{formatPct((deviation.benchmark_return_pct ?? 0) / 100, 2)}</p>
                    {deviation.excess_vs_benchmark_pct != null && (
                      <p className="text-xs text-muted-foreground">
                        {deviation.excess_vs_benchmark_pct >= 0 ? "Beat" : "Trailed"} by {Math.abs(deviation.excess_vs_benchmark_pct).toFixed(2)} pp
                      </p>
                    )}
                  </div>
                )}
              </div>
              <p className="leading-relaxed">{e.contributing_factors}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
