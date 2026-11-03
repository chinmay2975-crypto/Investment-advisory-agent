import { CheckCircle2, Circle, Loader2, Sparkles, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useCountries, useGoals, useHoldings, useProfile } from "@/api/hooks";
import { type AdviceContext, type AdviceSection, type AdviceStage, streamAdvice } from "@/api/sse";
import { PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

const STAGES = [
  { stage: "analyze_portfolio", label: "Analysing your portfolio" },
  { stage: "load_country_context", label: "Loading country conventions" },
  { stage: "retrieve_market_context", label: "Retrieving market context" },
  { stage: "generate_advice", label: "Generating suggestion" },
];

type RunState = {
  stages: Record<string, AdviceStage["status"]>;
  context: AdviceContext | null;
  sections: AdviceSection[];
  done: { recommendation_id: number; llm_provider: string } | null;
  error: string | null;
};
const EMPTY: RunState = { stages: {}, context: null, sections: [], done: null, error: null };

function SectionBody({ section }: { section: AdviceSection }) {
  const { key, content } = section;
  if (key === "target_allocation" && content && typeof content === "object") {
    const data = Object.entries(content as Record<string, number>).map(([name, value]) => ({ name, value }));
    return (
      <div className="h-48">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 10 }}>
            <XAxis type="number" unit="%" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Bar dataKey="value" fill="var(--chart-1)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  if (key === "suggested_instruments" && Array.isArray(content)) {
    return (
      <div className="flex flex-wrap gap-2">
        {content.map((item) => (
          <Badge key={String(item)} variant="secondary">
            {String(item)}
          </Badge>
        ))}
      </div>
    );
  }
  if (key === "goal_probability" && typeof content === "number") {
    return (
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-primary" style={{ width: `${Math.round(content * 100)}%` }} />
        </div>
        <span className="font-medium">{Math.round(content * 100)}%</span>
        <span className="text-xs text-muted-foreground">model estimate, not a promise</span>
      </div>
    );
  }
  if (key === "risks" && Array.isArray(content)) {
    return (
      <ul className="list-disc space-y-1 pl-5">
        {content.map((risk) => (
          <li key={String(risk)}>{String(risk)}</li>
        ))}
      </ul>
    );
  }
  return <p className="whitespace-pre-line leading-relaxed">{String(content)}</p>;
}

export default function AdvicePage() {
  const profile = useProfile();
  const goals = useGoals();
  const holdings = useHoldings();
  const countries = useCountries();

  const [goalId, setGoalId] = useState<string>("none");
  const [country, setCountry] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunState>(EMPTY);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const effectiveCountry = country ?? profile.data?.country ?? "auto";
  const hasHoldings = (holdings.data?.length ?? 0) > 0;
  const needsCountry = !hasHoldings && effectiveCountry === "auto";

  const start = async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setRun(EMPTY);
    setRunning(true);
    try {
      await streamAdvice(
        {
          goal_id: goalId === "none" ? null : Number(goalId),
          holdings: null,
          country: effectiveCountry === "auto" ? null : effectiveCountry,
          base_currency: profile.data?.base_currency ?? null,
          lookback: "1y",
        },
        (event) =>
          setRun((prev) => {
            switch (event.event) {
              case "stage":
                return { ...prev, stages: { ...prev.stages, [event.data.stage]: event.data.status } };
              case "context":
                return { ...prev, context: event.data };
              case "section":
                return { ...prev, sections: [...prev.sections, event.data] };
              case "done":
                return { ...prev, done: event.data };
              case "error":
                return { ...prev, error: event.data.message };
            }
          }),
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setRun((prev) => ({ ...prev, error: err instanceof Error ? err.message : "The stream failed" }));
      }
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const started = running || run.sections.length > 0 || run.error;
  const mainSections = run.sections.filter((s) => s.key !== "disclaimer");
  const disclaimer = run.sections.find((s) => s.key === "disclaimer");

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader
        title="Advice"
        description="An AI-generated, country-aware suggestion based on your profile, holdings and recent market data."
      />

      <Alert variant="info">
        <Sparkles className="text-primary" />
        <AlertDescription>
          This is general information produced by a language model, not licensed financial advice. It can be wrong or
          out of date — treat it as a starting point for your own research.
        </AlertDescription>
      </Alert>

      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="goal">Plan against a goal (optional)</Label>
            <Select id="goal" value={goalId} onChange={(e) => setGoalId(e.target.value)} disabled={running}>
              <option value="none">No specific goal</option>
              {(goals.data ?? []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.category} — target {g.target_amount.toLocaleString()} by {g.target_date.slice(0, 10)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="advice-country">Country</Label>
            <Select id="advice-country" value={effectiveCountry} onChange={(e) => setCountry(e.target.value)} disabled={running}>
              <option value="auto">Auto-detect from holdings</option>
              {(countries.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          {running ? (
            <Button variant="outline" onClick={stop}>
              <Square /> Stop
            </Button>
          ) : (
            <Button onClick={start} disabled={needsCountry || !profile.data}>
              <Sparkles /> Get suggestion
            </Button>
          )}
        </CardContent>
        {(!profile.data || needsCountry) && !profile.isLoading && (
          <CardContent className="pt-0 text-sm text-muted-foreground">
            {!profile.data ? (
              <>
                <Link to="/onboarding" className="text-primary underline">Set up your profile</Link> first.
              </>
            ) : (
              <>
                You have no saved holdings — choose a country, or{" "}
                <Link to="/portfolio" className="text-primary underline">add holdings</Link>.
              </>
            )}
          </CardContent>
        )}
        {!hasHoldings && !needsCountry && profile.data && (
          <CardContent className="pt-0 text-sm text-muted-foreground">
            No saved holdings — you'll get general guidance for the selected country.
          </CardContent>
        )}
      </Card>

      {started && (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Progress</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-3">
                  {STAGES.map(({ stage, label }) => {
                    const status = run.stages[stage];
                    return (
                      <li key={stage} className="flex items-center gap-2 text-sm">
                        {status === "completed" ? (
                          <CheckCircle2 className="size-4 text-success" />
                        ) : status === "started" && running ? (
                          <Loader2 className="size-4 animate-spin text-primary" />
                        ) : (
                          <Circle className="size-4 text-muted-foreground" />
                        )}
                        <span className={status ? "" : "text-muted-foreground"}>{label}</span>
                      </li>
                    );
                  })}
                </ol>
              </CardContent>
            </Card>
            {run.context && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Using</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm">
                  <p>
                    {run.context.country_name}{" "}
                    <Badge variant="secondary">{run.context.source === "inferred" ? "inferred" : "your choice"}</Badge>
                  </p>
                  <p className="text-muted-foreground">Currency: {run.context.currency}</p>
                  <p className="text-muted-foreground">Benchmark: {run.context.benchmark_name}</p>
                  {run.context.warnings.map((w) => (
                    <p key={w} className="text-xs text-amber-700">
                      {w}
                    </p>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            {run.error && (
              <Alert variant="destructive">
                <div>
                  <AlertTitle>Couldn't finish the suggestion</AlertTitle>
                  <AlertDescription>{run.error}</AlertDescription>
                </div>
              </Alert>
            )}
            {mainSections.length === 0 && running && (
              <Card>
                <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" /> Working on it — the model call usually takes 10–30 seconds.
                </CardContent>
              </Card>
            )}
            {mainSections.map((section) => (
              <Card key={section.key}>
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs font-medium uppercase tracking-wide">{section.title}</CardDescription>
                </CardHeader>
                <CardContent className={section.key === "what" ? "text-lg font-medium" : "text-sm"}>
                  <SectionBody section={section} />
                </CardContent>
              </Card>
            ))}
            {disclaimer && (
              <Alert variant="info" className="text-muted-foreground">
                <AlertDescription>
                  <p className="text-foreground">{String(disclaimer.content)}</p>
                </AlertDescription>
              </Alert>
            )}
            {run.done && (
              <Card>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
                  <span>
                    Saved as suggestion #{run.done.recommendation_id} (generated by {run.done.llm_provider}).
                  </span>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/recommendations?id=${run.done.recommendation_id}`}>Refine, approve or export →</Link>
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
