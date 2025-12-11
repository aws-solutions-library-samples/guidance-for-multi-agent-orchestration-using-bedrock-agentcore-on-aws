import { User, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Message as MessageType } from '@/types/chat';
import ToolIndicator from './ToolIndicator';

interface MessageProps {
  message: MessageType;
  isStreaming?: boolean;
  isWaiting?: boolean;
}

export default function Message({ message, isStreaming = false, isWaiting = false }: MessageProps) {
  const isUser = message.role === 'user';

  return (
    <div 
      className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
      role="article"
      aria-label={`${isUser ? 'User' : 'Assistant'} message`}
    >
      {!isUser && (
        <div 
          className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center"
          aria-hidden="true"
        >
          <Bot className="w-5 h-5 text-white" aria-hidden="true" />
        </div>
      )}
      
      <div className={`flex flex-col max-w-[70%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-lg px-4 py-2 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-900 border border-gray-200'
          }`}
          role="region"
          aria-label={`${isUser ? 'Your' : 'Assistant'} message content`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <>
              <div className="prose prose-sm max-w-none [&_p]:my-3 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
              {isWaiting && (
                <div className="flex gap-1 mt-2" aria-hidden="true">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              )}
            </>
          )}
        </div>
        
        {!isUser && message.toolsUsed && message.toolsUsed.length > 0 && (
          <div className="mt-2" role="status" aria-label="Tools used by assistant">
            <ToolIndicator tools={message.toolsUsed} />
          </div>
        )}
        
        {!isStreaming && (
          <time 
            className="text-xs text-gray-500 mt-1"
            dateTime={message.timestamp.toISOString()}
            aria-label={`Sent at ${message.timestamp.toLocaleTimeString()}`}
          >
            {message.timestamp.toLocaleTimeString([], { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </time>
        )}
      </div>
      
      {isUser && (
        <div 
          className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center"
          aria-hidden="true"
        >
          <User className="w-5 h-5 text-white" aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
