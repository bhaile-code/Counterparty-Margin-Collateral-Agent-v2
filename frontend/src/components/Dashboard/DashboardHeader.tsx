import { Upload } from 'lucide-react';
import { Button } from '../shared/Button';

interface DashboardHeaderProps {
  onUploadClick: () => void;
}

export function DashboardHeader({ onUploadClick }: DashboardHeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-primary">
              CSA Margin Manager
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              AI-powered collateral agreement analysis and margin calculation
            </p>
          </div>

          <Button
            onClick={onUploadClick}
            icon={<Upload className="w-5 h-5" />}
            size="lg"
          >
            Upload New CSA
          </Button>
        </div>
      </div>
    </header>
  );
}
