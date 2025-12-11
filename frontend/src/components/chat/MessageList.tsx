import { useEffect, useRef } from 'react';
import Message from './Message';
import type { Message as MessageType } from '@/types/chat';

interface MessageListProps {
  messages: MessageType[];
  currentResponse?: string;
  isWaiting?: boolean;
}

export default function MessageList({ messages, currentResponse, isWaiting = false }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentResponse]);

  return (
    <div 
      className="h-full overflow-y-auto px-4 py-6"
      role="log"
      aria-live="polite"
      aria-atomic="false"
      aria-relevant="additions"
      aria-label="Message history"
    >
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.length === 0 && !currentResponse && (
          <div 
            className="text-center text-gray-500 mt-20"
            role="status"
            aria-label="Welcome message"
          >
            <h2 className="text-2xl font-semibold mb-2">Welcome to Customer Support</h2>
            <p>How can I help you today?</p>
          </div>
        )}
        
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
        
        {currentResponse && (
          <Message
            message={{
              id: 'streaming',
              role: 'assistant',
              content: currentResponse,
              timestamp: new Date(),
            }}
            isStreaming
            isWaiting={isWaiting}
          />
        )}
        
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>
    </div>
  );
}
