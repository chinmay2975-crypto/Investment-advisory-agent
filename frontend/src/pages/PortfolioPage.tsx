import { zodResolver } from "@hookform/resolvers/zod";
import { ClipboardPaste, FileUp, Loader2, Plus, Save, Sparkles, Trash2, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import {
  type HoldingDraft,
  type ImportResult,
  useCountries,
  useHoldings,
  useImportPortfolio,
  useInferCountry,
  useProfile,
  useSaveHoldings,
} from "@/api/hooks";
import { ErrorState, LoadingCards, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const rowSchema = z.object({
  id: z.number().optional(),
  ticker: z
    .string()
    .trim()
    .min(1, "Required")
    .max(24, "Too long")
    .regex(/^[A-Za-z0-9.^=&_-]+$/, "Invalid characters")
    .transform((t) => t.toUpperCase()),
  quantity: z.number({ error: "Number required" }).positive("Must be > 0"),
  cost_basis: z.number().nonnegative("Must be ≥ 0").nullable(),
});

const formSchema = z.object({
  rows: z.array(rowSchema).superRefine((rows, ctx) => {
    const seen = new Set<string>();
    rows.forEach((row, index) => {
      const key = row.ticker.toUpperCase();
      if (seen.has(key)) ctx.addIssue({ code: "custom", message: "Duplicate ticker", path: [index, "ticker"] });
      seen.add(key);
    });
  }),
});
type FormValues = z.input<typeof formSchema>;

const ACCEPTED = ".csv,.tsv,.txt,.xlsx,.xls,.xlsm,.ods,.json,.pdf,.docx,.html,.htm,.png,.jpg,.jpeg,.webp,.gif,.bmp,image/*";
const CONFIDENCE_VARIANT = { high: "success", medium: "warning", low: "destructive" } as const;
const FIELD_LABELS: Record<string, string> = {
  ticker: "ticker",
  name: "name",
  quantity: "quantity",
  unit_cost: "cost / unit",
  total_cost: "total cost",
  exchange: "exchange",
};
const FORMAT_LABELS: Record<string, string> = {
  csv: "CSV",
  excel: "a spreadsheet",
  json: "JSON",
  pdf: "PDF",
  word: "a Word document",
  html: "a web page",
  image: "an image",
  text: "text",
};

function ImportSummary({ result, count, onClose }: { result: ImportResult; count: number; onClose: () => void }) {
  const ai = result.method === "ai";
  const mapping = result.column_mapping ?? {};
  const warnings = result.warnings ?? [];
  const skipped = result.skipped ?? [];
  return (
    <Alert variant={ai ? "warning" : "info"} className="mb-4">
      {ai ? <Sparkles className="text-amber-600" /> : <FileUp className="text-primary" />}
      <div className="flex-1 space-y-1">
        <AlertTitle>
          {ai ? "Read by AI — check every row before saving" : `Imported ${count} holding(s) from ${FORMAT_LABELS[result.source_format]}`}
        </AlertTitle>
        <AlertDescription className="space-y-1">
          {Object.keys(mapping).length > 0 && (
            <p>
              Columns used:{" "}
              {Object.entries(mapping)
                .map(([field, header]) => `“${header}” → ${FIELD_LABELS[field] ?? field}`)
                .join(", ")}
            </p>
          )}
          {result.method === "lines" && <p>Read line by line as “ticker quantity [cost]”.</p>}
          {warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          {skipped.length > 0 && (
            <details>
              <summary className="cursor-pointer">{skipped.length} row(s) skipped</summary>
              <ul className="mt-1 list-disc pl-5">
                {skipped.map((s) => (
                  <li key={`${s.row}-${s.reason}`}>
                    Row {s.row}: {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </AlertDescription>
      </div>
      <Button variant="ghost" size="icon" onClick={onClose} aria-label="Dismiss">
        <X />
      </Button>
    </Alert>
  );
}

export default function PortfolioPage() {
  const holdings = useHoldings();
  const profile = useProfile();
  const countries = useCountries();
  const save = useSaveHoldings();
  const importer = useImportPortfolio();
  const fileInput = useRef<HTMLInputElement>(null);

  const [panelOpen, setPanelOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [market, setMarket] = useState<string | null>(null);
  const [replaceRows, setReplaceRows] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [lastImport, setLastImport] = useState<{ result: ImportResult; count: number } | null>(null);

  const defaultMarket = market ?? profile.data?.country ?? "";

  const form = useForm<FormValues>({ resolver: zodResolver(formSchema), defaultValues: { rows: [] } });
  const { fields, append, remove, replace, update } = useFieldArray({ control: form.control, name: "rows" });

  useEffect(() => {
    if (holdings.data && !form.formState.isDirty) {
      form.reset({
        rows: holdings.data.map((h) => ({ id: h.id, ticker: h.ticker, quantity: h.quantity, cost_basis: h.cost_basis ?? null })),
      });
    }
  }, [holdings.data, form]);

  const watchedRows = useWatch({ control: form.control, name: "rows" });
  const tickers = useMemo(
    () => (watchedRows ?? []).map((r) => (r?.ticker ?? "").trim().toUpperCase()).filter(Boolean),
    [watchedRows],
  );
  const inference = useInferCountry(tickers);
  const inferenceByTicker = new Map((inference.data?.holdings ?? []).map((h) => [h.ticker.toUpperCase(), h]));
  // Tickers from the last import that the backend couldn't find market data for.
  const noMarketData = new Set(
    (lastImport?.result.holdings ?? []).filter((h) => h.price_found === false).map((h) => h.ticker),
  );

  const applyImport = (result: ImportResult) => {
    const imported: HoldingDraft[] = result.holdings.map((h) => ({
      ticker: h.ticker,
      quantity: h.quantity,
      cost_basis: h.cost_basis ?? null,
    }));
    if (replaceRows || fields.length === 0) {
      replace(imported);
    } else {
      // Add new tickers; overwrite rows whose ticker already exists (the table forbids duplicates).
      const current = form.getValues("rows");
      for (const row of imported) {
        const existing = current.findIndex((r) => r.ticker.trim().toUpperCase() === row.ticker);
        if (existing >= 0) update(existing, { ...current[existing], quantity: row.quantity, cost_basis: row.cost_basis });
        else append(row);
      }
    }
    form.trigger();
    setLastImport({ result, count: imported.length });
    setPanelOpen(false);
    setPasteText("");
  };

  const runImport = (input: { file?: File; text?: string }) =>
    importer.mutate({ ...input, defaultCountry: defaultMarket || null }, { onSuccess: applyImport });

  const onSave = form.handleSubmit(async (values) => {
    const next = formSchema.parse(values).rows;
    await save.mutateAsync({ current: holdings.data ?? [], next });
    form.reset(values); // refetched holdings (with server ids) replace this once they arrive
  });

  if (holdings.isLoading) return <LoadingCards count={2} />;
  if (holdings.error) return <ErrorState error={holdings.error} onRetry={() => holdings.refetch()} />;

  const rowErrors = form.formState.errors.rows;

  return (
    <div>
      <PageHeader
        title="Portfolio"
        description="Type holdings in, or import a broker export in almost any format. Nothing is saved until you click Save."
        actions={
          <>
            <Button variant={panelOpen ? "secondary" : "outline"} onClick={() => setPanelOpen((open) => !open)}>
              <Upload /> Import
            </Button>
            <Button onClick={onSave} disabled={save.isPending || !form.formState.isDirty}>
              {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save holdings
            </Button>
          </>
        }
      />

      {panelOpen && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Import holdings</CardTitle>
            <CardDescription>
              Broker exports, statements or screenshots — CSV, Excel/ODS, PDF (even scanned), Word, saved web
              pages, JSON, or a photo/screenshot of your holdings. Column names are matched automatically. Or
              paste text like <code>RELIANCE.NS 20 2400</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="market">Market for tickers without a suffix</Label>
                <Select id="market" value={defaultMarket} onChange={(e) => setMarket(e.target.value)}>
                  <option value="">Leave them as-is (US-style)</option>
                  {(countries.data ?? []).map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name} ({c.ticker_suffixes[0] ?? "no suffix"})
                    </option>
                  ))}
                </Select>
              </div>
              {fields.length > 0 && (
                <label className="flex items-center gap-2 self-end pb-2 text-sm">
                  <input type="checkbox" checked={replaceRows} onChange={(e) => setReplaceRows(e.target.checked)} />
                  Replace the {fields.length} row(s) already in the table
                </label>
              )}
            </div>

            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const file = e.dataTransfer.files?.[0];
                if (file) runImport({ file });
              }}
              className={cn(
                "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-center text-sm text-muted-foreground transition-colors",
                dragging && "border-primary bg-primary/5",
              )}
            >
              <FileUp className="size-8" />
              <p>Drop a file here, or</p>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPTED}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) runImport({ file });
                  e.target.value = "";
                }}
              />
              <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()} disabled={importer.isPending}>
                Choose file
              </Button>
              <p className="text-xs">Max 10 MB · spreadsheets, PDF, Word, HTML, JSON, text, PNG/JPG screenshots</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="paste">Or paste holdings</Label>
              <textarea
                id="paste"
                rows={5}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder={"RELIANCE.NS 20 2400\nNSE:TCS, 10\nAAPL 5 180\n…or paste rows copied from your broker's holdings page"}
                className="w-full rounded-md border border-input bg-card px-3 py-2 font-mono text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => runImport({ text: pasteText })}
                disabled={!pasteText.trim() || importer.isPending}
              >
                <ClipboardPaste /> Read pasted text
              </Button>
            </div>

            {importer.isPending && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Reading your holdings… (screenshots, scans and documents without a clear
                table are read by AI and can take up to a minute)
              </p>
            )}
            {importer.error && (
              <Alert variant="destructive">
                <AlertDescription>{importer.error.message}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {lastImport && <ImportSummary {...lastImport} onClose={() => setLastImport(null)} />}
      {save.error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{save.error.message}</AlertDescription>
        </Alert>
      )}
      {save.isSuccess && !form.formState.isDirty && (
        <Alert variant="info" className="mb-4">
          <AlertDescription>
            Holdings saved. <Link to="/dashboard" className="font-medium text-primary underline">View the dashboard →</Link>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
          <CardDescription>
            Use exchange tickers: RELIANCE.NS / TCS.BO (India), VOD.L (UK), AAPL (US). Cost basis is per unit, in the
            holding's own currency.
            {inference.data?.inferred_country &&
              ` Portfolio looks ${inference.data.is_mixed ? "mixed, mostly " : ""}${inference.data.inferred_country} (${inference.data.confidence} confidence).`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {fields.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              No holdings yet. Add a row, or use <span className="font-medium text-foreground">Import</span> to load a
              broker export.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-48">Ticker</TableHead>
                  <TableHead>Market</TableHead>
                  <TableHead className="w-36">Quantity</TableHead>
                  <TableHead className="w-40">Cost basis / unit</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {fields.map((field, index) => {
                  const ticker = (watchedRows?.[index]?.ticker ?? "").trim().toUpperCase();
                  const detected = inferenceByTicker.get(ticker);
                  const errors = rowErrors?.[index];
                  return (
                    <TableRow key={field.id}>
                      <TableCell>
                        <Input placeholder="e.g. INFY.NS" aria-invalid={!!errors?.ticker} {...form.register(`rows.${index}.ticker`)} />
                        {errors?.ticker && <p className="mt-1 text-xs text-destructive">{errors.ticker.message}</p>}
                      </TableCell>
                      <TableCell>
                        {detected ? (
                          <Badge variant={CONFIDENCE_VARIANT[detected.confidence]} title={detected.reason}>
                            {detected.country ?? "Unknown"} · {detected.confidence}
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                        {noMarketData.has(ticker) && (
                          <Badge variant="destructive" className="ml-1" title="No price data found — check the spelling or suffix">
                            no market data
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          step="any"
                          aria-invalid={!!errors?.quantity}
                          {...form.register(`rows.${index}.quantity`, { valueAsNumber: true })}
                        />
                        {errors?.quantity && <p className="mt-1 text-xs text-destructive">{errors.quantity.message}</p>}
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          step="any"
                          placeholder="optional"
                          {...form.register(`rows.${index}.cost_basis`, {
                            setValueAs: (v) => (v === "" || v === null || Number.isNaN(Number(v)) ? null : Number(v)),
                          })}
                        />
                        {errors?.cost_basis && <p className="mt-1 text-xs text-destructive">{errors.cost_basis.message}</p>}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" onClick={() => remove(index)} aria-label={`Remove ${ticker || "row"}`}>
                          <Trash2 />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
          <Button variant="outline" size="sm" className="mt-4" onClick={() => append({ ticker: "", quantity: 1, cost_basis: null })}>
            <Plus /> Add holding
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
