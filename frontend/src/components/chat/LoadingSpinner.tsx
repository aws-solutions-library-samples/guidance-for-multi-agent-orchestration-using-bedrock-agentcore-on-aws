import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Loading spinner component for message sending state
 * Requirement 2.5: Display loading indicator while message is being sent
 */
export default function LoadingSpinner({ 
  message = 'Sending message...', 
  size = 'md' 
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  return (
    <div 
      className="flex items-center gap-2 text-gray-600"
      role="status"
      aria-live="polite"
      aria-label={message}
    >
      <Loader2 
        className={`${sizeClasses[size]} animate-spin`} 
        aria-hidden="true"
      />
      <span className="text-sm">{message}</span>
    </div>
  );
}
