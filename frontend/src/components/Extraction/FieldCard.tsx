/**
 * FieldCard Component
 *
 * Displays an extracted field with its value, confidence score, and optional citation.
 * Used in the ExtractionPage to show CSA terms and metadata.
 */

import { StatusBadge } from '../shared';
import { Info } from 'lucide-react';
import { useState } from 'react';

interface FieldCardProps {
  label: string;
  value: string | number | null | undefined;
  confidence?: number; // 0-1 scale
  citation?: string; // Source text from PDF
  valueClassName?: string;
}

export function FieldCard({
  label,
  value,
  confidence,
  citation,
  valueClassName = ''
}: FieldCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  // Determine confidence badge variant
  const getConfidenceBadge = () => {
    if (confidence === undefined) return null;

    const percentage = Math.round(confidence * 100);
    let variant: 'success' | 'warning' | 'error';

    if (confidence >= 0.8) {
      variant = 'success';
    } else if (confidence >= 0.6) {
      variant = 'warning';
    } else {
      variant = 'error';
    }

    return (
      <StatusBadge variant={variant} size="sm">
        {percentage}% confidence
      </StatusBadge>
    );
  };

  // Display value or "Not specified" if missing
  const displayValue = value !== null && value !== undefined && value !== ''
    ? value
    : <span className="text-gray-400 italic">Not specified</span>;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Label */}
          <div className="text-sm font-medium text-gray-600 mb-1">
            {label}
          </div>

          {/* Value */}
          <div className={`text-lg font-semibold text-gray-900 break-words ${valueClassName}`}>
            {displayValue}
          </div>

          {/* Confidence Badge */}
          {confidence !== undefined && (
            <div className="mt-2">
              {getConfidenceBadge()}
            </div>
          )}
        </div>

        {/* Citation Tooltip */}
        {citation && (
          <div className="relative flex-shrink-0">
            <button
              type="button"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              className="text-gray-400 hover:text-gray-600 transition-colors p-1"
              aria-label="View source citation"
            >
              <Info className="w-5 h-5" />
            </button>

            {/* Tooltip */}
            {showTooltip && (
              <div className="absolute right-0 top-8 z-10 w-80 bg-gray-900 text-white text-sm rounded-lg p-3 shadow-lg">
                <div className="text-xs text-gray-300 mb-1 font-medium">Source Citation:</div>
                <div className="text-sm leading-relaxed">"{citation}"</div>
                {/* Triangle pointer */}
                <div className="absolute -top-2 right-4 w-0 h-0 border-l-8 border-r-8 border-b-8 border-transparent border-b-gray-900" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
