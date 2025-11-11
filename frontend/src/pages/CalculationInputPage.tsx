/**
 * Calculation Input Page - Collect exposure and collateral data for margin calculation
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Calculator, AlertCircle, ChevronDown, AlertTriangle, History } from 'lucide-react';
import { Button } from '../components/shared/Button';
import { Spinner } from '../components/shared/Spinner';
import { CalculationsModal } from '../components/Calculation';
import { getCSATerms, getDocumentDetail } from '../api/documents';
import { calculateMargin } from '../api/calculations';
import { formatCurrency } from '../utils/formatting';
import { CollateralCSVUpload } from '../components/Calculation/CollateralCSVUpload';
import { CollateralReviewTable } from '../components/Calculation/CollateralReviewTable';
import { CollateralSummary } from '../components/Calculation/CollateralSummary';
import type { CSATerms, DocumentDetailResponse } from '../types/documents';
import type { MatchedCollateralItem, CollateralItem } from '../types/collateral';

export function CalculationInputPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  // CSA Terms state
  const [csaTerms, setCsaTerms] = useState<CSATerms | null>(null);
  const [documentDetail, setDocumentDetail] = useState<DocumentDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCalculationsModal, setShowCalculationsModal] = useState(false);

  // Form state
  const [netExposure, setNetExposure] = useState<string>('');
  const [partyPerspective, setPartyPerspective] = useState<'party_a' | 'party_b'>('party_b');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Collateral state
  const [collateralItems, setCollateralItems] = useState<MatchedCollateralItem[]>([]);
  const [showCollateralInput, setShowCollateralInput] = useState(false);

  // Fetch CSA terms on mount
  useEffect(() => {
    async function fetchData() {
      if (!documentId) {
        setError('Document ID is required');
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const [terms, detail] = await Promise.all([
          getCSATerms(documentId),
          getDocumentDetail(documentId),
        ]);
        setCsaTerms(terms);
        setDocumentDetail(detail);
        setError(null);
      } catch (err) {
        console.error('Error fetching CSA terms:', err);
        setError('Failed to load CSA terms. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [documentId]);

  // Get selected party's terms
  const getSelectedPartyTerms = () => {
    if (!csaTerms) return null;

    if (partyPerspective === 'party_a') {
      return {
        name: csaTerms.party_a || 'Party A',
        threshold: csaTerms.party_a_threshold,
        minimumTransferAmount: csaTerms.party_a_minimum_transfer_amount,
        independentAmount: csaTerms.party_a_independent_amount,
      };
    } else {
      return {
        name: csaTerms.party_b || 'Party B',
        threshold: csaTerms.party_b_threshold,
        minimumTransferAmount: csaTerms.party_b_minimum_transfer_amount,
        independentAmount: csaTerms.party_b_independent_amount,
      };
    }
  };

  // Convert MatchedCollateralItem to CollateralItem for API
  const convertMatchedItemsToCollateralItems = (
    matched: MatchedCollateralItem[]
  ): CollateralItem[] => {
    console.log('[DEBUG] Converting matched collateral items:', matched);
    const filtered = matched.filter((item) => {
      // Must have a haircut rate to perform calculation
      const hasHaircut = item.haircut_rate !== undefined && item.haircut_rate !== null;

      // Must have at least one type identifier (CSA description or standardized type)
      const hasTypeIdentifier =
        (item.matched_csa_description && item.matched_csa_description.trim() !== '') ||
        (item.matched_standardized_type && item.matched_standardized_type.trim() !== '');

      return hasHaircut && hasTypeIdentifier;
    });
    console.log('[DEBUG] Filtered collateral items:', filtered);

    const converted = filtered.map((item) => {
      // Strip "StandardizedCollateralType." prefix if present
      let collateralType = item.matched_standardized_type || 'OTHER';
      if (collateralType.startsWith('StandardizedCollateralType.')) {
        collateralType = collateralType.replace('StandardizedCollateralType.', '');
      }

      const collateralItem: any = {
        collateral_type: collateralType,
        market_value: item.market_value,
        haircut_rate: item.haircut_rate || 0,
        currency: item.currency,
      };

      // Only include maturity_years if it exists and is a valid number
      if (item.maturity_max !== null && item.maturity_max !== undefined) {
        collateralItem.maturity_years = item.maturity_max;
      }

      return collateralItem;
    });
    console.log('[DEBUG] Converted to CollateralItem[]:', converted);

    return converted;
  };

  // Collateral handlers
  const handleCollateralImport = (matched: MatchedCollateralItem[]) => {
    setCollateralItems(matched);
    setShowCollateralInput(true);
  };

  const handleRemoveCollateralItem = (rowNumber: number) => {
    setCollateralItems((prev) => prev.filter((item) => item.csv_row_number !== rowNumber));
  };

  const handleCollateralItemsChange = (items: MatchedCollateralItem[]) => {
    setCollateralItems(items);
  };

  const handleCollateralError = (errorMsg: string) => {
    setError(errorMsg);
  };

  // Validate form
  const validateForm = (): boolean => {
    if (!netExposure || parseFloat(netExposure) < 0) {
      setValidationError('Net exposure must be a positive number');
      return false;
    }

    const selectedTerms = getSelectedPartyTerms();
    if (!selectedTerms) {
      setValidationError('CSA terms not available');
      return false;
    }

    if (selectedTerms.threshold === undefined || selectedTerms.threshold === null) {
      setValidationError(`${selectedTerms.name} does not have a threshold defined in the CSA terms`);
      return false;
    }

    setValidationError(null);
    return true;
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm() || !documentId) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const payload = {
        document_id: documentId,
        net_exposure: parseFloat(netExposure),
        posted_collateral: convertMatchedItemsToCollateralItems(collateralItems),
        party_perspective: partyPerspective,
      };
      console.log('[DEBUG] Sending calculation request:', JSON.stringify(payload, null, 2));

      const response = await calculateMargin(payload);

      // Navigate to results page
      navigate(`/calculation/${response.calculation_id}/results`);
    } catch (err: any) {
      console.error('Error calculating margin:', err);
      console.error('Error response:', err.response?.data);

      // Handle validation errors (422)
      let errorMessage = 'Failed to calculate margin. Please check your inputs and try again.';
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          // Pydantic validation errors
          const validationErrors = err.response.data.detail.map((e: any) =>
            `${e.loc?.join('.') || 'field'}: ${e.msg}`
          ).join('; ');
          errorMessage = `Validation error: ${validationErrors}`;
        } else if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        }
      }
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-gray-600">Loading CSA terms...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !csaTerms) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                icon={<ArrowLeft className="w-4 h-4" />}
                onClick={() => navigate(`/extraction/${documentId}`)}
              >
                Back to Extraction Results
              </Button>
            </div>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-red-800 mb-2">Error Loading CSA Terms</h2>
            <p className="text-red-700 mb-4">{error}</p>
            <Button onClick={() => window.location.reload()}>Try Again</Button>
          </div>
        </main>
      </div>
    );
  }

  const selectedTerms = getSelectedPartyTerms();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              icon={<ArrowLeft className="w-4 h-4" />}
              onClick={() => navigate(`/extraction/${documentId}`)}
            >
              Back to Extraction Results
            </Button>

            {documentDetail?.processing_status?.has_calculations && (
              <Button
                variant="secondary"
                size="sm"
                icon={<History className="w-4 h-4" />}
                onClick={() => setShowCalculationsModal(true)}
              >
                View Calculations
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {/* Document Context Card */}
          {csaTerms && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">CSA Agreement</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Party A:</span>
                  <p className="font-medium text-gray-800">{csaTerms.party_a || 'Not specified'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Party B:</span>
                  <p className="font-medium text-gray-800">{csaTerms.party_b || 'Not specified'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Currency:</span>
                  <p className="font-medium text-gray-800">{csaTerms.currency || 'USD'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Rounding:</span>
                  <p className="font-medium text-gray-800">{csaTerms.rounding || 'Nearest 100,000'}</p>
                </div>
              </div>
            </div>
          )}

          {/* Calculation Form */}
          <div className="bg-white rounded-lg shadow-sm p-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">
              Calculate Margin Requirement
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Party Perspective Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Party Perspective
                </label>
                <p className="text-sm text-gray-500 mb-3">
                  Select which party's perspective to calculate the margin requirement from
                </p>
                <div className="space-y-3">
                  {/* Party A Option */}
                  <label
                    className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      partyPerspective === 'party_a'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="party_perspective"
                      value="party_a"
                      checked={partyPerspective === 'party_a'}
                      onChange={(e) => setPartyPerspective(e.target.value as 'party_a')}
                      className="mt-1 mr-3"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-800">
                        {csaTerms?.party_a || 'Party A'}
                      </div>
                      {csaTerms?.party_a_threshold !== undefined && (
                        <div className="mt-2 text-sm text-gray-600 space-y-1">
                          <div>Threshold: {formatCurrency(csaTerms.party_a_threshold)}</div>
                          {csaTerms.party_a_minimum_transfer_amount !== undefined && (
                            <div>MTA: {formatCurrency(csaTerms.party_a_minimum_transfer_amount)}</div>
                          )}
                          {csaTerms.party_a_independent_amount !== undefined && csaTerms.party_a_independent_amount > 0 && (
                            <div>Independent Amount: {formatCurrency(csaTerms.party_a_independent_amount)}</div>
                          )}
                        </div>
                      )}
                    </div>
                  </label>

                  {/* Party B Option */}
                  <label
                    className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      partyPerspective === 'party_b'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="party_perspective"
                      value="party_b"
                      checked={partyPerspective === 'party_b'}
                      onChange={(e) => setPartyPerspective(e.target.value as 'party_b')}
                      className="mt-1 mr-3"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-800">
                        {csaTerms?.party_b || 'Party B'}
                      </div>
                      {csaTerms?.party_b_threshold !== undefined && (
                        <div className="mt-2 text-sm text-gray-600 space-y-1">
                          <div>Threshold: {formatCurrency(csaTerms.party_b_threshold)}</div>
                          {csaTerms.party_b_minimum_transfer_amount !== undefined && (
                            <div>MTA: {formatCurrency(csaTerms.party_b_minimum_transfer_amount)}</div>
                          )}
                          {csaTerms.party_b_independent_amount !== undefined && csaTerms.party_b_independent_amount > 0 && (
                            <div>Independent Amount: {formatCurrency(csaTerms.party_b_independent_amount)}</div>
                          )}
                        </div>
                      )}
                    </div>
                  </label>
                </div>
              </div>

              {/* Net Exposure Input */}
              <div>
                <label htmlFor="net_exposure" className="block text-sm font-medium text-gray-700 mb-2">
                  Net Exposure ({csaTerms?.currency || 'USD'})
                </label>
                <p className="text-sm text-gray-500 mb-2">
                  Enter the current net exposure amount. Positive values indicate {selectedTerms?.name} owes money to the counterparty.
                </p>
                <input
                  type="number"
                  id="net_exposure"
                  value={netExposure}
                  onChange={(e) => {
                    setNetExposure(e.target.value);
                    setValidationError(null);
                  }}
                  placeholder="Enter net exposure amount"
                  required
                  step="0.01"
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Collateral Section */}
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowCollateralInput(!showCollateralInput)}
                  className="w-full px-4 py-3 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Posted Collateral (Optional)
                    </h3>
                    {collateralItems.length > 0 && (
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">
                        {collateralItems.length} items
                      </span>
                    )}
                  </div>
                  <ChevronDown
                    className={`w-5 h-5 text-gray-500 transition-transform ${
                      showCollateralInput ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {showCollateralInput && (
                  <div className="p-4 space-y-4">
                    {/* Show upload if no collateral, otherwise show review table */}
                    {collateralItems.length === 0 ? (
                      <CollateralCSVUpload
                        documentId={documentId!}
                        onImportSuccess={handleCollateralImport}
                        onError={handleCollateralError}
                      />
                    ) : (
                      <>
                        {/* Collateral warnings */}
                        {collateralItems.some((item) => item.warnings.length > 0) && (
                          <div className="flex items-center gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                            <AlertTriangle className="w-5 h-5 text-yellow-600" />
                            <div className="flex-1">
                              <p className="text-sm font-medium text-yellow-900">
                                Collateral Warnings
                              </p>
                              <p className="text-xs text-yellow-700">
                                Some collateral items have warnings. Review the table below before
                                submitting.
                              </p>
                            </div>
                          </div>
                        )}

                        {/* Summary */}
                        <CollateralSummary matchedItems={collateralItems} />

                        {/* Review Table */}
                        <CollateralReviewTable
                          matchedItems={collateralItems}
                          eligibleCollateral={csaTerms?.eligible_collateral || []}
                          documentId={documentId!}
                          onItemsChange={handleCollateralItemsChange}
                          onRemoveItem={handleRemoveCollateralItem}
                        />

                        {/* Clear/Import Different CSV */}
                        <div className="flex gap-3">
                          <button
                            type="button"
                            onClick={() => setCollateralItems([])}
                            className="text-sm text-red-600 hover:text-red-700 hover:underline"
                          >
                            Clear All Collateral
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Validation Error */}
              {validationError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">{validationError}</p>
                </div>
              )}

              {/* Submission Error */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* Submit Buttons */}
              <div className="flex gap-4">
                <Button
                  type="submit"
                  disabled={isSubmitting || !netExposure}
                  icon={<Calculator className="w-4 h-4" />}
                  loading={isSubmitting}
                >
                  {isSubmitting ? 'Calculating...' : 'Calculate Margin'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => navigate('/')}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
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
