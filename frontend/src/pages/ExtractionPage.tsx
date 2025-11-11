/**
 * Extraction Results Page
 *
 * Displays extracted CSA terms and normalized collateral from a processed document.
 * Shows confidence scores, field values, and allows navigation to calculation.
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Calculator, FileText, History } from 'lucide-react';
import { Button, Spinner, StatusBadge } from '../components/shared';
import { CSATermsSection, CollateralList } from '../components/Extraction';
import { CalculationsModal } from '../components/Calculation';
import { getCSATerms, getDocumentDetail } from '../api/documents';
import type { CSATerms, DocumentDetailResponse } from '../types/documents';
import { formatFileSize, formatDate } from '../utils/formatting';

export function ExtractionPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [csaTerms, setCsaTerms] = useState<CSATerms | null>(null);
  const [documentDetail, setDocumentDetail] = useState<DocumentDetailResponse | null>(null);
  const [showCalculationsModal, setShowCalculationsModal] = useState(false);

  // Fetch document detail and CSA terms on mount
  useEffect(() => {
    if (!documentId) {
      setError('No document ID provided');
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch document detail and CSA terms in parallel
        const [detail, terms] = await Promise.all([
          getDocumentDetail(documentId),
          getCSATerms(documentId),
        ]);

        setDocumentDetail(detail);
        setCsaTerms(terms);
      } catch (err: any) {
        console.error('Failed to fetch extraction data:', err);
        setError(err.message || 'Failed to load extraction results');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [documentId]);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-gray-600">Loading extraction results...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !csaTerms) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <Button
              variant="ghost"
              size="sm"
              icon={<ArrowLeft className="w-4 h-4" />}
              onClick={() => navigate('/')}
            >
              Back to Dashboard
            </Button>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-red-500 mb-4">
              <FileText className="w-16 h-16 mx-auto opacity-50" />
            </div>
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Unable to Load Extraction Results
            </h2>
            <p className="text-gray-600 mb-6">
              {error || 'This document has not been fully processed yet.'}
            </p>
            <Button variant="primary" onClick={() => navigate('/')}>
              Return to Dashboard
            </Button>
          </div>
        </main>
      </div>
    );
  }

  // Check if processing is complete
  const isProcessingComplete = documentDetail?.processing_status?.mapped_to_csa_terms;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                icon={<ArrowLeft className="w-4 h-4" />}
                onClick={() => navigate('/')}
              >
                Back to Dashboard
              </Button>
              <div className="h-6 w-px bg-gray-300" />
              <div>
                <h1 className="text-lg font-semibold text-gray-900">
                  {documentDetail?.filename || 'Document'}
                </h1>
                <div className="flex items-center gap-3 mt-1">
                  {documentDetail && (
                    <>
                      <span className="text-sm text-gray-500">
                        {formatFileSize(documentDetail.file_size)}
                      </span>
                      <span className="text-sm text-gray-500">
                        Uploaded {formatDate(documentDetail.uploaded_at)}
                      </span>
                    </>
                  )}
                  {isProcessingComplete && (
                    <StatusBadge variant="success" size="sm">
                      Processed
                    </StatusBadge>
                  )}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              {documentDetail?.processing_status?.has_calculations && (
                <Button
                  variant="secondary"
                  icon={<History className="w-4 h-4" />}
                  onClick={() => setShowCalculationsModal(true)}
                >
                  View Calculations
                </Button>
              )}
              <Button
                variant="primary"
                icon={<Calculator className="w-4 h-4" />}
                onClick={() => navigate(`/calculation/${documentId}/input`)}
                disabled={!isProcessingComplete}
              >
                Calculate Margin
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {/* CSA Terms Section */}
          <CSATermsSection csaTerms={csaTerms} />

          {/* Eligible Collateral Section */}
          <CollateralList collateral={csaTerms.eligible_collateral || []} />

          {/* Processing Metadata (if available) */}
          {documentDetail?.processing_status && (
            <div className="bg-white rounded-lg p-6 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Processing Status
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Parsed</div>
                  <div className="font-medium">
                    {documentDetail.processing_status.parsed ? '✓ Yes' : '✗ No'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Extracted</div>
                  <div className="font-medium">
                    {documentDetail.processing_status.extracted ? '✓ Yes' : '✗ No'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Normalized</div>
                  <div className="font-medium">
                    {documentDetail.processing_status.normalized ? '✓ Yes' : '✗ No'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Mapped</div>
                  <div className="font-medium">
                    {documentDetail.processing_status.mapped_to_csa_terms ? '✓ Yes' : '✗ No'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Calculations Modal */}
      {documentId && (
        <CalculationsModal
          isOpen={showCalculationsModal}
          onClose={() => setShowCalculationsModal(false)}
          documentId={documentId}
          documentName={documentDetail?.filename}
        />
      )}
    </div>
  );
}
