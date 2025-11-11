/**
 * Dashboard Page - Main entry point showing all counterparties
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDocuments } from '../api/documents';
import type { DocumentListItem } from '../types/documents';
import { DashboardHeader, CounterpartyCard, ActivityFeed } from '../components/Dashboard';
import { UploadModal } from '../components/Upload';
import { Spinner } from '../components/shared';

export function DashboardPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  async function fetchDocuments() {
    try {
      setLoading(true);
      const docs = await listDocuments();
      // Sort by most recent upload first (create new array to avoid mutation)
      const sortedDocs = [...docs].sort((a, b) => {
        const dateA = new Date(a.uploaded_at).getTime();
        const dateB = new Date(b.uploaded_at).getTime();
        return dateB - dateA;
      });
      setDocuments(sortedDocs);
      setError(null);
    } catch (err) {
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }

  function handleUploadClick() {
    setUploadModalOpen(true);
  }

  function handleViewDetails(documentId: string) {
    navigate(`/extraction/${documentId}`);
  }

  function handleCalculateMargin(documentId: string) {
    navigate(`/calculation/${documentId}/input`);
  }

  function handleUploadComplete(documentId: string) {
    setUploadModalOpen(false);
    fetchDocuments(); // Refresh document list
    // Optionally navigate to extraction page
    navigate(`/extraction/${documentId}`);
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-gray-600">Loading documents...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={fetchDocuments}
            className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-hover"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <DashboardHeader onUploadClick={handleUploadClick} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {documents.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <p className="text-gray-500 mb-4">No documents uploaded yet</p>
            <p className="text-sm text-gray-400 mb-6">
              Upload your first CSA document to get started with AI-powered margin analysis
            </p>
            <button
              onClick={handleUploadClick}
              className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-hover font-medium"
            >
              Upload Your First CSA
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Document List - 2/3 width */}
            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-2xl font-semibold text-gray-800 mb-4">
                Active Counterparties ({documents.length})
              </h2>
              {documents.map((doc) => (
                <CounterpartyCard
                  key={doc.document_id}
                  document={doc}
                  onViewDetails={handleViewDetails}
                  onCalculateMargin={handleCalculateMargin}
                />
              ))}
            </div>

            {/* Activity Feed - 1/3 width */}
            <div className="lg:col-span-1">
              <ActivityFeed documents={documents} />
            </div>
          </div>
        )}
      </main>

      {/* Upload Modal */}
      {uploadModalOpen && (
        <UploadModal
          isOpen={uploadModalOpen}
          onClose={() => setUploadModalOpen(false)}
          onSuccess={handleUploadComplete}
        />
      )}
    </div>
  );
}
