import { Loader2, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

import { useMarketQuery, useMarketRefresh } from "@/api/hooks";
import { EmptyState, PageHeader } from "@/components/StateViews";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function MarketPage() {
  const refresh = useMarketRefresh();
  const search = useMarketQuery();
  const [query, setQuery] = useState("inflation outlook");

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader
        title="Market data"
        description="The grounding documents (indices, rates, inflation, news) that suggestions are allowed to cite."
        actions={
          <Button variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            {refresh.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Refresh data
          </Button>
        }
      />
      {refresh.isPending && <p className="text-sm text-muted-foreground">Fetching from yfinance, FRED and NewsAPI — about 30 seconds…</p>}
      {refresh.error && (
        <Alert variant="destructive">
          <AlertDescription>{refresh.error.message}</AlertDescription>
        </Alert>
      )}
      {refresh.data && (
        <Card>
          <CardContent className="flex flex-wrap gap-2 p-4 text-sm">
            <span className="font-medium">Ingested {refresh.data.documents_ingested} documents:</span>
            {Object.entries(refresh.data.by_category).map(([category, count]) => (
              <Badge key={category} variant="secondary">
                {category.replace("_", " ")} {count}
              </Badge>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Search the context store</CardTitle>
          <CardDescription>Semantic search over the ingested documents.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) search.mutate({ q: query.trim(), n: 8 });
            }}
          >
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Nifty 50 performance" />
            <Button disabled={search.isPending}>{search.isPending ? <Loader2 className="animate-spin" /> : <Search />}</Button>
          </form>
          {search.error && (
            <Alert variant="destructive">
              <AlertDescription>{search.error.message}</AlertDescription>
            </Alert>
          )}
          {search.data?.length === 0 && <EmptyState title="No documents found" description="Try refreshing the data first." />}
          <div className="space-y-3">
            {search.data?.map((doc, i) => (
              <div key={i} className="rounded-lg border p-3 text-sm">
                <div className="mb-1 flex flex-wrap gap-1.5">
                  <Badge variant="secondary">{String(doc.metadata.category ?? "unknown")}</Badge>
                  <Badge variant="outline">{String(doc.metadata.source ?? "")}</Badge>
                  {doc.metadata.country ? <Badge>{String(doc.metadata.country)}</Badge> : null}
                  <span className="text-xs text-muted-foreground">as of {String(doc.metadata.as_of ?? "").slice(0, 10)}</span>
                </div>
                <p>{doc.text}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
