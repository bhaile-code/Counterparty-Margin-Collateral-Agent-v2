/**
 * CalculationSummaryCard - Displays margin call calculation summary with action indicator
 */

import { TrendingUp, TrendingDown, MinusCircle } from 'lucide-react';
import { formatCurrency, formatDate } from '../../utils/formatting';
import type { MarginCall } from '../../types/calculations';

interface CalculationSummaryCardProps {
  marginCall: MarginCall;
}

export function CalculationSummaryCard({ marginCall }: CalculationSummaryCardProps) {
  const { action, amount, currency, calculation_date, counterparty_name } = marginCall;

  // Action configuration
  const actionConfig = {
    CALL: {
      label: 'Margin Call',
      description: 'Counterparty must post additional collateral',
      icon: TrendingUp,
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      textColor: 'text-red-800',
      iconColor: 'text-red-500',
      badgeColor: 'bg-red-500',
    },
    RETURN: {
      label: 'Collateral Return',
      description: 'Counterparty can request collateral back',
      icon: TrendingDown,
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      textColor: 'text-green-800',
      iconColor: 'text-green-500',
      badgeColor: 'bg-green-500',
    },
    NO_ACTION: {
      label: 'No Action Required',
      description: 'Current collateral is adequate',
      icon: MinusCircle,
      bgColor: 'bg-gray-50',
      borderColor: 'border-gray-200',
      textColor: 'text-gray-800',
      iconColor: 'text-gray-500',
      badgeColor: 'bg-gray-500',
    },
  };

  // Fallback to NO_ACTION if action is not recognized
  const config = actionConfig[action] || actionConfig.NO_ACTION;
  const Icon = config.icon;

  return (
    <div className={`rounded-lg border-2 ${config.borderColor} ${config.bgColor} p-6`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bgColor}`}>
            <Icon className={`w-6 h-6 ${config.iconColor}`} />
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${config.textColor}`}>{config.label}</h3>
            <p className="text-sm text-gray-600">{config.description}</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-medium text-white ${config.badgeColor}`}>
          {action?.replace('_', ' ') || 'Unknown'}
        </div>
      </div>

      {/* Amount Display */}
      <div className="mb-6">
        <p className="text-sm text-gray-500 mb-1">Amount</p>
        <p className={`text-3xl font-bold ${config.textColor}`}>
          {formatCurrency(amount, currency)}
        </p>
      </div>

      {/* Metadata Grid */}
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
        <div>
          <p className="text-sm text-gray-500">Counterparty</p>
          <p className="font-medium text-gray-800">{counterparty_name || 'Unknown'}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Calculation Date</p>
          <p className="font-medium text-gray-800">{formatDate(calculation_date)}</p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Net Exposure:</span>
          <span className="font-medium text-gray-800">{formatCurrency(marginCall.net_exposure, currency)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Threshold:</span>
          <span className="font-medium text-gray-800">{formatCurrency(marginCall.threshold, currency)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Posted Collateral:</span>
          <span className="font-medium text-gray-800">
            {formatCurrency(
              marginCall.posted_collateral_items.reduce((sum, item) => sum + item.market_value, 0),
              currency
            )}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Effective Collateral:</span>
          <span className="font-medium text-gray-800">{formatCurrency(marginCall.effective_collateral, currency)}</span>
        </div>
        <div className="flex justify-between text-sm font-semibold pt-2 border-t border-gray-200">
          <span className="text-gray-700">Exposure Above Threshold:</span>
          <span className={config.textColor}>{formatCurrency(marginCall.exposure_above_threshold, currency)}</span>
        </div>
      </div>
    </div>
  );
}
