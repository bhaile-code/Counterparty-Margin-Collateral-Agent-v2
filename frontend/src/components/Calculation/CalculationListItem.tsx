/**
 * CalculationListItem - Displays a single calculation in a list view
 */

import { Calendar, TrendingUp, TrendingDown, MinusCircle, FileText, Sparkles } from 'lucide-react';
import { formatCurrency, formatDate } from '../../utils/formatting';
import type { CalculationSummary } from '../../types/calculations';

interface CalculationListItemProps {
  calculation: CalculationSummary;
  onClick: () => void;
}

export function CalculationListItem({ calculation, onClick }: CalculationListItemProps) {
  const {
    calculation_date,
    net_exposure,
    party_perspective,
    action,
    amount,
    currency,
    counterparty_name,
    has_explanation,
    has_formula_pattern,
  } = calculation;

  const actionConfig: Record<string, any> = {
    CALL: {
      label: 'Call',
      icon: TrendingUp,
      bgColor: 'bg-red-50',
      textColor: 'text-red-700',
      iconColor: 'text-red-500',
      badgeColor: 'bg-red-100 text-red-700',
    },
    RETURN: {
      label: 'Return',
      icon: TrendingDown,
      bgColor: 'bg-green-50',
      textColor: 'text-green-700',
      iconColor: 'text-green-500',
      badgeColor: 'bg-green-100 text-green-700',
    },
    NO_ACTION: {
      label: 'No Action',
      icon: MinusCircle,
      bgColor: 'bg-gray-50',
      textColor: 'text-gray-700',
      iconColor: 'text-gray-500',
      badgeColor: 'bg-gray-100 text-gray-700',
    },
  };

  const config = actionConfig[action] || actionConfig.NO_ACTION;
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-all cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bgColor}`}>
            <Icon className={`w-5 h-5 ${config.iconColor}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-semibold ${config.badgeColor} px-2 py-0.5 rounded`}>
                {config.label}
              </span>
              <span className="text-xs text-gray-500">
                {party_perspective === 'party_a' ? 'Party A' : 'Party B'} Perspective
              </span>
            </div>
            <p className={`text-lg font-bold mt-1 ${config.textColor}`}>
              {formatCurrency(amount, currency)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {has_explanation && (
            <div className="p-1 rounded bg-purple-100" title="Has explanation">
              <Sparkles className="w-4 h-4 text-purple-600" />
            </div>
          )}
          {has_formula_pattern && (
            <div className="p-1 rounded bg-blue-100" title="Has formula pattern">
              <FileText className="w-4 h-4 text-blue-600" />
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-gray-500 text-xs">Date</p>
          <div className="flex items-center gap-1 mt-0.5">
            <Calendar className="w-3 h-3 text-gray-400" />
            <p className="font-medium text-gray-800">{formatDate(calculation_date)}</p>
          </div>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Net Exposure</p>
          <p className="font-medium text-gray-800 mt-0.5">
            {formatCurrency(net_exposure, currency)}
          </p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Counterparty</p>
          <p className="font-medium text-gray-800 mt-0.5 truncate" title={counterparty_name}>
            {counterparty_name || 'Unknown'}
          </p>
        </div>
      </div>

      <div className="mt-2 text-xs text-blue-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        Click to view full results →
      </div>
    </button>
  );
}
