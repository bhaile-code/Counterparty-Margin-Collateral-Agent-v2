/**
 * Documents API - Handles all document-related API calls
 */

import { apiClient } from './client';
import type {
  DocumentUploadResponse,
  DocumentDetailResponse,
  DocumentListItem,
  CSATerms,
  ParseResult,
  ExtractionResult,
  NormalizedCollateralTable,
} from '../types/documents';
import type {
  ProcessOptions,
  StartProcessingResponse,
  JobResponse,
  JobStatus,
} from '../types/jobs';

/**
 * Upload a CSA PDF document
 */
export async function uploadDocument(
  file: File,
  counterpartyName?: string
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (counterpartyName) {
    formData.append('counterparty_name', counterpartyName);
  }

  const response = await apiClient.post<DocumentUploadResponse>(
    '/documents/upload',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return response.data;
}

/**
 * Parse document with LandingAI ADE
 */
export async function parseDocument(documentId: string): Promise<ParseResult> {
  const response = await apiClient.post<ParseResult>(
    `/documents/parse/${documentId}`
  );
  return response.data;
}

/**
 * Extract CSA fields from parsed document
 */
export async function extractDocument(parseId: string): Promise<ExtractionResult> {
  const response = await apiClient.post<ExtractionResult>(
    `/documents/extract/${parseId}`
  );
  return response.data;
}

/**
 * Normalize collateral table with AI (single-agent)
 */
export async function normalizeCollateral(
  extractionId: string
): Promise<NormalizedCollateralTable> {
  const response = await apiClient.post<NormalizedCollateralTable>(
    `/documents/normalize/${extractionId}`
  );
  return response.data;
}

/**
 * Map extraction + normalization to CSA terms
 */
export async function mapToCSATerms(documentId: string): Promise<CSATerms> {
  const response = await apiClient.post<CSATerms>(
    `/documents/map/${documentId}`
  );
  return response.data;
}

/**
 * Get CSA terms for a document
 */
export async function getCSATerms(documentId: string): Promise<CSATerms> {
  const response = await apiClient.get<CSATerms>(
    `/documents/csa-terms/${documentId}`
  );
  return response.data;
}

/**
 * Get processing status for a document
 */
export async function getDocumentDetail(
  documentId: string
): Promise<DocumentDetailResponse> {
  const response = await apiClient.get<DocumentDetailResponse>(
    `/documents/${documentId}/detail`
  );
  return response.data;
}

/**
 * List all documents
 */
export async function listDocuments(): Promise<DocumentListItem[]> {
  const response = await apiClient.get<{ documents: DocumentListItem[]; count: number }>('/documents/list');
  return response.data.documents;
}

/**
 * Delete a document
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}

/**
 * Start unified processing pipeline for a document
 */
export async function startProcessing(
  documentId: string,
  options?: ProcessOptions
): Promise<StartProcessingResponse> {
  // Backend expects query parameters, not body
  const params: any = {};
  if (options?.normalize_method) params.normalize_method = options.normalize_method;
  if (options?.save_intermediate_steps !== undefined) params.save_intermediate_steps = options.save_intermediate_steps;
  if (options?.calculate_margin !== undefined) params.calculate_margin = options.calculate_margin;
  if (options?.portfolio_value !== undefined) params.portfolio_value = options.portfolio_value;

  const response = await apiClient.post<StartProcessingResponse>(
    `/documents/process/${documentId}`,
    {},  // Empty body
    { params }  // Query parameters
  );
  return response.data;
}

/**
 * Get job status for background processing
 */
export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await apiClient.get<JobResponse>(`/documents/jobs/${jobId}`);
  return response.data;
}

/**
 * List all background jobs
 */
export async function listJobs(
  documentId?: string,
  status?: JobStatus
): Promise<JobResponse[]> {
  const params: any = {};
  if (documentId) params.document_id = documentId;
  if (status) params.status = status;

  const response = await apiClient.get<JobResponse[]>('/documents/jobs', { params });
  return response.data;
}

/**
 * Cancel a running background job
 */
export async function cancelJob(jobId: string): Promise<void> {
  await apiClient.delete(`/documents/jobs/${jobId}`);
}

/**
 * Upload and process a CSA document using unified endpoint
 * Returns the completed job with results
 */
export async function processDocument(
  file: File,
  counterpartyName?: string,
  onProgress?: (progress: number, step: string) => void
): Promise<JobResponse> {
  // Step 1: Upload document
  onProgress?.(0, 'Uploading document');
  const uploadResult = await uploadDocument(file, counterpartyName);
  const documentId = uploadResult.document_id;

  // Step 2: Start unified processing
  onProgress?.(10, 'Starting processing');
  const { job_id } = await startProcessing(documentId, {
    normalize_method: 'multi-agent', // Use multi-agent for complete normalization
  });

  // Step 3: Poll for completion
  const MAX_POLLING_DURATION = 10 * 60 * 1000; // 10 minutes
  const pollingStartTime = Date.now();
  let job = await getJobStatus(job_id);

  while (job.status === 'processing' || job.status === 'pending') {
    // Safety check: prevent infinite polling
    if (Date.now() - pollingStartTime > MAX_POLLING_DURATION) {
      throw new Error('Processing timed out after 10 minutes');
    }

    const stepName = job.current_step || 'processing';
    onProgress?.(job.progress, stepName);

    // Poll every 2 seconds
    await new Promise(resolve => setTimeout(resolve, 2000));
    job = await getJobStatus(job_id);
  }

  // Check final status
  if (job.status === 'failed') {
    // Extract error message from errors array (backend stores errors as array)
    const latestError = job.errors && job.errors.length > 0
      ? job.errors[job.errors.length - 1]
      : null;
    const errorMessage = latestError
      ? `${latestError.step}: ${latestError.message}`
      : 'Processing failed';
    throw new Error(errorMessage);
  }

  if (job.status === 'cancelled') {
    throw new Error('Processing was cancelled');
  }

  // Success!
  onProgress?.(100, 'Completed');
  return job;
}

/**
 * LEGACY: Manual orchestration (deprecated - use processDocument instead)
 * Auto-chain all processing steps after upload
 * Returns the document ID when all steps are complete
 */
export async function processDocumentManual(
  file: File,
  counterpartyName?: string,
  onProgress?: (step: string, status: string) => void
): Promise<string> {
  // Step 1: Upload
  onProgress?.('upload', 'in_progress');
  const uploadResult = await uploadDocument(file, counterpartyName);
  const documentId = uploadResult.document_id;
  onProgress?.('upload', 'complete');

  // Step 2: Parse
  onProgress?.('parse', 'in_progress');
  await parseDocument(documentId);

  // Poll for parse completion
  let detail = await getDocumentDetail(documentId);
  while (!detail.processing_status.parsed) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    detail = await getDocumentDetail(documentId);
  }
  const parseId = detail.artifact_ids.parse_id!;
  onProgress?.('parse', 'complete');

  // Step 3: Extract
  onProgress?.('extract', 'in_progress');
  await extractDocument(parseId);

  // Poll for extraction completion
  detail = await getDocumentDetail(documentId);
  while (!detail.processing_status.extracted) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    detail = await getDocumentDetail(documentId);
  }
  const extractionId = detail.artifact_ids.extraction_id!;
  onProgress?.('extract', 'complete');

  // Step 4: Normalize
  onProgress?.('normalize', 'in_progress');
  await normalizeCollateral(extractionId);

  // Poll for normalization completion
  detail = await getDocumentDetail(documentId);
  while (!detail.processing_status.normalized) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    detail = await getDocumentDetail(documentId);
  }
  onProgress?.('normalize', 'complete');

  // Step 5: Map
  onProgress?.('map', 'in_progress');
  await mapToCSATerms(documentId);

  // Poll for mapping completion
  detail = await getDocumentDetail(documentId);
  while (!detail.processing_status.mapped_to_csa_terms) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    detail = await getDocumentDetail(documentId);
  }
  onProgress?.('map', 'complete');

  return documentId;
}
