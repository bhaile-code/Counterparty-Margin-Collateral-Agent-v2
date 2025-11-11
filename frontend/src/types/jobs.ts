/**
 * Job-related types for unified processing endpoint
 */

import type { CSATerms } from './documents';

export type JobStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";

export interface ProcessOptions {
  normalize_method?: "simple" | "multi-agent";
  save_intermediate_steps?: boolean;
  calculate_margin?: boolean;
  portfolio_value?: number;
}

export interface JobError {
  step: string;
  message: string;
  timestamp: string;
}

export interface JobResponse {
  job_id: string;
  document_id: string;
  status: JobStatus;
  progress: number;
  current_step?: string;
  step_timings?: Record<string, number>;
  results?: {
    parse_id?: string;
    extraction_id?: string;
    normalized_collateral_id?: string;
    csa_terms_id?: string;
    csa_terms?: CSATerms;
    normalization_metadata?: {
      overall_confidence?: number;
      requires_human_review?: boolean;
      agents_used?: string[];
      total_processing_time?: number;
    };
  };
  errors?: JobError[];
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface StartProcessingResponse {
  job_id: string;
  status: JobStatus;
  polling_url: string;
}
