/**
 * API client for formula pattern extraction and retrieval
 */

import { apiClient } from './client';

export interface FormulaPatternResult {
  document_id: string;
  extraction_timestamp: string;
  patterns: Record<string, any>;
  threshold_structure: any;
  haircut_structure: any;
  complexity_score: number;
  overall_confidence: number;
  variations_summary: string[];
}

export interface ExtractPatternsResponse {
  status: string;
  document_id: string;
  patterns: FormulaPatternResult;
  extraction_time_seconds: number;
  cached: boolean;
}

/**
 * Extract formula patterns from a CSA document
 */
export async function extractFormulaPatterns(
  documentId: string,
  forceReextract: boolean = false
): Promise<ExtractPatternsResponse> {
  const response = await apiClient.post<ExtractPatternsResponse>(
    `/formula-analysis/${documentId}/extract-patterns`,
    null,
    {
      params: { force_reextract: forceReextract },
    }
  );
  return response.data;
}

/**
 * Get previously extracted formula patterns
 */
export async function getFormulaPatterns(documentId: string): Promise<FormulaPatternResult> {
  const response = await apiClient.get<{ patterns: FormulaPatternResult }>(
    `/formula-analysis/${documentId}/patterns`
  );
  return response.data.patterns;
}

/**
 * Get complexity analysis for a CSA document
 */
export async function getComplexityAnalysis(documentId: string): Promise<any> {
  const response = await apiClient.get(`/formula-analysis/${documentId}/complexity-analysis`);
  return response.data;
}

/**
 * Delete stored formula patterns
 */
export async function deleteFormulaPatterns(documentId: string): Promise<void> {
  await apiClient.delete(`/formula-analysis/${documentId}/patterns`);
}
