/**
 * Common types shared across the application
 */

export type StatusType = 'success' | 'warning' | 'error';

export interface ProcessingStatus {
  uploaded: boolean;
  parsed: boolean;
  extracted: boolean;
  normalized: boolean;
  mapped_to_csa_terms: boolean;
  has_calculations: boolean;
}

export interface ArtifactIds {
  parse_id: string | null;
  extraction_id: string | null;
  normalized_collateral_id: string | null;
  csa_terms_id: string | null;
  calculation_ids: string[];
}

export interface ValidationWarning {
  check: string;
  severity: string;
  message: string;
  affected_fields?: string[];
  recommendation?: string;
}

export interface ValidationError {
  check: string;
  message: string;
  affected_fields: string[];
}
