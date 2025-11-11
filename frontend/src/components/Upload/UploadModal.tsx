import { useState, useCallback, useRef } from 'react';
import { Loader2, Check, Circle } from 'lucide-react';
import { Modal } from '../shared/Modal';
import { Button } from '../shared/Button';
import { FileDropzone } from './FileDropzone';
import { usePolling } from '../../hooks/usePolling';
import { processDocument, getDocumentDetail } from '../../api/documents';
import type { DocumentDetailResponse } from '../../types/documents';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (documentId: string) => void;
}

type UploadState = 'selecting' | 'uploading' | 'processing' | 'complete' | 'error';

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [state, setState] = useState<UploadState>('selecting');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const hasTransitionedToProcessing = useRef(false);

  // Polling for processing status
  const { stopPolling } = usePolling<DocumentDetailResponse>(
    async () => {
      if (!documentId) throw new Error('No document ID');
      const response = await getDocumentDetail(documentId);
      return response;
    },
    (data) => {
      // Stop polling when processing is complete
      return data.processing_status.mapped_to_csa_terms === true;
    },
    2000 // Poll every 2 seconds
  );

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    setError(null);
  }, []);

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
    setError(null);
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      setState('uploading');
      setError(null);

      // Start processing using unified endpoint with progress callback
      const response = await processDocument(
        selectedFile,
        undefined, // counterpartyName
        (progress, step) => {
          setUploadProgress(progress);
          setCurrentStep(step);

          // Switch to processing state once upload is complete
          if (progress >= 10 && !hasTransitionedToProcessing.current) {
            hasTransitionedToProcessing.current = true;
            setState('processing');
          }
        }
      );

      setDocumentId(response.document_id);

      // Mark as complete
      setState('complete');
      setUploadProgress(100);
      setCurrentStep('Completed');

    } catch (err) {
      setState('error');
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    }
  };

  const handleClose = () => {
    // Only allow close if not currently uploading
    if (state !== 'uploading') {
      resetState();
      onClose();
    }
  };

  const handleComplete = () => {
    if (documentId) {
      resetState();
      onSuccess(documentId);
    }
  };

  const resetState = () => {
    setState('selecting');
    setSelectedFile(null);
    setDocumentId(null);
    setError(null);
    setUploadProgress(0);
    setCurrentStep('');
    hasTransitionedToProcessing.current = false;
    stopPolling();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={
        state === 'selecting' || state === 'uploading'
          ? 'Upload CSA Document'
          : state === 'processing'
          ? 'Processing Document'
          : state === 'complete'
          ? 'Processing Complete'
          : 'Upload Error'
      }
      maxWidth="lg"
    >
      <div className="space-y-6">
        {/* File Selection State */}
        {(state === 'selecting' || state === 'uploading') && (
          <>
            <FileDropzone
              onFileSelect={handleFileSelect}
              selectedFile={selectedFile}
              onRemove={handleRemoveFile}
              disabled={state === 'uploading'}
            />

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button
                variant="secondary"
                onClick={handleClose}
                disabled={state === 'uploading'}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleUpload}
                disabled={!selectedFile || state === 'uploading'}
                loading={state === 'uploading'}
              >
                {state === 'uploading' ? 'Uploading...' : 'Upload & Process'}
              </Button>
            </div>
          </>
        )}

        {/* Processing State */}
        {state === 'processing' && (
          <>
            <div className="p-6">
              <div className="mb-4">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {currentStep || 'Processing...'}
                  </span>
                  <span className="text-sm text-gray-500">{uploadProgress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>

              {/* Step indicators */}
              <div className="space-y-3 mt-6">
                <div className="flex items-center">
                  {uploadProgress >= 20 ? (
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                  ) : (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
                  )}
                  <span className={uploadProgress >= 20 ? 'text-green-700' : 'text-gray-600'}>
                    Parse Document
                  </span>
                </div>

                <div className="flex items-center">
                  {uploadProgress >= 40 ? (
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                  ) : uploadProgress >= 20 ? (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 mr-3" />
                  )}
                  <span className={uploadProgress >= 40 ? 'text-green-700' : 'text-gray-600'}>
                    Extract CSA Terms
                  </span>
                </div>

                <div className="flex items-center">
                  {uploadProgress >= 70 ? (
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                  ) : uploadProgress >= 40 ? (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 mr-3" />
                  )}
                  <span className={uploadProgress >= 70 ? 'text-green-700' : 'text-gray-600'}>
                    Normalize Collateral (Multi-Agent)
                  </span>
                </div>

                <div className="flex items-center">
                  {uploadProgress >= 90 ? (
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                  ) : uploadProgress >= 70 ? (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-500 mr-3" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 mr-3" />
                  )}
                  <span className={uploadProgress >= 90 ? 'text-green-700' : 'text-gray-600'}>
                    Map to System
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button
                variant="secondary"
                onClick={handleClose}
              >
                Close (Processing Continues)
              </Button>
            </div>
          </>
        )}

        {/* Complete State */}
        {state === 'complete' && (
          <>
            <div className="p-6">
              <div className="bg-green-50 border-2 border-green-200 rounded-lg p-6 text-center">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="w-6 h-6 text-green-600" />
                </div>
                <h3 className="text-lg font-semibold text-green-900 mb-2">
                  Processing Complete!
                </h3>
                <p className="text-sm text-green-700">
                  Your CSA document has been successfully processed with multi-agent normalization.
                </p>
              </div>

              {/* Step indicators - all complete */}
              <div className="space-y-3 mt-6">
                <div className="flex items-center">
                  <Check className="w-5 h-5 text-green-500 mr-3" />
                  <span className="text-green-700">Parse Document</span>
                </div>
                <div className="flex items-center">
                  <Check className="w-5 h-5 text-green-500 mr-3" />
                  <span className="text-green-700">Extract CSA Terms</span>
                </div>
                <div className="flex items-center">
                  <Check className="w-5 h-5 text-green-500 mr-3" />
                  <span className="text-green-700">Normalize Collateral (Multi-Agent)</span>
                </div>
                <div className="flex items-center">
                  <Check className="w-5 h-5 text-green-500 mr-3" />
                  <span className="text-green-700">Map to System</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button
                variant="secondary"
                onClick={handleClose}
              >
                Close
              </Button>
              <Button
                variant="primary"
                onClick={handleComplete}
              >
                View Extraction Results
              </Button>
            </div>
          </>
        )}

        {/* Error State */}
        {state === 'error' && error && (
          <>
            <div className="bg-red-50 border-2 border-red-200 rounded-lg p-6 text-center">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl text-red-600">✗</span>
              </div>
              <h3 className="text-lg font-semibold text-red-900 mb-2">
                Upload Failed
              </h3>
              <p className="text-sm text-red-700">{error}</p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button
                variant="secondary"
                onClick={handleClose}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  setState('selecting');
                  setError(null);
                }}
              >
                Try Again
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
