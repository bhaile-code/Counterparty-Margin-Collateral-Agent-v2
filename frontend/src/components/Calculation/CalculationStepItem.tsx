/**
 * CalculationStepItem - Displays individual calculation step with formula and inputs
 */

import { ChevronRight, FileText } from 'lucide-react';
import { formatCurrency } from '../../utils/formatting';
import type { CalculationStep } from '../../types/calculations';

interface CalculationStepItemProps {
  step: CalculationStep;
  currency: string;
  isLast?: boolean;
}

export function CalculationStepItem({ step, currency, isLast = false }: CalculationStepItemProps) {
  const { step_number, description, formula, inputs, result, source_clause } = step;

  return (
    <div className="relative">
      <div className="bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow">
        {/* Step Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-semibold flex items-center justify-center text-sm">
            {step_number}
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-800 mb-1">{description}</h4>
            {source_clause && (
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <FileText className="w-3 h-3" />
                <span>{source_clause}</span>
              </div>
            )}
          </div>
        </div>

        {/* Formula */}
        {formula && (
          <div className="mb-3 p-3 bg-gray-50 rounded border border-gray-200">
            <p className="text-xs text-gray-500 mb-1 font-medium">Formula:</p>
            <code className="text-sm text-gray-800 font-mono">{formula}</code>
          </div>
        )}

        {/* Inputs */}
        {inputs && Object.keys(inputs).length > 0 && (
          <div className="mb-3">
            <p className="text-xs text-gray-500 mb-2 font-medium">Inputs:</p>
            <div className="space-y-1">
              {Object.entries(inputs).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-gray-600">{formatInputKey(key)}:</span>
                  <span className="font-medium text-gray-800">
                    {formatInputValue(value, currency)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Result */}
        <div className="pt-3 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <span className="text-sm font-semibold text-gray-700">Result:</span>
            <span className="text-lg font-bold text-blue-600">
              {formatCurrency(result, currency)}
            </span>
          </div>
        </div>
      </div>

      {/* Connector Line */}
      {!isLast && (
        <div className="flex justify-center py-2">
          <ChevronRight className="w-5 h-5 text-gray-400 transform rotate-90" />
        </div>
      )}
    </div>
  );
}

/**
 * Format input key for display (snake_case to Title Case)
 */
function formatInputKey(key: string): string {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format input value for display
 */
function formatInputValue(value: any, currency: string): string {
  if (typeof value === 'number') {
    // If it looks like a monetary value (large number), format as currency
    if (Math.abs(value) >= 100) {
      return formatCurrency(value, currency);
    }
    // Otherwise, format as number with decimals
    return value.toFixed(4);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  if (value === null || value === undefined) {
    return 'N/A';
  }
  // Handle arrays (e.g., posted_collateral items)
  if (Array.isArray(value)) {
    if (value.length === 0) return 'None';
    // For collateral items, show count and summary
    return `${value.length} item(s)`;
  }
  // Handle objects - show as formatted JSON
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}
