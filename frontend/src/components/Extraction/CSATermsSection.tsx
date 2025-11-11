/**
 * CSATermsSection Component
 *
 * Displays extracted CSA terms in an organized grid layout.
 * Groups related fields and shows confidence scores for each field.
 */

import type { CSATerms } from '../../types/documents';
import { FieldCard } from './FieldCard';
import { formatCurrency, formatDate } from '../../utils/formatting';

interface CSATermsSectionProps {
  csaTerms: CSATerms;
}

export function CSATermsSection({ csaTerms }: CSATermsSectionProps) {
  const {
    party_a,
    party_b,
    party_a_threshold,
    party_b_threshold,
    party_a_minimum_transfer_amount,
    party_b_minimum_transfer_amount,
    party_a_independent_amount,
    party_b_independent_amount,
    rounding,
    valuation_agent,
    effective_date,
    confidence_scores,
  } = csaTerms;

  // DEBUG: Log data to verify values are received
  console.log('CSATermsSection - Full csaTerms:', csaTerms);
  console.log('CSATermsSection - party_a_threshold:', party_a_threshold, 'type:', typeof party_a_threshold);
  console.log('CSATermsSection - party_b_threshold:', party_b_threshold, 'type:', typeof party_b_threshold);
  console.log('CSATermsSection - confidence_scores:', confidence_scores);
  console.log('CSATermsSection - confidence_scores keys:', confidence_scores ? Object.keys(confidence_scores) : 'undefined');

  return (
    <div className="bg-gray-50 rounded-lg p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">
        Extracted CSA Terms
      </h2>

      {/* Party Identification */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <FieldCard
          label="Party A"
          value={party_a}
          confidence={confidence_scores?.['agreement_info.party_a']}
        />

        <FieldCard
          label="Party B"
          value={party_b}
          confidence={confidence_scores?.['agreement_info.party_b']}
        />

        <FieldCard
          label="Effective Date"
          value={effective_date ? formatDate(effective_date) : undefined}
          confidence={confidence_scores?.['agreement_info.effective_date']}
        />

        <FieldCard
          label="Rounding Amount"
          value={formatCurrency(rounding)}
          confidence={confidence_scores?.['core_margin_terms.rounding']}
        />

        {valuation_agent && (
          <FieldCard
            label="Valuation Agent"
            value={valuation_agent}
            confidence={confidence_scores?.['agreement_info.valuation_agent']}
          />
        )}
      </div>

      {/* Party-Specific Margin Terms - Side by Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Party A Terms */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">
            Party A Terms
          </h3>
          <div className="space-y-3">
            <FieldCard
              label="Threshold"
              value={party_a_threshold !== undefined ? formatCurrency(party_a_threshold) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_a_threshold']}
              valueClassName="text-navy-600"
            />
            <FieldCard
              label="Minimum Transfer Amount"
              value={party_a_minimum_transfer_amount !== undefined ? formatCurrency(party_a_minimum_transfer_amount) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_a_minimum_transfer_amount']}
            />
            <FieldCard
              label="Independent Amount"
              value={party_a_independent_amount !== undefined ? formatCurrency(party_a_independent_amount) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_a_independent_amount']}
            />
          </div>
        </div>

        {/* Party B Terms */}
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 border-b pb-2">
            Party B Terms
          </h3>
          <div className="space-y-3">
            <FieldCard
              label="Threshold"
              value={party_b_threshold !== undefined ? formatCurrency(party_b_threshold) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_b_threshold']}
              valueClassName="text-navy-600"
            />
            <FieldCard
              label="Minimum Transfer Amount"
              value={party_b_minimum_transfer_amount !== undefined ? formatCurrency(party_b_minimum_transfer_amount) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_b_minimum_transfer_amount']}
            />
            <FieldCard
              label="Independent Amount"
              value={party_b_independent_amount !== undefined ? formatCurrency(party_b_independent_amount) : undefined}
              confidence={confidence_scores?.['core_margin_terms.party_b_independent_amount']}
            />
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <div className="flex items-center gap-6 text-sm text-gray-600">
          <div>
            <span className="font-medium">Total Fields Extracted:</span>{' '}
            {Object.keys(confidence_scores || {}).length}
          </div>
          {confidence_scores && (
            <div>
              <span className="font-medium">Average Confidence:</span>{' '}
              {Math.round(
                Object.values(confidence_scores).reduce((a, b) => a + b, 0) /
                Object.values(confidence_scores).length * 100
              )}%
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
