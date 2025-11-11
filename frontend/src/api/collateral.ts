/**
 * Collateral API - Handles collateral CSV import and matching
 */

import { apiClient } from './client';
import type {
  ParsedCollateralItem,
  MatchedCollateralItem,
  ImportCollateralResponse,
  MatchCollateralResponse,
  HaircutLookupResponse,
} from '../types/collateral';

/**
 * Import and parse collateral CSV file
 */
export async function importCollateralCSV(
  file: File,
  documentId: string
): Promise<ImportCollateralResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_id', documentId);

  const response = await apiClient.post<ImportCollateralResponse>(
    '/collateral/import',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
}

/**
 * Match parsed collateral items to CSA collateral descriptions using AI
 */
export async function matchCollateral(
  documentId: string,
  parsedItems: ParsedCollateralItem[],
  defaultScenario?: string
): Promise<MatchCollateralResponse> {
  const response = await apiClient.post<MatchCollateralResponse>(
    '/collateral/match',
    {
      document_id: documentId,
      parsed_items: parsedItems,
      default_scenario: defaultScenario,
    }
  );

  return response.data;
}

/**
 * Lookup haircut for specific collateral type and maturity range
 * Used when user manually changes collateral selections
 */
export async function lookupHaircut(
  documentId: string,
  csaDescription: string,
  ratingEvent: string,
  maturityMin?: number | null,
  maturityMax?: number | null
): Promise<HaircutLookupResponse> {
  const response = await apiClient.post<HaircutLookupResponse>(
    '/collateral/lookup-haircut',
    {
      document_id: documentId,
      csa_description: csaDescription,
      rating_event: ratingEvent,
      maturity_min: maturityMin,
      maturity_max: maturityMax,
    }
  );

  return response.data;
}

/**
 * Import CSV and match to CSA in one call
 * Convenience method that combines import + match steps
 */
export async function importAndMatchCollateral(
  file: File,
  documentId: string,
  defaultScenario?: string
): Promise<{
  importResult: ImportCollateralResponse;
  matchResult: MatchCollateralResponse;
}> {
  // Step 1: Import and parse CSV
  const importResult = await importCollateralCSV(file, documentId);

  // Check for parse errors
  if (importResult.error_rows > 0) {
    console.warn(`CSV import has ${importResult.error_rows} error rows`);
  }

  // Filter out items with parse errors
  const validItems = importResult.parsed_items.filter(
    (item) => item.parse_errors.length === 0
  );

  if (validItems.length === 0) {
    throw new Error('No valid collateral items to match');
  }

  // Step 2: Match to CSA collateral
  const matchResult = await matchCollateral(documentId, validItems, defaultScenario);

  return { importResult, matchResult };
}
