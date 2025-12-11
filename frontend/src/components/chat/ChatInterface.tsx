import { useChatContext } from '@/contexts/ChatContext';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ErrorMessage from './ErrorMessage';
import LoadingSpinner from './LoadingSpinner';
import ActiveToolsIndicator from './ActiveToolsIndicator';

export default function ChatInterface() {
  const { 
    messages, 
    isStreaming,
    isSending,
    currentResponse,
    activeTools,
    error,
    isWaiting,
    sendMessage,
    retryLastMessage,
    clearError,
  } = useChatContext();

  const handleSend = async (content: string) => {
    await sendMessage(content);
  };

  const handleRetry = () => {
    clearError();
    retryLastMessage();
  };

  return (
    <div 
      className="flex flex-col h-full bg-background"
      role="main"
      aria-label="Chat interface"
    >
      <div 
        className="flex-1 overflow-hidden"
        role="region"
        aria-label="Conversation history"
      >
        <MessageList messages={messages} currentResponse={currentResponse} isWaiting={isWaiting} />
      </div>
      
      {error && (
        <div className="px-4 py-2 border-t border-border">
          <ErrorMessage 
            error={error} 
            onRetry={error.retryable ? handleRetry : undefined}
            onDismiss={clearError}
          />
        </div>
      )}
      
      {isSending && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200">
          <div className="max-w-3xl mx-auto">
            <LoadingSpinner message="Sending message..." size="sm" />
          </div>
        </div>
      )}
      
      {isStreaming && activeTools.length > 0 && (
        <ActiveToolsIndicator tools={activeTools} />
      )}
      
      <MessageInput 
        onSend={handleSend} 
        disabled={isStreaming || isSending}
        isLoading={isSending}
      />
    </div>
  );
}
