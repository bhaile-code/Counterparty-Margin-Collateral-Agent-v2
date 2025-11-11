/**
 * Calculation-related types
 */

import type { CollateralItem } from './documents';

export interface CalculationRequest {
  document_id: string;
  net_exposure: number;
  posted_collateral: CollateralItem[];
  party_perspective?: "party_a" | "party_b";
}

export interface CalculationStep {
  step_number: number;
  description: string;
  formula?: string;
  inputs: Record<string, any>;
  result: number;
  source_clause?: string;
}

export interface MarginCall {
  action: "CALL" | "RETURN" | "NO_ACTION";
  amount: number;
  currency: string;
  calculation_date: string;
  net_exposure: number;
  threshold: number;
  posted_collateral_items: CollateralItem[];
  effective_collateral: number;
  exposure_above_threshold: number;
  calculation_steps: CalculationStep[];
  csa_terms_id?: string;
  counterparty_name?: string;
}

export interface CalculationResponse {
  calculation_id: string;
  margin_call: MarginCall;
  created_at: string;
  document_id?: string;
  has_explanation?: boolean;
  has_formula_pattern?: boolean;
}

export interface CalculationBreakdownStep {
  step: string;
  value: number;
  source?: string;
  explanation?: string;
}

export interface AuditTrailEvent {
  timestamp: string;
  event: string;
  details: string;
}

export interface MarginCallExplanation {
  narrative: string;
  key_factors: string[];
  calculation_breakdown: CalculationBreakdownStep[];
  audit_trail: AuditTrailEvent[];
  citations: Record<string, number | null>;
  risk_assessment?: string;
  next_steps?: string;
  generated_at: string;
  llm_model: string;
  document_id: string;
  margin_call_action: string;
  margin_call_amount: number;
  counterparty_name: string;
}

export interface ExplanationResponse {
  explanation_id: string;
  calculation_id: string;
  explanation: MarginCallExplanation;
  created_at: string;
}

export interface CalculationListItem {
  calculation_id: string;
  document_id: string;
  counterparty_name?: string;
  margin_call_action: string;
  margin_call_amount: number;
  calculation_date: string;
  has_explanation: boolean;
}

export interface CalculationSummary {
  calculation_id: string;
  calculation_date: string;
  net_exposure: number;
  party_perspective: string;
  action: string;
  amount: number;
  currency: string;
  counterparty_name?: string;
  has_explanation: boolean;
  has_formula_pattern: boolean;
}
