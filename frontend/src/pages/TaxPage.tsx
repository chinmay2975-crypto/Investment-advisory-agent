import { Loader2 } from "lucide-react";
import { useState } from "react";

import { useCountries, useProfile, useUsTaxAnalysis } from "@/api/hooks";
import { CountrySelector } from "@/components/CountrySelector";
import { Disclaimer } from "@/components/Disclaimer";
import { ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatMoney, formatPct } from "@/lib/utils";

export default function TaxPage() {
  const countries = useCountries();
  const profile = useProfile();
  const [choice, setChoice] = useState<string | null>(null);
  const [rate, setRate] = useState(0.24);
  const [income, setIncome] = useState(100000);
  const [filing, setFiling] = useState("single");
  const usTax = useUsTaxAnalysis();

  if (countries.isLoading || profile.isLoading) return <LoadingCards count={3} />;
  if (countries.error) return <ErrorState error={countries.error} onRetry={() => countries.refetch()} />;

  const code = choice ?? profile.data?.country ?? "US";
  const country = countries.data?.find((c) => c.code === code);

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title="Tax notes" description="Summary-level capital gains rules per country. General information only." />
      <CountrySelector countries={countries.data ?? []} value={code} onChange={setChoice} />

      {country && (
        <Card>
          <CardHeader>
            <CardTitle>Capital gains in {country.name}</CardTitle>
            <CardDescription>
              {country.capital_gains_tax.as_of}
              {country.capital_gains_tax.short_term_holding_months
                ? ` · short-term means held ${country.capital_gains_tax.short_term_holding_months} months or less`
                : " · no short/long-term distinction"}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 text-sm md:grid-cols-2">
            <ul className="list-disc space-y-1.5 pl-5">
              {country.capital_gains_tax.summary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div>
              <p className="font-medium">Tax-advantaged accounts</p>
              <ul className="mt-1 space-y-1 text-muted-foreground">
                {country.tax_advantaged_accounts.map((a) => (
                  <li key={a.name}>
                    <span className="text-foreground">{a.name}</span> — {a.summary}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">{country.capital_gains_tax.notice}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {code === "US" && (
        <Card>
          <CardHeader>
            <CardTitle>Rough US federal estimate for your saved holdings</CardTitle>
            <CardDescription>
              Uses holding period and cost basis of saved holdings; ignores state tax, NIIT and wash sales.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-4 sm:items-end">
              <div className="space-y-1.5">
                <Label htmlFor="rate">Ordinary income rate</Label>
                <Input id="rate" type="number" step="0.01" min={0} max={0.6} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="income">Taxable income (USD)</Label>
                <Input id="income" type="number" min={0} value={income} onChange={(e) => setIncome(Number(e.target.value))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="filing">Filing status</Label>
                <Select id="filing" value={filing} onChange={(e) => setFiling(e.target.value)}>
                  <option value="single">Single</option>
                  <option value="married_filing_jointly">Married filing jointly</option>
                </Select>
              </div>
              <Button
                onClick={() => usTax.mutate({ ordinary_income_tax_rate: rate, taxable_income: income, filing_status: filing })}
                disabled={usTax.isPending}
              >
                {usTax.isPending && <Loader2 className="animate-spin" />} Estimate
              </Button>
            </div>
            {usTax.error && (
              <Alert variant="destructive">
                <AlertDescription>{usTax.error.message}</AlertDescription>
              </Alert>
            )}
            {usTax.data && (
              <>
                <p className="text-sm">
                  Unrealised gain {formatMoney(usTax.data.total_unrealized_gain, "USD")} · estimated tax if sold{" "}
                  <span className="font-semibold">{formatMoney(usTax.data.total_estimated_tax, "USD")}</span>
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Holding period</TableHead>
                      <TableHead className="text-right">Gain</TableHead>
                      <TableHead className="text-right">Rate</TableHead>
                      <TableHead className="text-right">Est. tax</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usTax.data.holdings.map((h) => (
                      <TableRow key={h.ticker}>
                        <TableCell>{h.ticker}</TableCell>
                        <TableCell>{h.holding_period.replace("_", "-")}</TableCell>
                        <TableCell className="text-right">{formatMoney(h.unrealized_gain, "USD")}</TableCell>
                        <TableCell className="text-right">{formatPct(h.estimated_tax_rate, 0)}</TableCell>
                        <TableCell className="text-right">{formatMoney(h.estimated_tax, "USD")}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </CardContent>
        </Card>
      )}
      <Disclaimer countryText={country?.regulatory_disclaimer} />
    </div>
  );
}
