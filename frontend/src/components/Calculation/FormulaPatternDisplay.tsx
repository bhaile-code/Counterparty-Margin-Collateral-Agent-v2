/**
 * FormulaPatternDisplay - Displays extracted formula patterns from CSA documents
 *
 * Shows pattern analysis including:
 * - Delivery/Return amount patterns (greatest_of, sum_of, etc.)
 * - Threshold structures
 * - Haircut dependencies
 * - Complexity scoring
 */

import { FileText, TrendingUp, Shield, Info, AlertCircle } from 'lucide-react';

interface FormulaPattern {
  pattern_name: string;
  pattern_type: string;
  components: string[];
  clause_text: string;
  source_page: number;
  confidence: number;
  variations_detected: string[];
  reasoning?: string;
}

interface ThresholdStructure {
  structure_type: string;
  party_a_base: string | number;
  party_b_base: string | number;
  triggers?: any;
  source_clause: string;
  source_page: number;
  confidence: number;
}

interface CollateralHaircutStructure {
  dependency_type: string;
  table_reference: string;
  source_page: number;
  varies_by: string[];
  confidence: number;
  rating_scenarios?: string[];
}

interface FormulaPatternResult {
  document_id: string;
  extraction_timestamp: string;
  patterns: Record<string, FormulaPattern>;
  threshold_structure: ThresholdStructure;
  haircut_structure: CollateralHaircutStructure;
  complexity_score: number;
  overall_confidence: number;
  variations_summary: string[];
}

interface FormulaPatternDisplayProps {
  patterns: FormulaPatternResult;
}

export function FormulaPatternDisplay({ patterns }: FormulaPatternDisplayProps) {
  // Get pattern badge color based on type
  const getPatternBadgeColor = (type: string): string => {
    const colors: Record<string, string> = {
      greatest_of: 'bg-green-100 text-green-800 border-green-200',
      sum_of: 'bg-blue-100 text-blue-800 border-blue-200',
      conditional: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      single_rating: 'bg-purple-100 text-purple-800 border-purple-200',
      other: 'bg-gray-100 text-gray-800 border-gray-200',
    };
    return colors[type] || colors.other;
  };

  // Get complexity label and color
  const getComplexityInfo = (score: number): { label: string; color: string; bgColor: string } => {
    if (score < 0.3) {
      return { label: 'Simple', color: 'text-green-700', bgColor: 'bg-green-50 border-green-200' };
    }
    if (score < 0.6) {
      return { label: 'Moderate', color: 'text-yellow-700', bgColor: 'bg-yellow-50 border-yellow-200' };
    }
    return { label: 'Complex', color: 'text-red-700', bgColor: 'bg-red-50 border-red-200' };
  };

  // Get CSA type label
  const getCSATypeLabel = (): string => {
    if (!patterns.patterns.delivery_amount) return 'Unknown';

    const deliveryPattern = patterns.patterns.delivery_amount;

    if (deliveryPattern.pattern_type === 'greatest_of') {
      return deliveryPattern.components.length >= 2
        ? 'Dual Agency - Greatest Of'
        : 'Multi-Component - Greatest Of';
    } else if (deliveryPattern.pattern_type === 'sum_of') {
      return 'Multi-Component - Sum Of';
    } else if (deliveryPattern.pattern_type === 'single_rating') {
      return 'Single Rating Agency';
    } else if (deliveryPattern.pattern_type === 'conditional') {
      return 'Conditional Logic';
    }
    return 'Custom Pattern';
  };

  const complexityInfo = getComplexityInfo(patterns.complexity_score);
  const csaType = getCSATypeLabel();

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-blue-100">
            <FileText className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-800">CSA Formula Pattern Analysis</h3>
            <p className="text-sm text-gray-600">{csaType}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Complexity */}
          <div className={`p-4 rounded-lg border ${complexityInfo.bgColor}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">Complexity</span>
              <span className={`text-lg font-bold ${complexityInfo.color}`}>
                {complexityInfo.label}
              </span>
            </div>
            <div className="mt-2 text-xs text-gray-600">
              Score: {(patterns.complexity_score * 100).toFixed(0)}%
            </div>
          </div>

          {/* Confidence */}
          <div className="p-4 rounded-lg border bg-blue-50 border-blue-200">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">Extraction Confidence</span>
              <span className="text-lg font-bold text-blue-700">
                {(patterns.overall_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="mt-2 text-xs text-gray-600">
              Pattern recognition quality
            </div>
          </div>
        </div>
      </div>

      {/* Delivery Amount Pattern */}
      {patterns.patterns.delivery_amount && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-gray-800 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-gray-600" />
                Delivery Amount Pattern
              </h4>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium border ${getPatternBadgeColor(
                  patterns.patterns.delivery_amount.pattern_type
                )}`}
              >
                {patterns.patterns.delivery_amount.pattern_type.replace('_', ' ').toUpperCase()}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-4">
            {/* Components */}
            {patterns.patterns.delivery_amount.components.length > 0 && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">Components:</div>
                <div className="flex flex-wrap gap-2">
                  {patterns.patterns.delivery_amount.components.map((comp, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-gray-100 text-gray-700 rounded-md text-sm font-mono"
                    >
                      {comp}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Clause Text */}
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">CSA Clause:</div>
              <blockquote className="border-l-4 border-blue-400 pl-4 py-2 bg-gray-50 text-sm text-gray-700 italic">
                {patterns.patterns.delivery_amount.clause_text}
              </blockquote>
            </div>

            {/* Source & Confidence */}
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-200">
              <div className="text-sm">
                <span className="text-gray-600">Source Page:</span>{' '}
                <span className="font-medium text-gray-800">
                  {patterns.patterns.delivery_amount.source_page}
                </span>
              </div>
              <div className="text-sm">
                <span className="text-gray-600">Confidence:</span>{' '}
                <span className="font-medium text-gray-800">
                  {(patterns.patterns.delivery_amount.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Variations */}
            {patterns.patterns.delivery_amount.variations_detected.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-600 mt-0.5" />
                  <div>
                    <div className="text-sm font-medium text-yellow-800 mb-1">
                      Variations Detected
                    </div>
                    <ul className="text-sm text-yellow-700 space-y-1">
                      {patterns.patterns.delivery_amount.variations_detected.map((variation, idx) => (
                        <li key={idx} className="flex items-start gap-1">
                          <span>•</span>
                          <span>{variation}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Threshold Structure */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h4 className="font-semibold text-gray-800 flex items-center gap-2">
            <Shield className="w-4 h-4 text-gray-600" />
            Threshold Structure
          </h4>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-md text-sm font-medium">
              {patterns.threshold_structure.structure_type.replace('_', ' ').toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Party A Threshold</div>
              <div className="text-lg font-semibold text-gray-800">
                {String(patterns.threshold_structure.party_a_base).toUpperCase()}
              </div>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Party B Threshold</div>
              <div className="text-lg font-semibold text-gray-800">
                {String(patterns.threshold_structure.party_b_base).toUpperCase()}
              </div>
            </div>
          </div>

          {patterns.threshold_structure.triggers && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <Info className="w-4 h-4 text-blue-600 mt-0.5" />
                <div className="text-sm text-blue-700">
                  <div className="font-medium mb-1">Rating Triggers Present</div>
                  <div className="text-xs">
                    This CSA includes rating-dependent threshold adjustments
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="text-sm text-gray-600 pt-2 border-t border-gray-200">
            <span className="font-medium">Source:</span> Page{' '}
            {patterns.threshold_structure.source_page}
          </div>
        </div>
      </div>

      {/* Haircut Structure */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h4 className="font-semibold text-gray-800 flex items-center gap-2">
            <Shield className="w-4 h-4 text-gray-600" />
            Collateral Haircut Structure
          </h4>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-md text-sm font-medium">
              {patterns.haircut_structure.dependency_type.replace('_', ' ').toUpperCase()}
            </span>
          </div>

          {patterns.haircut_structure.varies_by.length > 0 && (
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">Varies By:</div>
              <div className="flex flex-wrap gap-2">
                {patterns.haircut_structure.varies_by.map((factor, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1 bg-gray-100 text-gray-700 rounded-md text-sm"
                  >
                    {factor.replace('_', ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {patterns.haircut_structure.rating_scenarios && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="text-sm text-purple-800">
                <div className="font-medium mb-1">
                  {patterns.haircut_structure.rating_scenarios.length} Rating Scenarios
                </div>
                <div className="text-xs text-purple-600">
                  Haircuts vary based on rating agency trigger events
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-gray-200">
            <div className="text-sm">
              <span className="text-gray-600">Table Reference:</span>{' '}
              <span className="font-medium text-gray-800">
                {patterns.haircut_structure.table_reference}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-gray-600">Source Page:</span>{' '}
              <span className="font-medium text-gray-800">
                {patterns.haircut_structure.source_page}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Pattern Comparison Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-5">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <div className="font-semibold mb-2">How This CSA Compares to Others</div>
            <p className="mb-2">
              This CSA uses a{' '}
              <strong>
                {patterns.patterns.delivery_amount?.pattern_type.replace('_', ' ') || 'standard'}
              </strong>{' '}
              pattern for Delivery Amount calculations. Other CSAs may use different approaches:
            </p>
            <ul className="space-y-1 text-xs text-blue-800">
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0">•</span>
                <span>
                  <strong>Single rating agency</strong> - Uses only one rating agency's requirements
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0">•</span>
                <span>
                  <strong>Sum of</strong> - Adds multiple components together
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0">•</span>
                <span>
                  <strong>Conditional</strong> - Different formulas based on trigger events
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0">•</span>
                <span>
                  <strong>Greatest of (Dual Agency)</strong> - Takes the higher of two rating
                  agencies' calculations
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Overall Variations Summary */}
      {patterns.variations_summary.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-yellow-900">
              <div className="font-semibold mb-2">Non-Standard Patterns Detected</div>
              <ul className="space-y-1 text-xs text-yellow-800">
                {patterns.variations_summary.map((variation, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="flex-shrink-0">•</span>
                    <span>{variation}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
