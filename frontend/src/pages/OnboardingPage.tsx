import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  useAllocationTemplate,
  useCountries,
  useHoldings,
  useInferCountry,
  useProfile,
  useSaveProfile,
} from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { CountrySelector } from "@/components/CountrySelector";
import { Disclaimer } from "@/components/Disclaimer";
import { ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

const schema = z.object({
  country: z.string().min(1, "Choose a country"),
  base_currency: z.string().min(1),
  risk_cadence: z.enum(["Conservative", "Balanced", "Aggressive"]),
  horizon_years: z.number({ error: "Enter a number of years" }).int().min(1).max(60),
});
type Values = z.infer<typeof schema>;

export default function OnboardingPage() {
  const navigate = useNavigate();
  const countries = useCountries();
  const profile = useProfile();
  const holdings = useHoldings();
  const saveProfile = useSaveProfile();

  const tickers = useMemo(() => (holdings.data ?? []).map((h) => h.ticker), [holdings.data]);
  const inference = useInferCountry(tickers);
  const template = useAllocationTemplate(!!profile.data);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { country: "", base_currency: "", risk_cadence: "Balanced", horizon_years: 10 },
  });
  const country = useWatch({ control: form.control, name: "country" });
  const selectedCountry = countries.data?.find((c) => c.code === country);

  // Pre-fill once data arrives: saved profile wins, otherwise pre-select the inferred country.
  useEffect(() => {
    if (form.formState.isDirty || profile.isLoading || countries.isLoading) return;
    const p = profile.data;
    const inferred = inference.data?.inferred_country ?? "";
    const code = p?.country ?? inferred;
    const currency = p?.base_currency ?? countries.data?.find((c) => c.code === code)?.currency ?? "";
    form.reset({
      country: code,
      base_currency: currency,
      risk_cadence: (p?.risk_cadence as Values["risk_cadence"]) ?? "Balanced",
      horizon_years: p?.horizon_years ?? 10,
    });
  }, [profile.data, profile.isLoading, inference.data, countries.data, countries.isLoading, form]);

  if (countries.isLoading || profile.isLoading) return <LoadingCards count={3} />;
  if (countries.error) return <ErrorState error={countries.error} onRetry={() => countries.refetch()} />;

  const onSubmit = form.handleSubmit(async (values) => {
    await saveProfile.mutateAsync({ ...values, preferences: {}, restrictions: {} });
    navigate(tickers.length ? "/dashboard" : "/portfolio");
  });

  return (
    <div className="max-w-4xl">
      <PageHeader
        title={profile.data ? "Profile & country" : "Set up your profile"}
        description="Your country decides the currency, benchmark, risk-free rate and tax notes used across the app."
      />
      <form onSubmit={onSubmit} className="space-y-6" noValidate>
        <Card>
          <CardHeader>
            <CardTitle>Country</CardTitle>
            <CardDescription>
              {inference.data?.inferred_country
                ? `We detected ${inference.data.inferred_country} from your saved holdings (${inference.data.confidence} confidence). You can override it.`
                : "Add holdings later and we'll suggest a country from your tickers; for now, pick one."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Controller
              control={form.control}
              name="country"
              render={({ field }) => (
                <CountrySelector
                  countries={countries.data ?? []}
                  value={field.value}
                  inferred={
                    inference.data
                      ? { country: inference.data.inferred_country, confidence: inference.data.confidence }
                      : null
                  }
                  onChange={(code) => {
                    field.onChange(code);
                    const currency = countries.data?.find((c) => c.code === code)?.currency;
                    if (currency) form.setValue("base_currency", currency, { shouldDirty: true });
                  }}
                />
              )}
            />
            {form.formState.errors.country && (
              <p className="text-xs text-destructive">{form.formState.errors.country.message}</p>
            )}
            {inference.data?.is_mixed && (
              <Alert variant="info">
                <AlertDescription>
                  Your portfolio spans several markets (
                  {inference.data.breakdown.map((b) => `${b.country} ${(b.weight * 100).toFixed(0)}%`).join(", ")}). The
                  dashboard shows each market separately plus a combined view in your base currency.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Financial profile</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="risk">Risk comfort</Label>
              <Select id="risk" {...form.register("risk_cadence")}>
                <option value="Conservative">Conservative</option>
                <option value="Balanced">Balanced</option>
                <option value="Aggressive">Aggressive</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="horizon">Investment horizon (years)</Label>
              <Input id="horizon" type="number" min={1} max={60} {...form.register("horizon_years", { valueAsNumber: true })} />
              {form.formState.errors.horizon_years && (
                <p className="text-xs text-destructive">{form.formState.errors.horizon_years.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="currency">Base currency for combined views</Label>
              <Select id="currency" {...form.register("base_currency")}>
                {(countries.data ?? []).map((c) => (
                  <option key={c.currency} value={c.currency}>
                    {c.currency} ({c.currency_symbol})
                  </option>
                ))}
              </Select>
            </div>
            {template.data && (
              <div className="sm:col-span-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                Default starting allocation for your saved risk comfort:
                {Object.entries(template.data).map(([asset, pct]) => (
                  <Badge key={asset} variant="secondary">
                    {asset} {pct}%
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {selectedCountry && (
          <Card>
            <CardHeader>
              <CardTitle>What changes for {selectedCountry.name}</CardTitle>
              <CardDescription>General information as of {selectedCountry.capital_gains_tax.as_of}.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <p className="font-medium">Market conventions</p>
                <ul className="mt-1 space-y-1 text-muted-foreground">
                  <li>Currency: {selectedCountry.currency}</li>
                  <li>Benchmark: {selectedCountry.benchmark_name} ({selectedCountry.benchmark_ticker})</li>
                  <li>Risk-free proxy: {selectedCountry.risk_free_rate_label}</li>
                  <li>
                    Ticker format:{" "}
                    {selectedCountry.ticker_suffixes.length ? selectedCountry.ticker_suffixes.join(" / ") : "no suffix (e.g. AAPL)"}
                  </li>
                </ul>
              </div>
              <div>
                <p className="font-medium">Tax-advantaged accounts</p>
                <ul className="mt-1 space-y-1 text-muted-foreground">
                  {selectedCountry.tax_advantaged_accounts.map((a) => (
                    <li key={a.name}>
                      <span className="text-foreground">{a.name}</span> — {a.summary}
                    </li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        )}

        <Disclaimer countryText={selectedCountry?.regulatory_disclaimer} />

        {saveProfile.error && (
          <Alert variant="destructive">
            <AlertDescription>{saveProfile.error.message}</AlertDescription>
          </Alert>
        )}
        <div className="flex items-center gap-3">
          <Button type="submit" size="lg" disabled={saveProfile.isPending}>
            {saveProfile.isPending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />} Save profile
          </Button>
          {saveProfile.isSuccess && <span className="text-sm text-success">Saved</span>}
        </div>
      </form>
    </div>
  );
}
