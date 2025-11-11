/**
 * Calculation Results Page - Display margin calculation results, steps, and AI explanation
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Download, RefreshCw, Sparkles, AlertCircle, FileCode } from 'lucide-react';
import { Button } from '../components/shared/Button';
import { Spinner } from '../components/shared/Spinner';
import {
  CalculationSummaryCard,
  CalculationStepItem,
  ExplanationPanel,
  AuditTrailTimeline,
} from '../components/Calculation';
import { FormulaPatternDisplay } from '../components/Calculation/FormulaPatternDisplay';
import { AuditScriptViewer } from '../components/Calculation/AuditScriptViewer';
import { getCalculation, generateExplanation, getExplanation } from '../api/calculations';
import { downloadMarginCallNotice, downloadAuditTrail } from '../api/exports';
import { getFormulaPatterns } from '../api/formula-patterns';
import { generateAuditScript, getAuditScript, type AuditScript } from '../api/script-generation';
import type { MarginCall, MarginCallExplanation } from '../types/calculations';
import type { FormulaPatternResult } from '../api/formula-patterns';

export function CalculationResultsPage() {
  const { calculationId } = useParams<{ calculationId: string }>();
  const navigate = useNavigate();

  // Calculation state
  const [calculation, setCalculation] = useState<MarginCall | null>(null);
  const [calculationResponse, setCalculationResponse] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Explanation state
  const [explanation, setExplanation] = useState<MarginCallExplanation | null>(null);
  const [isGeneratingExplanation, setIsGeneratingExplanation] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);

  // Formula pattern state
  const [formulaPatterns, setFormulaPatterns] = useState<FormulaPatternResult | null>(null);
  const [isLoadingPatterns, setIsLoadingPatterns] = useState(false);

  // Audit script state
  const [auditScript, setAuditScript] = useState<AuditScript | null>(null);
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [scriptError, setScriptError] = useState<string | null>(null);

  // Export state
  const [isExporting, setIsExporting] = useState(false);

  // Fetch calculation and explanation on mount
  useEffect(() => {
    async function fetchData() {
      if (!calculationId) {
        setError('Calculation ID is required');
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);

        // Fetch calculation response with flags
        const calcResponse = await getCalculation(calculationId);
        setCalculationResponse(calcResponse);
        setCalculation(calcResponse.margin_call);

        const documentId = calcResponse.document_id || calcResponse.margin_call.csa_terms_id;

        // Auto-fetch explanation if it exists
        if (calcResponse.has_explanation) {
          try {
            const explanationData = await getExplanation(calculationId);
            setExplanation(explanationData);
          } catch (err: any) {
            console.error('Error fetching explanation:', err);
          }
        }

        // Auto-fetch formula patterns if they exist
        if (calcResponse.has_formula_pattern && documentId) {
          try {
            setIsLoadingPatterns(true);
            const patternsData = await getFormulaPatterns(documentId);
            setFormulaPatterns(patternsData);
          } catch (err: any) {
            console.error('Error fetching patterns:', err);
          } finally {
            setIsLoadingPatterns(false);
          }
        }

        // Try to fetch audit script (if available)
        try {
          const scriptData = await getAuditScript(calculationId);
          setAuditScript(scriptData);
        } catch (err: any) {
          // Script doesn't exist yet - that's okay, only log unexpected errors
          if (err.response?.status !== 404) {
            console.error('Error fetching script:', err);
          }
        }

        setError(null);
      } catch (err) {
        console.error('Error fetching calculation:', err);
        setError('Failed to load calculation results. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [calculationId]);

  // Generate explanation
  const handleGenerateExplanation = async () => {
    if (!calculationId) return;

    setIsGeneratingExplanation(true);
    setExplanationError(null);

    try {
      const response = await generateExplanation(calculationId);
      setExplanation(response.explanation);
    } catch (err) {
      console.error('Error generating explanation:', err);
      setExplanationError('Failed to generate explanation. Please try again.');
    } finally {
      setIsGeneratingExplanation(false);
    }
  };

  // Export calculation results
  const handleExportCalculation = async () => {
    if (!calculationId || !calculation) return;

    setIsExporting(true);
    try {
      await downloadMarginCallNotice(calculationId, calculation.counterparty_name || 'Unknown', 'pdf');
    } catch (err) {
      console.error('Error exporting calculation:', err);
      alert('Failed to export calculation. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  // Export audit trail
  const handleExportAuditTrail = async () => {
    if (!calculationId || !calculation) return;

    setIsExporting(true);
    try {
      await downloadAuditTrail(calculationId, calculation.counterparty_name || 'Unknown', 'json');
    } catch (err) {
      console.error('Error exporting audit trail:', err);
      alert('Failed to export audit trail. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  // Generate audit script
  const handleGenerateScript = async () => {
    if (!calculationId) return;

    setIsGeneratingScript(true);
    setScriptError(null);

    try {
      const response = await generateAuditScript(calculationId);
      setAuditScript({
        script: response.script,
        generated_at: new Date().toISOString(),
        patterns_used: response.patterns_used,
        patterns_auto_extracted: response.patterns_auto_extracted,
        pattern_extraction_time_seconds: response.pattern_extraction_time_seconds,
        script_stats: response.script_stats,
      });
    } catch (err: any) {
      console.error('Error generating script:', err);
      const errorMessage = err.response?.data?.detail || 'Failed to generate audit script. Please try again.';
      setScriptError(errorMessage);
    } finally {
      setIsGeneratingScript(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-gray-600">Loading calculation results...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !calculation) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                icon={<ArrowLeft className="w-4 h-4" />}
                onClick={() => navigate('/')}
              >
                Back to Dashboard
              </Button>
            </div>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-red-800 mb-2">Error Loading Results</h2>
            <p className="text-red-700 mb-4">{error || 'Calculation not found'}</p>
            <Button onClick={() => window.location.reload()}>Try Again</Button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                icon={<ArrowLeft className="w-4 h-4" />}
                onClick={() => navigate('/')}
              >
                Back to Dashboard
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                icon={<Download className="w-4 h-4" />}
                onClick={handleExportCalculation}
                disabled={isExporting}
              >
                Export Results
              </Button>
              {explanation && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Download className="w-4 h-4" />}
                  onClick={handleExportAuditTrail}
                  disabled={isExporting}
                >
                  Export Audit Trail
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* Page Title */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Margin Calculation Results</h1>
            <p className="text-gray-600 mt-2">
              Calculation ID: <code className="bg-gray-100 px-2 py-1 rounded text-sm">{calculationId}</code>
            </p>
          </div>

          {/* Summary Card */}
          {calculation && <CalculationSummaryCard marginCall={calculation} />}

          {/* Calculation Steps */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Calculation Breakdown</h2>
            <p className="text-sm text-gray-600 mb-6">
              Step-by-step breakdown of how the margin requirement was calculated
            </p>
            <div className="space-y-4">
              {calculation?.calculation_steps?.map((step, index) => (
                <CalculationStepItem
                  key={step.step_number}
                  step={step}
                  currency={calculation.currency}
                  isLast={index === calculation.calculation_steps.length - 1}
                />
              )) || (
                <p className="text-gray-500 text-sm">No calculation steps available.</p>
              )}
            </div>
          </div>

          {/* Explanation Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-800">AI Explanation</h2>
              {!explanation && (
                <Button
                  variant="primary"
                  icon={<Sparkles className="w-4 h-4" />}
                  onClick={handleGenerateExplanation}
                  loading={isGeneratingExplanation}
                  disabled={isGeneratingExplanation}
                >
                  {isGeneratingExplanation ? 'Generating...' : 'Generate Explanation'}
                </Button>
              )}
              {explanation && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<RefreshCw className="w-4 h-4" />}
                  onClick={handleGenerateExplanation}
                  loading={isGeneratingExplanation}
                  disabled={isGeneratingExplanation}
                >
                  Regenerate
                </Button>
              )}
            </div>

            {explanationError && (
              <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start gap-3 mb-4">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-800">{explanationError}</p>
              </div>
            )}

            {!explanation && !isGeneratingExplanation && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                <Sparkles className="w-12 h-12 text-blue-500 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Generate AI Explanation
                </h3>
                <p className="text-gray-600 mb-4">
                  Get a detailed, natural language explanation of this margin calculation with key factors, risk assessment, and recommended next steps.
                </p>
                <Button
                  icon={<Sparkles className="w-4 h-4" />}
                  onClick={handleGenerateExplanation}
                >
                  Generate Explanation
                </Button>
              </div>
            )}

            {isGeneratingExplanation && (
              <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
                <Spinner size="lg" />
                <p className="mt-4 text-gray-600">Generating AI explanation...</p>
                <p className="text-sm text-gray-500 mt-2">This may take 10-30 seconds</p>
              </div>
            )}

            {explanation && <ExplanationPanel explanation={explanation} />}
          </div>

          {/* Audit Trail */}
          {explanation && explanation.audit_trail && explanation.audit_trail.length > 0 && (
            <AuditTrailTimeline auditTrail={explanation.audit_trail} />
          )}

          {/* Formula Pattern Analysis */}
          {formulaPatterns && (
            <div>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Formula Pattern Analysis</h2>
              <FormulaPatternDisplay patterns={formulaPatterns} />
            </div>
          )}

          {/* Audit Script Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
                <FileCode className="w-5 h-5" />
                Audit Script Documentation
              </h2>
              {!auditScript && !isGeneratingScript && (
                <Button
                  variant="primary"
                  icon={<FileCode className="w-4 h-4" />}
                  onClick={handleGenerateScript}
                >
                  Generate Audit Script
                </Button>
              )}
            </div>

            {scriptError && (
              <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start gap-3 mb-4">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-800 mb-1">Script Generation Failed</p>
                  <p className="text-sm text-red-700">{scriptError}</p>
                  {scriptError.includes('patterns not found') && (
                    <p className="text-xs text-red-600 mt-2">
                      Hint: Generate formula patterns first from the document processing page.
                    </p>
                  )}
                </div>
              </div>
            )}

            {!auditScript && !isGeneratingScript && !scriptError && (
              <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg p-6 text-center">
                <FileCode className="w-12 h-12 text-indigo-500 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Generate Audit Script
                </h3>
                <p className="text-gray-600 mb-4 max-w-2xl mx-auto">
                  Create a transparent, annotated Python script that documents this calculation's logic.
                  Includes CSA clause citations, pattern annotations, and step-by-step explanations.
                </p>
                <Button
                  icon={<FileCode className="w-4 h-4" />}
                  onClick={handleGenerateScript}
                >
                  Generate Audit Script
                </Button>
              </div>
            )}

            {isGeneratingScript && (
              <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
                <Spinner size="lg" />
                <p className="mt-4 text-gray-600 font-medium">Generating audit script...</p>
                <div className="mt-4 max-w-md mx-auto space-y-2">
                  <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                    <span>Checking formula patterns...</span>
                  </div>
                  <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse delay-75"></div>
                    <span>Extracting patterns if needed...</span>
                  </div>
                  <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                    <div className="w-2 h-2 bg-blue-300 rounded-full animate-pulse delay-150"></div>
                    <span>Generating annotated script...</span>
                  </div>
                </div>
                <p className="text-sm text-gray-500 mt-6">This may take 15-60 seconds</p>
              </div>
            )}

            {auditScript && (
              <AuditScriptViewer
                script={auditScript.script}
                calculationId={calculationId!}
                generatedAt={auditScript.generated_at}
                patternsUsed={auditScript.patterns_used}
                patternsAutoExtracted={auditScript.patterns_auto_extracted}
                patternExtractionTime={auditScript.pattern_extraction_time_seconds}
                scriptStats={auditScript.script_stats}
              />
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-4 pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              icon={<RefreshCw className="w-4 h-4" />}
              onClick={() => navigate(`/calculation/${calculation?.csa_terms_id}/input`)}
              disabled={!calculation?.csa_terms_id}
            >
              Run New Calculation
            </Button>
            <Button
              variant="ghost"
              onClick={() => navigate('/')}
            >
              Return to Dashboard
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
