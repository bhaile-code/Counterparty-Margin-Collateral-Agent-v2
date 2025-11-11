/**
 * Document-related types
 */

import type { NormalizedCollateral, CollateralItem } from './collateral';
import type { ProcessingStatus, ArtifactIds } from './common';

// Re-export for convenience
export type { CollateralItem };

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_size: number;
  upload_timestamp: string;
  status: string;
}

export interface DocumentDetailResponse {
  document_id: string;
  filename: string;
  file_size: number;
  uploaded_at: string;
  processing_status: ProcessingStatus;
  artifact_ids: ArtifactIds;
  errors: string[];
}

export interface DocumentListItem {
  document_id: string;
  filename: string;
  file_size: number;
  uploaded_at: string;
  counterparty_name?: string;
  party_a?: string;
  party_b?: string;
  status: string;
  has_csa_terms: boolean;
  has_calculations: boolean;
  processing_status?: ProcessingStatus;
}

export interface CSATerms {
  // Party identification
  party_a?: string;
  party_b?: string;

  // Party-specific margin terms
  party_a_threshold?: number;
  party_b_threshold?: number;
  party_a_minimum_transfer_amount?: number;
  party_b_minimum_transfer_amount?: number;
  party_a_independent_amount?: number;
  party_b_independent_amount?: number;
  rounding: number;
  currency: string;

  // Collateral references
  normalized_collateral_id: string;
  eligible_collateral?: NormalizedCollateral[];

  // Optional fields
  valuation_agent?: string;
  effective_date?: string;
  confidence_scores?: Record<string, number>;
  source_pages?: Record<string, number>;
  source_document_id?: string;
}

export interface ParseResult {
  parse_id: string;
  document_id: string;
  status: string;
  pages_count?: number;
  created_at: string;
}

export interface ExtractionResult {
  extraction_id: string;
  parse_id: string;
  status: string;
  extracted_fields: Record<string, any>;
  confidence_scores: Record<string, number>;
  created_at: string;
}

export interface NormalizedCollateralTable {
  normalized_id: string;
  extraction_id: string;
  collateral_items: NormalizedCollateral[];
  status: string;
  created_at: string;
}
