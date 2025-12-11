import { createContext, useContext, ReactNode } from 'react';
import { useChat, UseChatReturn } from '@/hooks/useChat';

/**
 * Chat context for sharing chat state across components
 * Allows Header to trigger new conversation while ChatInterface manages messages
 * Requirements: 4.5, 9.1, 9.2
 */
const ChatContext = createContext<UseChatReturn | null>(null);

interface ChatProviderProps {
  children: ReactNode;
}

/**
 * Provider component that wraps the app and provides chat state
 */
export function ChatProvider({ children }: ChatProviderProps) {
  const chatState = useChat();
  
  return (
    <ChatContext.Provider value={chatState}>
      {children}
    </ChatContext.Provider>
  );
}

/**
 * Hook to access chat context
 * Must be used within ChatProvider
 */
export function useChatContext(): UseChatReturn {
  const context = useContext(ChatContext);
  
  if (!context) {
    throw new Error('useChatContext must be used within ChatProvider');
  }
  
  return context;
}
