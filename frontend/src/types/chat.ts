// Chat and message type definitions

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolsUsed?: string[];
}

export interface ChatSession {
  sessionId: string;
  messages: Message[];
  createdAt: Date;
  lastActivity: Date;
}

export interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentResponse: string;
  sessionId: string;
  error: Error | null;
}

export interface ToolInvocation {
  toolName: string;
  timestamp: Date;
}
