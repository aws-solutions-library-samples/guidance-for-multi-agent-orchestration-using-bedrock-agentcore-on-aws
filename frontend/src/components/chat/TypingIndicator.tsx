import { Bot } from 'lucide-react';

interface TypingIndicatorProps {
  message?: string;
}

/**
 * Typing indicator component for streaming responses
 * Requirement 3.2: Display typing indicator during agent response streaming
 * Requirement 8.1: Display typing indicator when agent is processing request
 */
export default function TypingIndicator({ message }: TypingIndicatorProps) {
  return (
    <div 
      className="px-4 py-2 bg-gray-50"
      role="status"
      aria-live="polite"
      aria-label={message || "Assistant is typing"}
    >
      <div className="max-w-3xl mx-auto">
        <div className="flex gap-3 items-center">
          <div 
            className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center"
            aria-hidden="true"
          >
            <Bot className="w-5 h-5 text-white" aria-hidden="true" />
          </div>
          <div className="bg-white rounded-lg px-4 py-3 border border-gray-200">
            <div className="flex items-center gap-2">
              <div className="flex gap-1" aria-hidden="true">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              {message && (
                <span className="text-sm text-gray-600 ml-2">{message}</span>
              )}
            </div>
            <span className="sr-only">
              {message || "Assistant is typing a response"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
