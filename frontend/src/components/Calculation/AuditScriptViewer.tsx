/**
 * AuditScriptViewer - Displays generated Python audit scripts with syntax highlighting
 */

import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Download, FileCode, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../shared/Button';

interface AuditScriptViewerProps {
  script: string;
  calculationId: string;
  generatedAt?: string;
  patternsUsed?: boolean;
  patternsAutoExtracted?: boolean;
  patternExtractionTime?: number;
  scriptStats?: {
    length_chars: number;
    length_lines: number;
    has_docstring: boolean;
    has_type_hints: boolean;
  };
}

export function AuditScriptViewer({
  script,
  calculationId,
  generatedAt,
  patternsUsed = true,
  patternsAutoExtracted = false,
  patternExtractionTime,
  scriptStats,
}: AuditScriptViewerProps) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(script);
      setCopied(true);
      setCopyError(null);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      setCopyError('Failed to copy to clipboard');
      setTimeout(() => setCopyError(null), 3000);
    }
  };

  const handleDownload = () => {
    try {
      const blob = new Blob([script], { type: 'text/x-python' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `margin_audit_${calculationId}.py`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download:', err);
    }
  };

  return (
    <div className="space-y-4">
      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-blue-100">
            <FileCode className="w-5 h-5 text-blue-600" />
          </div>
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-blue-900 mb-1">
              Audit Script Documentation
            </h4>
            <p className="text-sm text-blue-700 mb-2">
              This Python code documents the calculation logic extracted from the CSA.
              It includes clause citations, pattern annotations, and step-by-step logic explanation.
            </p>
            <div className="flex items-center gap-4 text-xs text-blue-600">
              {patternsUsed && (
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" />
                  Pattern-Enhanced
                </span>
              )}
              {scriptStats && (
                <>
                  <span>{scriptStats.length_lines} lines</span>
                  <span>{(scriptStats.length_chars / 1024).toFixed(1)} KB</span>
                  {scriptStats.has_type_hints && <span>Type hints included</span>}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Pattern Auto-Extraction Success Banner */}
      {patternsAutoExtracted && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-green-900 mb-1">
                Formula Patterns Auto-Extracted
              </h4>
              <p className="text-sm text-green-700">
                Formula patterns were automatically extracted before generating this script.
                {patternExtractionTime && (
                  <span className="ml-1">
                    Extraction completed in {patternExtractionTime.toFixed(1)}s.
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          <span className="font-medium text-gray-700">Note:</span> This is documentation format, not meant for execution.
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={copied}
            className="relative"
          >
            {copied ? (
              <>
                <CheckCircle className="w-4 h-4 mr-1" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-1" />
                Copy Code
              </>
            )}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleDownload}
          >
            <Download className="w-4 h-4 mr-1" />
            Download .py File
          </Button>
        </div>
      </div>

      {/* Copy Error Message */}
      {copyError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600" />
          <p className="text-sm text-red-700">{copyError}</p>
        </div>
      )}

      {/* Code Display with Syntax Highlighting */}
      <div className="rounded-lg border border-gray-300 overflow-hidden shadow-sm">
        <SyntaxHighlighter
          language="python"
          style={vscDarkPlus}
          showLineNumbers
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: '0.875rem',
            lineHeight: '1.5',
          }}
          lineNumberStyle={{
            minWidth: '3em',
            paddingRight: '1em',
            color: '#6e7681',
            userSelect: 'none',
          }}
          wrapLines={true}
          wrapLongLines={true}
        >
          {script}
        </SyntaxHighlighter>
      </div>

      {/* Script Stats Footer */}
      {scriptStats && (
        <div className="text-xs text-gray-500 flex items-center justify-between border-t border-gray-200 pt-3">
          <div className="flex items-center gap-4">
            <span>Lines: {scriptStats.length_lines}</span>
            <span>Characters: {scriptStats.length_chars.toLocaleString()}</span>
          </div>
          {generatedAt && (
            <span>Generated: {new Date(generatedAt).toLocaleString()}</span>
          )}
        </div>
      )}
    </div>
  );
}
