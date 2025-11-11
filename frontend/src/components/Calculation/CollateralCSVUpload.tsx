/**
 * CollateralCSVUpload Component
 *
 * CSV file upload with drag-and-drop for collateral import
 * Includes template download and validation
 */

import { useCallback, useState } from 'react';
import { Upload, X, FileText, AlertCircle, Download, Loader2 } from 'lucide-react';
import { downloadCSVTemplate, validateCSVFile } from '../../utils/csvTemplate';
import { importAndMatchCollateral } from '../../api/collateral';
import type { MatchedCollateralItem } from '../../types/collateral';

interface CollateralCSVUploadProps {
  documentId: string;
  onImportSuccess: (matchedItems: MatchedCollateralItem[]) => void;
  onError: (error: string) => void;
}

export function CollateralCSVUpload({
  documentId,
  onImportSuccess,
  onError,
}: CollateralCSVUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleFile = (file: File) => {
    const validation = validateCSVFile(file);

    if (!validation.valid) {
      setError(validation.error || 'Invalid CSV file');
      setSelectedFile(null);
      return;
    }

    setError(null);
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError(null);

    try {
      const { matchResult } = await importAndMatchCollateral(selectedFile, documentId);

      onImportSuccess(matchResult.matched_items);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to import collateral';
      setError(errorMessage);
      onError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemove = () => {
    setSelectedFile(null);
    setError(null);
  };

  const handleDownloadTemplate = () => {
    downloadCSVTemplate();
  };

  return (
    <div className="space-y-4">
      {/* Template Download Button */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">Import Collateral from CSV</h3>
        <button
          onClick={handleDownloadTemplate}
          className="flex items-center gap-2 px-3 py-2 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
        >
          <Download className="w-4 h-4" />
          Download Template
        </button>
      </div>

      {/* File Upload Area */}
      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            isDragging
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <div className="flex flex-col items-center gap-3">
            <div className="p-3 bg-gray-100 rounded-full">
              <Upload className="w-6 h-6 text-gray-600" />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-900">
                Drop CSV file here or{' '}
                <label className="text-blue-600 hover:text-blue-700 cursor-pointer">
                  browse
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileInput}
                    className="hidden"
                  />
                </label>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                CSV file with collateral descriptions and maturity ranges
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Selected File Display */
        <div className="border-2 border-green-300 bg-green-50 rounded-lg p-4">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-green-100 rounded-lg">
              <FileText className="w-6 h-6 text-green-600" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-gray-900 truncate">{selectedFile.name}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {(selectedFile.size / 1024).toFixed(1)} KB • CSV File
                  </p>
                </div>

                {!isUploading && (
                  <button
                    onClick={handleRemove}
                    className="ml-4 p-1 hover:bg-green-200 rounded transition-colors"
                    title="Remove file"
                  >
                    <X className="w-5 h-5 text-gray-600" />
                  </button>
                )}
              </div>

              {/* Upload Button */}
              <button
                onClick={handleUpload}
                disabled={isUploading}
                className="mt-3 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Importing & Matching...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Import & Match Collateral
                  </>
                )}
              </button>

              {error && (
                <div className="mt-3 flex items-center gap-2 text-sm text-red-600">
                  <AlertCircle className="w-4 h-4" />
                  {error}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-md">
        <p className="font-medium mb-1">CSV Format:</p>
        <ul className="list-disc list-inside space-y-1">
          <li>
            <strong>Required:</strong> description, market_value
          </li>
          <li>
            <strong>Optional:</strong> maturity_min, maturity_max, currency, valuation_scenario
          </li>
          <li>
            <strong>Maturity range examples:</strong> "1,3" (1-3 years), ",5" (≤5 years), "10," (≥10
            years)
          </li>
        </ul>
      </div>
    </div>
  );
}
