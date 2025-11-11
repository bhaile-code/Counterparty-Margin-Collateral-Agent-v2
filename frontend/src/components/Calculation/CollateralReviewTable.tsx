/**
 * CollateralReviewTable Component
 *
 * Interactive table for reviewing and editing matched collateral items
 * Supports manual overrides for all fields with real-time haircut updates
 */

import { useState } from 'react';
import { Trash2, AlertTriangle, Lock, Unlock, Info } from 'lucide-react';
import type { MatchedCollateralItem } from '../../types/collateral';
import type { NormalizedCollateral } from '../../types/collateral';
import { MaturityRangeInput } from './MaturityRangeInput';
import { lookupHaircut } from '../../api/collateral';
import { formatMaturityRange } from '../../utils/csvTemplate';

interface CollateralReviewTableProps {
  matchedItems: MatchedCollateralItem[];
  eligibleCollateral: NormalizedCollateral[];
  documentId: string;
  onItemsChange: (items: MatchedCollateralItem[]) => void;
  onRemoveItem: (rowNumber: number) => void;
}

export function CollateralReviewTable({
  matchedItems,
  eligibleCollateral,
  documentId,
  onItemsChange,
  onRemoveItem,
}: CollateralReviewTableProps) {
  const [expandedTooltips, setExpandedTooltips] = useState<Set<number>>(new Set());

  if (matchedItems.length === 0) {
    return null;
  }

  const toggleTooltip = (rowNumber: number) => {
    const newSet = new Set(expandedTooltips);
    if (newSet.has(rowNumber)) {
      newSet.delete(rowNumber);
    } else {
      newSet.add(rowNumber);
    }
    setExpandedTooltips(newSet);
  };

  const updateItem = (rowNumber: number, updates: Partial<MatchedCollateralItem>) => {
    const newItems = matchedItems.map((item) => {
      if (item.csv_row_number === rowNumber) {
        return { ...item, ...updates };
      }
      return item;
    });
    onItemsChange(newItems);
  };

  const handleDescriptionChange = (rowNumber: number, description: string) => {
    updateItem(rowNumber, { csv_description: description });
  };

  const handleMarketValueChange = (rowNumber: number, value: string) => {
    const marketValue = parseFloat(value) || 0;
    updateItem(rowNumber, { market_value: marketValue });
  };

  const handleMaturityChange = async (
    rowNumber: number,
    min: number | null,
    max: number | null
  ) => {
    const item = matchedItems.find((i) => i.csv_row_number === rowNumber);
    if (!item) return;

    updateItem(rowNumber, { maturity_min: min, maturity_max: max });

    // Auto-lookup haircut if not manually overridden
    if (item.haircut_source === 'auto' && item.matched_csa_description) {
      try {
        const result = await lookupHaircut(
          documentId,
          item.matched_csa_description,
          item.valuation_scenario,
          min,
          max
        );

        updateItem(rowNumber, {
          maturity_min: min,
          maturity_max: max,
          haircut_rate: result.haircut || 0,
          matched_maturity_bucket_min: result.bucket_min,
          matched_maturity_bucket_max: result.bucket_max,
          warnings: result.warnings,
        });
      } catch (error) {
        console.error('Failed to lookup haircut:', error);
      }
    }
  };

  const handleCollateralTypeChange = async (rowNumber: number, csaDescription: string) => {
    const item = matchedItems.find((i) => i.csv_row_number === rowNumber);
    if (!item) return;

    // Reset haircut source to auto when changing type
    updateItem(rowNumber, {
      matched_csa_description: csaDescription,
      haircut_source: 'auto',
    });

    // Lookup new haircut
    try {
      const result = await lookupHaircut(
        documentId,
        csaDescription,
        item.valuation_scenario,
        item.maturity_min,
        item.maturity_max
      );

      updateItem(rowNumber, {
        matched_csa_description: csaDescription,
        haircut_rate: result.haircut || 0,
        matched_maturity_bucket_min: result.bucket_min,
        matched_maturity_bucket_max: result.bucket_max,
        haircut_source: 'auto',
        warnings: result.warnings,
      });
    } catch (error) {
      console.error('Failed to lookup haircut:', error);
    }
  };

  const handleScenarioChange = async (rowNumber: number, scenario: string) => {
    const item = matchedItems.find((i) => i.csv_row_number === rowNumber);
    if (!item) return;

    updateItem(rowNumber, { valuation_scenario: scenario });

    // Auto-lookup haircut if not manually overridden
    if (item.haircut_source === 'auto' && item.matched_csa_description) {
      try {
        const result = await lookupHaircut(
          documentId,
          item.matched_csa_description,
          scenario,
          item.maturity_min,
          item.maturity_max
        );

        updateItem(rowNumber, {
          valuation_scenario: scenario,
          haircut_rate: result.haircut || 0,
          matched_maturity_bucket_min: result.bucket_min,
          matched_maturity_bucket_max: result.bucket_max,
          warnings: result.warnings,
        });
      } catch (error) {
        console.error('Failed to lookup haircut:', error);
      }
    }
  };

  const handleHaircutChange = (rowNumber: number, value: string) => {
    const haircut = parseFloat(value) / 100 || 0; // Convert percentage to decimal
    updateItem(rowNumber, {
      haircut_rate: haircut,
      haircut_source: 'manual_override',
    });
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) {
      return 'bg-green-100 text-green-800';
    } else if (confidence >= 0.5) {
      return 'bg-yellow-100 text-yellow-800';
    } else {
      return 'bg-red-100 text-red-800';
    }
  };

  // Get unique scenarios from eligible collateral
  const availableScenarios = Array.from(
    new Set(
      eligibleCollateral.flatMap((nc) =>
        'rating_events' in nc && Array.isArray(nc.rating_event) ? nc.rating_event : []
      )
    )
  );

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900">Review & Edit Matched Collateral</h3>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Row</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">
                Description
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">
                Market Value
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600 min-w-[160px]">
                Maturity Range
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600 min-w-[180px]">
                Matched Collateral
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600 min-w-[140px]">
                Matched Bucket
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Scenario</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Haircut %</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Warnings</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-600"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {matchedItems.map((item) => (
              <tr key={item.csv_row_number} className="hover:bg-gray-50">
                {/* Row Number */}
                <td className="px-3 py-3 text-gray-600 font-mono text-xs">
                  #{item.csv_row_number}
                </td>

                {/* Description */}
                <td className="px-3 py-3">
                  <input
                    type="text"
                    value={item.csv_description}
                    onChange={(e) => handleDescriptionChange(item.csv_row_number, e.target.value)}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </td>

                {/* Market Value */}
                <td className="px-3 py-3">
                  <input
                    type="number"
                    value={item.market_value}
                    onChange={(e) => handleMarketValueChange(item.csv_row_number, e.target.value)}
                    className="w-32 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </td>

                {/* Maturity Range */}
                <td className="px-3 py-3 min-w-[160px]">
                  <MaturityRangeInput
                    minYears={item.maturity_min}
                    maxYears={item.maturity_max}
                    onChange={(min, max) => handleMaturityChange(item.csv_row_number, min, max)}
                  />
                </td>

                {/* Matched Collateral Type */}
                <td className="px-3 py-3 min-w-[180px]">
                  <div className="space-y-1">
                    <select
                      value={item.matched_csa_description || ''}
                      onChange={(e) =>
                        handleCollateralTypeChange(item.csv_row_number, e.target.value)
                      }
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="">Select...</option>
                      {eligibleCollateral.map((nc, idx) => (
                        <option key={idx} value={nc.base_description}>
                          {nc.base_description}
                        </option>
                      ))}
                    </select>
                    {item.match_confidence > 0 && (
                      <div className="flex items-center gap-1">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${getConfidenceBadge(
                            item.match_confidence
                          )}`}
                        >
                          {(item.match_confidence * 100).toFixed(0)}% match
                        </span>
                        <button
                          onClick={() => toggleTooltip(item.csv_row_number)}
                          className="p-0.5 hover:bg-gray-200 rounded"
                          title="View reasoning"
                        >
                          <Info className="w-3 h-3 text-gray-500" />
                        </button>
                      </div>
                    )}
                    {expandedTooltips.has(item.csv_row_number) && (
                      <div className="mt-1 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-gray-700">
                        {item.match_reasoning}
                      </div>
                    )}
                  </div>
                </td>

                {/* Matched Bucket */}
                <td className="px-3 py-3 text-xs text-gray-600 min-w-[140px]">
                  {formatMaturityRange(
                    item.matched_maturity_bucket_min,
                    item.matched_maturity_bucket_max
                  )}
                </td>

                {/* Valuation Scenario */}
                <td className="px-3 py-3">
                  <select
                    value={item.valuation_scenario}
                    onChange={(e) => handleScenarioChange(item.csv_row_number, e.target.value)}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {availableScenarios.map((scenario) => (
                      <option key={scenario} value={scenario}>
                        {scenario}
                      </option>
                    ))}
                  </select>
                </td>

                {/* Haircut */}
                <td className="px-3 py-3">
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={((item.haircut_rate || 0) * 100).toFixed(2)}
                      onChange={(e) => handleHaircutChange(item.csv_row_number, e.target.value)}
                      step="0.01"
                      className="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    {item.haircut_source === 'manual_override' ? (
                      <Unlock className="w-4 h-4 text-orange-500" title="Manually overridden" />
                    ) : (
                      <Lock className="w-4 h-4 text-green-500" title="Auto-populated" />
                    )}
                  </div>
                </td>

                {/* Warnings */}
                <td className="px-3 py-3">
                  {item.warnings.length > 0 && (
                    <button
                      onClick={() => toggleTooltip(item.csv_row_number + 1000)}
                      className="flex items-center gap-1 px-2 py-1 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800 hover:bg-yellow-100"
                      title="View warnings"
                    >
                      <AlertTriangle className="w-3 h-3" />
                      {item.warnings.length}
                    </button>
                  )}
                  {expandedTooltips.has(item.csv_row_number + 1000) && (
                    <div className="absolute mt-1 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-gray-700 shadow-lg z-10 max-w-xs">
                      <ul className="list-disc list-inside space-y-1">
                        {item.warnings.map((warning, idx) => (
                          <li key={idx}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </td>

                {/* Remove */}
                <td className="px-3 py-3">
                  <button
                    onClick={() => onRemoveItem(item.csv_row_number)}
                    className="p-1 hover:bg-red-100 rounded text-red-600 transition-colors"
                    title="Remove item"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
