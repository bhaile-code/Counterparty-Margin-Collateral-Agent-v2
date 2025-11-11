/**
 * API client for script generation endpoints
 */

import { apiClient } from './client';

export interface GenerateScriptResponse {
  status: string;
  calculation_id: string;
  script: string;
  script_path: string;
  generation_time_seconds: number;
  patterns_used: boolean;
  patterns_auto_extracted: boolean;
  pattern_extraction_time_seconds?: number;
  script_stats: {
    length_chars: number;
    length_lines: number;
    has_docstring: boolean;
    has_type_hints: boolean;
    generation_time: number;
  };
}

export interface AuditScript {
  script: string;
  generated_at: string;
  patterns_used: boolean;
  patterns_auto_extracted?: boolean;
  pattern_extraction_time_seconds?: number;
  script_stats: {
    length_chars: number;
    length_lines: number;
    has_docstring: boolean;
    has_type_hints: boolean;
  };
}

export interface ScriptMetadata {
  calculation_id: string;
  document_id: string;
  generated_at: string;
  script_path: string;
  script_length: number;
  script_lines: number;
  patterns_used: boolean;
}

/**
 * Generate an audit script for a margin calculation
 *
 * Note: This may take longer if formula patterns need to be extracted first.
 * The apiClient is configured with a 5-minute timeout to accommodate pattern extraction + script generation.
 */
export async function generateAuditScript(
  calculationId: string
): Promise<GenerateScriptResponse> {
  const response = await apiClient.post<GenerateScriptResponse>(
    `/script-generation/${calculationId}/generate`,
    {}
  );
  return response.data;
}

/**
 * Get a previously generated audit script
 */
export async function getAuditScript(
  calculationId: string
): Promise<AuditScript> {
  const response = await apiClient.get<AuditScript>(
    `/script-generation/${calculationId}/script`
  );
  return response.data;
}

/**
 * Delete an audit script (force regeneration)
 */
export async function deleteAuditScript(
  calculationId: string
): Promise<void> {
  await apiClient.delete(
    `/script-generation/${calculationId}/script`
  );
}
