import { GitCompare, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { type Recommendation, useGoals, useRunScenario, useScenarios } from "@/api/hooks";
import { EmptyState, ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";

const VARIANTS = [
  { key: "conservative_recommendation", label: "Conservative", icon: "🛡️" },
  { key: "balanced_recommendation", label: "Balanced", icon: "⚖️" },
  { key: "aggressive_recommendation", label: "Aggressive", icon: "🚀" },
] as const;

function VariantCard({ label, icon, rec }: { label: string; icon: string; rec: Recommendation }) {
  const p = rec.payload as { what?: string; goal_probability?: number; goal_probability_method?: string; target_allocation?: Record<string, number>; risks?: string[] };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>
            {icon} {label}
          </span>
          <Badge title={p.goal_probability_method === "monte_carlo" ? "Monte Carlo simulation of this allocation" : "LLM estimate"}>
            {Math.round((p.goal_probability ?? 0) * 100)}% goal prob.{p.goal_probability_method === "monte_carlo" ? " (simulated)" : ""}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p>{p.what}</p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(p.target_allocation ?? {}).map(([k, v]) => (
            <Badge key={k} variant="secondary">
              {k} {v}%
            </Badge>
          ))}
        </div>
        <ul className="list-disc pl-5 text-muted-foreground">
          {(p.risks ?? []).slice(0, 3).map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function ScenariosPage() {
  const goals = useGoals();
  const [goalId, setGoalId] = useState<number | null>(null);
  const effectiveGoal = goalId ?? goals.data?.[0]?.id ?? null;
  const history = useScenarios(effectiveGoal);
  const run = useRunScenario();

  if (goals.isLoading) return <LoadingCards count={3} />;
  if (goals.error) return <ErrorState error={goals.error} onRetry={() => goals.refetch()} />;
  if (!goals.data?.length) {
    return (
      <div>
        <PageHeader title="Scenarios" />
        <EmptyState
          title="Scenarios compare risk levels for a goal"
          description="Create a goal first."
          action={
            <Button asChild>
              <Link to="/goals">Create a goal</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const latest = history.data?.at(-1);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scenarios"
        description="The same goal planned three ways — compare conservative, balanced and aggressive side by side."
        actions={
          <>
            <Select className="w-64" value={effectiveGoal ?? ""} onChange={(e) => setGoalId(Number(e.target.value))}>
              {goals.data.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.category} (by {g.target_date.slice(0, 10)})
                </option>
              ))}
            </Select>
            <Button onClick={() => effectiveGoal && run.mutate(effectiveGoal)} disabled={run.isPending}>
              {run.isPending ? <Loader2 className="animate-spin" /> : <GitCompare />} Run comparison
            </Button>
          </>
        }
      />
      {run.isPending && <LoadingCards count={3} label="Generating three suggestions in parallel — this can take 20–40 seconds" />}
      {run.error && (
        <Alert variant="destructive">
          <AlertDescription>{run.error.message}</AlertDescription>
        </Alert>
      )}
      {history.error && <ErrorState error={history.error} onRetry={() => history.refetch()} />}
      {!run.isPending && latest && (
        <>
          <p className="text-sm text-muted-foreground">Latest run #{latest.id} · {latest.created_at.slice(0, 16).replace("T", " ")}</p>
          <div className="grid gap-4 lg:grid-cols-3">
            {VARIANTS.map((v) => (
              <VariantCard key={v.key} label={v.label} icon={v.icon} rec={latest[v.key]} />
            ))}
          </div>
        </>
      )}
      {history.data && history.data.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Earlier runs for this goal</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {[...history.data].reverse().slice(1).map((r) => (
              <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 border-b py-2 last:border-0">
                <span className="text-muted-foreground">
                  Run #{r.id} · {r.created_at.slice(0, 16).replace("T", " ")}
                </span>
                <span className="flex gap-1.5">
                  {VARIANTS.map((v) => (
                    <Badge key={v.key} variant="secondary">
                      {v.icon} {Math.round(((r[v.key].payload as { goal_probability?: number }).goal_probability ?? 0) * 100)}%
                    </Badge>
                  ))}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {!run.isPending && history.data?.length === 0 && (
        <EmptyState title="No comparisons for this goal yet" description="Run one to see three risk levels side by side." />
      )}
    </div>
  );
}
