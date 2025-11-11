import { useCallback, useState } from 'react';
import { Upload, X, FileText, AlertCircle } from 'lucide-react';
import { validateFile } from '../../utils/validation';
import { formatFileSize } from '../../utils/formatting';

interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onRemove: () => void;
  disabled?: boolean;
}

export function FileDropzone({
  onFileSelect,
  selectedFile,
  onRemove,
  disabled = false
}: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, [disabled]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleFile = (file: File) => {
    const validation = validateFile(file);

    if (!validation.valid) {
      setError(validation.error || 'Invalid file');
      return;
    }

    setError(null);
    onFileSelect(file);
  };

  if (selectedFile) {
    return (
      <div className="border-2 border-green-300 bg-green-50 rounded-lg p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-green-100 rounded-lg">
            <FileText className="w-8 h-8 text-green-600" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-gray-900 truncate">
                  {selectedFile.name}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  {formatFileSize(selectedFile.size)} • PDF Document
                </p>
              </div>

              {!disabled && (
                <button
                  onClick={onRemove}
                  className="ml-4 p-1 hover:bg-green-200 rounded transition-colors"
                  title="Remove file"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-colors
          ${isDragging ? 'border-primary bg-blue-50' : 'border-gray-300 bg-gray-50'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary hover:bg-blue-50'}
        `}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          accept=".pdf,application/pdf"
          onChange={handleFileInput}
          disabled={disabled}
        />

        <label
          htmlFor="file-upload"
          className={`${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className="flex flex-col items-center">
            <div className={`
              p-4 rounded-full mb-4
              ${isDragging ? 'bg-primary bg-opacity-10' : 'bg-gray-200'}
            `}>
              <Upload className={`
                w-8 h-8
                ${isDragging ? 'text-primary' : 'text-gray-400'}
              `} />
            </div>

            <p className="text-lg font-medium text-gray-900 mb-2">
              Drop your CSA document here
            </p>

            <p className="text-sm text-gray-500 mb-4">
              or click to browse files
            </p>

            <p className="text-xs text-gray-400">
              PDF files only, maximum 50 MB
            </p>
          </div>
        </label>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-900">Upload Error</p>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
