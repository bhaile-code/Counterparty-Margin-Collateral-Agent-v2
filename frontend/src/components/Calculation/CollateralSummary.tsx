/**
 * CollateralSummary Component
 *
 * Displays aggregate statistics about matched collateral items
 * Shows total values, effective values, warnings, and breakdowns
 */

import { AlertTriangle, Info, TrendingUp } from 'lucide-react';
import type { MatchedCollateralItem } from '../../types/collateral';

interface CollateralSummaryProps {
  matchedItems: MatchedCollateralItem[];
}

export function CollateralSummary({ matchedItems }: CollateralSummaryProps) {
  if (matchedItems.length === 0) {
    return null;
  }

  // Calculate totals
  const totalMarketValue = matchedItems.reduce((sum, item) => sum + item.market_value, 0);

  const totalEffectiveValue = matchedItems.reduce((sum, item) => {
    const haircut = item.haircut_rate || 0;
    return sum + item.market_value * (1 - haircut);
  }, 0);

  const averageHaircut =
    matchedItems.reduce((sum, item) => {
      const haircut = item.haircut_rate || 0;
      return sum + haircut * item.market_value;
    }, 0) / (totalMarketValue || 1);

  // Count warnings and confidence
  const warningCount = matchedItems.reduce((sum, item) => sum + item.warnings.length, 0);

  const lowConfidenceCount = matchedItems.filter((item) => item.match_confidence < 0.7).length;

  // Group by collateral type
  const byType = matchedItems.reduce((acc, item) => {
    const type = item.matched_csa_description || 'Unknown';
    if (!acc[type]) {
      acc[type] = { count: 0, value: 0 };
    }
    acc[type].count++;
    acc[type].value += item.market_value;
    return acc;
  }, {} as Record<string, { count: number; value: number }>);

  // Group by scenario
  const byScenario = matchedItems.reduce((acc, item) => {
    const scenario = item.valuation_scenario || 'Unknown';
    if (!acc[scenario]) {
      acc[scenario] = { count: 0, value: 0 };
    }
    acc[scenario].count++;
    acc[scenario].value += item.market_value;
    return acc;
  }, {} as Record<string, { count: number; value: number }>);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return (value * 100).toFixed(1) + '%';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900">Collateral Summary</h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Main Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-500 font-medium">Total Items</p>
            <p className="text-2xl font-bold text-gray-900">{matchedItems.length}</p>
          </div>

          <div>
            <p className="text-xs text-gray-500 font-medium">Market Value</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(totalMarketValue)}
            </p>
          </div>

          <div>
            <p className="text-xs text-gray-500 font-medium">Effective Value</p>
            <p className="text-2xl font-bold text-green-600">
              {formatCurrency(totalEffectiveValue)}
            </p>
            <p className="text-xs text-gray-500 mt-1">After haircuts</p>
          </div>

          <div>
            <p className="text-xs text-gray-500 font-medium">Avg Haircut</p>
            <p className="text-2xl font-bold text-gray-900">{formatPercent(averageHaircut)}</p>
          </div>
        </div>

        {/* Warnings & Confidence */}
        {(warningCount > 0 || lowConfidenceCount > 0) && (
          <div className="flex items-center gap-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            {warningCount > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-yellow-600" />
                <span className="font-medium text-yellow-900">
                  {warningCount} {warningCount === 1 ? 'Warning' : 'Warnings'}
                </span>
              </div>
            )}

            {lowConfidenceCount > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <Info className="w-4 h-4 text-blue-600" />
                <span className="font-medium text-blue-900">
                  {lowConfidenceCount} Low Confidence {lowConfidenceCount === 1 ? 'Match' : 'Matches'} (&lt;70%)
                </span>
              </div>
            )}
          </div>
        )}

        {/* Breakdown by Collateral Type */}
        {Object.keys(byType).length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              By Collateral Type
            </h4>
            <div className="space-y-1">
              {Object.entries(byType)
                .sort((a, b) => b[1].value - a[1].value)
                .map(([type, data]) => (
                  <div key={type} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">
                      {type} <span className="text-gray-500">({data.count})</span>
                    </span>
                    <span className="font-medium text-gray-900">{formatCurrency(data.value)}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Breakdown by Scenario */}
        {Object.keys(byScenario).length > 1 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-2">By Valuation Scenario</h4>
            <div className="space-y-1">
              {Object.entries(byScenario)
                .sort((a, b) => b[1].value - a[1].value)
                .map(([scenario, data]) => (
                  <div key={scenario} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">
                      {scenario} <span className="text-gray-500">({data.count})</span>
                    </span>
                    <span className="font-medium text-gray-900">{formatCurrency(data.value)}</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
