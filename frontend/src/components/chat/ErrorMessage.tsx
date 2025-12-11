import { AlertCircle, RefreshCw } from 'lucide-react';
import { AgentError } from '@/lib/error-handler';

interface ErrorMessageProps {
  error: AgentError;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export default function ErrorMessage({ error, onRetry, onDismiss }: ErrorMessageProps) {
  return (
    <div
      className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
        
        <div className="flex-1 min-w-0">
          <p className="text-red-800 font-medium text-sm">
            {error.message}
          </p>
          
          {error.statusCode && (
            <p className="text-red-600 text-xs mt-1">
              Error code: {error.statusCode}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {error.retryable && onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              aria-label="Retry request"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              Retry
            </button>
          )}
          
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="text-red-600 hover:text-red-800 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded"
              aria-label="Dismiss error"
            >
              ×
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
