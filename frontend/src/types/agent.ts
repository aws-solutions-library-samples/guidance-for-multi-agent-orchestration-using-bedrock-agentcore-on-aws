// Agent request and response type definitions

export interface AgentRequest {
  prompt: string;
  sessionId: string;
}

export interface AgentStreamEvent {
  type: 'text-delta' | 'tool-use' | 'completion' | 'error';
  content?: string;
  toolName?: string;
  error?: string;
}

export interface AgentResponse {
  content: string;
  toolsUsed: string[];
  timestamp: Date;
}

export interface AgentError {
  message: string;
  code: string;
  statusCode?: number;
  retryable: boolean;
}

export interface StreamingState {
  isStreaming: boolean;
  currentChunk: string;
  toolsInProgress: string[];
}
