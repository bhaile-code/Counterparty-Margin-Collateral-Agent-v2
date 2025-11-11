/**
 * CalculationsModal - Modal for displaying list of calculations for a document
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { Modal } from '../shared/Modal';
import { Spinner } from '../shared/Spinner';
import { CalculationListItem } from './CalculationListItem';
import { getCalculationsByDocument } from '../../api/calculations';
import type { CalculationSummary } from '../../types/calculations';

interface CalculationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  documentName?: string;
}

export function CalculationsModal({
  isOpen,
  onClose,
  documentId,
  documentName,
}: CalculationsModalProps) {
  const navigate = useNavigate();
  const [calculations, setCalculations] = useState<CalculationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && documentId) {
      fetchCalculations();
    }
  }, [isOpen, documentId]);

  async function fetchCalculations() {
    try {
      setIsLoading(true);
      setError(null);
      const data = await getCalculationsByDocument(documentId);
      setCalculations(data);
    } catch (err: any) {
      console.error('Error fetching calculations:', err);
      setError(err.response?.data?.detail || 'Failed to load calculations');
    } finally {
      setIsLoading(false);
    }
  }

  function handleCalculationClick(calculationId: string) {
    navigate(`/calculation/${calculationId}/results`);
    onClose();
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={documentName ? `Calculations for ${documentName}` : 'Calculations'}
      maxWidth="2xl"
    >
      <div className="space-y-4">
        {isLoading && (
          <div className="flex justify-center items-center py-12">
            <Spinner size="lg" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {!isLoading && !error && calculations.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No calculations found for this document.</p>
            <p className="text-sm text-gray-400 mt-2">
              Create a calculation to see it appear here.
            </p>
          </div>
        )}

        {!isLoading && !error && calculations.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-gray-600">
                {calculations.length} calculation{calculations.length !== 1 ? 's' : ''} found
              </p>
              <p className="text-xs text-gray-500">Sorted by newest first</p>
            </div>

            <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-2">
              {calculations.map((calc) => (
                <CalculationListItem
                  key={calc.calculation_id}
                  calculation={calc}
                  onClick={() => handleCalculationClick(calc.calculation_id)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
