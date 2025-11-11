/**
 * CollateralList Component
 *
 * Displays normalized collateral items in a table with maturity buckets and haircuts.
 * Shows all eligible collateral types extracted from the CSA document.
 * Rating events/scenarios are displayed as parent column groups.
 */

import React from 'react';
import type { NormalizedCollateral } from '../../types/collateral';
import { StatusBadge } from '../shared';

interface CollateralListProps {
  collateral: NormalizedCollateral[];
}

export function CollateralList({ collateral = [] }: CollateralListProps) {
  // Format collateral type for display
  const formatType = (type: string): string => {
    return type
      .split('_')
      .map(word => word.charAt(0) + word.slice(1).toLowerCase())
      .join(' ');
  };

  // Format maturity range
  const formatMaturity = (minYears?: number | null, maxYears?: number | null): string => {
    // Check for null or undefined (nullish values)
    if ((minYears === null || minYears === undefined) &&
        (maxYears === null || maxYears === undefined)) {
      return 'All Maturities';
    }
    if (minYears != null && maxYears != null) {
      return `${minYears}-${maxYears} years`;
    }
    if (minYears != null) {
      return `${minYears}+ years`;
    }
    if (maxYears != null) {
      return `Up to ${maxYears} ${maxYears === 1 ? 'year' : 'years'}`;
    }
    return 'All Maturities';
  };

  // Format percentage
  const formatPercent = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  // Truncate text for display
  const truncateText = (text: string | undefined, maxLength: number = 40): string => {
    if (!text) return '—';
    if (text.length <= maxLength) return text;
    return `${text.substring(0, maxLength)}...`;
  };

  // Pivot collateral data by type+maturity, grouping scenarios
  interface PivotedRow {
    type: string;
    description?: string;
    maturityMin?: number;
    maturityMax?: number;
    scenarios: Map<string, { haircut: number; valuation: number }>;
    confidence?: number;
  }

  const pivotData = (): { rows: PivotedRow[]; scenarios: string[] } => {
    const rowMap = new Map<string, PivotedRow>();
    const scenarioSet = new Set<string>();

    // Guard against undefined or non-array collateral
    if (!collateral || !Array.isArray(collateral)) {
      return { rows: [], scenarios: [] };
    }

    collateral.forEach((item) => {
      const ratingEvent = item.rating_event || 'Default';
      scenarioSet.add(ratingEvent);

      if (item.maturity_buckets && item.maturity_buckets.length > 0) {
        // Process each maturity bucket
        item.maturity_buckets.forEach((bucket) => {
          const key = `${item.standardized_type}|${bucket.min_years ?? 'null'}|${bucket.max_years ?? 'null'}`;

          if (!rowMap.has(key)) {
            rowMap.set(key, {
              type: item.standardized_type,
              description: item.base_description,
              maturityMin: bucket.min_years,
              maturityMax: bucket.max_years,
              scenarios: new Map(),
              confidence: item.confidence,
            });
          }

          const row = rowMap.get(key)!;
          row.scenarios.set(ratingEvent, {
            haircut: bucket.haircut,
            valuation: bucket.valuation_percentage,
          });
        });
      } else {
        // Flat values (no maturity buckets)
        const key = `${item.standardized_type}|flat`;

        if (!rowMap.has(key)) {
          rowMap.set(key, {
            type: item.standardized_type,
            description: item.base_description,
            scenarios: new Map(),
            confidence: item.confidence,
          });
        }

        const row = rowMap.get(key)!;
        row.scenarios.set(ratingEvent, {
          haircut: item.flat_haircut ?? 0,
          valuation: item.flat_valuation_percentage ?? 0,
        });
      }
    });

    return {
      rows: Array.from(rowMap.values()),
      scenarios: Array.from(scenarioSet).sort(),
    };
  };

  const { rows: pivotedRows, scenarios } = pivotData();
  const showValuation = scenarios.length <= 3;

  if (collateral.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          Eligible Collateral
        </h2>
        <p className="text-gray-500 italic">No eligible collateral found.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">
          Eligible Collateral ({collateral.length} types)
        </h2>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              {/* First header row: Parent scenario columns */}
              <tr>
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r border-gray-200"
                  rowSpan={2}
                >
                  Collateral Type
                </th>
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r border-gray-200"
                  rowSpan={2}
                >
                  Collateral Description
                </th>
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r border-gray-200"
                  rowSpan={2}
                >
                  Maturity Range
                </th>
                {scenarios.map((scenario) => (
                  <th
                    key={scenario}
                    className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase tracking-wider border-r border-gray-200 bg-gray-100"
                    colSpan={showValuation ? 2 : 1}
                  >
                    {scenario}
                  </th>
                ))}
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  rowSpan={2}
                >
                  Confidence
                </th>
              </tr>
              {/* Second header row: Sub-columns (Haircut / Valuation) */}
              <tr>
                {scenarios.map((scenario) => (
                  <React.Fragment key={`${scenario}-sub`}>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-l border-gray-200">
                      Haircut
                    </th>
                    {showValuation && (
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r border-gray-200">
                        Val %
                      </th>
                    )}
                  </React.Fragment>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {pivotedRows.map((row, index) => (
                <tr key={index} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 border-r border-gray-100">
                    <div className="font-semibold">{formatType(row.type)}</div>
                  </td>
                  <td
                    className="px-4 py-3 text-sm text-gray-600 border-r border-gray-100 max-w-xs truncate cursor-help"
                    title={row.description || ''}
                  >
                    {truncateText(row.description, 40)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 border-r border-gray-100">
                    {formatMaturity(row.maturityMin, row.maturityMax)}
                  </td>
                  {scenarios.map((scenario) => {
                    const data = row.scenarios.get(scenario);
                    return (
                      <React.Fragment key={`${index}-${scenario}`}>
                        <td className="px-4 py-3 text-sm font-semibold text-gray-900 border-l border-gray-100">
                          {data ? formatPercent(data.haircut) : '—'}
                        </td>
                        {showValuation && (
                          <td className="px-4 py-3 text-sm text-gray-700 border-r border-gray-100">
                            {data ? formatPercent(data.valuation) : '—'}
                          </td>
                        )}
                      </React.Fragment>
                    );
                  })}
                  <td className="px-4 py-3 text-sm">
                    {row.confidence !== undefined ? (
                      <StatusBadge
                        variant={row.confidence >= 0.8 ? 'success' : row.confidence >= 0.6 ? 'warning' : 'error'}
                        size="sm"
                      >
                        {Math.round(row.confidence * 100)}%
                      </StatusBadge>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Notes section if any collateral has notes */}
      {collateral.some(item => item.notes) && (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">Additional Notes:</h3>
          <ul className="space-y-1 text-sm text-blue-800">
            {collateral
              .filter(item => item.notes)
              .map((item, index) => (
                <li key={index}>
                  <span className="font-medium">{formatType(item.standardized_type)}:</span> {item.notes}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
