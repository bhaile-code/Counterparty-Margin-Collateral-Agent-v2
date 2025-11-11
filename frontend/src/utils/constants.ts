/**
 * Application constants
 */

import type { StatusType } from '../types/common';

/**
 * Status badge configurations
 */
export const STATUS_CONFIG: Record<
  StatusType,
  { color: string; bgColor: string; label: string }
> = {
  success: {
    color: 'text-green-800',
    bgColor: 'bg-green-100',
    label: 'High Confidence',
  },
  warning: {
    color: 'text-amber-800',
    bgColor: 'bg-amber-100',
    label: 'Review Recommended',
  },
  error: {
    color: 'text-red-800',
    bgColor: 'bg-red-100',
    label: 'Extraction Uncertain',
  },
};

/**
 * Processing step labels
 */
export const PROCESSING_STEPS = {
  upload: 'Uploading document',
  parse: 'Parsing document structure',
  extract: 'Extracting CSA terms',
  normalize: 'Normalizing collateral table (AI)',
  map: 'Mapping to system format',
} as const;

/**
 * Confidence thresholds for status badges
 */
export const CONFIDENCE_THRESHOLDS = {
  HIGH: 0.8,
  MEDIUM: 0.5,
} as const;

/**
 * Get status from confidence score
 */
export function getStatusFromConfidence(confidence?: number): StatusType {
  if (!confidence || confidence < CONFIDENCE_THRESHOLDS.MEDIUM) return 'error';
  if (confidence < CONFIDENCE_THRESHOLDS.HIGH) return 'warning';
  return 'success';
}

/**
 * Common collateral types for dropdown (simplified for MVP)
 */
export const COMMON_COLLATERAL_TYPES = [
  { value: 'CASH_USD', label: 'Cash (USD)' },
  { value: 'US_TREASURY', label: 'US Treasury Securities' },
  { value: 'CORPORATE_BONDS', label: 'Investment Grade Corporate Bonds' },
  { value: 'US_AGENCY', label: 'US Agency Securities' },
] as const;
