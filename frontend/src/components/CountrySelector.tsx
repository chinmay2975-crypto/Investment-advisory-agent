import { Check } from "lucide-react";

import type { Country } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Props = {
  countries: Country[];
  value: string | null;
  onChange: (code: string) => void;
  inferred?: { country: string | null; confidence: string } | null;
};

export function CountrySelector({ countries, value, onChange, inferred }: Props) {
  return (
    <div role="radiogroup" className="grid gap-3 sm:grid-cols-3">
      {countries.map((country) => {
        const selected = value === country.code;
        const isInferred = inferred?.country === country.code;
        return (
          <button
            key={country.code}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(country.code)}
            className={cn(
              "relative rounded-xl border bg-card p-4 text-left shadow-sm transition-all hover:border-primary/50",
              selected && "border-primary ring-2 ring-primary/30",
            )}
          >
            {selected && <Check className="absolute right-3 top-3 size-4 text-primary" />}
            {/* Text code rather than a flag emoji: Windows renders flag emoji as plain letters. */}
            <div className="inline-flex size-9 items-center justify-center rounded-lg bg-primary/10 text-sm font-semibold text-primary">
              {country.code}
            </div>
            <div className="mt-2 font-medium">{country.name}</div>
            <div className="text-xs text-muted-foreground">
              {country.currency} · {country.benchmark_name}
            </div>
            {isInferred && (
              <Badge variant="success" className="mt-2">
                Inferred from portfolio · {inferred?.confidence}
              </Badge>
            )}
          </button>
        );
      })}
    </div>
  );
}
