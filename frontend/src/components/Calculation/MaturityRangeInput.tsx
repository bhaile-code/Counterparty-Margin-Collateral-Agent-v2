/**
 * MaturityRangeInput Component
 *
 * Dual number input for maturity range (min/max years)
 * Supports unbounded ranges (blank = no limit)
 */

import React from 'react';
import { formatMaturityRange } from '../../utils/csvTemplate';

interface MaturityRangeInputProps {
  minYears?: number | null;
  maxYears?: number | null;
  onChange: (min: number | null, max: number | null) => void;
  disabled?: boolean;
  error?: string;
}

export function MaturityRangeInput({
  minYears,
  maxYears,
  onChange,
  disabled = false,
  error,
}: MaturityRangeInputProps) {
  const handleMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.trim();
    const newMin = value === '' ? null : parseFloat(value);
    onChange(newMin, maxYears === undefined ? null : maxYears);
  };

  const handleMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.trim();
    const newMax = value === '' ? null : parseFloat(value);
    onChange(minYears === undefined ? null : minYears, newMax);
  };

  // Validate min <= max
  const hasValidationError =
    minYears !== null &&
    minYears !== undefined &&
    maxYears !== null &&
    maxYears !== undefined &&
    minYears > maxYears;

  const displayText = formatMaturityRange(minYears, maxYears);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Min Years
          </label>
          <input
            type="number"
            value={minYears === null || minYears === undefined ? '' : minYears}
            onChange={handleMinChange}
            disabled={disabled}
            min={0}
            step={0.1}
            placeholder="No min"
            className={`w-full px-3 py-2 text-sm border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
              hasValidationError || error
                ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                : 'border-gray-300'
            } ${disabled ? 'bg-gray-50 cursor-not-allowed' : 'bg-white'}`}
          />
        </div>

        <div className="pt-6 text-gray-500 text-sm font-medium">to</div>

        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Max Years
          </label>
          <input
            type="number"
            value={maxYears === null || maxYears === undefined ? '' : maxYears}
            onChange={handleMaxChange}
            disabled={disabled}
            min={0}
            step={0.1}
            placeholder="No max"
            className={`w-full px-3 py-2 text-sm border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
              hasValidationError || error
                ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                : 'border-gray-300'
            } ${disabled ? 'bg-gray-50 cursor-not-allowed' : 'bg-white'}`}
          />
        </div>
      </div>

      {/* Display formatted range */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-600 italic">{displayText}</p>

        {/* Validation error */}
        {hasValidationError && (
          <p className="text-xs text-red-600">Min cannot exceed max</p>
        )}

        {/* Custom error */}
        {error && !hasValidationError && (
          <p className="text-xs text-red-600">{error}</p>
        )}
      </div>
    </div>
  );
}
