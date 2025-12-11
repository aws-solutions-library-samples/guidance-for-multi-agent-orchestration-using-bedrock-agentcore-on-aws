/**
 * Custom error class for agent-related errors
 */
export class AgentError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode?: number,
    public retryable: boolean = false
  ) {
    super(message);
    this.name = 'AgentError';
    Object.setPrototypeOf(this, AgentError.prototype);
  }
}

/**
 * Error codes for different error types
 */
export const ErrorCodes = {
  AUTH_FAILED: 'AUTH_FAILED',
  AUTH_EXPIRED: 'AUTH_EXPIRED',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'SERVER_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  STREAM_ERROR: 'STREAM_ERROR',
  FORBIDDEN: 'FORBIDDEN',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
} as const;

/**
 * Handle API errors and convert them to AgentError instances
 */
export function handleApiError(error: unknown): AgentError {
  // Handle Response objects (fetch errors)
  if (error instanceof Response) {
    return classifyHttpError(error.status, error.statusText);
  }

  // Handle Error objects
  if (error instanceof Error) {
    // Network errors
    if (error.message.includes('fetch') || error.message.includes('network')) {
      return new AgentError(
        'Network error. Please check your connection and try again.',
        ErrorCodes.NETWORK_ERROR,
        undefined,
        true
      );
    }

    // Stream errors
    if (error.message.includes('stream') || error.message.includes('SSE')) {
      return new AgentError(
        'Connection interrupted. Please try again.',
        ErrorCodes.STREAM_ERROR,
        undefined,
        true
      );
    }

    // Generic error
    return new AgentError(
      error.message || 'An unexpected error occurred.',
      ErrorCodes.UNKNOWN_ERROR,
      undefined,
      false
    );
  }

  // Unknown error type
  return new AgentError(
    'An unexpected error occurred. Please try again.',
    ErrorCodes.UNKNOWN_ERROR,
    undefined,
    false
  );
}

/**
 * Classify HTTP errors by status code
 */
export function classifyHttpError(status: number, statusText: string): AgentError {
  switch (status) {
    case 401:
      return new AgentError(
        'Authentication failed. Please log in again.',
        ErrorCodes.AUTH_FAILED,
        401,
        false
      );

    case 403:
      return new AgentError(
        'Access denied. You do not have permission to perform this action.',
        ErrorCodes.FORBIDDEN,
        403,
        false
      );

    case 429:
      return new AgentError(
        'Too many requests. Please wait a moment and try again.',
        ErrorCodes.RATE_LIMITED,
        429,
        true
      );

    case 500:
    case 502:
    case 503:
    case 504:
      return new AgentError(
        'Server error. Please try again in a moment.',
        ErrorCodes.SERVER_ERROR,
        status,
        true
      );

    default:
      return new AgentError(
        `Request failed: ${statusText || 'Unknown error'}`,
        ErrorCodes.UNKNOWN_ERROR,
        status,
        status >= 500
      );
  }
}

/**
 * Handle streaming connection failures
 */
export function handleStreamError(error: unknown): AgentError {
  if (error instanceof AgentError) {
    return error;
  }

  return new AgentError(
    'Streaming connection failed. Please try again.',
    ErrorCodes.STREAM_ERROR,
    undefined,
    true
  );
}

/**
 * Check if an error requires authentication redirect
 */
export function requiresAuthRedirect(error: AgentError): boolean {
  return error.code === ErrorCodes.AUTH_FAILED || error.code === ErrorCodes.AUTH_EXPIRED;
}
