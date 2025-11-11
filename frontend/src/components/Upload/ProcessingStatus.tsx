import { Check, Loader2 } from 'lucide-react';
import type { ProcessingStatus as ProcessingStatusType } from '../../types/common';

interface ProcessingStep {
  key: keyof ProcessingStatusType;
  label: string;
  description: string;
}

const PROCESSING_STEPS: ProcessingStep[] = [
  {
    key: 'parsed',
    label: 'Parse Document',
    description: 'Analyzing document structure with LandingAI'
  },
  {
    key: 'extracted',
    label: 'Extract CSA Terms',
    description: 'Extracting key CSA fields and clauses'
  },
  {
    key: 'normalized',
    label: 'Normalize Collateral',
    description: 'AI-powered collateral table normalization'
  },
  {
    key: 'mapped_to_csa_terms',
    label: 'Map to System',
    description: 'Mapping to CSA terms format'
  }
];

interface ProcessingStatusProps {
  status: ProcessingStatusType;
  error?: string | null;
}

export function ProcessingStatus({ status, error }: ProcessingStatusProps) {
  const getCurrentStep = (): number => {
    if (status.mapped_to_csa_terms) return 4;
    if (status.normalized) return 3;
    if (status.extracted) return 2;
    if (status.parsed) return 1;
    return 0;
  };

  const currentStep = getCurrentStep();
  const isComplete = status.mapped_to_csa_terms;

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border-2 border-red-200 rounded-lg p-6 text-center">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">✗</span>
          </div>
          <h3 className="text-lg font-semibold text-red-900 mb-2">
            Processing Failed
          </h3>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="p-6">
        <div className="bg-green-50 border-2 border-green-200 rounded-lg p-6 text-center">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-6 h-6 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-green-900 mb-2">
            Processing Complete!
          </h3>
          <p className="text-sm text-green-700">
            Your CSA document has been successfully processed and is ready for review.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 text-center">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Processing Document
        </h3>
        <p className="text-sm text-gray-600">
          Step {currentStep} of {PROCESSING_STEPS.length}
        </p>
      </div>

      <div className="space-y-4">
        {PROCESSING_STEPS.map((step, index) => {
          const stepNumber = index + 1;
          const isCompleted = status[step.key] === true;
          const isActive = stepNumber === currentStep + 1;
          const isPending = stepNumber > currentStep + 1;

          return (
            <div
              key={step.key}
              className={`
                flex items-start gap-4 p-4 rounded-lg transition-colors
                ${isActive ? 'bg-blue-50 border-2 border-blue-200' : ''}
                ${isCompleted ? 'bg-green-50' : ''}
                ${isPending ? 'bg-gray-50' : ''}
              `}
            >
              {/* Step indicator */}
              <div className={`
                flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm
                ${isCompleted ? 'bg-green-500 text-white' : ''}
                ${isActive ? 'bg-blue-500 text-white' : ''}
                ${isPending ? 'bg-gray-300 text-gray-600' : ''}
              `}>
                {isCompleted ? (
                  <Check className="w-5 h-5" />
                ) : isActive ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  stepNumber
                )}
              </div>

              {/* Step content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={`
                    font-medium
                    ${isCompleted ? 'text-green-900' : ''}
                    ${isActive ? 'text-blue-900' : ''}
                    ${isPending ? 'text-gray-500' : ''}
                  `}>
                    {step.label}
                  </p>
                  {isCompleted && (
                    <span className="text-xs text-green-600 font-medium">
                      Complete
                    </span>
                  )}
                  {isActive && (
                    <span className="text-xs text-blue-600 font-medium">
                      In Progress
                    </span>
                  )}
                </div>
                <p className={`
                  text-sm mt-1
                  ${isCompleted ? 'text-green-700' : ''}
                  ${isActive ? 'text-blue-700' : ''}
                  ${isPending ? 'text-gray-400' : ''}
                `}>
                  {step.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="mt-6">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-500"
            style={{ width: `${(currentStep / PROCESSING_STEPS.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
