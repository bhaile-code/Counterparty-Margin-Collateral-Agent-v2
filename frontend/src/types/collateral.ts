/**
 * Collateral-related types
 */

export const StandardizedCollateralType = {
  CASH_USD: "CASH_USD",
  CASH_EUR: "CASH_EUR",
  CASH_GBP: "CASH_GBP",
  CASH_JPY: "CASH_JPY",
  US_TREASURY: "US_TREASURY",
  US_AGENCY: "US_AGENCY",
  US_AGENCY_MBS: "US_AGENCY_MBS",
  COMMERCIAL_PAPER: "COMMERCIAL_PAPER",
  CORPORATE_BONDS: "CORPORATE_BONDS",
  MORTGAGE_BACKED_SECURITIES: "MORTGAGE_BACKED_SECURITIES",
  ASSET_BACKED_SECURITIES: "ASSET_BACKED_SECURITIES",
  MUNICIPAL_BONDS: "MUNICIPAL_BONDS",
  FOREIGN_SOVEREIGN: "FOREIGN_SOVEREIGN",
  EQUITIES_LISTED: "EQUITIES_LISTED",
  EQUITIES_NON_LISTED: "EQUITIES_NON_LISTED",
  MONEY_MARKET_FUNDS: "MONEY_MARKET_FUNDS",
  COMMODITIES: "COMMODITIES",
  UNKNOWN: "UNKNOWN",
  OTHER: "OTHER",
} as const;

export type StandardizedCollateralType = typeof StandardizedCollateralType[keyof typeof StandardizedCollateralType];

export interface MaturityBucket {
  min_years?: number;
  max_years?: number;
  valuation_percentage: number;
  haircut: number;
  original_text?: string;
}

export interface NormalizedCollateral {
  standardized_type: StandardizedCollateralType;
  base_description: string;
  maturity_buckets: MaturityBucket[];
  rating_event?: string;
  flat_valuation_percentage?: number;
  flat_haircut?: number;
  confidence?: number;
  notes?: string;
}

export interface CollateralItem {
  collateral_type: string;
  market_value: number;
  haircut_rate: number;
  currency: string;
  maturity_date?: string;
  maturity_years?: number;
}

export interface ParsedCollateralItem {
  csv_row_number: number;
  description: string;
  market_value: number;
  maturity_min?: number | null;
  maturity_max?: number | null;
  currency: string;
  valuation_scenario?: string | null;
  parse_errors: string[];
}

export interface MatchedCollateralItem {
  csv_row_number: number;
  csv_description: string;
  market_value: number;
  maturity_min?: number | null;
  maturity_max?: number | null;
  currency: string;
  valuation_scenario: string;

  // AI Matching results
  matched_csa_description?: string | null;
  matched_standardized_type?: string | null;
  matched_maturity_bucket_min?: number | null;
  matched_maturity_bucket_max?: number | null;
  match_confidence: number;
  match_reasoning: string;

  // Haircut lookup
  haircut_rate?: number | null;
  haircut_source: string;
  warnings: string[];
}

export interface ImportCollateralResponse {
  document_id: string;
  parsed_items: ParsedCollateralItem[];
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  errors: string[];
}

export interface MatchCollateralResponse {
  document_id: string;
  matched_items: MatchedCollateralItem[];
  summary: {
    total_items: number;
    high_confidence: number;
    medium_confidence: number;
    low_confidence: number;
    warnings_count: number;
    total_market_value: number;
    total_effective_value: number;
  };
}

export interface HaircutLookupResponse {
  haircut: number | null;
  bucket_min: number | null;
  bucket_max: number | null;
  warnings: string[];
}
