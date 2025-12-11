import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface MessageInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
}

export default function MessageInput({ onSend, disabled = false, isLoading = false }: MessageInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Refocus input when loading completes
  useEffect(() => {
    if (!isLoading && !disabled) {
      textareaRef.current?.focus();
    }
  }, [isLoading, disabled]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
      // Reset textarea height after sending
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
      // Return focus to textarea after sending
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div 
      className="border-t border-gray-200 bg-white p-4"
      role="region"
      aria-label="Message input area"
    >
      <div className="max-w-3xl mx-auto">
        <form 
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          aria-label="Send message form"
        >
          <div className="flex gap-2 items-end">
            <label htmlFor="message-input" className="sr-only">
              Type your message
            </label>
            <textarea
              ref={textareaRef}
              id="message-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={disabled}
              rows={1}
              className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              style={{
                minHeight: '52px',
                maxHeight: '200px',
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
              }}
              aria-label="Message input"
              aria-describedby="message-input-help"
              aria-required="true"
            />
            <button
              type="submit"
              onClick={handleSend}
              disabled={disabled || !input.trim() || isLoading}
              className="flex-shrink-0 bg-blue-600 text-white rounded-lg px-4 py-3 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              aria-label={isLoading ? "Sending message" : "Send message"}
              aria-disabled={disabled || !input.trim() || isLoading}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="w-5 h-5" aria-hidden="true" />
              )}
              <span className="sr-only">{isLoading ? "Sending" : "Send"}</span>
            </button>
          </div>
          <p 
            id="message-input-help" 
            className="text-xs text-gray-500 mt-2"
            role="note"
          >
            Press Enter to send, Shift+Enter for new line
          </p>
        </form>
      </div>
    </div>
  );
}
