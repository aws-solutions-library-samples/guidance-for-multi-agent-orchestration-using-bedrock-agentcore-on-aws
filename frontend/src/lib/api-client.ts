import { AgentError } from './error-handler';

// Re-export AgentError for convenience
export { AgentError } from './error-handler';

/**
 * AgentCore Runtime client for direct SSE streaming
 * Calls AgentCore Runtime endpoint with JWT authentication
 */

/**
 * Request payload for AgentCore Runtime
 */
export interface AgentRequest {
  prompt: string;
  sessionId: string;
  customerId?: string;
}

/**
 * Stream event types from AgentCore Runtime
 */
export interface AgentStreamEvent {
  type: 'text-delta' | 'tool-use' | 'completion' | 'error' | 'text-block-stop';
  content?: string;
  toolName?: string;
  error?: string;
}

/**
 * AgentCore Runtime client for direct SSE streaming
 */
export class AgentCoreClient {
  private runtimeUrl: string;
  private region: string;

  constructor() {
    // Get runtime ARN from environment
    const runtimeArn = import.meta.env.VITE_AGENTCORE_RUNTIME_ARN;
    this.region = import.meta.env.VITE_AWS_REGION || 'us-east-1';
    
    if (!runtimeArn) {
      throw new Error('VITE_AGENTCORE_RUNTIME_ARN environment variable not set');
    }

    // Construct AgentCore Runtime endpoint URL
    const encodedArn = encodeURIComponent(runtimeArn);
    this.runtimeUrl = `https://bedrock-agentcore.${this.region}.amazonaws.com/runtimes/${encodedArn}/invocations?qualifier=DEFAULT`;
  }

  /**
   * Stream a message using AgentCore Runtime SSE
   * @param request - The agent request with prompt and session ID
   * @param onEvent - Callback function for each stream event
   * @param jwtToken - JWT Bearer token for authentication
   * @throws AgentError for authentication, network, or API errors
   */
  async streamMessage(
    request: AgentRequest,
    onEvent: (event: AgentStreamEvent) => void,
    jwtToken: string
  ): Promise<void> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout
      
      const response = await fetch(this.runtimeUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${jwtToken}`,
          'Content-Type': 'application/json',
          'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': request.sessionId
        },
        body: JSON.stringify({ prompt: request.prompt }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new AgentError(
          `AgentCore Runtime error: ${response.status} ${response.statusText}`,
          'RUNTIME_ERROR',
          response.status
        );
      }

      if (!response.body) {
        throw new AgentError(
          'No response body from AgentCore Runtime',
          'NO_RESPONSE_BODY'
        );
      }

      // Process SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const contentBlocks: Record<number, string> = {};
      const toolUseMap: Record<string, string> = {};
      let textBlockStopped = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            try {
              const event = JSON.parse(data);
              
              if (event.event) {
                const eventObj = event.event;

                // Handle text deltas
                if (eventObj.contentBlockDelta) {
                  const delta = eventObj.contentBlockDelta;
                  const index = delta.contentBlockIndex;
                  const text = delta.delta?.text || '';
                  
                  if (!contentBlocks[index]) {
                    contentBlocks[index] = '';
                  }
                  
                  // Add spacing if text resumes after a stop
                  let textToSend = text;
                  if (textBlockStopped && index === 0 && text) {
                    textToSend = '\n\n' + text;
                    textBlockStopped = false;
                  }
                  
                  contentBlocks[index] += textToSend;
                  
                  onEvent({
                    type: 'text-delta',
                    content: textToSend
                  });
                }

                // Handle tool use start
                else if (eventObj.contentBlockStart) {
                  const start = eventObj.contentBlockStart.start;
                  if (start?.toolUse) {
                    const toolName = start.toolUse.name;
                    const toolId = start.toolUse.toolUseId;
                    toolUseMap[toolId] = toolName;
                    
                    onEvent({
                      type: 'tool-use',
                      toolName
                    });
                  }
                }

                // Handle content block stop
                else if (eventObj.contentBlockStop) {
                  const index = eventObj.contentBlockStop.contentBlockIndex;
                  // Track when text block (index 0) stops
                  if (index === 0) {
                    textBlockStopped = true;
                    onEvent({
                      type: 'text-block-stop'
                    });
                  }
                }

                // Handle completion
                else if (eventObj.messageStop) {
                  const stopReason = eventObj.messageStop.stopReason;
                  if (stopReason === 'end_turn') {
                    const fullContent = Object.values(contentBlocks).join('');
                    onEvent({
                      type: 'completion',
                      content: fullContent
                    });
                  }
                }
              }
            } catch (e) {
              console.warn('Failed to parse SSE event:', data, e);
            }
          }
        }
      }
    } catch (error: any) {
      console.error('Stream message error:', error);
      
      if (error instanceof AgentError) {
        throw error;
      }
      
      if (error.name === 'AbortError') {
        throw new AgentError(
          'Request timed out after 2 minutes',
          'TIMEOUT_ERROR',
          408,
          true
        );
      }
      
      throw new AgentError(
        error.message || 'Failed to stream message',
        'STREAM_ERROR',
        undefined,
        true
      );
    }
  }

  /**
   * Clean up any active connections
   */
  cleanup(): void {
    // No cleanup needed for fetch-based streaming
  }
}
