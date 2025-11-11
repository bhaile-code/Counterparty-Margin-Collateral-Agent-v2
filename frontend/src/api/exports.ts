/**
 * Exports API - Handles all export-related API calls
 */

import { apiClient } from './client';

/**
 * Export margin call notice
 */
export async function exportMarginCallNotice(
  calculationId: string,
  format: 'json' | 'pdf' = 'pdf'
): Promise<Blob> {
  const response = await apiClient.get(
    `/export/margin-call-notice/${calculationId}`,
    {
      params: { format },
      responseType: 'blob',
    }
  );
  return response.data;
}

/**
 * Export audit trail
 */
export async function exportAuditTrail(
  calculationId: string,
  format: 'json' | 'csv' = 'json'
): Promise<Blob> {
  const response = await apiClient.get(
    `/export/audit-trail/${calculationId}`,
    {
      params: { format },
      responseType: 'blob',
    }
  );
  return response.data;
}

/**
 * Download a blob as a file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Export margin call notice and trigger download
 */
export async function downloadMarginCallNotice(
  calculationId: string,
  counterpartyName: string,
  format: 'json' | 'pdf' = 'pdf'
): Promise<void> {
  const blob = await exportMarginCallNotice(calculationId, format);
  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `Margin_Call_Notice_${counterpartyName}_${timestamp}.${format}`;
  downloadBlob(blob, filename);
}

/**
 * Export audit trail and trigger download
 */
export async function downloadAuditTrail(
  calculationId: string,
  counterpartyName: string,
  format: 'json' | 'csv' = 'json'
): Promise<void> {
  const blob = await exportAuditTrail(calculationId, format);
  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `Audit_Trail_${counterpartyName}_${timestamp}.${format}`;
  downloadBlob(blob, filename);
}
