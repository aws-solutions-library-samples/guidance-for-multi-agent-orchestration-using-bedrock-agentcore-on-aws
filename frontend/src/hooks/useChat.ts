import { useState, useCallback, useRef } from 'react';
import { AgentCoreClient, AgentStreamEvent, AgentError } from '@/lib/api-client';
import { requiresAuthRedirect, handleStreamError } from '@/lib/error-handler';
import { useAuth } from './useAuth';
import { Message } from '@/types/chat';
import { v4 as uuidv4 } from 'uuid';

// Re-export AgentCoreError for backward compatibility
export class AgentCoreError extends AgentError {
  constructor(
    message: string,
    public statusCode?: number,
    public retryable: boolean = false
  ) {
    super(message, 'AGENT_CORE_ERROR', statusCode, retryable);
  }
}

/**
 * Chat state and actions returned by useChat hook
 */
export interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
  isSending: boolean;
  currentResponse: string;
  activeTools: string[];
  error: AgentCoreError | null;
  sessionId: string;
  isWaiting: boolean;
  sendMessage: (content: string) => Promise<void>;
  clearError: () => void;
  retryLastMessage: () => void;
  resetChat: () => void;
  startNewConversation: () => void;
}

/**
 * Custom hook for managing chat state and AgentCore interactions
 * 
 * Features:
 * - Message state management (user and assistant messages)
 * - Persistent session ID for AgentCore Memory
 * - Streaming response handling with real-time updates
 * - Tool invocation tracking
 * - Error handling with retry support
 * 
 * Requirements: 2.3, 3.2, 4.1, 13.1
 */
export function useChat(): UseChatReturn {
  // Message history state
  const [messages, setMessages] = useState<Message[]>([]);
  
  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  
  // Loading state for message sending
  const [isSending, setIsSending] = useState(false);
  
  // Error state
  const [error, setError] = useState<AgentCoreError | null>(null);
  
  // Session ID - persistent for conversation continuity with AgentCore Memory
  const [sessionId, setSessionId] = useState(() => uuidv4());
  
  // Track tools used during current response (for real-time display)
  const toolsUsedRef = useRef<string[]>([]);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  
  // Initialize AgentCore client
  const clientRef = useRef<AgentCoreClient | null>(null);
  
  // Get auth hook for token access
  const { getAccessToken, logout } = useAuth();
  
  // Lazy initialize AgentCore client
  const getClient = useCallback((): AgentCoreClient => {
    if (!clientRef.current) {
      console.log('Using AgentCore Runtime client (direct SSE)');
      clientRef.current = new AgentCoreClient();
    }
    
    return clientRef.current;
  }, []);

  /**
   * Handle streaming events from AgentCore Runtime
   * Requirement 3.2: Handle streaming events (text-delta, tool-use, completion, error)
   * Requirement 8.2: Display tool name being invoked in real-time
   */
  const handleStreamEvent = useCallback((event: AgentStreamEvent) => {
    switch (event.type) {
      case 'text-delta':
        // Append text content to current response
        if (event.content) {
          setCurrentResponse(prev => prev + event.content);
          setIsWaiting(false);
        }
        break;
      
      case 'text-block-stop':
        // Text block ended, now waiting for tools or next block
        setIsWaiting(true);
        break;
        
      case 'tool-use':
        // Track tool invocations and update active tools for real-time display
        // Requirement 8.2: Display tool name being invoked
        if (event.toolName && !toolsUsedRef.current.includes(event.toolName)) {
          toolsUsedRef.current.push(event.toolName);
          setActiveTools([...toolsUsedRef.current]);
        }
        break;
        
      case 'completion':
        // Finalize assistant message and add to history
        // Use event.content if available (from mutation response), otherwise use accumulated currentResponse
        const finalContent = event.content || currentResponse;
        
        if (finalContent) {
          const assistantMessage: Message = {
            id: uuidv4(),
            role: 'assistant',
            content: finalContent,
            timestamp: new Date(),
            toolsUsed: toolsUsedRef.current.length > 0 
              ? [...toolsUsedRef.current] 
              : undefined,
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
        
        // Reset streaming state
        setCurrentResponse('');
        toolsUsedRef.current = [];
        setActiveTools([]);
        setIsStreaming(false);
        setIsWaiting(false);
        break;
        
      case 'error':
        // Handle streaming errors
        // Requirement 10.4: Handle streaming connection failures
        const errorMessage = event.error || 'An error occurred during streaming';
        const streamError = handleStreamError(new Error(errorMessage));
        setError(streamError);
        setIsStreaming(false);
        setIsWaiting(false);
        setCurrentResponse('');
        toolsUsedRef.current = [];
        setActiveTools([]);
        break;
    }
  }, []);

  /**
   * Send a message to the AgentCore Runtime
   * Requirement 2.3: Display customer message and transmit to AgentCore Runtime
   * Requirement 2.5: Display loading indicator while message is being sent
   * Requirement 13.1: Pass session identifier in header for AgentCore Memory
   * Requirement 10.2: Handle authentication errors with redirect to login
   */
  const sendMessage = useCallback(async (content: string) => {
    // Validate input
    if (!content.trim()) {
      return;
    }
    
    // Clear any previous errors
    setError(null);
    
    // Set sending state (before adding message to show loading)
    // Requirement 2.5: Display loading indicator while message is being sent
    setIsSending(true);
    
    // Add user message to history
    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    // Initialize streaming state
    setIsStreaming(true);
    setCurrentResponse('');
    toolsUsedRef.current = [];
    setActiveTools([]);
    
    try {
      const client = getClient();
      
      // Get JWT token from auth hook
      const jwtToken = await getAccessToken();
      
      if (!jwtToken) {
        throw new AgentCoreError('No authentication token available', 401);
      }
      
      // Clear sending state once streaming starts
      setIsSending(false);
      
      // Stream message to AgentCore Runtime
      await client.streamMessage(
        {
          prompt: content.trim(),
          sessionId,
        },
        handleStreamEvent,
        jwtToken
      );
    } catch (err) {
      // Handle errors
      let agentError: AgentError;
      
      if (err instanceof AgentCoreError || err instanceof AgentError) {
        agentError = err;
      } else {
        agentError = new AgentCoreError(
          'Failed to send message. Please try again.',
          undefined,
          true
        );
      }
      
      setError(agentError);
      
      // Handle authentication errors with redirect to login
      if (requiresAuthRedirect(agentError)) {
        try {
          await logout();
        } catch (signOutError) {
          console.error('Failed to sign out:', signOutError);
        }
      }
      
      // Reset streaming and sending state on error
      setIsSending(false);
      setIsStreaming(false);
      setCurrentResponse('');
      toolsUsedRef.current = [];
      setActiveTools([]);
    }
  }, [sessionId, handleStreamEvent, getClient]);

  /**
   * Clear current error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Retry the last user message
   * Requirement 10.3: Add retry functionality for retryable errors
   */
  const retryLastMessage = useCallback(() => {
    // Find the last user message
    const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');
    
    if (lastUserMessage) {
      // Resend the message
      sendMessage(lastUserMessage.content);
    }
  }, [messages, sendMessage]);

  /**
   * Reset chat state (clear messages and errors)
   * Note: This does NOT generate a new session ID
   * Use startNewConversation() to start a fresh conversation with new session
   */
  const resetChat = useCallback(() => {
    setMessages([]);
    setCurrentResponse('');
    setIsStreaming(false);
    setIsSending(false);
    setError(null);
    toolsUsedRef.current = [];
    setActiveTools([]);
  }, []);

  /**
   * Start a new conversation with a fresh session ID
   * Requirement 4.5: Generate new session identifier for new conversation
   * Requirement 9.1: Generate new session identifier when customer clicks new conversation button
   */
  const startNewConversation = useCallback(() => {
    // Clear all chat state
    setMessages([]);
    setCurrentResponse('');
    setIsStreaming(false);
    setIsSending(false);
    setError(null);
    toolsUsedRef.current = [];
    setActiveTools([]);
    
    // Generate new session ID for AgentCore Memory
    setSessionId(uuidv4());
  }, []);

  return {
    messages,
    isStreaming,
    isSending,
    currentResponse,
    activeTools,
    error,
    sessionId,
    isWaiting,
    sendMessage,
    clearError,
    retryLastMessage,
    resetChat,
    startNewConversation,
  };
}
