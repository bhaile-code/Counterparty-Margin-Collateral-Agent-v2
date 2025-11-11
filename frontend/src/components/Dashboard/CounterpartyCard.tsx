import { FileText, Eye, Calculator } from 'lucide-react';
import { Button } from '../shared/Button';
import { formatDateTime, formatFileSize } from '../../utils/formatting';
import type { DocumentListItem } from '../../types/documents';

interface CounterpartyCardProps {
  document: DocumentListItem;
  onViewDetails: (documentId: string) => void;
  onCalculateMargin: (documentId: string) => void;
}

export function CounterpartyCard({
  document,
  onViewDetails,
  onCalculateMargin
}: CounterpartyCardProps) {
  // Allow viewing details if CSA terms exist OR if fully mapped
  const isProcessed = document.processing_status?.mapped_to_csa_terms || document.has_csa_terms || false;
  const isProcessing = !isProcessed && (
    document.processing_status?.uploaded ||
    document.processing_status?.parsed ||
    document.processing_status?.extracted ||
    document.processing_status?.normalized
  );

  const getStatusBadge = () => {
    if (isProcessed) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          Processed
        </span>
      );
    }
    if (isProcessing) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          Processing...
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
        Uploaded
      </span>
    );
  };

  // Display logic for party names
  // Primary: Show both parties if available
  // Fallback 1: Show available party and mark other as "Unknown"
  // Fallback 2: Show "Parties Not Yet Extracted" (filename shown in subtitle)
  const getDisplayName = () => {
    if (document.party_a && document.party_b) {
      return `${document.party_a} • ${document.party_b}`;
    }
    if (document.party_a || document.party_b) {
      const partyA = document.party_a || 'Unknown';
      const partyB = document.party_b || 'Unknown';
      return `${partyA} • ${partyB}`;
    }
    return 'Parties Not Yet Extracted';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary bg-opacity-10 rounded-lg">
                <FileText className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900">
                  {getDisplayName()}
                </h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  {document.filename}
                </p>
              </div>
            </div>
          </div>
          <div>
            {getStatusBadge()}
          </div>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
          <div>
            <span className="text-gray-500">Uploaded:</span>
            <span className="ml-2 text-gray-900 font-medium">
              {formatDateTime(document.uploaded_at)}
            </span>
          </div>
          <div>
            <span className="text-gray-500">File Size:</span>
            <span className="ml-2 text-gray-900 font-medium">
              {formatFileSize(document.file_size)}
            </span>
          </div>
        </div>

        {/* Processing Status Details */}
        {isProcessing && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-800 font-medium">
              Document is being processed...
            </p>
            <div className="mt-2 flex items-center gap-2 text-xs text-blue-600">
              {document.processing_status?.uploaded && <span>✓ Uploaded</span>}
              {document.processing_status?.parsed && <span>✓ Parsed</span>}
              {document.processing_status?.extracted && <span>✓ Extracted</span>}
              {document.processing_status?.normalized && <span>✓ Normalized</span>}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            icon={<Eye className="w-4 h-4" />}
            onClick={() => onViewDetails(document.document_id)}
            disabled={!isProcessed}
          >
            View Details
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Calculator className="w-4 h-4" />}
            onClick={() => onCalculateMargin(document.document_id)}
            disabled={!isProcessed}
          >
            Calculate Margin
          </Button>
        </div>
      </div>
    </div>
  );
}
