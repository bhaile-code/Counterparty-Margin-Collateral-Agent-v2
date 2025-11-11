/**
 * LEGACY: Older simplified documents API - only used for multi-agent processing
 * For standard document processing, use documents.ts instead
 */

import { apiClient } from './client';
import type {
  DocumentUploadResponse,
  DocumentDetailResponse,
  DocumentListItem,
  CSATerms,
} from '../types/documents';

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
export async function parseDocument(documentId: string): Promise<void> {
  await apiClient.post(`/documents/parse/${documentId}`);
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
 * Get CSA terms for a document
 */
export async function getCSATerms(documentId: string): Promise<CSATerms> {
  const response = await apiClient.get<CSATerms>(
    `/documents/csa-terms/${documentId}`
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
 * Upload and start processing a CSA document
 * Returns document_id for polling via getDocumentDetail()
 */
export async function processDocument(
  file: File,
  counterpartyName?: string
): Promise<DocumentUploadResponse> {
  // Upload the file
  const uploadResult = await uploadDocument(file, counterpartyName);

  // Trigger parse (backend will auto-chain extract → normalize → map)
  await parseDocument(uploadResult.document_id);

  // Return upload result with document_id
  // Caller should poll getDocumentDetail() to track processing status
  return uploadResult;
}
