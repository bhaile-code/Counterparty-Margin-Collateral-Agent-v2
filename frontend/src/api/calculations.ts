/**
 * Calculations API - Handles all calculation-related API calls
 */

import { apiClient } from './client';
import type {
  CalculationRequest,
  CalculationResponse,
  MarginCall,
  MarginCallExplanation,
  ExplanationResponse,
  CalculationListItem,
  CalculationSummary,
} from '../types/calculations';

/**
 * Calculate margin call
 */
export async function calculateMargin(
  request: CalculationRequest
): Promise<CalculationResponse> {
  const response = await apiClient.post<CalculationResponse>(
    '/calculations/calculate',
    request
  );
  return response.data;
}

/**
 * Generate LLM explanation for calculation
 */
export async function generateExplanation(
  calculationId: string
): Promise<ExplanationResponse> {
  const response = await apiClient.post<ExplanationResponse>(
    `/calculations/${calculationId}/explain`
  );
  return response.data;
}

/**
 * Get calculation by ID
 */
export async function getCalculation(calculationId: string): Promise<CalculationResponse> {
  const response = await apiClient.get<CalculationResponse>(
    `/calculations/${calculationId}`
  );
  return response.data;
}

/**
 * Get explanation for calculation
 */
export async function getExplanation(
  calculationId: string
): Promise<MarginCallExplanation> {
  const response = await apiClient.get<MarginCallExplanation>(
    `/calculations/${calculationId}/explanation`
  );
  return response.data;
}

/**
 * List all calculations
 */
export async function listCalculations(): Promise<CalculationListItem[]> {
  const response = await apiClient.get<CalculationListItem[]>('/calculations/');
  return response.data;
}

/**
 * Calculate and auto-generate explanation
 * Returns both calculation and explanation
 */
export async function calculateWithExplanation(
  request: CalculationRequest
): Promise<{
  calculation: CalculationResponse;
  explanation: ExplanationResponse;
}> {
  // Step 1: Calculate
  const calculation = await calculateMargin(request);

  // Step 2: Generate explanation
  const explanation = await generateExplanation(calculation.calculation_id);

  return { calculation, explanation };
}

/**
 * Get all calculations for a specific document
 */
export async function getCalculationsByDocument(
  documentId: string
): Promise<CalculationSummary[]> {
  const response = await apiClient.get<{
    status: string;
    document_id: string;
    count: number;
    calculations: CalculationSummary[];
  }>(`/calculations/by-document/${documentId}`);
  return response.data.calculations;
}
