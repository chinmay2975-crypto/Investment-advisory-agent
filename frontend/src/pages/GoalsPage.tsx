import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCreateGoal, useGoalAnalysis, useGoals } from "@/api/hooks";
import { EmptyState, ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cn, formatPct } from "@/lib/utils";

const schema = z
  .object({
    category: z.string().trim().min(1, "Required").max(50),
    target_amount: z.number({ error: "Enter an amount" }).positive(),
    current_amount: z.number({ error: "Enter an amount" }).nonnegative(),
    target_date: z.string().min(1, "Pick a date"),
    contribution_cadence: z.enum(["monthly", "quarterly", "annually"]),
    contribution_amount: z.number({ error: "Enter an amount" }).nonnegative(),
  })
  .refine((v) => new Date(v.target_date) > new Date(), { message: "Must be in the future", path: ["target_date"] });
type Values = z.infer<typeof schema>;

export default function GoalsPage() {
  const goals = useGoals();
  const createGoal = useCreateGoal();
  const [selected, setSelected] = useState<number | null>(null);
  const [assumedReturn, setAssumedReturn] = useState(0.06);
  const analysis = useGoalAnalysis(selected, assumedReturn);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      category: "Retirement",
      target_amount: 1000000,
      current_amount: 100000,
      target_date: "",
      contribution_cadence: "monthly",
      contribution_amount: 10000,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const goal = await createGoal.mutateAsync({ ...values, target_date: `${values.target_date}T00:00:00` });
    setSelected(goal.id);
    form.reset();
  });

  const errors = form.formState.errors;

  return (
    <div className="space-y-6">
      <PageHeader title="Goals" description="Amounts are in your own currency; the maths is currency-neutral." />
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>New goal</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-3" noValidate>
              {(
                [
                  ["category", "Goal", "text"],
                  ["target_amount", "Target amount", "number"],
                  ["current_amount", "Saved so far", "number"],
                  ["contribution_amount", "Regular contribution", "number"],
                  ["target_date", "Target date", "date"],
                ] as const
              ).map(([name, label, type]) => (
                <div key={name} className="space-y-1.5">
                  <Label htmlFor={name}>{label}</Label>
                  <Input
                    id={name}
                    type={type}
                    step="any"
                    aria-invalid={!!errors[name]}
                    {...form.register(name, type === "number" ? { valueAsNumber: true } : {})}
                  />
                  {errors[name] && <p className="text-xs text-destructive">{errors[name]?.message}</p>}
                </div>
              ))}
              <div className="space-y-1.5">
                <Label htmlFor="cadence">Contribution frequency</Label>
                <Select id="cadence" {...form.register("contribution_cadence")}>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="annually">Annually</option>
                </Select>
              </div>
              {createGoal.error && (
                <Alert variant="destructive">
                  <AlertDescription>{createGoal.error.message}</AlertDescription>
                </Alert>
              )}
              <Button className="w-full" disabled={createGoal.isPending}>
                {createGoal.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Add goal
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {goals.isLoading && <LoadingCards count={2} />}
          {goals.error && <ErrorState error={goals.error} onRetry={() => goals.refetch()} />}
          {goals.data?.length === 0 && <EmptyState title="No goals yet" description="Add one to plan suggestions against it." />}
          {goals.data?.map((goal) => {
            const progress = goal.target_amount ? Math.min(goal.current_amount / goal.target_amount, 1) : 0;
            return (
              <button
                key={goal.id}
                type="button"
                onClick={() => setSelected(goal.id)}
                className={cn(
                  "block w-full rounded-xl border bg-card p-4 text-left shadow-sm transition-colors hover:border-primary/50",
                  selected === goal.id && "border-primary ring-2 ring-primary/20",
                )}
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium">{goal.category}</p>
                  <Badge variant="secondary">by {goal.target_date.slice(0, 10)}</Badge>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${progress * 100}%` }} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {goal.current_amount.toLocaleString()} of {goal.target_amount.toLocaleString()} ({formatPct(progress, 0)})
                </p>
              </button>
            );
          })}

          {selected !== null && (
            <Card>
              <CardHeader>
                <CardTitle>Is it on track?</CardTitle>
                <CardDescription>Deterministic projection — no market forecast involved.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="assumed">Assumed annual return: {formatPct(assumedReturn, 0)}</Label>
                  <input
                    id="assumed"
                    type="range"
                    min={0}
                    max={0.2}
                    step={0.01}
                    value={assumedReturn}
                    onChange={(e) => setAssumedReturn(Number(e.target.value))}
                    className="w-full accent-[var(--primary)]"
                  />
                </div>
                {analysis.isLoading && <LoadingCards count={3} />}
                {analysis.error && <ErrorState error={analysis.error} />}
                {analysis.data && (
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Required annual return</p>
                      <p className="text-xl font-semibold">{formatPct(analysis.data.required_annual_return, 2)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Projected value</p>
                      <p className="text-xl font-semibold">{Math.round(analysis.data.projected_value).toLocaleString()}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">On track?</p>
                      <p className={cn("text-xl font-semibold", analysis.data.is_sufficient ? "text-success" : "text-destructive")}>
                        {analysis.data.is_sufficient ? "Yes" : "Not yet"}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
