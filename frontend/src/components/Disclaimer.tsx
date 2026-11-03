import { Info } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";

export const GENERAL_NOTICE =
  "InvestAd provides general information for educational purposes, not licensed financial, tax or investment advice. " +
  "Figures use public market data that may be delayed or incomplete, and AI-generated suggestions can be wrong. " +
  "Consider speaking to a qualified adviser before acting.";

/** Country-specific regulatory disclaimer; the general notice is already in the page footer. */
export function Disclaimer({ countryText }: { countryText?: string | null }) {
  if (!countryText) return null;
  return (
    <Alert variant="info">
      <Info className="text-primary" />
      <AlertDescription>{countryText}</AlertDescription>
    </Alert>
  );
}
