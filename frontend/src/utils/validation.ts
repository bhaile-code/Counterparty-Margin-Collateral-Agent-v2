/**
 * Validation utilities for file uploads and forms
 */

export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validate file for upload
 */
export function validateFile(file: File): FileValidationResult {
  // Check file type
  if (file.type !== 'application/pdf') {
    return {
      valid: false,
      error: 'Only PDF files are supported. Please upload a PDF document.',
    };
  }

  // Check file size (max 50MB)
  const maxSize = 50 * 1024 * 1024; // 50MB in bytes
  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File size exceeds 50MB limit. Please upload a smaller file.',
    };
  }

  return { valid: true };
}

/**
 * Validate PDF magic bytes
 */
export async function isPDF(file: File): Promise<boolean> {
  const buffer = await file.slice(0, 4).arrayBuffer();
  const bytes = new Uint8Array(buffer);
  // PDF files start with "%PDF"
  return bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46;
}
