import { AlertTriangle, ArrowRight, Loader2, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { type Analysis, type AnalyzeRequest, useAnalysis, useCountries, useHoldings, useProfile } from "@/api/hooks";
import { Disclaimer } from "@/components/Disclaimer";
import { EmptyState, ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn, formatMoney, formatNumber, formatPct } from "@/lib/utils";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];
const OTHER_COLOR = "oklch(0.8 0.01 255)";
type Grouping = "holding" | "asset" | "sector" | "country" | "currency";

function donutData(analysis: Analysis, grouping: Grouping) {
  const fromMap = (map: Record<string, number>) => Object.entries(map).map(([name, value]) => ({ name, value }));
  let rows =
    grouping === "holding"
      ? analysis.holdings.filter((h) => h.weight > 0).map((h) => ({ name: h.ticker, value: h.weight }))
      : grouping === "asset"
        ? fromMap(analysis.allocation_by_asset_class)
        : grouping === "sector"
          ? fromMap(analysis.allocation_by_sector)
          : grouping === "country"
            ? fromMap(analysis.allocation_by_country)
            : fromMap(analysis.currency_exposure);
  rows = rows.sort((a, b) => b.value - a.value);
  if (rows.length > 7) {
    const other = rows.slice(6).reduce((sum, r) => sum + r.value, 0);
    rows = [...rows.slice(0, 6), { name: "Other", value: other }];
  }
  return rows;
}

function MetricCard({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "good" | "bad" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("mt-1 text-2xl font-semibold", tone === "good" && "text-success", tone === "bad" && "text-destructive")}>
          {value}
        </p>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

const tone = (v: number | null | undefined) => (v === null || v === undefined ? undefined : v >= 0 ? "good" : "bad");

export default function DashboardPage() {
  const profile = useProfile();
  const holdings = useHoldings();
  const countries = useCountries();
  const [countryChoice, setCountryChoice] = useState<string | null>(null);
  const [currencyChoice, setCurrencyChoice] = useState<string | null>(null);
  const [lookback, setLookback] = useState<AnalyzeRequest["lookback"]>("1y");
  const [grouping, setGrouping] = useState<Grouping>("holding");

  const country = countryChoice ?? profile.data?.country ?? "auto";
  const currency = currencyChoice ?? profile.data?.base_currency ?? "auto";

  const request = useMemo<AnalyzeRequest | null>(() => {
    if (!holdings.data?.length) return null;
    return {
      holdings: holdings.data.map((h) => ({ ticker: h.ticker, quantity: h.quantity, cost_basis: h.cost_basis ?? null })),
      country: country === "auto" ? null : country,
      base_currency: currency === "auto" ? null : currency,
      lookback,
    };
  }, [holdings.data, country, currency, lookback]);
  const analysis = useAnalysis(request);

  if (profile.isLoading || holdings.isLoading) return <LoadingCards />;
  if (profile.error) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  if (profile.data === null) return <Navigate to="/onboarding" replace />;
  if (holdings.error) return <ErrorState error={holdings.error} onRetry={() => holdings.refetch()} />;

  const controls = (
    <>
      <Select className="w-44" value={country} onChange={(e) => setCountryChoice(e.target.value)} aria-label="Country">
        <option value="auto">Country: auto-detect</option>
        {(countries.data ?? []).map((c) => (
          <option key={c.code} value={c.code}>
            {c.name}
          </option>
        ))}
      </Select>
      <Select className="w-40" value={currency} onChange={(e) => setCurrencyChoice(e.target.value)} aria-label="Base currency">
        <option value="auto">Currency: auto</option>
        {(countries.data ?? []).map((c) => (
          <option key={c.currency} value={c.currency}>
            View in {c.currency}
          </option>
        ))}
      </Select>
      <Select className="w-28" value={lookback} onChange={(e) => setLookback(e.target.value as AnalyzeRequest["lookback"])} aria-label="Period">
        <option value="6mo">6 months</option>
        <option value="1y">1 year</option>
        <option value="2y">2 years</option>
        <option value="5y">5 years</option>
      </Select>
    </>
  );

  if (!holdings.data?.length) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <EmptyState
          title="No holdings yet"
          description="Add your holdings to see allocation, risk metrics and performance against your local benchmark."
          action={
            <Button asChild>
              <Link to="/portfolio">
                Add holdings <ArrowRight />
              </Link>
            </Button>
          }
        />
      </div>
    );
  }

  const data = analysis.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description={data ? `Prices as of ${data.as_of} · ${data.lookback} lookback` : "Analysing your portfolio…"}
        actions={
          <>
            {controls}
            <Button variant="outline" size="icon" onClick={() => analysis.refetch()} aria-label="Refresh">
              {analysis.isFetching ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            </Button>
          </>
        }
      />

      {analysis.isLoading && <LoadingCards label="Fetching market data — the first load for new tickers can take a few seconds" />}
      {analysis.error && <ErrorState error={analysis.error} onRetry={() => analysis.refetch()} />}

      {data && (
        <>
          <Card className="bg-gradient-to-r from-primary/10 to-transparent">
            <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Total value ({data.base_currency})</p>
                <p className="text-3xl font-semibold">{formatMoney(data.total_value_base, data.base_currency)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Country</p>
                <p className="font-medium">
                  {data.country_name}{" "}
                  <Badge variant={data.country.source === "inferred" ? "secondary" : "default"}>
                    {data.country.source === "inferred"
                      ? `inferred · ${data.country.inference?.confidence ?? ""} confidence`
                      : "selected by you"}
                  </Badge>
                </p>
              </div>
              {data.country.inference?.is_mixed && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Markets</p>
                  <p className="font-medium">
                    {Object.entries(data.allocation_by_country)
                      .map(([c, w]) => `${c} ${formatPct(w, 0)}`)
                      .join("  ")}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {data.warnings.length > 0 && (
            <Alert variant="warning">
              <AlertTriangle className="text-amber-600" />
              <div>
                <AlertTitle>Some data needs attention</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc pl-4">
                    {data.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </div>
            </Alert>
          )}

          {data.combined_metrics && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <MetricCard
                label={`${data.lookback} return`}
                value={formatPct(data.combined_metrics.total_return)}
                hint={`${data.combined_metrics.benchmark_name}: ${formatPct(data.combined_metrics.benchmark_total_return)}`}
                tone={tone(data.combined_metrics.total_return)}
              />
              <MetricCard
                label="Volatility (ann.)"
                value={formatPct(data.combined_metrics.annualized_volatility)}
                hint="Std. dev. of daily returns × √252"
              />
              <MetricCard
                label="Sharpe ratio"
                value={formatNumber(data.combined_metrics.sharpe_ratio)}
                hint={`Risk-free: ${formatPct(data.combined_metrics.risk_free_rate.rate, 2)} (${data.combined_metrics.risk_free_rate.source})`}
              />
              <MetricCard
                label="Beta"
                value={formatNumber(data.combined_metrics.beta)}
                hint={`vs ${data.combined_metrics.benchmark_name}`}
              />
              <MetricCard label="Max drawdown" value={formatPct(data.combined_metrics.max_drawdown)} tone="bad" />
              <MetricCard
                label="Concentration"
                value={data.concentration ? formatNumber(data.concentration.hhi, 3) : "—"}
                hint={
                  data.concentration
                    ? `HHI · ≈${data.concentration.effective_holdings.toFixed(1)} effective holdings · top ${data.concentration.largest_position_ticker} ${formatPct(data.concentration.largest_position_weight, 0)}`
                    : undefined
                }
              />
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Allocation</CardTitle>
                <CardDescription>Share of total value in {data.base_currency}</CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs value={grouping} onValueChange={(v) => setGrouping(v as Grouping)}>
                  <TabsList className="flex w-full flex-wrap">
                    <TabsTrigger value="holding">Holdings</TabsTrigger>
                    <TabsTrigger value="asset">Asset class</TabsTrigger>
                    <TabsTrigger value="sector">Sector</TabsTrigger>
                    <TabsTrigger value="country">Country</TabsTrigger>
                    <TabsTrigger value="currency">Currency</TabsTrigger>
                  </TabsList>
                </Tabs>
                <div className="h-72">
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={donutData(data, grouping)} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
                        {donutData(data, grouping).map((entry, i) => (
                          <Cell key={entry.name} fill={entry.name === "Other" ? OTHER_COLOR : COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatPct(Number(value))} />
                      <Legend verticalAlign="bottom" iconType="circle" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Performance vs {data.combined_metrics?.benchmark_name ?? "benchmark"}</CardTitle>
                <CardDescription>Both rebased to 100 · portfolio valued in {data.base_currency}</CardDescription>
              </CardHeader>
              <CardContent>
                {data.performance.length ? (
                  <div className="h-80">
                    <ResponsiveContainer>
                      <LineChart data={data.performance} margin={{ left: -10, right: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
                        <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
                        <Tooltip formatter={(value) => Number(value).toFixed(1)} />
                        <Legend />
                        <Line type="monotone" dataKey="portfolio" name="Your portfolio" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                        <Line
                          type="monotone"
                          dataKey="benchmark"
                          name={data.combined_metrics?.benchmark_name ?? "Benchmark"}
                          stroke="var(--chart-3)"
                          strokeWidth={2}
                          strokeDasharray="4 3"
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Not enough price history to chart.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>By country</CardTitle>
                <CardDescription>Each market in its own currency, against its local benchmark and risk-free rate</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {data.per_country.map((c) => (
                  <div key={c.country} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <p className="font-medium">
                        {c.name}
                      </p>
                      <Badge variant="secondary">{formatPct(c.weight, 0)} of portfolio</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {formatMoney(c.value_local, c.currency)}
                      {c.currency !== data.base_currency && ` ≈ ${formatMoney(c.value_base, data.base_currency)}`} ·{" "}
                      {c.tickers.join(", ")}
                    </p>
                    {c.metrics && (
                      <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                        <div>
                          <p className="text-xs text-muted-foreground">Return</p>
                          <p className={cn(tone(c.metrics.total_return) === "bad" ? "text-destructive" : "text-success")}>
                            {formatPct(c.metrics.total_return)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">{c.metrics.benchmark_name}</p>
                          <p>{formatPct(c.metrics.benchmark_total_return)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Sharpe</p>
                          <p>{formatNumber(c.metrics.sharpe_ratio)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Beta</p>
                          <p>{formatNumber(c.metrics.beta)}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>By sector</CardTitle>
                <CardDescription>Share of total value in {data.base_currency}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-72">
                  <ResponsiveContainer>
                    <BarChart
                      layout="vertical"
                      data={Object.entries(data.allocation_by_sector).map(([name, value]) => ({ name, value }))}
                      margin={{ left: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                      <XAxis type="number" tickFormatter={(v) => formatPct(Number(v), 0)} tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(value) => formatPct(Number(value))} />
                      <Bar dataKey="value" name="Weight" fill="var(--chart-2)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Holdings</CardTitle>
              <CardDescription>
                Price and gain in each holding's own currency; value also shown in {data.base_currency}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Holding</TableHead>
                    <TableHead>Market</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">Value (local)</TableHead>
                    <TableHead className="text-right">Value ({data.base_currency})</TableHead>
                    <TableHead className="text-right">Weight</TableHead>
                    <TableHead className="text-right">Unrealised gain</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.holdings.map((h) => (
                    <TableRow key={h.ticker}>
                      <TableCell>
                        <p className="font-medium">{h.ticker}</p>
                        <p className="text-xs text-muted-foreground">
                          {h.name ?? "—"} · {h.sector}
                        </p>
                      </TableCell>
                      <TableCell>
                        {h.country}{" "}
                        <span className="text-xs text-muted-foreground">({h.currency})</span>
                      </TableCell>
                      <TableCell className="text-right">{h.quantity}</TableCell>
                      <TableCell className="text-right">{formatMoney(h.price, h.currency)}</TableCell>
                      <TableCell className="text-right">{formatMoney(h.value_local, h.currency)}</TableCell>
                      <TableCell className="text-right">{formatMoney(h.value_base, data.base_currency)}</TableCell>
                      <TableCell className="text-right">{formatPct(h.weight)}</TableCell>
                      <TableCell
                        className={cn(
                          "text-right",
                          h.unrealized_gain_local !== null && (h.unrealized_gain_local >= 0 ? "text-success" : "text-destructive"),
                        )}
                      >
                        {h.unrealized_gain_local === null ? "—" : formatMoney(h.unrealized_gain_local, h.currency)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tax notes for {data.country_name}</CardTitle>
              <CardDescription>General information, {data.tax_notes.as_of}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm md:grid-cols-2">
              <ul className="list-disc space-y-1 pl-4">
                {data.tax_notes.summary.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <div>
                <p className="font-medium">Tax-advantaged accounts</p>
                <ul className="mt-1 space-y-1 text-muted-foreground">
                  {data.tax_advantaged_accounts.map((a) => (
                    <li key={a.name}>
                      <span className="text-foreground">{a.name}</span> — {a.summary}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-muted-foreground">{data.tax_notes.notice}</p>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button asChild>
              <Link to="/advice">
                Get a suggestion for this portfolio <ArrowRight />
              </Link>
            </Button>
          </div>
          <Disclaimer countryText={data.regulatory_disclaimer} />
        </>
      )}
    </div>
  );
}
